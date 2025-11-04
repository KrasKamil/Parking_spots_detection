import os
import glob
import math
import subprocess

IMG_DIR = os.path.join("data", "source", "img")

def list_files_three_columns(folder, pattern="*.png", cols=3):
    """Listuje pliki w folderze w formacie trójkolumnowym."""
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files:
        print(f"No files matching {pattern} in folder: {folder}")
        return []
    names = [os.path.basename(p) for p in files]
    maxlen = max(len(n) for n in names) + 4
    rows = math.ceil(len(names) / cols)

    print("\nAvailable files:")
    for r in range(rows):
        row_str = ""
        for c in range(cols):
            idx = r + c * rows
            if idx < len(names):
                entry = f"[{idx+1:2d}] {names[idx]}"
                row_str += entry.ljust(maxlen)
        print(row_str)
    print("")
    return files


def get_direct_youtube_url(youtube_url: str) -> str:
    """Uses yt-dlp to extract the direct stream URL for a YouTube video."""
    try:
        # Use yt-dlp to get direct stream URL with best video quality
        command = [
            'yt-dlp',
            '--get-url',
            '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            youtube_url
        ]
        
        # Execute command and capture result (URL)
        direct_url = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
        
        if direct_url.startswith('http'):
            print("✅ YouTube link detected. Successfully obtained direct stream URL.")
            return direct_url
            
    except FileNotFoundError:
        print("❌ Error: Command 'yt-dlp' not found. Make sure it is installed.")
    except Exception as e:
        print(f"❌ Error extracting URL from YouTube: {e}")
        
    return youtube_url # Return original URL as fallback