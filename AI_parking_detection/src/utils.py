import cv2
import pickle
import numpy as np
from typing import List, Tuple, Optional, Union
import os

class ParkClassifier:
    """Generic parking space classifier using digital image processing"""
    
    def __init__(self, 
                 car_park_positions_path: str,
                 rect_width: int = 107,
                 rect_height: int = 48,
                 processing_params: dict = None):
        
        self.car_park_positions, self.route_points = self._read_positions(car_park_positions_path)
        self.rect_height = rect_height
        self.rect_width = rect_width
        self.car_park_positions_path = car_park_positions_path
        
        # Set default processing parameters
        self.processing_params = processing_params or {
            "gaussian_blur_kernel": [3, 3],
            "gaussian_blur_sigma": 1,
            "adaptive_threshold_max_value": 255,
            "adaptive_threshold_block_size": 25,
            "adaptive_threshold_c": 16,
            "median_blur_kernel": 5,
            "dilate_kernel_size": [3, 3],
            "dilate_iterations": 1
        }
    
    def _read_positions(self, car_park_positions_path: str) -> Tuple[List, List]:
        """Read parking positions and route points from pickle file"""
        if not os.path.exists(car_park_positions_path):
            print(f"Positions file not found: {car_park_positions_path}")
            return [], []
        try:
            with open(car_park_positions_path, 'rb') as f:
                data = pickle.load(f)

                if isinstance(data, list):
                    # Stary format (tylko lista pozycji)
                    return data, []
                else:
                    # Nowy format (słownik)
                    return data.get('car_park_positions', []), data.get('route_points', [])

        except Exception as e:
            print(f"Error reading positions file: {e}")
            return [], []
    
    def classify(self, 
                 image: np.ndarray, 
                 processed_image: np.ndarray,
                 threshold: int = 900) -> Tuple[np.ndarray, dict]:
        """Classify parking spaces and return annotated image with statistics"""
        
        empty_spaces = 0
        occupied_spaces = 0
        space_details = []
        
        for i, pos in enumerate(self.car_park_positions):
            # Handle both rectangle (4 points) and polygon formats
            if isinstance(pos, dict):
                # New format with 4 points
                points = pos['points']
                is_irregular = pos.get('irregular', False)
                
                # Get bounding box
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                # Create mask for irregular shapes
                if is_irregular:
                    mask = np.zeros(processed_image.shape, dtype=np.uint8)
                    pts = np.array(points, dtype=np.int32)
                    cv2.fillPoly(mask, [pts], 255)
                    crop = cv2.bitwise_and(processed_image[y_min:y_max, x_min:x_max], 
                                          mask[y_min:y_max, x_min:x_max])
                else:
                    crop = processed_image[y_min:y_max, x_min:x_max]
                
                # Count non-zero pixels
                count = cv2.countNonZero(crop)
                
            else:
                # Old format (backward compatibility)
                x, y = pos
                points = [(x, y), 
                         (x + self.rect_width, y), 
                         (x + self.rect_width, y + self.rect_height), 
                         (x, y + self.rect_height)]
                is_irregular = False
                
                col_start, col_stop = x, x + self.rect_width
                row_start, row_stop = y, y + self.rect_height
                crop = processed_image[row_start:row_stop, col_start:col_stop]
                count = cv2.countNonZero(crop)
            
            # Classify space
            is_empty = count < threshold
            if is_empty:
                empty_spaces += 1
                color = (0, 255, 0)  # Green for empty
                thickness = 5
                status = "Empty"
            else:
                occupied_spaces += 1
                color = (0, 0, 255)  # Red for occupied
                thickness = 2
                status = "Occupied"
            
            # Store space details
            space_details.append({
                'id': i,
                'points': points,
                'status': status,
                'pixel_count': count,
                'is_empty': is_empty,
                'irregular': is_irregular
            })
            
            # Draw polygon
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(image, [pts], True, color, thickness)
            
            # Draw space number
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            cv2.putText(image, str(i), (center_x - 10, center_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw info panel
        self._draw_info_panel(image, empty_spaces, len(self.car_park_positions))
        
        # NOWE: Wizualizacja trasy do pierwszego wolnego miejsca
        first_empty_space = next((s for s in space_details if s['is_empty']), None)
        if first_empty_space and self.route_points:
            self._draw_route_to_space(image, first_empty_space)
            
        stats = {
            'empty_spaces': empty_spaces,
            'occupied_spaces': occupied_spaces,
            'total_spaces': len(self.car_park_positions),
            'occupancy_rate': (occupied_spaces / len(self.car_park_positions) * 100) if self.car_park_positions else 0,
            'space_details': space_details
        }
        
        return image, stats
    
    def _draw_route_to_space(self, image: np.ndarray, target_space: dict): 
        """Draw route from route points to the target parking space"""
        if not self.route_points:
            return
            
        # Środek wolnego miejsca (używamy target_space)
        points = target_space['points'] 
        end_x = sum(p[0] for p in points) // len(points)
        end_y = sum(p[1] for p in points) // len(points)
        end_point = (end_x, end_y)

        color = (255, 255, 0) # Żółty/cyjan

        # Użyj wszystkich punktów trasy dojazdu
        route_path = list(self.route_points)
        route_path.append(end_point)

        for i in range(1, len(route_path)):
            p1 = route_path[i-1]
            p2 = route_path[i]

            # Rysowanie linii
            cv2.line(image, p1, p2, color, 3)

            # Dodanie strzałki na końcu każdego segmentu
            self._draw_arrowhead(image, p1, p2, color) # Rysuj grot strzałki na każdym segmencie (wizualizacja kierunku)
            

        # 2. Podświetlenie numeru wolnego miejsca
        center_x = end_point[0]
        center_y = end_point[1]
        cv2.circle(image, end_point, 15, color, 4)

        cv2.putText(image, "DOJAZD", (center_x - 30, center_y + 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    def _draw_arrowhead(self, img, p1, p2, color):
        """Draw a simple arrowhead on the line segment from p1 to p2"""
        v = np.array(p2) - np.array(p1)
        
        # Zabezpieczenie przed zerową długością wektora
        if np.linalg.norm(v) == 0:
            return
            
        # Oblicz wektor kierunkowy i jednostkowy
        v_norm = v / np.linalg.norm(v)

        # Kąt wektora
        angle = np.arctan2(v[1], v[0])

        # Długość strzałki
        arrow_len = 20

        # Obliczenie punktów bocznych (pod kątem +/- 30 stopni)
        a1 = angle - np.pi/6
        a2 = angle + np.pi/6

        pt1 = (int(p2[0] - arrow_len * np.cos(a1)), int(p2[1] - arrow_len * np.sin(a1)))
        pt2 = (int(p2[0] - arrow_len * np.cos(a2)), int(p2[1] - arrow_len * np.sin(a2)))

        cv2.line(img, p2, pt1, color, 3)
        cv2.line(img, p2, pt2, color, 3)
        
    def _draw_info_panel(self, image: np.ndarray, empty_spaces: int, total_spaces: int):
        """Draw information panel on image"""
        # Background rectangle
        cv2.rectangle(image, (45, 30), (300, 85), (180, 0, 180), -1)
        
        # Text
        ratio_text = f'Free: {empty_spaces}/{total_spaces}'
        occupancy_rate = ((total_spaces - empty_spaces) / total_spaces * 100) if total_spaces > 0 else 0
        rate_text = f'Occupancy: {occupancy_rate:.1f}%'
        
        cv2.putText(image, ratio_text, (50, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(image, rate_text, (50, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    def implement_process(self, image: np.ndarray) -> np.ndarray:
        """Process image using configurable parameters"""
        params = self.processing_params
        
        # Create kernel
        kernel_size = np.ones(tuple(params["dilate_kernel_size"]), np.uint8)
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Gaussian blur
        blur = cv2.GaussianBlur(gray, 
                               tuple(params["gaussian_blur_kernel"]), 
                               params["gaussian_blur_sigma"])
        
        # Adaptive threshold
        thresholded = cv2.adaptiveThreshold(
            blur,
            params["adaptive_threshold_max_value"],
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            params["adaptive_threshold_block_size"],
            params["adaptive_threshold_c"]
        )
        
        # Median blur
        blur = cv2.medianBlur(thresholded, params["median_blur_kernel"])
        
        # Dilate
        dilate = cv2.dilate(blur, kernel_size, iterations=params["dilate_iterations"])
        
        return dilate


class CoordinateDenoter:
    """Generic coordinate annotation tool with rectangular and irregular modes"""
    
    def __init__(self, 
                 rect_width: int = 107, 
                 rect_height: int = 48, 
                 car_park_positions_path: str = "data/CarParkPos"):
        
        self.rect_width = rect_width
        self.rect_height = rect_height
        self.car_park_positions_path = car_park_positions_path
        self.car_park_positions = []
        
        # Mode settings
        self.mode = 'p'  # 'p' for rectangular (default), 'i' for irregular, 't' for route points
        self.irregular_points = []  # Temporary storage for irregular shape points
        self.route_points = [] # Points for visualizing route/arrows
        self.temp_image = None  # For displaying temporary points
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(car_park_positions_path), exist_ok=True)
    
    def set_mode(self, mode: str):
        """Set annotation mode: 'p' for rectangular, 'i' for irregular , 't' for route"""
        if mode in ['p', 'i', 't']:
            self.mode = mode
            self.irregular_points = []  # Reset temporary points when changing mode
            print(f"Mode changed to: {'Rectangular (P)' if mode == 'p' else 'Irregular (I)' if mode == 'i' else 'Route Points (T)'}")
        else:
            print(f"Invalid mode: {mode}. Use 'p' or 'i' or 't'.")
    
    def read_positions(self) -> List:
        """Read positions from file"""
        # ... (zmień zwracany typ na np. dict w myśl przyszłej implementacji)
        if os.path.exists(self.car_park_positions_path):
            try:
                with open(self.car_park_positions_path, 'rb') as f:
                    data = pickle.load(f)

                    if isinstance(data, list):
                        # Old format (lista pozycji)
                        self.car_park_positions = data
                        self.route_points = []
                        self._convert_old_format() # Konwersja tylko car_park_positions
                    else:
                        # Nowy format (słownik)
                        self.car_park_positions = data.get('car_park_positions', [])
                        self.route_points = data.get('route_points', [])
                        self._convert_old_format() # Konwersja tylko car_park_positions

            except Exception as e:
                print(f"Error reading positions: {e}")
                self.car_park_positions = []
                self.route_points = []

        return self.car_park_positions
        
    
    def _convert_old_format(self):
        """Convert old (x,y) format to new dict format with 4 points"""
        converted = []
        for pos in self.car_park_positions:
            if isinstance(pos, tuple):
                # Old format: (x, y)
                x, y = pos
                converted.append({
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                })
            else:
                # Already new format
                converted.append(pos)
        
        if converted != self.car_park_positions:
            self.car_park_positions = converted
            print("Converted positions to new format")
            self.save_positions()
    
    def save_positions(self):
        """Save positions to file"""
        data_to_save = {
            'car_park_positions': self.car_park_positions,
            'route_points': self.route_points
        }
        try:
            with open(self.car_park_positions_path, 'wb') as f:
                pickle.dump(data_to_save, f) # Zapisz słownik
            print(f"Saved {len(self.car_park_positions)} positions and {len(self.route_points)} route points to {self.car_park_positions_path}")
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def mouseClick(self, events: int, x: int, y: int, flags: int, params: int):
        """Mouse callback function with mode support"""
        if events == cv2.EVENT_LBUTTONDOWN:
            if self.mode == 'p':
                # Rectangular mode: single click
                new_position = {
                    'points': [
                        (x, y),
                        (x + self.rect_width, y),
                        (x + self.rect_width, y + self.rect_height),
                        (x, y + self.rect_height)
                    ],
                    'irregular': False
                }
                self.car_park_positions.append(new_position)
                print(f"Added rectangular position at: ({x}, {y})")
                self.save_positions()
                
            elif self.mode == 'i':
                # Irregular mode: collect 4 points
                self.irregular_points.append((x, y))
                print(f"Point {len(self.irregular_points)}/4 added: ({x}, {y})")
                
                if len(self.irregular_points) == 4:
                    # Save the irregular shape
                    new_position = {
                        'points': self.irregular_points.copy(),
                        'irregular': True
                    }
                    self.car_park_positions.append(new_position)
                    print(f"Added irregular position with points: {self.irregular_points}")
                    self.irregular_points = []  # Reset for next shape
                    self.save_positions()
            elif self.mode == 't': # Route points mode
                self.route_points.append((x, y))
                print(f"Added route point at: ({x}, {y})")
                self.save_positions()
                
                
        elif events == cv2.EVENT_RBUTTONDOWN:
            # Remove position if clicked inside existing shape
            for index, pos in enumerate(self.car_park_positions):
                points = pos['points']
                
                # Check if click is inside polygon
                pts = np.array(points, dtype=np.int32)
                if cv2.pointPolygonTest(pts, (x, y), False) >= 0:
                    removed_pos = self.car_park_positions.pop(index)
                    print(f"Removed position: {removed_pos['points']}")
                    self.save_positions()
                    break
            
            # Also cancel current irregular drawing on right-click
            if self.mode == 'i' and self.irregular_points:
                print(f"Cancelled irregular shape (had {len(self.irregular_points)} points)")
                self.irregular_points = []
                
            # Remove nearest route point on right-click in mode 't'    
            if self.mode == 't' and self.route_points:
                # Find nearest route point to remove
                distances = [np.sqrt((px - x)**2 + (py - y)**2) for px, py in self.route_points]
                min_dist_index = np.argmin(distances)

                if distances[min_dist_index] < 50: # Usuń tylko jeśli jest blisko (np. 50px)
                    removed_point = self.route_points.pop(min_dist_index)
                    print(f"Removed route point: {removed_point}. Remaining: {len(self.route_points)}")
                    self.save_positions()
        
    def draw_positions(self, image: np.ndarray) -> np.ndarray:
        """Draw all positions on image"""
        display_image = image.copy()
        
        # Draw existing positions
        for i, pos in enumerate(self.car_park_positions):
            points = pos['points']
            is_irregular = pos.get('irregular', False)
            
            # Choose color based on type
            color = (255, 0, 255) if is_irregular else (0, 0, 255)
            
            # Draw polygon
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(display_image, [pts], True, color, 2)
            
            # Draw space number at center
            center_x = sum(p[0] for p in points) // len(points)
            center_y = sum(p[1] for p in points) // len(points)
            cv2.putText(display_image, str(i), (center_x - 10, center_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Draw temporary irregular points
        if self.mode == 'i' and self.irregular_points:
            for idx, point in enumerate(self.irregular_points):
                cv2.circle(display_image, point, 5, (0, 255, 255), -1)
                cv2.putText(display_image, str(idx + 1), 
                           (point[0] + 10, point[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            # Draw lines connecting points
            if len(self.irregular_points) > 1:
                for i in range(len(self.irregular_points) - 1):
                    cv2.line(display_image, self.irregular_points[i], 
                            self.irregular_points[i + 1], (0, 255, 255), 1)
        # CODE FOR ROUTE POINTS
        if self.route_points:
            # Draw lines between points and point numbers
            for i in range(len(self.route_points)):
                cv2.circle(display_image, self.route_points[i], 8, (255, 255, 0), -1) # Kropka punktu
                cv2.putText(display_image, str(i), 
                            (self.route_points[i][0] + 10, self.route_points[i][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                if i > 0:
                    cv2.line(display_image, self.route_points[i-1], 
                            self.route_points[i], (255, 255, 0), 2) # Linia trasy
        
        return display_image
