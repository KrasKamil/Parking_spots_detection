import json
import os
import argparse

def create_new_parking_lot(name: str, 
                          rect_width: int = 107, 
                          rect_height: int = 48,
                          threshold: int = 900,
                          image_path: str = None,
                          video_path: str = None):
    """Create a new parking lot configuration"""
    
    config_path = "config/parking_config.json"
    
    # Load existing config
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = {"parking_lots": {}, "processing_params": {}}
    
    # Create new parking lot config
    positions_file = f"data/{name}_CarParkPos"
    
    new_lot = {
        "name": name.replace('_', ' ').title(),
        "rect_width": rect_width,
        "rect_height": rect_height,
        "threshold": threshold,
        "positions_file": positions_file,
        "source_image": image_path or f"data/source/{name}_image.png",
        "video_source": video_path or f"data/source/{name}_video.mp4"
    }
    
    # Add to config
    config["parking_lots"][name] = new_lot
    
    # Save config
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created parking lot configuration: {name}")
    print(f"Position file will be: {positions_file}")
    print(f"Expected image: {new_lot['source_image']}")
    print(f"Expected video: {new_lot['video_source']}")
    print("\nNext steps:")
    print(f"1. Place your image/video files in the expected locations")
    print(f"2. Run: python car_park_coordinate_generator.py --lot {name}")
    print(f"3. Run: python app.py --lot {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Setup new parking lot configuration')
    parser.add_argument('name', help='Parking lot name')
    parser.add_argument('--width', type=int, default=107, help='Rectangle width')
    parser.add_argument('--height', type=int, default=48, help='Rectangle height')
    parser.add_argument('--threshold', type=int, default=900, help='Classification threshold')
    parser.add_argument('--image', help='Path to source image')
    parser.add_argument('--video', help='Path to source video')
    
    args = parser.parse_args()
    
    create_new_parking_lot(
        name=args.name,
        rect_width=args.width,
        rect_height=args.height,
        threshold=args.threshold,
        image_path=args.image,
        video_path=args.video
    )