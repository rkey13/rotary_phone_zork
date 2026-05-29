import os

play_sound = None
SFX_DIR = ""

# --- ZORK STATE & MAP ---
zork_player = {}

zork_map = {
    "west_of_house": {
        "audio_desc": "locations/west_of_house.wav",
        "exits": {"4": "north_of_house"}, # 4=North
        "interactions": {
            "menu_audio": None,
            "choices": {"1": "mailbox", "2": "mat"},
            "auto_fallback": "mailbox"
        }
    },
    "north_of_house": {
        "audio_desc": "locations/north_of_house.wav",
        "instruction_audio": "instructions/north_of_house_instructions.wav",
        "exits": {"7": "west_of_house", "1": "behind_house", "4": "forest_path"}, # 7=West, 1=East, 4=North
        "interactions": {}
    },
    "forest_path": {
        "audio_desc": "locations/forest_path.wav",
        "exits": {"0": "north_of_house", "3": "up_a_tree"}, # 0=South, 3=Up
        "interactions": {}
    },
    "up_a_tree": {
        "audio_desc": "locations/up_a_tree.wav",
        "exits": {"9": "forest_path"}, # 9=Down
        "interactions": {
            "menu_audio": None,
            "choices": {"1": "egg"},
            "auto_fallback": "egg"
        }
    },
    "behind_house": {
        "audio_desc": "locations/behind_house.wav",
        "exits": {"7": "kitchen", "4": "north_of_house"}, # 7=West (Kitchen), 4=North
        "interactions": {
            "menu_audio": "actions/behind_house_interact_menu.wav",
            "choices": {"1": "window"},
            "auto_fallback": "window"
        }
    },
    "kitchen": {
        "audio_desc": "locations/kitchen.wav",
        "exits": {"7": "living_room", "1": "behind_house"}, # 7=West (Living Room), 1=East (Behind House)
        "interactions": {
            "menu_audio": None,
            "choices": {"1": "sack", "2": "bottle"},
            "auto_fallback": "sack"
        }
    },
    "living_room": {
        "audio_desc": "locations/living_room.wav",
        "exits": {"1": "kitchen", "9": "cellar"}, # 1=East, 9=Down
        "interactions": {
            "menu_audio": "actions/living_room_interact_menu.wav",
            "choices": {"1": "lantern", "2": "sword", "3": "rug", "4": "trapdoor"},
            "auto_fallback": "lantern"
        }
    },
    "cellar": {
        "audio_desc": "locations/cellar.wav",
        "exits": {"3": "living_room", "4": "troll_room"}, # 3=Up, 4=North
        "interactions": {}
    },
    "troll_room": {
        "audio_desc": "locations/troll_room.wav",
        "exits": {"0": "cellar"}, # 0=South
        "interactions": {
            "menu_audio": None,
            "choices": {"1": "troll"},
            "auto_fallback": "troll"
        }
    }
}

# --- ENGINE LOGIC ---
def init_zork(sound_callback, sfx_directory):
    global play_sound, SFX_DIR
    play_sound = sound_callback
    SFX_DIR = sfx_directory
    reset_zork()

