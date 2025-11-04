import json
import os
import argparse

CONFIG_FILE = "config/parking_config.json"
CALIBRATION_OUTPUT_FILE = "config/temp_calibration_data.json" 
TEMP_LOT_FILE = "config/temp_last_lot.json"

def load_or_create_config():
    """Loads existing configuration file or creates a new one with default structure."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
            "parking_lots": {
                "default": {
                    "name": "Default Parking Lot",
                    "rect_width": 107,
                    "rect_height": 48,
                    "threshold": 900,
                    "positions_file": "data/parking_lots/default_positions",
                    "source_image": "data/source/example_image.png",
                    "video_source": "data/source/carPark.mp4"
                },
                "empty_calibration": { 
                    "name": "Calibration Temporary",
                    "rect_width": 1, 
                    "rect_height": 1,
                    "threshold": 1,
                    "positions_file": "config/temp_calibration_positions",
                    "source_image": "data/source/example_image.png", 
                    "video_source": ""
                }
            },
            "processing_params": {
                "gaussian_blur_kernel": [3, 3],
                "gaussian_blur_sigma": 1,
                "adaptive_threshold_max_value": 255,
                "adaptive_threshold_block_size": 25,
                "adaptive_threshold_c": 16,
                "median_blur_kernel": 5,
                "dilate_kernel_size": [3, 3],
                "dilate_iterations": 1
            }
        }


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
def save_last_lot_name(lot_name: str):
    """Saves the name of the last successfully created lot to a temporary file."""
    try:
        os.makedirs(os.path.dirname(TEMP_LOT_FILE), exist_ok=True)
        with open(TEMP_LOT_FILE, 'w') as f:
            json.dump({"lot_name": lot_name}, f)
        print(f"✅ Parking lot name '{lot_name}' saved temporarily.")
    except Exception as e:
        print(f"❌ Error saving parking lot name: {e}")


def create_parking_lot(config, name, rect_width, rect_height, threshold, image_path, video_path):
    """Adds a new parking lot configuration to config.json"""
    positions_file = f"data/parking_lots/{name}_positions"
    
    new_lot = {
        "name": name.replace('_', ' ').title(),
        "rect_width": rect_width,
        "rect_height": rect_height,
        "threshold": threshold,
        "positions_file": positions_file,
        "source_image": image_path or f"data/source/img/{name}.png",
        "video_source": video_path or f"data/source/video/{name}.mp4"
    }
    
    config["parking_lots"][name] = new_lot
    os.makedirs("data/parking_lots", exist_ok=True)
    save_config(config)
    save_last_lot_name(name)
    
    print(f"\n✅ Added configuration '{name}'!")
    print(f"📁 Positions file: {positions_file}")
    print(f"🖼️  Image: {new_lot['source_image']}")
    print(f"🎥  Video: {new_lot['video_source']}")
    print(f"\n📋 Next steps:")
    print(f"1. Mark parking spaces:")
    print(f"   python car_park_coordinate_generator.py --lot {name}")
    print(f"2. Start monitoring:")
    print(f"   python app.py --lot {name}")

def read_and_clean_calibration_data():
    """Reads temporary calibration data and removes the file."""
    if os.path.exists(CALIBRATION_OUTPUT_FILE):
        try:
            with open(CALIBRATION_OUTPUT_FILE, 'r') as f:
                data = json.load(f)
            os.remove(CALIBRATION_OUTPUT_FILE)  # Remove file to avoid using old data
            print(f"✅ Successfully loaded calibration dimensions: W={data.get('rect_width')}, H={data.get('rect_height')}")
            return data.get('rect_width'), data.get('rect_height')
        except Exception as e:
            print(f"❌ Error reading/removing calibration file: {e}")
            return None, None
    return None, None


def interactive_mode():
    """Runs interactive mode (with console prompts)."""
    
    # === 1.Parsing arguments from main.py ===
    parser = argparse.ArgumentParser(description='Interactive Parking Configuration Adder')
    parser.add_argument('--default_name', type=str, default='',
                        help='Default lot name derived from the selected image file.')
    parser.add_argument('--image_path', type=str, default='',
                        help='Path to the selected image file, used as default.')
    args = parser.parse_args()
    
    # Use and clean passed arguments
    initial_lot_name = args.default_name.lower().replace('.', '_').replace(' ', '_')
    initial_image_path = args.image_path
    # ==========================================
    
    config = load_or_create_config()
    print("Available parking lot configurations:")
    for n in config["parking_lots"].keys():
        # Filter 'default' from displayed list
        if n != 'default': 
            print(f"  - {n}")

    print("\n=== Adding New Parking Lot Configuration ===")
    
    # === AUTOMATIC CALIBRATION DATA RETRIEVAL ===
    default_width = 107
    default_height = 48
    
    calibrated_width, calibrated_height = read_and_clean_calibration_data()
    
    if calibrated_width is not None and calibrated_height is not None:
        default_width = calibrated_width
        default_height = calibrated_height
    
    print(f"--- Dimensions to enter (default: {default_width}x{default_height}px) ---")
    # =========================================
    
    # === 2. USE DEFAULT NAME (lot_name) ===
    # Use default name passed from main.py if it exists
    lot_name_prompt = f"Enter the new parking lot name (default '{initial_lot_name}'): " if initial_lot_name else "Enter the new parking lot name (e.g. 'mall_parking'): "
    
    lot_name = input(lot_name_prompt).strip()
    if not lot_name:
        lot_name = initial_lot_name # Use default name if user pressed Enter

    if not lot_name: # If still empty, ask again
        print("Parking lot name cannot be empty.")
        return 

    if lot_name in config["parking_lots"]:
        overwrite = input(f"Configuration '{lot_name}' already exists. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Cancelled.")
            return

    # Use lot_name as default display name
    display_name = input(f"Enter display name (default '{lot_name.replace('_', ' ').title()}'): ").strip()
    if not display_name:
        display_name = lot_name.replace('_', ' ').title()

    try:
        rect_width = int(input(f"Parking space rectangle width (default {default_width}): ") or str(default_width))
        rect_height = int(input(f"Parking space rectangle height (default {default_height}): ") or str(default_height))
        threshold = int(input("Classification threshold (default 900): ") or "900")
    except ValueError:
        print("Invalid numeric values. Using defaults.")
        rect_width, rect_height, threshold = default_width, default_height, 900
        
    # === 3. Use default image path ===

    image_path_prompt = f"Path to reference image (default '{initial_image_path}'): " if initial_image_path else "Path to reference image: "
    
    input_image_path = input(image_path_prompt).strip()
    if not input_image_path:
        input_image_path = initial_image_path
        
    video_path = input("Path to video file or IP camera URL (e.g. rtsp://user:pass@ip:port/stream): ").strip()

    # Call with valid and enriched data
    create_parking_lot(config, lot_name, rect_width, rect_height, threshold, input_image_path, video_path)


if __name__ == "__main__":
    interactive_mode()
