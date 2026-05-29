from gpiozero import Button
import time
import subprocess
import os
import signal
from datetime import datetime
import random
import glob
import zork_engine

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

# Tracks if the phone is in normal mode, or deep inside a menu
current_menu_state = "normal" 

# --- SYSTEM ACTIONS ---

def handle_zork_main(digit):
    """Handles standard navigation and root actions inside Zork."""
    global current_menu_state

    current_room = zork_player["current_room"]
    room_data = zork_map[current_room]

    # Check if they dialed a valid navigation direction (4=N, 0=S, 7=E, 1=W, 3=U, 9=D)
    if digit in room_data["exits"]:
        new_room = room_data["exits"][digit]
        zork_player["current_room"] = new_room

        print(f"Zork: Moving to {new_room}...")

        # Print the new room's description to the terminal for debugging
        # (You would normally store the text strings in your dictionary too!)
        print(f"Zork (Debug): Entered {new_room}.")

        # Play the new room's audio description
        new_audio = zork_map[new_room]["audio_desc"]
        if os.path.exists(f"{SFX_DIR}/zork/{new_audio}"):
            play_sound(f"{SFX_DIR}/zork/{new_audio}", blocking=False)

    # Check if they want to interact (2)
    elif digit == '2':
        trigger_interaction(current_room)

    # Check inventory (5)
    elif digit == '5':
        if not zork_player["inventory"]:
            print("Zork: Inventory is empty.")
            play_sound(f"{SFX_DIR}/zork/responses/inventory_empty.wav", blocking=False)
        else:
            print(f"Zork: Inventory contains {zork_player['inventory']}")
            # We can build a dynamic audio inventory reader later!

    # Look around again (8)
    elif digit == '8':
        print("Zork: Looking around...")
        audio = room_data["audio_desc"]
        if os.path.exists(f"{SFX_DIR}/zork/{audio}"):
            play_sound(f"{SFX_DIR}/zork/{audio}", blocking=False)

    else:
        print("Zork: You can't go that way / Invalid action.")
        play_sound(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav", blocking=False)


def stop_active_process():
    """Kills any currently playing or recording audio forcefully."""
    global current_process
    if current_process:
        try:
            current_process.kill() # Upgraded to a forceful kill instead of polite SIGTERM
        except Exception:
            pass
        current_process = None
        
    # SLEDGEHAMMER FALLBACK: Guarantee absolute silence on the soundcard
    subprocess.run(["killall", "-9", "aplay", "arecord"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def play_sound(filepath, blocking=False):
    """Plays an optimized WAV audio file instantly, but allows instant interruption."""
    global current_process
    stop_active_process() 
    
    cmd = ["aplay", "-D", "plughw:0,0", filepath] 
        
    # ALWAYS use Popen so the script remembers the process and can kill it
    current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if blocking:
        # Instead of completely freezing the script, wait in tiny loops.
        # If the user hangs up, stop_active_process() sets current_process to None, 
        # instantly breaking this loop and killing the sound!
        while current_process is not None and current_process.poll() is None:
            time.sleep(0.05)


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

def handle_menu_input(number):
    """Processes dialed digits when the user is inside the Operator Tree."""
    global current_menu_state
    print(f"*** MENU INPUT RECEIVED: {number} | CURRENT STATE: {current_menu_state} ***")

    # --- BRANCH: MAIN OPERATOR MENU ---
    if current_menu_state == "operator_main":
        if number == '1':
            print("Operator: Sync selected. Awaiting confirmation.")
            play_sound(f"{SFX_DIR}/operator_sync_confirm.wav", blocking=False)
            current_menu_state = "operator_sync_confirm" # Move them deeper into the tree
            
        elif number == '9':
            print("Operator: Exiting menu.")
            play_sound(f"{SFX_DIR}/operator_exit.wav", blocking=True)
            current_menu_state = "normal" # Kick them back to regular phone mode
            
        else:
            print("Operator: Invalid choice.")
            play_sound(f"{SFX_DIR}/operator_invalid.wav", blocking=False)
            # State remains "operator_main" so they can try again

    # --- BRANCH: SYNC CONFIRMATION ---
    elif current_menu_state == "operator_sync_confirm":
        if number == '2':
            print("Operator: Confirmed. Running sync...")
            play_sound(f"{SFX_DIR}/operator_syncing_now.wav", blocking=True)
            
            # Actually trigger the sync script!
            subprocess.run(["/usr/bin/python3", "/home/codar/rotary_phone/sync_archive.py"])
            
            play_sound(f"{SFX_DIR}/operator_sync_complete.wav", blocking=False)
            current_menu_state = "normal" # Reset to normal after finishing
            
        elif number == '1':
            print("Operator: Sync cancelled.")
            play_sound(f"{SFX_DIR}/operator_sync_cancelled.wav", blocking=False)
            current_menu_state = "normal" # Reset
            
        else:
            print("Operator: Invalid confirmation.")
            play_sound(f"{SFX_DIR}/operator_invalid.wav", blocking=False)
            current_menu_state = "normal" # Kick them out on a bad input

def handle_special_digit(digit):
    """Routes single-digit commands to their specific interactive functions."""
    global current_menu_state
    print(f"*** SPECIAL FUNCTION TRIGGERED: {digit} ***")
    
    if digit == '7':
        # --- ROTARY ROULETTE ---
        print("Starting Rotary Roulette...")
        if os.path.exists(f"{SFX_DIR}/roulette_intro.wav"):
            play_sound(f"{SFX_DIR}/roulette_intro.wav", blocking=True)
            
        # Get all valid wav files
        all_files = glob.glob(os.path.join(AUDIO_DIR, "*.wav"))
        
        # Loop random files until the user hangs up the handset
        while all_files and hook_switch.is_pressed:
            random_file = random.choice(all_files)
            
            # Ensure we don't accidentally play back _new sync artifacts
            if "_new.wav" in random_file:
                continue
                
            print(f"Roulette playing: {os.path.basename(random_file)}")
            play_sound(random_file, blocking=True)
            time.sleep(0.5) # Brief pause between calls
            
    elif digit == '0':
        # --- OPERATOR MENU ---
        print("Starting Operator Menu...")
        current_menu_state = "operator_main"
        # Play the audio in the background so the script can immediately listen to the rotary dial again
        if os.path.exists(f"{SFX_DIR}/operator_main_menu.wav"):
            play_sound(f"{SFX_DIR}/operator_main_menu.wav", blocking=False) 

    elif digit == '9':
        # --- ZORK BOOT SEQUENCE ---
        print("\n=== STARTING ZORK ===")
        zork_engine.reset_zork() # Ensure the player's inventory and flags are completely wiped clean
        current_menu_state = "zork_main"

        # 1. Print Debug Text to Terminal
        print("Zork (Description): West of House. You are standing in an open field west of a white house, with a boarded front door. There is a small mailbox here. A rubber mat saying 'Welcome' lies in front of the door.")
        print("Zork (Instructions): To go North, dial 4. To go South, dial 0. To interact with the mailbox or the mat, dial 2. To check your inventory, dial 5.")

        # 2. Play the Description (blocking=True so it finishes before the instructions start)
        if os.path.exists(f"{SFX_DIR}/zork/locations/west_of_house.wav"):
            play_sound(f"{SFX_DIR}/zork/locations/west_of_house.wav", blocking=True)

        # 3. Play the Instructions (blocking=False so the script immediately starts listening to the rotary dial)
        if os.path.exists(f"{SFX_DIR}/zork/instructions/west_of_house_instructions.wav"):
            play_sound(f"{SFX_DIR}/zork/instructions/west_of_house_instructions.wav", blocking=False)
        
    else:
        # Placeholder for 1-6, 8, 9
        print(f"Special digit {digit} is reserved but unassigned.")
        if os.path.exists(f"{SFX_DIR}/unassigned.wav"):
            play_sound(f"{SFX_DIR}/unassigned.wav", blocking=True)

def handle_completed_number(number):
    """Routes the dialed number based on the current state of the phone."""
    global current_menu_state
    print(f"\n--- DIALING COMPLETE: {number} ---")

    # 1. STATE INTERCEPT: Are we trapped inside a menu or a game?
    if current_menu_state in ["operator_main", "operator_sync_confirm"]:
        handle_menu_input(number)
        return

    elif current_menu_state == "zork_main":
        new_state = zork_engine.handle_zork_main(number)
        if new_state: # If the engine requested a state change, apply it!
            current_menu_state = new_state
        return

    elif current_menu_state == "zork_interact_menu":
        # (We will build this in the zork_engine.py next!)
        zork_engine.handle_zork_interact_menu(number)
        return

    elif current_menu_state == "zork_purgatory":
        zork_engine.handle_zork_purgatory(number)
        return

    # 2. SPECIAL DIGIT INTERCEPT: Is it exactly 1 digit in normal mode? (0-9)
    if len(number) == 1:
        handle_special_digit(number)
        return

    # 3. REGULAR DIALING: Execute standard audio archive lookup
    search_pattern = os.path.join(AUDIO_DIR, f"{number}*.*")
    candidate_files = glob.glob(search_pattern)

    valid_extensions = ('.wav', '.webm', '.m4a', '.mp4', '.mp3', '.ogg', '.flac')
    playable_files = []

    for filepath in candidate_files:
        filename = os.path.basename(filepath)
        if not filename.lower().endswith(valid_extensions):
            continue

        # Strip the extension and isolate the dialed prefix
        name_without_ext = os.path.splitext(filename)[0]
        parts = name_without_ext.split('_')

        # Strict match to prevent 112 from playing when 11 is dialed
        if parts[0] == number:
            playable_files.append(filepath)

    if playable_files:
        file_to_play = random.choice(playable_files)
        print(f"Found {len(playable_files)} exact artifacts. Randomly selected: {os.path.basename(file_to_play)}")

        # Play the fake ringtone to mask the loading gap
        if os.path.exists(f"{SFX_DIR}/ringing.wav"):
            print("Simulating network connection (Ringing)...")
            play_sound(f"{SFX_DIR}/ringing.wav", blocking=True)

        play_sound(file_to_play)

    else:
        print("No artifacts found for this exact number. Prompting to record new artifact...")

        if os.path.exists(f"{SFX_DIR}/ringing.wav"):
            play_sound(f"{SFX_DIR}/ringing.wav", blocking=True)

        record_local_artifact(number)



# --- EVENT HANDLERS ---

def hook_picked_up():
    print("Phone Off-Hook.")
    global dialed_number
    dialed_number = ""
    play_sound(f"{SFX_DIR}/dial_tone.wav") 

def hook_hung_up():
    print("Phone Hung Up.")
    global dialed_number, is_dialing, pulse_count, current_menu_state
    
    stop_active_process()
    dialed_number = ""
    is_dialing = False
    pulse_count = 0
    current_menu_state = "normal" # CRITICAL: Escapes the user from any menus

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

# Initialize Zork with our local audio tools
zork_engine.init_zork(play_sound, SFX_DIR)

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
