from gpiozero import Button
import time
import subprocess
import os
import requests
import signal

# --- CONFIGURATION ---
DIAL_PIN = 17 
HOOK_PIN = 27
AUDIO_DIR = "/home/codar/rotary_audio"
SFX_DIR = "/home/codar/sfx"
API_URL = "https://rotary-backend.your-subdomain.workers.dev" # Update this to your actual Worker URL

# Setup buttons (Software debouncing included)
# pull_up=True means the pin reads HIGH normally, and LOW when the switch connects to Ground
dial_switch = Button(DIAL_PIN, pull_up=True, bounce_time=0.05)
hook_switch = Button(HOOK_PIN, pull_up=True, bounce_time=0.1) 

# State variables
pulse_count = 0
dialed_number = ""
last_pulse_time = time.time()
is_dialing = False
current_process = None # Tracks active audio playing/recording

# --- SYSTEM ACTIONS ---

def stop_active_process():
    """Kills any currently playing or recording audio"""
    global current_process
    if current_process:
        try:
            # Terminate the process cleanly
            os.kill(current_process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        current_process = None

def play_sound(filepath, blocking=False):
    """Plays an audio file. blocking=True pauses the script until the audio finishes."""
    global current_process
    stop_active_process() # Stop anything else currently playing
    
    if filepath.endswith('.wav'):
        # aplay is instant and lightweight for standard wav files
        cmd = ["aplay", filepath] 
    else:
        # For webm/mp3/m4a, use VLC and force it through ALSA
        cmd = ["cvlc", "-A", "alsa", "--play-and-exit", filepath]
        
    if blocking:
        subprocess.run(cmd)
    else:
        current_process = subprocess.Popen(cmd)

def record_and_upload(phone_number):
    """Records audio from the USB mic and POSTs it to the Cloudflare API"""
    global current_process
    
    # Play prompt: "Please leave a message after the tone"
    play_sound(f"{SFX_DIR}/prompt.wav", blocking=True)
    play_sound(f"{SFX_DIR}/beep.wav", blocking=True)
    
    filename = f"{phone_number}_new.wav"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    print(f"Recording message for {phone_number}...")
    
    # arecord captures audio. hw:0,0 points to your USB Audio Device
    current_process = subprocess.Popen([
        "arecord", "-D", "hw:0,0", "-f", "S16_LE", "-r", "44100", filepath
    ])
    
    # Record until they hang up. 
    while hook_switch.is_pressed: 
        time.sleep(0.5)
        
    # Hook switch was released (hung up). Process is stopped by the hook_hung_up handler.
    print(f"Finished recording. Uploading to {API_URL}...")
    
    try:
        # POST the recorded file to your Cloudflare Backend
        with open(filepath, 'rb') as f:
            files = {'audio': (filename, f, 'audio/wav')}
            data = {'phone_number': phone_number, 'description': 'Recorded via Physical Rotary Phone'}
            response = requests.post(f"{API_URL}/api/upload", files=files, data=data)
            print("Upload status:", response.status_code)
    except Exception as e:
        print("Upload failed:", e)

def handle_completed_number(number):
    """Decides whether to play an existing audio file or record a new one"""
    print(f"\n--- DIALING COMPLETE: {number} ---")
    
    # Check if a file exists locally for this number
    possible_extensions = ['.webm', '.m4a', '.mp4', '.wav', '.mp3']
    file_to_play = None
    
    for ext in possible_extensions:
        path = os.path.join(AUDIO_DIR, f"{number}{ext}")
        if os.path.exists(path):
            file_to_play = path
            break
            
    if file_to_play:
        print(f"Active deployment found. Playing: {file_to_play}")
        play_sound(file_to_play)
    else:
        print("No active deployment found. Prompting to record new artifact...")
        record_and_upload(number)


# --- EVENT HANDLERS ---

def hook_picked_up():
    print("Phone Off-Hook.")
    global dialed_number
    dialed_number = ""
    play_sound(f"{SFX_DIR}/dial_tone.wav") 

def hook_hung_up():
    print("Phone Hung Up.")
    global dialed_number, is_dialing
    stop_active_process()
    dialed_number = ""
    is_dialing = False

# Assuming switch connects to Ground when lifted (pressed = off hook)
hook_switch.when_pressed = hook_picked_up   
hook_switch.when_released = hook_hung_up    

def handle_pulse():
    global pulse_count, last_pulse_time, is_dialing
    if hook_switch.is_pressed: # Only register pulses if the phone is actually picked up
        if not is_dialing:
            stop_active_process() # Stop the dial tone as soon as the first pulse hits
            
        is_dialing = True
        pulse_count += 1
        last_pulse_time = time.time()

dial_switch.when_pressed = handle_pulse


# --- MAIN LOOP ---
print("Rotary Archiver initialized. Waiting for interaction...")

try:
    while True:
        time.sleep(0.05)
        
        # 1. Logic to determine if a SINGLE digit is finished dialing
        # (e.g., dial has returned to rest and 0.4 seconds have passed)
        if is_dialing and (time.time() - last_pulse_time > 0.4):
            # Rotary dials send 10 pulses for the number '0'
            digit = 0 if pulse_count == 10 else pulse_count
            dialed_number += str(digit)
            
            # PLAY AUDIO FEEDBACK FOR THE DIGIT (Optional: Comment out if you prefer mechanical sounds)
            if os.path.exists(f"{SFX_DIR}/dtmf_{digit}.wav"):
                play_sound(f"{SFX_DIR}/dtmf_{digit}.wav", blocking=True)
                
            print(f"Digit registered: {digit} | Current sequence: {dialed_number}")
            
            # Reset pulse count for the next digit
            pulse_count = 0
            is_dialing = False
            
        # 2. Logic to determine if the ENTIRE phone number is finished
        # (e.g., they stopped dialing for 3 seconds, and the phone is still off the hook)
        if hook_switch.is_pressed and len(dialed_number) > 0 and not is_dialing and (time.time() - last_pulse_time > 3.0):
            handle_completed_number(dialed_number)
            
            # Reset the number sequence so it doesn't trigger repeatedly
            dialed_number = "" 

except KeyboardInterrupt:
    print("\nShutting down Rotary Archive...")
    stop_active_process()
