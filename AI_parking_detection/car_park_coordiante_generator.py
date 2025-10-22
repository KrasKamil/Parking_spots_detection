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
    
    coordinate_generator.read_positions()
    
    print(f"Coordinate Generator for: {lot_config['name']}")
    print("Controls:")
    print("- 'p': Switch to Rectangular mode (single click) [DEFAULT]")
    print("- 'i': Switch to Irregular mode (4 clicks)")
    print("- 't': Switch to **Route Points (T)** mode (single click to add, right click to remove nearest)") # 
    print("- Left click: Add parking space (mode p/i) / Add route point (mode t)") 
    print("- Right click: Remove parking space / Cancel irregular shape / Remove nearest route point") 
    print("- 'r': **Reset ALL** positions (Parking Spots and Route Points)") 
    print("- 's': Save positions")
    print("- 'q' or ESC: Quit")
    print(f"\nCurrent mode: Rectangular (P)")
    
    while True:
        # Load image
        try:
            image = cv2.imread(image_path)
            if image is None:
                print(f"Could not load image: {image_path}")
                break
        except Exception as e:
            print(f"Error loading image: {e}")
            break
        
        # Draw all positions
        display_image = coordinate_generator.draw_positions(image)
        
        # Add position counter and mode indicator
        mode_text = ""
        if coordinate_generator.mode == 'p':
            mode_text = "Rectangular (P)"
        elif coordinate_generator.mode == 'i':
            mode_text = f"Irregular (I) - Point {len(coordinate_generator.irregular_points)}/4"
        elif coordinate_generator.mode == 't': # <-- NOWE: Wyświetlanie trybu trasy
            mode_text = f"Route Points (T) - Total: {len(coordinate_generator.route_points)}"

        cv2.rectangle(display_image, (10, 10), (450, 70), (0, 0, 0), -1) # Powiększ pole info
        cv2.putText(display_image, f"Positions: {len(coordinate_generator.car_park_positions)}", 
                (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(display_image, mode_text, 
                (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        cv2.imshow("Parking Space Coordinator", display_image)
        cv2.setMouseCallback("Parking Space Coordinator", coordinate_generator.mouseClick)
        
        key = cv2.waitKey(1) & 0xFF  
        if key == ord("q") or key == 27:
            break
        elif key == ord("p"):
            coordinate_generator.set_mode('p')
        elif key == ord("i"):
            coordinate_generator.set_mode('i')
        elif key == ord("t"): # <-- NOWE: Klawisz dla trybu trasy
            coordinate_generator.set_mode('t')
        elif key == ord("r"): # <-- reset
            coordinate_generator.car_park_positions = []
            coordinate_generator.irregular_points = []
            coordinate_generator.route_points = [] # <-- Resetuj również punkty trasy
            coordinate_generator.save_positions()
            print("Reset all positions")
        elif key == ord("s"):
            coordinate_generator.save_positions()
            print("Saved positions")
    
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
