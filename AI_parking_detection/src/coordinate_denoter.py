import cv2
import pickle
import numpy as np
from typing import List, Tuple, Dict, Any
import os
import string
import math
import json

CALIBRATION_OUTPUT_FILE = "config/temp_calibration_data.json"

# === CoordinateDenoter Class (Responsible for Annotation and Configuration) ===
class CoordinateDenoter:
    """
    Generic coordinate annotation tool with rectangular and irregular modes.
    Responsibilities: Managing parking positions and route points (CRUD),
    handling user interface (mouse, keyboard, temporary drawing),
    and saving calibration results.
    """
    
    def __init__(self, 
                 rect_width: int = 107, 
                 rect_height: int = 48, 
                 car_park_positions_path: str = "data/CarParkPos"):
        
        self.rect_width = rect_width
        self.rect_height = rect_height
        self.car_park_positions_path = car_park_positions_path
        self.car_park_positions : List[Dict[str, Any]] = []
        
        # Mode settings
        self.mode = 'p'  # 'p': rect, 'i': irregular, 't': route, 'e': edit ID, 'c': calibration
        self.irregular_points = []
        self.route_points = []
        
        # Nowe zmienne dla symulowanego pola tekstowego
        self.is_editing_id = False
        self.edit_target_index = -1
        self.input_buffer = ""
        self.blink_state = True
        
        os.makedirs(os.path.dirname(car_park_positions_path), exist_ok=True)
      
    def _save_calibration_results(self, width: int, height: int):
        """Saves temporary calibration results to JSON file."""
        data = {
            "rect_width": width,
            "rect_height": height
        }
        os.makedirs(os.path.dirname(CALIBRATION_OUTPUT_FILE), exist_ok=True)
        try:
            with open(CALIBRATION_OUTPUT_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✅ Calibration results automatically saved to {CALIBRATION_OUTPUT_FILE}")
        except Exception as e:
            print(f"❌ Error saving calibration results: {e}")
            
    # --- Managing  ---
    def _get_next_id(self) -> int:
        """Generates the next unique numeric ID, considering gaps."""
        if not self.car_park_positions: return 1
            
        existing_int_ids = set()
        for pos in self.car_park_positions:
            spot_id = pos.get('id')
            try:
                if isinstance(spot_id, str) and spot_id.isdigit():
                    existing_int_ids.add(int(spot_id))
                elif isinstance(spot_id, int):
                    existing_int_ids.add(spot_id)
            except:
                pass 
        
        if not existing_int_ids: return 1

        sorted_ids = sorted(list(existing_int_ids))
        
        expected_id = 1
        for current_id in sorted_ids:
            if current_id > expected_id:
                return expected_id
            expected_id = current_id + 1
            
        return expected_id
    
    def set_mode(self, mode: str):
        """Set annotation mode: 'p', 'i', 't', 'e', or 'c'"""
        if mode in ['p', 'i', 't', 'e', 'c']:
            self.mode = mode
            self.irregular_points = []
            
            if mode == 'p': text = 'Rectangular (P)'
            elif mode == 'i': text = 'Irregular (I)'
            elif mode == 't': text = 'Route Points (T)'
            elif mode == 'e': text = 'Edit ID (E)'
            elif mode == 'c': text = 'CALIBRATION (C)'
            
                
            print(f"Mode changed to: {text}")
        else:
            print(f"Invalid mode: {mode}. Use 'p', 'i', 't', 'e' or 'c'.")
    
    def read_positions(self) -> List[Dict[str, Any]]:
        """Read positions from file"""
        if os.path.exists(self.car_park_positions_path):
            try:
                with open(self.car_park_positions_path, 'rb') as f:
                    data = pickle.load(f)

                    if isinstance(data, list):
                        self.car_park_positions = data
                        self.route_points = []
                    else:
                        self.car_park_positions = data.get('car_park_positions', [])
                        self.route_points = data.get('route_points', [])
                    
                    self._convert_old_format()

            except Exception as e:
                print(f"Error reading positions: {e}")
                self.car_park_positions = []
                self.route_points = []

        return self.car_park_positions
        
    def _convert_old_format(self):
        """Convert old formats to new dict format and ensure 'id' exists."""
        # Conversion logic is necessary to ensure consistency after splitting
        converted = []
        next_id = 1
        
        existing_ids = []
        for pos in self.car_park_positions:
            if isinstance(pos, dict) and 'id' in pos:
                try:
                    spot_id = pos['id']
                    if isinstance(spot_id, str) and spot_id.isdigit():
                         existing_ids.append(int(spot_id))
                    elif isinstance(spot_id, int):
                        existing_ids.append(spot_id)
                except: pass
        
        if existing_ids:
            next_id = max(existing_ids) + 1
        
        changed = False
        for pos in self.car_park_positions:
            if isinstance(pos, tuple):
                x, y = pos
                converted.append({
                    'id': str(next_id),
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                })
                next_id += 1
                changed = True
            elif 'id' not in pos:
                pos['id'] = str(next_id) 
                converted.append(pos)
                next_id += 1
                changed = True
            else:
                converted.append(pos)
        
        if changed:
            self.car_park_positions = converted
            print("Converted positions to new format and ensured unique IDs.")
            self.save_positions()
    
    def save_positions(self):
        """Save positions to file"""
        data_to_save = {
            'car_park_positions': self.car_park_positions,
            'route_points': self.route_points
        }
        try:
            with open(self.car_park_positions_path, 'wb') as f:
                pickle.dump(data_to_save, f)
            print(f"Saved {len(self.car_park_positions)} positions and {len(self.route_points)} route points to {self.car_park_positions_path}")
        except Exception as e:
            print(f"Error saving positions: {e}")
            
    # --- Interface Handling (Mouse/Keyboard/Drawing) ---
    def _handle_text_input(self, key_code: int):
        """Handles keyboard input when in ID editing state."""
        char = chr(key_code)
        
        if key_code == 13: # Enter key (confirmation)
            if self.input_buffer:
                new_id_str = self.input_buffer.strip()
                current_spot_index = self.edit_target_index
                
                existing_spot_index = -1
                for i, pos in enumerate(self.car_park_positions):
                    if i != current_spot_index and str(pos.get('id')) == new_id_str:
                        existing_spot_index = i
                        break
                        
                if existing_spot_index != -1:
                    # ID Swap
                    old_id_of_current_spot = str(self.car_park_positions[current_spot_index]['id'])
                    self.car_park_positions[existing_spot_index]['id'] = old_id_of_current_spot
                    self.car_park_positions[current_spot_index]['id'] = new_id_str
                    print(f"SUCCESS: Swapped ID '{new_id_str}' with ID '{old_id_of_current_spot}'.")
                    
                else:
                    # Set new ID
                    self.car_park_positions[current_spot_index]['id'] = new_id_str
                    print(f"SUCCESS: ID updated to '{new_id_str}'.")

                self.save_positions()
            else:
                print("ID change cancelled - input was cleared.")
            
            # End editing
            self.is_editing_id = False
            self.input_buffer = ""
            self.edit_target_index = -1
            self.set_mode('p')
            return True

        elif key_code == 8: # Backspace key
            self.input_buffer = self.input_buffer[:-1]
            return True

        elif char in string.ascii_letters or char in string.digits or char in [' ', '-', '_']:
            if len(self.input_buffer) < 20:
                self.input_buffer += char
            return True
        
        return False
    
    def mouseClick(self, events: int, x: int, y: int, flags: int, params: int):
        """Mouse callback function with mode support"""
        if events == cv2.EVENT_LBUTTONDOWN:
            if self.mode == 'p':
                # Rectangular mode
                new_position = {
                    'id': str(self._get_next_id()),
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                }
                self.car_park_positions.append(new_position)
                print(f"Added rectangular position (ID: {new_position['id']}) at: ({x}, {y})")
                self.save_positions()
                
            elif self.mode == 'i':
                # Irregular mode: collect 4 points
                self.irregular_points.append((x, y))
                print(f"Point {len(self.irregular_points)}/4 added: ({x}, {y})")
                
                if len(self.irregular_points) == 4:
                    new_position = {
                        'id':str(self._get_next_id()),
                        'points': self.irregular_points.copy(),
                        'irregular': True
                    }
                    self.car_park_positions.append(new_position)
                    print(f"Added irregular position with points: {self.irregular_points}")
                    self.irregular_points = []
                    self.save_positions()
            
            elif self.mode == 't': # Route points mode
                self.route_points.append((x, y))
                print(f"Added route point at: ({x}, {y})")
                self.save_positions()
                
            elif self.mode == 'e': 
                if self.is_editing_id: return

                target_spot_index = -1
                for i, pos in enumerate(self.car_park_positions):
                    points = pos['points']
                    pts = np.array(points, dtype=np.int32)
                    if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                        target_spot_index = i
                        break
                
                if target_spot_index != -1:
                    self.edit_target_index = target_spot_index
                    self.input_buffer = str(self.car_park_positions[target_spot_index]['id'])
                    self.is_editing_id = True
                    print(f"Entering edit mode for ID: {self.input_buffer}")
                else:
                    print("No spot found at clicked location.")
            
            elif self.mode == 'c': # <= CALIBRATION MODE
                self.irregular_points.append((x, y))
                print(f"Calibration Point {len(self.irregular_points)} added: ({x}, {y})")

                if len(self.irregular_points) == 2:
                    (x1, y1), (x2, y2) = self.irregular_points

                    width = abs(x2 - x1)
                    height = abs(y2 - y1)

                    print("\n=== CALIBRATION RESULTS ===")
                    print(f"Width (px): {width}")
                    print(f"Height (px): {height}")
                    print("=========================")
                    
                    # SAVE RESULTS TO TEMPORARY FILE
                    self._save_calibration_results(width, height) 
                    
                    self.irregular_points = []
                    #self.set_mode('p') # Return to default mode
                    
        elif events == cv2.EVENT_RBUTTONDOWN:
            # Remove position
            for index, pos in enumerate(self.car_park_positions):
                points = pos['points']
                pts = np.array(points, dtype=np.int32)
                if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                    removed_pos = self.car_park_positions.pop(index)
                    print(f"Removed position (ID: {removed_pos.get('id', 'N/A')})")
                    self.save_positions()
                    break
                
            if self.mode == 'i' and self.irregular_points:
                print(f"Cancelled irregular shape (had {len(self.irregular_points)} points)")
                self.irregular_points = []
                
            if self.mode == 't' and self.route_points:
                distances = [np.sqrt((px - x)**2 + (py - y)**2) for px, py in self.route_points]
                min_dist_index = np.argmin(distances)

                if distances[min_dist_index] < 50:
                    self.route_points.pop(min_dist_index)
                    print(f"Removed nearest route point. Remaining: {len(self.route_points)}")
                    self.save_positions()
        

    def draw_positions(self, image: np.ndarray) -> np.ndarray:
        """Draw all positions on image, including temporary points and text input box if active."""
        display_image = image.copy()
        
        # 1. Drawing existing positions
        for i, pos in enumerate(self.car_park_positions):
            points = pos['points']
            is_irregular = pos.get('irregular', False)
            spot_id = str(pos.get('id', '?'))

            color = (0, 0, 255)
            if is_irregular: color = (255, 0, 255)
            
            if self.is_editing_id and i == self.edit_target_index:
                 color = (0, 255, 0) 

            pts = np.array(points, dtype=np.int32)
            cv2.polylines(display_image, [pts], True, color, 2)
            
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            cv2.putText(display_image, spot_id, (center_x - 10, center_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 2. Drawing simulated text field (Edit ID)
        if self.is_editing_id:
            points = self.car_park_positions[self.edit_target_index]['points']
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            
            box_width, box_height = 160, 30
            box_start = (center_x - box_width // 2, center_y - box_height - 10)
            box_end = (center_x + box_width // 2, center_y - 10)

            bg_color = (255, 255, 255) if self.blink_state else (150, 150, 150)
            border_color = (255, 255, 0)
            
            cv2.rectangle(display_image, box_start, box_end, bg_color, -1) 
            cv2.rectangle(display_image, box_start, box_end, border_color, 2)
            
            text_x, text_y = box_start[0] + 5, box_end[1] - 8
            cv2.putText(display_image, self.input_buffer, 
                        (text_x, text_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # 3. Draw temporary points (Tryb 'i' i 'c')
        if (self.mode == 'i' or self.mode == 'c') and self.irregular_points:
            color = (0, 255, 255)
            if self.mode == 'c' and len(self.irregular_points) == 1:
                color = (0, 255, 0) # First calibration point in green

            for idx, point in enumerate(self.irregular_points):
                cv2.circle(display_image, point, 5, color, -1)
                
                # Drawing connecting line in 'c' mode (calibration)
                if self.mode == 'c' and len(self.irregular_points) == 2:
                    (x1, y1), (x2, y2) = self.irregular_points
                    
                    # Drawing calibration rectangle
                    cv2.rectangle(display_image, (x1, y1), (x2, y2), (255, 255, 0), 2) 

                # Drawing labels/points in mode 'i'
            if self.mode == 'i':
                for idx, point in enumerate(self.irregular_points):
                    cv2.putText(display_image, str(idx + 1), 
                                (point[0] + 10, point[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

                if len(self.irregular_points) > 1:
                    for i in range(len(self.irregular_points) - 1):
                        cv2.line(display_image, self.irregular_points[i], 
                                 self.irregular_points[i + 1], (0, 255, 255), 1)


        # 4. CODE FOR ROUTE POINTS (Tryb 't')
        if self.route_points:
            for i in range(len(self.route_points)):
                cv2.circle(display_image, self.route_points[i], 8, (255, 255, 0), -1) 
                cv2.putText(display_image, str(i), 
                             (self.route_points[i][0] + 10, self.route_points[i][1] - 10),
                             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                if i > 0:
                    cv2.line(display_image, self.route_points[i-1], 
                             self.route_points[i], (255, 255, 0), 2)

        return display_image