def reset_zork():
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
    current_room = zork_player["current_room"]
    room_data = zork_map[current_room]

    # 1. Check for compass navigation
    if digit in room_data["exits"]:
        new_room = room_data["exits"][digit]

        # --- CONDITIONAL MOVEMENT LOCKS ---
        if new_room == "cellar" and not zork_player["flags"]["trapdoor_open"]:
            print("Zork: The trapdoor is closed.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav", blocking=False)
            return "zork_main"

        # Lock the Kitchen Window (Entering)
        if new_room == "kitchen" and current_room == "behind_house" and not zork_player["flags"]["window_open"]:
            print("Zork: The window is closed.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/window_closed.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/window_closed.wav", blocking=False)
            return "zork_main"

        # Lock the Kitchen Window (Exiting)
        if new_room == "behind_house" and current_room == "kitchen" and not zork_player["flags"]["window_open"]:
            print("Zork: The window is closed.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/window_closed.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/window_closed.wav", blocking=False)
            return "zork_main"

        zork_player["current_room"] = new_room
        print(f"Zork (Debug): Entered {new_room}.")

        new_audio = zork_map[new_room]["audio_desc"]
        instruction_audio = zork_map[new_room].get("instruction_audio")

        # THE HYBRID AUDIO SYSTEM:
        if instruction_audio and os.path.exists(f"{SFX_DIR}/zork/{instruction_audio}"):
            # Block until description finishes, then play instructions
            if os.path.exists(f"{SFX_DIR}/zork/{new_audio}"):
                play_sound(f"{SFX_DIR}/zork/{new_audio}", blocking=True)
            play_sound(f"{SFX_DIR}/zork/{instruction_audio}", blocking=False)
        else:
            # Just play the normal room description
            if os.path.exists(f"{SFX_DIR}/zork/{new_audio}"):
                play_sound(f"{SFX_DIR}/zork/{new_audio}", blocking=False)

    # 2. Check for interaction
    elif digit == '2':
        return trigger_interaction(current_room)

    # 3. Check inventory
    elif digit == '5':
        if not zork_player["inventory"]:
            print("Zork: Inventory is empty.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/inventory_empty.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/inventory_empty.wav", blocking=False)
        else:
            print(f"Zork: Inventory contains {zork_player['inventory']}")

            # Optional: Play a prefix audio file first (e.g., "You are currently holding...")
            if os.path.exists(f"{SFX_DIR}/zork/responses/inventory_contains.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/inventory_contains.wav", blocking=True)

            # Loop through the inventory and play the "_taken" file for each item
            for item in zork_player["inventory"]:
                audio_file = f"{SFX_DIR}/zork/items/{item}_taken.wav"
                if os.path.exists(audio_file):
                    play_sound(audio_file, blocking=True)

    # 4. Look around
    elif digit == '8':
        print("Zork: Looking around...")
        audio = room_data["audio_desc"]
        instruction_audio = room_data.get("instruction_audio")

        if instruction_audio and os.path.exists(f"{SFX_DIR}/zork/{instruction_audio}"):
            if os.path.exists(f"{SFX_DIR}/zork/{audio}"):
                play_sound(f"{SFX_DIR}/zork/{audio}", blocking=True)
            play_sound(f"{SFX_DIR}/zork/{instruction_audio}", blocking=False)
        else:
            if os.path.exists(f"{SFX_DIR}/zork/{audio}"):
                play_sound(f"{SFX_DIR}/zork/{audio}", blocking=False)

    else:
        print("Zork: You can't go that way / Invalid action.")
        if os.path.exists(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav", blocking=False)

    return "zork_main"

def trigger_interaction(room_id):
    room_data = zork_map[room_id]
    interactions = room_data.get("interactions")

    if not interactions:
        print("Zork: Nothing obvious to interact with here.")
        if os.path.exists(f"{SFX_DIR}/zork/responses/nothing_to_interact_with.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/nothing_to_interact_with.wav", blocking=False)
        return "zork_main"

    menu_audio_file = interactions.get("menu_audio")

    if menu_audio_file and os.path.exists(f"{SFX_DIR}/zork/{menu_audio_file}"):
        print(f"Zork: Playing interaction menu for {room_id}...")
        play_sound(f"{SFX_DIR}/zork/{menu_audio_file}", blocking=False)
        return "zork_interact_menu"
    else:
        target_item = interactions.get("auto_fallback")
        print(f"Zork: No menu audio. Auto-interacting with fallback: {target_item}")
        return process_item_action(target_item)

def handle_zork_interact_menu(digit):
    current_room = zork_player["current_room"]
    choices = zork_map[current_room]["interactions"]["choices"]

    if digit in choices:
        selected_item = choices[digit]
        new_state = process_item_action(selected_item)
        return new_state if new_state else "zork_main"
    else:
        print("Zork: Invalid item selection.")
        if os.path.exists(f"{SFX_DIR}/zork/responses/invalid_choice.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/invalid_choice.wav", blocking=False)
        return "zork_main"

def process_item_action(item_name):
    global zork_player

    if item_name == "mailbox":
        if not zork_player["flags"]["mailbox_open"]:
            # Interaction 1: Open the closed mailbox (DO NOT add to inventory here!)
            zork_player["flags"]["mailbox_open"] = True
            print("Zork: Opening the small mailbox. It reveals a leaflet.")
            if os.path.exists(f"{SFX_DIR}/zork/events/opening_mailbox.wav"):
                play_sound(f"{SFX_DIR}/zork/events/opening_mailbox.wav", blocking=False)

        elif "leaflet" not in zork_player["inventory"]:
            # Interaction 2: Mailbox is open, but leaflet is still inside. Route to the take action!
            return process_item_action("leaflet")

        else:
            # Interaction 3+: Mailbox is open, and leaflet is already in inventory
            print("Zork: The mailbox is already open and empty.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/already_open.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/already_open.wav", blocking=False)

    elif item_name == "leaflet":
        if "leaflet" not in zork_player["inventory"]:
            zork_player["inventory"].append("leaflet")
            print("Zork: Leaflet taken.")
            if os.path.exists(f"{SFX_DIR}/zork/items/leaflet_taken.wav"):
                play_sound(f"{SFX_DIR}/zork/items/leaflet_taken.wav", blocking=False)
        else:
            # Fallback just in case they trigger it another way
            print("Zork: Reading: WELCOME TO ZORK...")
            if os.path.exists(f"{SFX_DIR}/zork/items/read_leaflet.wav"):
                play_sound(f"{SFX_DIR}/zork/items/read_leaflet.wav", blocking=False)
    elif item_name == "mat":
        print("Zork: A rubber mat saying 'Welcome' lies in front of the door.")

    elif item_name == "window":
        if not zork_player["flags"]["window_open"]:
            zork_player["flags"]["window_open"] = True
            print("Zork: With great effort, you open the window.")
            if os.path.exists(f"{SFX_DIR}/zork/events/window_opens.wav"):
                play_sound(f"{SFX_DIR}/zork/events/window_opens.wav", blocking=False)
        else:
            print("Zork: You climb through the open window into the kitchen.")
            zork_player["current_room"] = "kitchen"
            if os.path.exists(f"{SFX_DIR}/zork/locations/kitchen.wav"):
                play_sound(f"{SFX_DIR}/zork/locations/kitchen.wav", blocking=False)

    elif item_name == "lantern":
        if "lantern" not in zork_player["inventory"]:
            zork_player["inventory"].append("lantern")
            print("Zork: Brass lantern taken.")
            if os.path.exists(f"{SFX_DIR}/zork/items/lantern_taken.wav"):
                play_sound(f"{SFX_DIR}/zork/items/lantern_taken.wav", blocking=False)

    elif item_name == "sword":
        if "sword" not in zork_player["inventory"]:
            zork_player["inventory"].append("sword")
            print("Zork: Elven sword taken.")
            if os.path.exists(f"{SFX_DIR}/zork/items/sword_taken.wav"):
                play_sound(f"{SFX_DIR}/zork/items/sword_taken.wav", blocking=False)

    elif item_name == "rug":
        if not zork_player["flags"]["rug_moved"]:
            zork_player["flags"]["rug_moved"] = True
            print("Zork: Rug moved, revealing trapdoor.")
            if os.path.exists(f"{SFX_DIR}/zork/events/rug_moved.wav"):
                play_sound(f"{SFX_DIR}/zork/events/rug_moved.wav", blocking=False)
        else:
            print("Zork: The rug has already been moved.")

    elif item_name == "trapdoor":
        if not zork_player["flags"]["rug_moved"]:
            print("Zork: You don't see a trapdoor here.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/cant_go_that_way.wav", blocking=False)
        elif not zork_player["flags"]["trapdoor_open"]:
            zork_player["flags"]["trapdoor_open"] = True
            print("Zork: Trapdoor opened.")
            if os.path.exists(f"{SFX_DIR}/zork/events/trapdoor_open.wav"):
                play_sound(f"{SFX_DIR}/zork/events/trapdoor_open.wav", blocking=False)
        else:
            print("Zork: The trapdoor is already open.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/already_open.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/already_open.wav", blocking=False)

    elif item_name == "egg":
        if "egg" not in zork_player["inventory"]:
            zork_player["inventory"].append("egg")
            print("Zork: Jewel-encrusted egg taken.")
            if os.path.exists(f"{SFX_DIR}/zork/items/egg_taken.wav"):
                play_sound(f"{SFX_DIR}/zork/items/egg_taken.wav", blocking=False)
        else:
            print("Zork: You already took the egg.")
            if os.path.exists(f"{SFX_DIR}/zork/responses/nothing_to_interact_with.wav"):
                play_sound(f"{SFX_DIR}/zork/responses/nothing_to_interact_with.wav", blocking=False)

    elif item_name == "troll":
        print("Zork: Player attacked the troll and died.")
        if os.path.exists(f"{SFX_DIR}/zork/events/troll_kills_you.wav"):
            play_sound(f"{SFX_DIR}/zork/events/troll_kills_you.wav", blocking=True)
        if os.path.exists(f"{SFX_DIR}/zork/events/purgatory_demo_pitch.wav"):
            play_sound(f"{SFX_DIR}/zork/events/purgatory_demo_pitch.wav", blocking=False)
        return "zork_purgatory" # This shifts the player's state!

    return "zork_main"

def handle_zork_purgatory(digit):
    if digit == '1':
        print("Zork: Reincarnating...")
        if os.path.exists(f"{SFX_DIR}/zork/responses/reincarnating.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/reincarnating.wav", blocking=True)
        reset_zork()
        if os.path.exists(f"{SFX_DIR}/zork/locations/west_of_house.wav"):
            play_sound(f"{SFX_DIR}/zork/locations/west_of_house.wav", blocking=False)
        return "zork_main"
    elif digit == '9':
        print("Zork: Player exited game.")
        if os.path.exists(f"{SFX_DIR}/operator_exit.wav"):
            play_sound(f"{SFX_DIR}/operator_exit.wav", blocking=True)
        return "normal"
    else:
        if os.path.exists(f"{SFX_DIR}/zork/responses/purgatory_invalid.wav"):
            play_sound(f"{SFX_DIR}/zork/responses/purgatory_invalid.wav", blocking=False)
        return "zork_purgatory"
