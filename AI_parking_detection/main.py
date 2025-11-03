import os
import glob
import subprocess
import json
import math

IMG_DIR = os.path.join("data", "source", "img")
CONFIG_PATH = os.path.join("config", "parking_config.json")


def list_files_three_columns(folder, pattern="*.png", cols=3):
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


def choose_file_interactively(files):
    if not files:
        return None
    while True:
        choice = input("Choose file (number), type 'latest' or 'q' to cancel: ").strip().lower()
        if choice == 'q':
            return None
        elif choice == 'latest':
            image_path = files[-1]
            print(f"Selected latest file: {os.path.basename(image_path)}")
            return image_path
        try:
            index = int(choice) - 1
            if 0 <= index < len(files):
                image_path = files[index]
                print(f"Selected file: {os.path.basename(image_path)}")
                return image_path
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid choice. Enter a number, 'latest' or 'q'.")


def get_last_added_lot_name():
    """Reads the last lot name saved by add_parking_config.py"""
    temp_file = os.path.join("config", "temp_last_lot.json")
    if os.path.exists(temp_file):
        with open(temp_file, 'r') as f:
            data = json.load(f)
            return data.get('lot_name')
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
        
        subprocess.run(["python", "car_park_coordinate_generator.py", 
                "--lot", "default", 
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
        subprocess.run(["python", "add_parking_config.py", 
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
        subprocess.run(["python", "car_park_coordinate_generator.py", "--lot", lot_name], check=True)
        print("✅ Completed car_park_coordinate_generator.py")
    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py ended with an error:", e)
        return

    try:
        print(f"\n== Running app.py --lot {lot_name} (Monitoring) ==")
        print("🎥 Starting monitoring preview. Close window to finish.")
        subprocess.run(["python", "app.py", "--lot", lot_name], check=True)
        print("✅ Monitoring completed.")
    except subprocess.CalledProcessError as e:
        print("❌ app.py ended with an error:", e)
        return
        
    print("\n=== Automatic configuration sequence completed successfully! ===")

if __name__ == "__main__":
    main()
