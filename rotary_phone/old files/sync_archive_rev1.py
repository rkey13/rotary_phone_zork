import os
import requests
import glob

# --- CONFIGURATION ---
AUDIO_DIR = "/home/codar/rotary_audio"
API_URL = "https://rotary-backend.your-subdomain.workers.dev" # Update this!

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
    
    # Find all files ending in _new.wav
    search_pattern = os.path.join(AUDIO_DIR, "*_new.wav")
    pending_files = glob.glob(search_pattern)
    
    if not pending_files:
        print("No new local recordings found.")
        return
        
    for filepath in pending_files:
        filename = os.path.basename(filepath)
        phone_number = filename.split('_')[0]
        
        print(f"Uploading {filename}...")
        try:
            with open(filepath, 'rb') as f:
                files = {'audio': (filename, f, 'audio/wav')}
                data = {'phone_number': phone_number, 'description': 'Recorded via Physical Rotary Phone'}
                
                response = requests.post(f"{API_URL}/api/upload", files=files, data=data)
                
                if response.status_code == 200:
                    print("  -> Upload successful!")
                    # Rename the file so it becomes the active local deployment
                    # e.g., 888_new.wav becomes 888.wav
                    new_filepath = os.path.join(AUDIO_DIR, f"{phone_number}.wav")
                    os.rename(filepath, new_filepath)
                else:
                    print(f"  -> Upload failed with status {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"  -> Error uploading {filename}: {e}")

def download_active_deployments():
    """Fetches the directory map and downloads missing active deployments."""
    print("\n--- Syncing Active Deployments from Cloudflare ---")
    
    try:
        # Assuming you create this endpoint on your Worker to return a list of active files
        # Example JSON response: [{"phone_number": "123", "audio_filename": "123.webm"}, ...]
        response = requests.get(f"{API_URL}/api/pi-sync")
        
        if response.status_code != 200:
            print("Failed to fetch directory map from API.")
            return
            
        directory_map = response.json()
        
        for item in directory_map:
            number = item.get("phone_number")
            filename = item.get("audio_filename")
            
            # Check if we already have an active file for this number
            # (We look for any extension since it could be .wav, .webm, etc.)
            existing_files = glob.glob(os.path.join(AUDIO_DIR, f"{number}.*"))
            
            # Filter out files that match the exact filename we are looking for
            has_exact_file = any(f.endswith(filename) for f in existing_files)
            
            if not has_exact_file:
                print(f"Downloading new deployment for {number}: {filename}...")
                audio_response = requests.get(f"{API_URL}/api/audio/{filename}")
                
                if audio_response.status_code == 200:
                    download_path = os.path.join(AUDIO_DIR, filename)
                    with open(download_path, "wb") as f:
                        f.write(audio_response.content)
                    
                    # Optional: Clean up older local files for this number to save space
                    for old_file in existing_files:
                        if old_file != download_path and not old_file.endswith('_new.wav'):
                            os.remove(old_file)
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
