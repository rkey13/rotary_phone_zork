import os
import requests
import glob

# --- CONFIGURATION ---
AUDIO_DIR = "/home/codar/rotary_audio"
API_URL = "https://rotary-backend.rkey13.workers.dev" # Make sure to update this!

def check_internet():
    """Pings the Cloudflare DNS to ensure we are actually online."""
    try:
        requests.get("https://1.1.1.1", timeout=3)
        return True
    except requests.ConnectionError:
        return False

def upload_pending_artifacts():
    """Finds all *_new.wav files and uploads them to the Cloudflare API."""
    print("--- Checking for pending uploads ---")
    
    search_pattern = os.path.join(AUDIO_DIR, "*_new.wav")
    pending_files = glob.glob(search_pattern)
    
    if not pending_files:
        print("No new local recordings found.")
        return
        
    for filepath in pending_files:
        filename = os.path.basename(filepath)
        # Because we structured it as number_timestamp_new.wav, [0] is the number
        phone_number = filename.split('_')[0] 
        
        print(f"Uploading {filename}...")
        try:
            with open(filepath, 'rb') as f:
                files = {'audio': (filename, f, 'audio/wav')}
                data = {'phone_number': phone_number, 'description': 'Recorded via Physical Rotary Phone'}
                
                response = requests.post(f"{API_URL}/api/upload", files=files, data=data)
                
                if response.status_code == 200:
                    print("  -> Upload successful!")
                    # Strip the _new suffix so it becomes a standard archive file
                    # e.g., 888_20260527_100000_new.wav -> 888_20260527_100000.wav
                    new_filepath = filepath.replace("_new.wav", ".wav")
                    os.rename(filepath, new_filepath)
                else:
                    print(f"  -> Upload failed with status {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"  -> Error uploading {filename}: {e}")

def download_active_deployments():
    """Fetches the directory map and downloads missing active deployments."""
    print("\n--- Syncing Active Deployments from Cloudflare ---")
    
    try:
        # Requires a backend endpoint returning [{"phone_number": "123", "audio_filename": "123.webm"}]
        response = requests.get(f"{API_URL}/api/pi-sync")
        
        if response.status_code != 200:
            print("Failed to fetch directory map from API.")
            return
            
        directory_map = response.json()
        
        for item in directory_map:
            number = item.get("phone_number")
            filename = item.get("audio_filename")
            
            # Check if we already have this exact file
            existing_files = glob.glob(os.path.join(AUDIO_DIR, f"{number}*.*"))
            has_exact_file = any(f.endswith(filename) for f in existing_files)
            
            if not has_exact_file:
                print(f"Downloading new deployment for {number}: {filename}...")
                audio_response = requests.get(f"{API_URL}/api/audio/{filename}")
                
                if audio_response.status_code == 200:
                    download_path = os.path.join(AUDIO_DIR, filename)
                    with open(download_path, "wb") as f:
                        f.write(audio_response.content)
                    print("  -> Download complete.")
                else:
                    print(f"  -> Failed to download audio file.")
            else:
                pass # Already have it
                
    except Exception as e:
        print(f"Error during download sync: {e}")

if __name__ == "__main__":
    print("Initiating Rotary Archive Sync sequence...")
    if check_internet():
        print("Internet connection verified.\n")
        upload_pending_artifacts()
        download_active_deployments()
        print("\nSync sequence complete.")
    else:
        print("NO INTERNET CONNECTION. Aborting sync.")
