from gpiozero import Button
import time
import subprocess
import os
import requests
import signal

# --- CONFIGURATION ---
DIAL_PIN = 17       # The pulse switch
HOOK_PIN = 27       # The handset hook switch
OFF_NORMAL_PIN = 22 # NEW: The off-normal/shunt switch

AUDIO_DIR = "/home/codar/rotary_audio"
SFX_DIR = "/home/codar/sfx"
API_URL = "https://rotary-backend.your-subdomain.workers.dev" 

# Setup buttons 
dial_switch = Button(DIAL_PIN, pull_up=True, bounce_time=0.02)
hook_switch = Button(HOOK_PIN, pull_up=True, bounce_time=0.1) 
off_normal_switch = Button(OFF_NORMAL_PIN, pull_up=True, bounce_time=0.1) 

# State variables
pulse_count = 0
dialed_number = ""
last_digit_time = time.time()
is_dialing = False
current_process = None 

# --- SYSTEM ACTIONS ---

def stop_active_process():
    global current_process
    if current_process:
        try:
            os.kill(current_process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        current_process = None

def play_sound(filepath, blocking=False):
    global current_process
    stop_active_process() 
    
    if filepath.endswith('.wav'):
        cmd = ["aplay", filepath] 
    else:
        cmd = ["cvlc", "-A", "alsa", "--play-and-exit", filepath]
        
    if blocking:
        subprocess.run(cmd)
    else:
        current_process = subprocess.Popen(cmd)

def record_and_upload(phone_number):
    global current_process
    play_sound(f"{SFX_DIR}/prompt.wav", blocking=True)
    play_sound(f"{SFX_DIR}/beep.wav", blocking=True)
    
    filename = f"{phone_number}_new.wav"
    filepath = os.path.join(AUDIO_DIR, filename)
    print(f"Recording message for {phone_number}...")
    
    current_process = subprocess.Popen([
        "arecord", "-D", "hw:0,0", "-f", "S16_LE", "-r", "44100", filepath
    ])
    
    while hook_switch.is_pressed: 
        time.sleep(0.5)
        
    print(f"Finished recording. Uploading to {API_URL}...")
    try:
        with open(filepath, 'rb') as f:
            files = {'audio': (filename, f, 'audio/wav')}
            data = {'phone_number': phone_number, 'description': 'Recorded via Physical Rotary Phone'}
            response = requests.post(f"{API_URL}/api/upload", files=files, data=data)
            print("Upload status:", response.status_code)
    except Exception as e:
        print("Upload failed:", e)

def handle_completed_number(number):
    print(f"\n--- DIALING COMPLETE: {number} ---")
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
    global dialed_number, is_dialing, pulse_count
    stop_active_process()
    dialed_number = ""
    is_dialing = False
    pulse_count = 0

hook_switch.when_pressed = hook_picked_up   
hook_switch.when_released = hook_hung_up    

def off_normal_engaged():
    """Triggered when the dial is pulled away from rest."""
    global is_dialing, pulse_count
    if hook_switch.is_pressed:
        stop_active_process() # Stop dial tone immediately
        is_dialing = True
        pulse_count = 0
        # print("Dial turning...") # Optional debug

def handle_pulse():
    """Triggered by the mechanical clicks as the dial spins back."""
    global pulse_count
    if is_dialing: 
        pulse_count += 1

def off_normal_disengaged():
    """Triggered when the dial perfectly returns to its resting state."""
    global is_dialing, pulse_count, dialed_number, last_digit_time
    
    if is_dialing:
        is_dialing = False
        last_digit_time = time.time() # Start the 3-second clock for the whole number
        
        if pulse_count > 0:
            digit = 0 if pulse_count == 10 else pulse_count
            dialed_number += str(digit)
            
            print(f"Digit registered: {digit} | Current sequence: {dialed_number}")
            
            if os.path.exists(f"{SFX_DIR}/dtmf_{digit}.wav"):
                play_sound(f"{SFX_DIR}/dtmf_{digit}.wav", blocking=False)
                
        pulse_count = 0

# Bind the new dial events
off_normal_switch.when_pressed = off_normal_engaged
off_normal_switch.when_released = off_normal_disengaged
dial_switch.when_pressed = handle_pulse

# --- MAIN LOOP ---
print("Rotary Archiver initialized. Waiting for interaction...")

try:
    while True:
        time.sleep(0.1)
        
        # We only need to check if the ENTIRE phone number is finished.
        # If 3 seconds have passed since the dial returned to rest, assume they are done.
        if hook_switch.is_pressed and len(dialed_number) > 0 and not is_dialing and (time.time() - last_digit_time > 3.0):
            handle_completed_number(dialed_number)
            dialed_number = "" 

except KeyboardInterrupt:
    print("\nShutting down Rotary Archive...")
    stop_active_process()
