import json
import os
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_path: str = "config/parking_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file not found: {self.config_path}")
            return self._create_default_config()
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        default_config = {
            "parking_lots": {
                "default": {
                    "name": "Default Parking Lot",
                    "rect_width": 107,
                    "rect_height": 48,
                    "threshold": 900,
                    "positions_file": "data/parking_lots/default_positions",
                    "source_image": "data/source/example_image.png",
                    "video_source": "data/source/carPark.mp4"
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
        
        # Save default config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def get_parking_lot_config(self, lot_name: str = "default") -> Dict[str, Any]:
        """Get configuration for specific parking lot"""
        return self.config["parking_lots"].get(lot_name, 
                                               self.config["parking_lots"]["default"])
    
    def get_processing_params(self) -> Dict[str, Any]:
        """Get image processing parameters"""
        return self.config["processing_params"]
    
    def list_parking_lots(self) -> list:
        """List available parking lot configurations"""
        return list(self.config["parking_lots"].keys())