import os
import glob
import subprocess
import json
import math
import cv2
import datetime
import sys 
from src.utils import list_files_three_columns, IMG_DIR, get_direct_youtube_url

CONFIG_PATH = os.path.join("config", "parking_config.json")

def choose_file_interactively(files):
    if not files:
        # If no files, offer to capture from source
        while True:
            choice = input("No files found. Type 'capture' to grab a frame from a source, or 'q' to cancel: ").strip().lower()
            if choice == 'q':
                return None
            elif choice == 'capture':
                
                lot_name = input("Enter a base name for the new parking lot (e.g., 'galeria_polnoc'): ").strip()
                if not lot_name:
                    print("Base name cannot be empty. Returning to menu.")
                    continue
                                
                video_url = input("Enter video/camera URL (e.g., rtsp://... or path/to/video.mp4): ").strip()
                return capture_frame_from_source(video_url, lot_name)
            else:
                print("Invalid choice. Enter 'capture' or 'q'.")
                
    while True:
        choice = input("Choose file (number), type 'latest', 'capture', or 'q' to cancel: ").strip().lower() 
        if choice == 'q':
            return None
        elif choice == 'latest':
            image_path = files[-1]
            print(f"Selected latest file: {os.path.basename(image_path)}")
            return image_path
        elif choice == 'capture':
            lot_name = input("Enter a base name for the new parking lot (e.g., 'galeria_polnoc'): ").strip()
            if not lot_name:
                print("Base name cannot be empty. Returning to menu.")
                continue
            
            video_url = input("Enter video/camera URL (e.g., rtsp://... or path/to/video.mp4): ").strip()
            if not video_url:
                 print("Source URL cannot be empty. Returning to menu.")
                 continue
            
           
            captured_path = capture_frame_from_source(video_url, lot_name)
            
            
            if captured_path:
                return captured_path
            else:
                continue

        try:
            index = int(choice) - 1
            if 0 <= index < len(files):
                image_path = files[index]
                print(f"Selected file: {os.path.basename(image_path)}")
                return image_path
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid choice. Enter a number, 'latest', 'capture', or 'q'.")


def get_last_added_lot_name():
    """Reads the last lot name saved by add_parking_config.py"""
    temp_file = os.path.join("config", "temp_last_lot.json")
    if os.path.exists(temp_file):
        with open(temp_file, 'r') as f:
            data = json.load(f)
            return data.get('lot_name')
    return None

def capture_frame_from_source(video_source: str, lot_name_prefix: str) -> str | None:
    """Connects to video source, captures a frame, saves it as PNG , and returns the file path."""
    final_source = get_direct_youtube_url(video_source)
    cap = cv2.VideoCapture(final_source, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        print(f"Error: Could not open video source: {video_source}")
        if not cap.isOpened():
            print(f"❌ Critical Error: Could not open video from backend source:" )
            return None
        
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = lot_name_prefix.lower().replace(' ', '_') 
        
        filename = f"{safe_prefix}_{timestamp}.png"
        filepath = os.path.join(IMG_DIR, filename) 

        os.makedirs(IMG_DIR, exist_ok=True) 
        
        cv2.imwrite(filepath, frame)
        print(f"✅ Pomyślnie przechwycono i zapisano klatkę: {filepath}")
        return filepath
    else:
        print("❌ Error: Could not read frame from video source.")
        return None

def main():
    print("=== Starting automatic configuration (Interactive mode) ===")
    
    # 1) Choose reference file
    files = list_files_three_columns(IMG_DIR)
    if not files:
        return

    image_path = choose_file_interactively(files)
    if not image_path:
        print("Canceled by user.")
        return

    image_filename = os.path.basename(image_path)
    default_lot_name = os.path.splitext(image_filename)[0].lower().replace(' ', '_')
    
    # 2) W/H Calibration (Run generator in 'c' mode)
    try:
        print("\n== Starting annotation tool in CALIBRATION MODE ==")
        print("💡 INSTRUCTIONS: Open window, press 'c', measure W/H dimensions (by clicking two corners) and close window.")
        
        subprocess.run([sys.executable, "car_park_coordinate_generator.py", 
                "--lot", "empty_calibration", 
                "--image", image_path, 
                "--mode", "c"], 
               check=True)
        print("✅ Calibration completed. Note the displayed W/H dimensions before proceeding.")

    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py ended with an error in calibration mode. Further steps canceled.")
        return

    # 3) Add/modify configuration (Interactively)
    try:
        print("\n== Running add_parking_config.py (enter measured parameters) ==")
        # Run without arguments, forcing interactive data collection.
        subprocess.run([sys.executable, "add_parking_config.py", 
                        "--default_name", default_lot_name, 
                        "--image_path", image_path], 
                       check=True)

    except subprocess.CalledProcessError as e:
        print("❌ add_parking_config.py ended with an error. Further steps canceled.")
        return

    # 4) Read parking lot name
    lot_name = get_last_added_lot_name()
    if not lot_name:
        print("❌ Failed to read parking lot name. Check if add_parking_config.py saved data correctly.")
        return

    print(f"\n📦 Detected parking lot name: {lot_name}")

    # 5) Run remaining steps (Annotation and Monitoring)
    # Run generator second time - now for marking positions for the created 'lot_name'.
    try:
        print(f"\n== Running car_park_coordinate_generator.py --lot {lot_name} ==")
        print("📌 Now you can mark all parking spaces (modes 'p', 'i').")
        
        subprocess.run([sys.executable, "car_park_coordinate_generator.py", "--lot", lot_name], check=True)
        print("✅ Completed car_park_coordinate_generator.py")
    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py ended with an error:", e)
        return

    try:
        print(f"\n== Running app.py --lot {lot_name} (Monitoring) ==")
        print("🎥 Starting monitoring preview. Close window to finish.")
        
        subprocess.run([sys.executable, "app.py", "--lot", lot_name], check=True)
        print("✅ Monitoring completed.")
    except subprocess.CalledProcessError as e:
        print("❌ app.py ended with an error:", e)
        return
        
    print("\n=== Automatic configuration sequence completed successfully! ===")

if __name__ == "__main__":
    main()