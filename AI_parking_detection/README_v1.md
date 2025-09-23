# Parking Spot AI - Generic Parking Space Detection System

A flexible, AI-powered parking space detection system that uses computer vision to monitor parking lot occupancy in real-time. The system supports multiple parking lots with different configurations and can process both video streams and static images.

---

## 🚀 Features

- **Generic Configuration System:** Support for multiple parking lots with different parameters
- **Real-time Video Processing:** Monitor parking spaces from video files or live cameras
- **Static Image Analysis:** Analyze parking occupancy from single images
- **Interactive Coordinate Tool:** Easy-to-use GUI for marking parking spaces
- **Configurable Processing:** Adjustable image processing parameters for different environments
- **Statistics & Reporting:** Detailed occupancy statistics and monitoring data
- **Export Capabilities:** Save annotated videos and snapshot images

---

## 📁 Project Structure

```
parking-spot-ai/
├── config/
│   └── parking_config.json          # Configuration file for different parking lots
├── data/
│   ├── CarParkPos                   # Default parking positions (text file)
│   └── source/
│       ├── example_image.png        # Sample reference image
│       └── carPark.mp4              # Sample video file
├── src/
│   ├── utils.py                     # Core classification and coordinate classes
│   └── config_manager.py            # Configuration management
├── app.py                           # Main monitoring application
├── car_park_coordinate_generator.py # Interactive coordinate annotation tool
├── setup_parking_lot.py             # Setup script for new parking lots
└── README.md
```

---

## 🔧 Installation

### Prerequisites

- Python 3.7+
- OpenCV
- NumPy

### Install Dependencies

```bash
pip install opencv-python numpy
```

### Clone Repository

```bash
git clone <your-repository-url>
cd parking-spot-ai
```

---

## ⚙️ Initial Setup

### 1. Prepare Your Data

Place your parking lot media files in the `data/source/` directory:

- Reference images (for coordinate annotation): `data/source/`
- Video files: `data/source/`

### 2. Create Configuration (Optional)

The system comes with a default configuration. To create a new parking lot setup:

```bash
python setup_parking_lot.py my_parking_lot --width 120 --height 60 --threshold 1000
```

**Parameters:**

- `name`: Unique identifier for your parking lot
- `--width`: Width of parking space rectangles (default: 107)
- `--height`: Height of parking space rectangles (default: 48)
- `--threshold`: Pixel threshold for empty/occupied classification (default: 900)
- `--image`: Path to reference image
- `--video`: Path to video file

---

## 🎯 Usage

### Step 1: Annotate Parking Spaces

First, you need to mark the parking spaces on your reference image:

```bash
# For default configuration
python car_park_coordinate_generator.py

# For specific parking lot
python car_park_coordinate_generator.py --lot my_parking_lot --image data/source/my_image.png
```

**Controls:**

- **Left Click:** Add parking space
- **Right Click:** Remove parking space
- **R:** Reset all positions
- **S:** Save positions
- **Q:** Quit

---

### Step 2: Monitor Parking Spaces

#### Video Monitoring (Default Mode)

```bash
# Use default configuration and video
python app.py

# Specify parking lot and video source
python app.py --lot my_parking_lot --video data/source/my_video.mp4

# Monitor from webcam
python app.py --lot default --video 0

# Save output video
python app.py --video input.mp4 --output annotated_output.mp4
```

#### Static Image Analysis

```bash
# Analyze single image
python app.py --mode image --image data/source/parking_image.jpg

# Use specific lot configuration
python app.py --lot my_parking_lot --mode image
```

**Monitoring Controls:**

- **Q:** Quit
- **S:** Save current frame as image
- **P:** Pause/Resume video
- **SPACE:** Step one frame (when paused)

---

## 🔧 Configuration

### Default Configuration

The system automatically creates a default configuration on first run. You can modify `config/parking_config.json`:

```json
{
  "parking_lots": {
    "default": {
      "name": "Default Parking Lot",
      "rect_width": 107,
      "rect_height": 48,
      "threshold": 900,
      "positions_file": "data/CarParkPos",
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
```

### Adding New Parking Lots

```bash
# Method 1: Using setup script
python setup_parking_lot.py shopping_mall --width 130 --height 70 --threshold 1200

# Method 2: Manual configuration
# Edit config/parking_config.json and add new parking lot entry
```

---

## 📋 Command Line Options

### car_park_coordinate_generator.py

```bash
python car_park_coordinate_generator.py [OPTIONS]
```

**Options:**

