import os

# These will be linked from your main script when the app boots
play_sound = None
SFX_DIR = ""

# --- ZORK STATE & MAP ---
zork_player = {}

zork_map = {
    "west_of_house": {
        "audio_desc": "locations/west_of_house.wav",
        "exits": {"4": "north_of_house", "0": "south_of_house"},
        "interactions": {
            "menu_audio": None, 
            "choices": {"1": "mailbox", "2": "mat"},
            "auto_fallback": "mailbox" 
        }
    }
    # We will expand the rest of the map here later!
}

# --- ENGINE LOGIC ---
def init_zork(sound_callback, sfx_directory):
    """Links the audio engine from the main script into Zork."""
    global play_sound, SFX_DIR
    play_sound = sound_callback
    SFX_DIR = sfx_directory
    reset_zork()

def reset_zork():
    """Wipes the player's inventory and resets the map."""
    global zork_player
    zork_player = {
        "current_room": "west_of_house",
        "inventory": [],
        "flags": {
            "mailbox_open": False,
            "window_open": False,
            "rug_moved": False,
            "trapdoor_open": False,
            "troll_alive": True
        }
    }

def handle_zork_main(digit):
    """Handles standard compass navigation and root actions."""
    current_room = zork_player["current_room"]
    room_data = zork_map[current_room]
    
    # 1. Check for compass navigation (4=N, 0=S, 7=E, 1=W, 3=U, 9=D)
    if digit in room_data["exits"]:
        new_room = room_data["exits"][digit]
        zork_player["current_room"] = new_room
        
        print(f"Zork (Debug): Entered {new_room}.")
        # Fallback debug text (you can replace these with actual dictionary strings later)
        print(f"Zork: Playing description for {new_room}...")
        
        new_audio = zork_map[new_room]["audio_desc"]
        if os.path.exists(f"{SFX_DIR}/zork/{new_audio}"):
            play_sound(f"{SFX_DIR}/zork/{new_audio}", blocking=False)
            
    # 2. Check for interaction (2)
    elif digit == '2':
        trigger_interaction(current_room)
        
    # 3. Check inventory (5)
    elif digit == '5':
        if not zork_player["inventory"]:
            print("Zork: Inventory is empty.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/inventory_empty.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/inventory_empty.wav", blocking=False)
        else:
            print(f"Zork: Inventory contains {zork_player['inventory']}")
            
    # 4. Look around / Repeat room description (8)
    elif digit == '8':
        print("Zork: Looking around...")
        audio = room_data["audio_desc"]
        if os.path.exists(f"{SFX_DIR}/zork/{audio}"):
            play_sound(f"{SFX_DIR}/zork/{audio}", blocking=False)
            
    else:
        print("Zork: You can't go that way / Invalid action.")
        if os.path.exists(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav", blocking=False)

def trigger_interaction(room_id):
    """Placeholder for the interaction menu logic we discussed."""
    print(f"Zork: Interacting in {room_id} (Logic pending implementation...)")

def handle_zork_purgatory(digit):
    """Placeholder for the death screen logic."""
    print("Zork: You are in purgatory. Dial 1 to restart.")
    if digit == '1':
        reset_zork()
        print("Zork: Reincarnating...")
