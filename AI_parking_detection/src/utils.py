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
        
        self.car_park_positions = self._read_positions(car_park_positions_path)
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
    
    def _read_positions(self, car_park_positions_path: str) -> List[Tuple[int, int]]:
        """Read parking positions from pickle file"""
        if not os.path.exists(car_park_positions_path):
            print(f"Positions file not found: {car_park_positions_path}")
            return []
        
        try:
            with open(car_park_positions_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error reading positions file: {e}")
            return []
    
    def classify(self, 
                 image: np.ndarray, 
                 processed_image: np.ndarray,
                 threshold: int = 900) -> Tuple[np.ndarray, dict]:
        """Classify parking spaces and return annotated image with statistics"""
        
        empty_spaces = 0
        occupied_spaces = 0
        space_details = []
        
        for i, (x, y) in enumerate(self.car_park_positions):
            # Define crop boundaries
            col_start, col_stop = x, x + self.rect_width
            row_start, row_stop = y, y + self.rect_height
            
            # Crop parking space
            crop = processed_image[row_start:row_stop, col_start:col_stop]
            
            # Count non-zero pixels
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
                'position': (x, y),
                'status': status,
                'pixel_count': count,
                'is_empty': is_empty
            })
            
            # Draw rectangle
            start_point = (x, y)
            end_point = (x + self.rect_width, y + self.rect_height)
            cv2.rectangle(image, start_point, end_point, color, thickness)
        
        # Draw info panel
        self._draw_info_panel(image, empty_spaces, len(self.car_park_positions))
        
        stats = {
            'empty_spaces': empty_spaces,
            'occupied_spaces': occupied_spaces,
            'total_spaces': len(self.car_park_positions),
            'occupancy_rate': occupied_spaces / len(self.car_park_positions) if self.car_park_positions else 0,
            'space_details': space_details
        }
        
        return image, stats
    
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
    """Generic coordinate annotation tool"""
    
    def __init__(self, 
                 rect_width: int = 107, 
                 rect_height: int = 48, 
                 car_park_positions_path: str = "data/CarParkPos"):
        
        self.rect_width = rect_width
        self.rect_height = rect_height
        self.car_park_positions_path = car_park_positions_path
        self.car_park_positions = []
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(car_park_positions_path), exist_ok=True)
    
    def read_positions(self) -> List[Tuple[int, int]]:
        """Read positions from file"""
        if os.path.exists(self.car_park_positions_path):
            try:
                with open(self.car_park_positions_path, 'rb') as f:
                    self.car_park_positions = pickle.load(f)
            except Exception as e:
                print(f"Error reading positions: {e}")
                self.car_park_positions = []
        
        return self.car_park_positions
    
    def save_positions(self):
        """Save positions to file"""
        try:
            with open(self.car_park_positions_path, 'wb') as f:
                pickle.dump(self.car_park_positions, f)
            print(f"Saved {len(self.car_park_positions)} positions to {self.car_park_positions_path}")
        except Exception as e:
            print(f"Error saving positions: {e}")
    
    def mouseClick(self, events: int, x: int, y: int, flags: int, params: int):
        """Mouse callback function"""
        if events == cv2.EVENT_LBUTTONDOWN:
            self.car_park_positions.append((x, y))
            print(f"Added position: ({x}, {y})")
        
        elif events == cv2.EVENT_RBUTTONDOWN:
            # Remove position if clicked inside existing rectangle
            for index, pos in enumerate(self.car_park_positions):
                x1, y1 = pos
                if (x1 <= x <= x1 + self.rect_width and 
                    y1 <= y <= y1 + self.rect_height):
                    removed_pos = self.car_park_positions.pop(index)
                    print(f"Removed position: {removed_pos}")
                    break
        
        # Auto-save after each change
        self.save_positions()