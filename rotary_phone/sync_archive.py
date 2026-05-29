import os
import shutil
import requests
import glob
import subprocess

# --- CONFIGURATION ---
AUDIO_DIR = "/home/codar/rotary_audio"
# Define your backup directory path
BACKUP_DIR = os.path.join(AUDIO_DIR, "originals_backup")
API_URL = "https://rotary-backend.rkey13.workers.dev"


def ensure_optimized_wav(filepath):
    """
    Converts non-WAV files to an optimized 44.1kHz Mono WAV file.
    Moves the original compressed file to a backup folder instead of deleting it.
    """
    base_path, ext = os.path.splitext(filepath)
    if ext.lower() == '.wav':
        return filepath 

    output_wav = f"{base_path}.wav"
    print(f"  -> [Optimization] Converting {os.path.basename(filepath)} to WAV...")

    cmd = [
        "ffmpeg", "-y",
        "-i", filepath,
        "-ar", "44100",
        "-ac", "1",
        "-af", "volume=-2dB",
        "-loglevel", "quiet",
        output_wav
    ]

    try:
        # Run conversion
        subprocess.run(cmd, check=True)
        
        # Ensure the backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Move the original non-wav file to the backup folder instead of deleting it
        backup_path = os.path.join(BACKUP_DIR, os.path.basename(filepath))
        shutil.move(filepath, backup_path)
        
        print(f"  -> Optimization complete. Original backed up to: originals_backup/{os.path.basename(filepath)}")
        return output_wav
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Optimization failed for {os.path.basename(filepath)}: {e}")
        return filepath

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
                    new_filepath = filepath.replace("_new.wav", ".wav")
                    os.rename(filepath, new_filepath)
                else:
                    print(f"  -> Upload failed with status {response.status_code}: {response.text}")
                    
        except Exception as e:
            print(f"  -> Error uploading {filename}: {e}")

def download_active_deployments():
    """Fetches the directory map and downloads missing active deployments securely."""
    print("\n--- Syncing Active Deployments from Cloudflare ---")
    
    try:
        response = requests.get(f"{API_URL}/api/pi-sync")
        
        if response.status_code != 200:
            print("Failed to fetch directory map from API.")
            return
            
        directory_map = response.json()
        
        for item in directory_map:
            number = item.get("phone_number")
            filename = item.get("audio_filename") # e.g., '11_abc.webm'
            
            # Calculate what the final optimized WAV filename looks like
            base_name, _ = os.path.splitext(filename)
            wav_filename = f"{base_name}.wav"
            
            # Map out all possible paths across active storage and backup targets
            local_file_path = os.path.join(AUDIO_DIR, filename)      # /rotary_audio/11_abc.webm
            local_wav_path = os.path.join(AUDIO_DIR, wav_filename)    # /rotary_audio/11_abc.wav
            local_backup_path = os.path.join(BACKUP_DIR, filename)   # /rotary_audio/originals_backup/11_abc.webm

            # SMART CHECK: If the WAV, the WebM, or the raw backup exist, we skip downloading!
            if os.path.exists(local_file_path) or os.path.exists(local_wav_path) or os.path.exists(local_backup_path):
                continue # Already processed cleanly, move to the next item

            # If it's truly a missing or brand new file, pull it down
            print(f"Downloading new deployment for {number}: {filename}...")
            audio_response = requests.get(f"{API_URL}/api/audio/{filename}")
            
            if audio_response.status_code == 200:
                with open(local_file_path, "wb") as f:
                    f.write(audio_response.content)
                
                # Transform the asset instantly to uncompressed WAV and archive the raw format
                optimized_path = ensure_optimized_wav(local_file_path)
                print("  -> Download and optimization complete.")
            else:
                print(f"  ❌ Failed to download audio file: {filename} (Status: {audio_response.status_code})")
                
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
