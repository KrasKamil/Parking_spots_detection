import cv2
import argparse
from src.utils import CoordinateDenoter
from src.config_manager import ConfigManager

def create_coordinate_generator(parking_lot_name: str = "default"):
    """Create coordinate generator for specific parking lot"""
    
    config_manager = ConfigManager()
    lot_config = config_manager.get_parking_lot_config(parking_lot_name)
    
    return CoordinateDenoter(
        rect_width=lot_config["rect_width"],
        rect_height=lot_config["rect_height"],
        car_park_positions_path=lot_config["positions_file"]
    ), lot_config

def demonstration(parking_lot_name: str = "default", image_path: str = None):
    """Interactive coordinate annotation tool"""
    
    coordinate_generator, lot_config = create_coordinate_generator(parking_lot_name)
    
    # Use provided image path or config default
    if image_path is None:
        image_path = lot_config["source_image"]
    
    # Read existing positions
    coordinate_generator.read_positions()
    
    print(f"Coordinate Generator for: {lot_config['name']}")
    print("Controls:")
    print("- Left click: Add parking space")
    print("- Right click: Remove parking space")
    print("- 'r': Reset all positions")
    print("- 's': Save positions")
    print("- 'q': Quit")
    
    while True:
        # Load and display image
        try:
            image = cv2.imread(image_path)
            if image is None:
                print(f"Could not load image: {image_path}")
                break
        except Exception as e:
            print(f"Error loading image: {e}")
            break
        
        # Draw existing rectangles
        for pos in coordinate_generator.car_park_positions:
            start = pos
            end = (pos[0] + coordinate_generator.rect_width, 
                   pos[1] + coordinate_generator.rect_height)
            cv2.rectangle(image, start, end, (0, 0, 255), 2)
        
        # Add position counter
        cv2.rectangle(image, (10, 10), (250, 40), (0, 0, 0), -1)
        cv2.putText(image, f"Positions: {len(coordinate_generator.car_park_positions)}", 
                   (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow("Parking Space Coordinator", image)
        cv2.setMouseCallback("Parking Space Coordinator", coordinate_generator.mouseClick)
        
        key = cv2.waitKey(1) & 0xFF  
        if key == ord("q"):
            break
        elif key == 27:  # ESC
            break
        elif key == ord("r"):
            coordinate_generator.car_park_positions = []
            coordinate_generator.save_positions()
            print("Reset all positions")
        elif key == ord("s"):
            coordinate_generator.save_positions()
            print("Saved positions")
            break
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parking Space Coordinate Generator')
    parser.add_argument('--lot', '-l', default='default', 
                       help='Parking lot configuration name')
    parser.add_argument('--image', '-i', default=None,
                       help='Path to image file')
    
    args = parser.parse_args()
    
    # List available configurations
    config_manager = ConfigManager()
    available_lots = config_manager.list_parking_lots()
    print(f"Available parking lot configurations: {available_lots}")
    
    demonstration(args.lot, args.image)