- `--lot`, `-l` TEXT     Parking lot configuration name (default: "default")
- `--image`, `-i` TEXT   Path to image file (overrides config)
- `--help`               Show help message

### app.py

```bash
python app.py [OPTIONS]
```

**Options:**

- `--lot`, `-l` TEXT        Parking lot configuration name (default: "default")
- `--video`, `-v` TEXT      Video source (file path or camera index)
- `--image`, `-i` TEXT      Static image path
- `--output`, `-o` TEXT     Output video path
- `--mode`, `-m` TEXT       Monitoring mode: "video" or "image" (default: "video")
- `--help`                  Show help message

### setup_parking_lot.py

```bash
python setup_parking_lot.py NAME [OPTIONS]
```

**Arguments:**

- `NAME`                  Parking lot name

**Options:**

- `--width` INT           Rectangle width (default: 107)
- `--height` INT          Rectangle height (default: 48)
- `--threshold` INT       Classification threshold (default: 900)
- `--image` TEXT          Path to source image
- `--video` TEXT          Path to source video
- `--help`                Show help message

---

## 🎯 Complete Workflow Example

Setting up a new parking lot called "mall":

```bash
# 1. Create configuration
python setup_parking_lot.py mall --width 120 --height 60 --threshold 1100 --image data/source/mall.jpg --video data/source/mall_video.mp4

# 2. Annotate parking spaces
python car_park_coordinate_generator.py --lot mall

# 3. Monitor parking lot
python app.py --lot mall --mode video

# 4. Analyze static image
python app.py --lot mall --mode image --image data/source/mall_test.jpg

# 5. Monitor live camera and save output
python app.py --lot mall --video 0 --output live_mall_monitoring.mp4
```

---

## 🔍 Understanding the Output

### Console Output

```
Available parking lot configurations: ['default', 'mall']
Initialized monitor for: Mall Parking Lot
Total parking spaces: 45
Frame 30: 12/45 spaces free (73.3% occupied)
Frame 60: 15/45 spaces free (66.7% occupied)
```

### Visual Output

- **Green rectangles:** Empty parking spaces
- **Red rectangles:** Occupied parking spaces
- **Info panel:** Shows free spaces count and occupancy percentage
- **Frame counter:** Current frame number (in video mode)

---

## 🛠️ Troubleshooting

### Common Issues

1. **"Config file not found" error:**
    ```bash
    # The system will create a default config automatically
    # Or manually create the config directory
    mkdir config
    ```

2. **"Could not load image/video" error:**
    ```bash
    # Check file paths and ensure files exist
    ls -la data/source/
    ```

3. **"No positions file found":**
    ```bash
    # Run coordinate generator first
    python car_park_coordinate_generator.py --lot your_lot_name
    ```

4. **Poor detection accuracy:**
    ```bash
    # Adjust threshold in configuration
    # Higher threshold = more spaces marked as empty
    # Lower threshold = more spaces marked as occupied
    ```

### Parameter Tuning

- **Rectangle Size:** Adjust `rect_width` and `rect_height` based on your parking space dimensions.
- **Threshold:** Fine-tune based on lighting conditions and camera angle:
    - Bright outdoor lots: Higher threshold (1000-1500)
    - Indoor/darker lots: Lower threshold (500-900)
    - Overhead cameras: Medium threshold (800-1200)
- **Processing Parameters:** Modify in `config/parking_config.json`:
    - Increase blur kernels for noisy images
    - Adjust adaptive threshold parameters for different lighting

---

## 📊 Output Statistics

The system provides detailed statistics:

- **Total spaces:** Number of configured parking spaces
- **Empty spaces:** Currently available spaces
- **Occupied spaces:** Currently occupied spaces
- **Occupancy rate:** Percentage of occupied spaces
- **Space details:** Individual space status and pixel counts

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙋‍♂️ Support

If you encounter any issues or have questions:

- Check the troubleshooting section above
- Ensure all file paths are correct
- Verify your Python and OpenCV installations
- Create an issue in the repository with detailed error messages

---

## 🎉 Quick Start Checklist

- [ ] Install dependencies (`pip install opencv-python numpy`)
- [ ] Place your image/video files in `data/source/`
- [ ] Run coordinate generator: `python car_park_coordinate_generator.py`
- [ ] Mark parking spaces with left clicks
- [ ] Save positions with 'S' key
- [ ] Run monitoring: `python app.py`
- [ ] Enjoy real-time parking monitoring!

---

Happy parking monitoring! 🚗🅿️