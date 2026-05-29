from gpiozero import Button
import time
import subprocess
import os
import signal
from datetime import datetime
import random
import glob

# --- CONFIGURATION ---
DIAL_PIN = 17       # The pulse switch
HOOK_PIN = 27       # The handset hook switch
OFF_NORMAL_PIN = 22 # The off-normal/shunt switch

AUDIO_DIR = "/home/codar/rotary_audio"
SFX_DIR = "/home/codar/sfx"

# Setup buttons (0.02 bounce_time catches rapid dial pulses)
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
    """Kills any currently playing or recording audio"""
    global current_process
    if current_process:
        try:
            os.kill(current_process.pid, signal.SIGTERM)
            # Give the ALSA audio system a tiny moment to release the hardware lock
            time.sleep(0.15)
        except ProcessLookupError:
            pass
        current_process = None

def play_sound(filepath, blocking=False):
    """Plays an audio file. blocking=True pauses the script until the audio finishes."""
    global current_process
    stop_active_process() 
    
    if filepath.endswith('.wav'):
        cmd = ["aplay", "-D", "plughw:0,0", filepath] 
    else:
        # Use ffplay for compressed files. 
        # -nodisp: no video window
        # -autoexit: close when finished
        # -ar 44100: forces a high-quality resample to standard CD audio
        # -af volume=-3dB: slightly lowers volume to prevent hardware clipping/scratchiness
        cmd = [
            "ffplay", 
            "-nodisp", 
            "-autoexit", 
            "-loglevel", "quiet", 
            "-ar", "44100",
            "-af", "volume=-3dB",
            filepath
        ]
        
    if blocking:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def record_local_artifact(phone_number):
    """Records audio from the USB mic and saves it locally with a timestamp."""
    global current_process
    
    play_sound(f"{SFX_DIR}/prompt.wav", blocking=True)
    play_sound(f"{SFX_DIR}/beep.wav", blocking=True)
    
    # Generate a timestamp (Format: YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Example filename: 5551234_20260527_201530_new.wav
    filename = f"{phone_number}_{timestamp}_new.wav"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    print(f"Recording message for {phone_number}...")
    
    # hw:0,0 targets your USB sound card
    current_process = subprocess.Popen([
        "arecord", "-D", "hw:0,0", "-f", "S16_LE", "-r", "44100", filepath
    ])
    
    # Keep recording as long as the phone is off the hook
    while hook_switch.is_pressed: 
        time.sleep(0.5)
        
    print(f"Finished recording. Saved locally as '{filename}' for future sync.")

def handle_completed_number(number):
    """Finds all audio files associated with the dialed number and plays one randomly."""
    print(f"\n--- DIALING COMPLETE: {number} ---")
    
    # Search for any file that starts with the phone number
    search_pattern = os.path.join(AUDIO_DIR, f"{number}*.*")
    all_matching_files = glob.glob(search_pattern)
    
    # Filter out things that aren't actually audio files
    valid_extensions = ('.webm', '.m4a', '.mp4', '.wav', '.mp3', '.ogg', '.flac')
    playable_files = [f for f in all_matching_files if f.lower().endswith(valid_extensions)]
    
    if playable_files:
        # Pick one at random from the list
        file_to_play = random.choice(playable_files)
        print(f"Found {len(playable_files)} artifacts. Randomly selected: {os.path.basename(file_to_play)}")
        play_sound(file_to_play)
    else:
        print("No artifacts found. Prompting to record new artifact...")
        record_local_artifact(number)


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
            
            # Optional: Play DTMF tones
            if os.path.exists(f"{SFX_DIR}/dtmf_{digit}.wav"):
                play_sound(f"{SFX_DIR}/dtmf_{digit}.wav", blocking=False)
                
        pulse_count = 0

off_normal_switch.when_pressed = off_normal_engaged
off_normal_switch.when_released = off_normal_disengaged
dial_switch.when_pressed = handle_pulse


# --- MAIN LOOP ---
print("Rotary Archiver initialized. Waiting for interaction...")

try:
    while True:
        time.sleep(0.1)
        
        # Check if 3 seconds have passed since the last digit was dialed
        if hook_switch.is_pressed and len(dialed_number) > 0 and not is_dialing and (time.time() - last_digit_time > 3.0):
            handle_completed_number(dialed_number)
            dialed_number = "" # Reset sequence so it doesn't trigger again

except KeyboardInterrupt:
    print("\nShutting down Rotary Archive...")
    stop_active_process()
