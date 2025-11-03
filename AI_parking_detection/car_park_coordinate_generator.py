import cv2
import argparse
from src.coordinate_denoter import CoordinateDenoter
from src.config_manager import ConfigManager
import time 

def create_coordinate_generator(parking_lot_name: str = "default"):
    """Create coordinate generator for specific parking lot"""
        
    config_manager = ConfigManager()
    lot_config = config_manager.get_parking_lot_config(parking_lot_name)
    
    return CoordinateDenoter(
        rect_width=lot_config["rect_width"],
        rect_height=lot_config["rect_height"],
        car_park_positions_path=lot_config["positions_file"]
    ), lot_config

LAST_BLINK_CHANGE = time.time()
BLINK_INTERVAL_SECONDS = 0.5 # Mruganie co 0.5 sekundy


def demonstration(parking_lot_name: str = "default", image_path: str = None, initial_mode: str = None):
    """Interactive coordinate annotation tool"""
    
    coordinate_generator, lot_config = create_coordinate_generator(parking_lot_name)
    if initial_mode:
        coordinate_generator.set_mode(initial_mode)
        print(f"Initial mode set from CLI: {initial_mode.upper()}")
    
    # Use provided image path or config default
    if image_path is None:
        image_path = lot_config["source_image"]
    
    # Read existing positions
    coordinate_generator.read_positions()
    
    global LAST_BLINK_CHANGE # Użyj globalnej zmiennej czasowej, aby zarządzać stanem
    
    print(f"Coordinate Generator for: {lot_config['name']}")
    print("Controls:")
    print("- 'p': Switch to Rectangular mode (single click) [DEFAULT]")
    print("- 'i': Switch to Irregular mode (4 clicks)")
    print("- 't': Switch to **Route Points (T)** mode (single click to add, right click to remove nearest)") # 
    print("- 'e': **Enter Edit ID Mode (E)** (then Left click inside a spot)") # <-- NOWA INSTRUKCJA
    print("- Left click: Add parking space (mode p/i) / Add route point (mode t) / Select spot to edit (mode e)") 
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
        
        # --- NOWA LOGIKA OBSŁUGI MRUGANIA (OPARTA NA CZASIE) ---
        current_time = time.time()
        if current_time - LAST_BLINK_CHANGE >= BLINK_INTERVAL_SECONDS and coordinate_generator.is_editing_id:
            coordinate_generator.blink_state = not coordinate_generator.blink_state
            LAST_BLINK_CHANGE = current_time
        # --- KONIEC NOWEJ LOGIKI ---
            
        # Draw all positions
        display_image = coordinate_generator.draw_positions(image)
        
        # Add position counter and mode indicator
        mode_text = ""
        if coordinate_generator.mode == 'p':
            mode_text = "Rectangular (P)"
        elif coordinate_generator.mode == 'i':
            mode_text = f"Irregular (I) - Point {len(coordinate_generator.irregular_points)}/4"
        elif coordinate_generator.mode == 't':
            mode_text = f"Route Points (T) - Total: {len(coordinate_generator.route_points)}"
        elif coordinate_generator.mode == 'e':
            mode_text = "Edit ID (E) - Click spot!" # Tryb edycji
        elif coordinate_generator.mode == 'c': # <= NOWY TRYB C
            mode_text = f"CALIBRATION (C) - Point {len(coordinate_generator.irregular_points)}/2"
            
        # Zmiana komunikatu, jeśli faktycznie wprowadzany jest tekst
        if coordinate_generator.is_editing_id:
             mode_text = f"EDITING ID: '{coordinate_generator.input_buffer}'"


        cv2.rectangle(display_image, (10, 10), (450, 70), (0, 0, 0), -1) 
        cv2.putText(display_image, f"Positions: {len(coordinate_generator.car_park_positions)}", 
                    (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(display_image, mode_text, 
                    (15, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        cv2.imshow("Parking Space Coordinator", display_image)
        cv2.setMouseCallback("Parking Space Coordinator", coordinate_generator.mouseClick)
        
        # cv2.waitKey(1) musi być, aby pętla działała i reagowała na zdarzenia myszy
        key = cv2.waitKey(1) & 0xFF
        
        # --- OBSŁUGA KLAWISZY W ZALEŻNOŚCI OD TRYBU ---
        
        if coordinate_generator.is_editing_id:
             # Jeśli edytujemy, klawisze obsługuje funkcja _handle_text_input
             if coordinate_generator._handle_text_input(key):
                 # Zresetuj czas mrugania, aby była ciągłość po wpisaniu znaku
                 LAST_BLINK_CHANGE = time.time() 
             
        # Jeśli nie edytujemy, obsługujemy klawisze zmieniające tryb
        else:
             if key == ord("q") or key == 27:
                 break
             elif key == ord("p"):
                 coordinate_generator.set_mode('p')
             elif key == ord("i"):
                 coordinate_generator.set_mode('i')
             elif key == ord("t"):
                 coordinate_generator.set_mode('t')
             elif key == ord("e"):
                 coordinate_generator.set_mode('e')
                 # Reset stanu mrugania przy wejściu w tryb edycji
                 coordinate_generator.blink_state = True
                 LAST_BLINK_CHANGE = time.time()
                 print("--- EDIT ID MODE ACTIVATED --- Click inside the spot you want to rename.")
             elif key == ord("c"): # <= NOWA OBSŁUGA KLAWISZA C
                 coordinate_generator.set_mode('c')
                 print("--- CALIBRATION MODE ACTIVATED --- Click two corner points of a typical parking space.")
             elif key == ord("r"):
                 coordinate_generator.car_park_positions = []
                 coordinate_generator.irregular_points = []
                 coordinate_generator.route_points = []
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
    
    # DODANA OBSŁUGA ARGUMENTU TRYBU
    parser.add_argument('--mode', '-m', default=None, 
                       help='Initial mode for the tool (e.g., "c" for calibration)') 
    
    args = parser.parse_args()
    
    # List available configurations
    config_manager = ConfigManager()
    available_lots = config_manager.list_parking_lots()
    display_lots = [lot for lot in available_lots if lot != 'default']
    print(f"Available parking lot configurations: {display_lots}")
    
    # Wywołanie z przekazaniem argumentu 'mode'
    demonstration(args.lot, args.image, initial_mode=args.mode)