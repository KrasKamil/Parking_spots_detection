# 🅿️ Parking Spot AI - Parking Space Detection System

A flexible parking space detection system using computer vision to monitor parking lot occupancy in real-time. The system supports multiple parking configurations and processes both video streams (including IP cameras/YouTube) and static images.

## 🚀 Key Features

* **Automatic Setup Workflow:** The `main.py` script provides a guided wizard to calibrate, configure, and annotate a new parking lot from start to finish.
* **Dimension Calibration:** Interactive mode (`-m c`) to measure parking space dimensions (`rect_width`, `rect_height`).
* **Advanced Annotation:** Supports **Rectangular** (`P`), **Irregular** (`I`), **Route Points** (`T`), and **Edit ID** (`E`) modes.
* **A\* Pathfinding Algorithm:** Calculates the optimal, safe route to the nearest free parking space, avoiding occupied spots.
* **Video Support:** Monitors from files, IP cameras, and YouTube videos (requires `yt-dlp` and FFMPEG support).

## 🏁 Example Results

Here is an example of the system in action, identifying empty (green) and occupied (red) spaces, and calculating the A\* route (blue line) to the nearest free spot.

<p align="center">
<img src="AI_parking_detection\results\parking_snapshot_20251104_095327.jpg">

## 🎯 Problem Definition & Solution

### Problem

Setting up a new parking lot surveillance system is often complex. Each camera has a different angle, and parking spaces have different dimensions, requiring manual code adjustments. Standard systems don't offer guidance for new lot configuration.

### Solution

This project provides a **generic, wizard-based solution**.

1.  **Automated Setup (`main.py`):** A master script runs you through all necessary steps, from calibration to monitoring.
2.  **Visual Calibration (`car_park_coordinate_generator.py`):** Instead of guessing pixel dimensions, you visually click two corners of a parking space to calibrate its size.
3.  **Generic Configuration (`config/parking_config.json`):** All settings (dimensions, thresholds, video paths) are stored in a central JSON file, allowing you to manage multiple lots without changing any code.
4.  **Advanced Annotation:** You can map out any parking lot shape (Rectangular/Irregular) and define navigation paths (`Route Points`) for the A\* algorithm.

## 💡 Core Concepts Used

* **Automated Workflow (`main.py`):** Uses the `subprocess` module to chain multiple Python scripts together, passing configuration data between them via temporary files.
* **Generic Configuration (`config_manager.py`):** A manager class that reads and writes to `parking_config.json`, decoupling the logic from specific lot settings.
* **Advanced Image Processing (`parking_classifier.py`):** Uses OpenCV techniques like Gaussian Blur, Adaptive Thresholding, and Dilation to isolate parking space markings and detect cars.
* **A\* Pathfinding (`parking_classifier.py`):** Implements the A\* search algorithm to find the shortest, safest path to an empty spot, using the user-defined `Route Points` as a graph.
* **Advanced Annotation UI (`coordinate_denoter.py`):** A stateful OpenCV GUI that handles multiple modes (P, I, T, E, C) and keyboard/mouse inputs for complex annotation.

## 📁 Project Structure

```
AI_parking_detector/
├── config/
│   └── parking_config.json          # Parking lot configurations and processing parameters.
├── data/
│   ├── parking_lots/                # Position files for different parking lots.
│   └── source/ 
|       ├── img/
|       └── video/
├── results/                         # Output folder for saved snapshots.
├── src/
│   ├── config_manager.py            # Configuration management.
│   ├── coordinate_denoter.py        # Annotation and calibration logic.
│   └── parking_classifier.py        # Classification and A* Pathfinding logic.
├── add_parking_config.py            # Interactively adds a new parking configuration.
├── app.py                           # Main monitoring application.
├── car_park_coordinate_generator.py # GUI tool for marking positions.
├── main.py                          # **Automatic setup workflow.**
└── requirements.txt
```

## 🔧 Installation

### Prerequisites

- Python 3.7+
- OpenCV
- NumPy
- Optional (for YouTube streams): yt-dlp and FFMPEG

### Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## ⚙️ Automatic Setup (Recommended Workflow)

Use the `main.py` script to run the complete setup sequence for a new parking lot without needing to call each tool manually:

```bash
python main.py
```

This script acts as a 'wizard' or manager that automates the entire setup. It works by calling the other command-line tools (`car_park_coordinate_generator.py`, `add_parking_config.py`, and `app.py`) in the correct sequence, using temporary files to pass crucial data (like calibration dimensions) between steps.

### Automatic Configuration Sequence

1. **Reference File Selection:** Interactively choose a reference image.
2. **Calibration (Mode 'c'):** The calibration tool starts automatically. In the window:
   - Press 'c'
   - Click two corners of a typical parking space
   - The dimensions will be saved and used in the next step
   - Close the window
3. **Configuration Creation:** `add_parking_config.py` runs. The W/H dimensions from calibration are automatically loaded and suggested.
4. **Annotation (Marking Positions):** `car_park_coordinate_generator.py` restarts for the new parking lot. Mark all spaces and route points.
5. **Start Monitoring:** `app.py` launches automatically with the new configuration.

## 🎯 Manual Annotation (car_park_coordinate_generator.py)

A GUI tool for precise position marking:

```bash
python car_park_coordinate_generator.py --lot <your_lot_name>
```

### Controls

| Mode / Action | Key | Description |
|--------------|-----|-------------|
| Rectangular | P | Left-click to add a rectangular space |
| Irregular | I | 4 clicks to create a polygon-shaped space |
| Route Points | T | Left-click to add a route point (for A* Pathfinding). Right-click to remove the nearest one |
| Edit ID | E | Left-click a spot to activate a text box to change its ID. Press Enter to confirm |
| CALIBRATION | C | Click two corners to measure W/H dimensions |
| Add/Select | L-Click | Adds a space/point or selects a spot for ID editing |
| Remove/Cancel | R-Click | Removes a parking space or cancels an irregular shape |
| Save | S | Saves the positions to the file |
| Quit | Q/ESC | Exits the tool |

## 🎥 Parking Monitoring (app.py)

Runs the real-time analysis or analyzes a static image:

```bash
python app.py --lot <your_lot_name> --video <your_video_source>
```

### Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| --lot, -l | Name of the parking lot configuration (default: 'default') | --lot mall |
| --video, -v | Video source (file, IP camera, YouTube URL, camera index: 0) | --video 0 or --video https://youtube.com/... |
| --image, -i | Path to a static image | --image data/img.jpg |
| --mode, -m | Mode: video (default) or image | --mode image |
| --output, -o | Path to save the output video file | --output out.mp4 |
| --scale_percent | Scale the output video/image display (e.g., 50 for 50%) | --scale_percent 50 |

### Parameter Overrides

All `processing_params` can be overridden (e.g., `--threshold_block 45`).

Example: `--threshold_c 10`

### A* Pathfinding

In video mode, the system automatically draws the shortest and safest route to the first available parking space using the annotated route points.

### Monitoring Controls (Video)

- **Q:** Quit
- **S:** Save the current frame as an image (in the results directory)
- **P:** Pause/Resume
- **SPACE:** Step forward one frame (only when paused)


## 📝 A Note on Configuration & Data

* `config/parking_config.json`: This file stores the *settings* for each parking lot, such as its name, W/H dimensions, detection threshold, and video source path.
* `data/parking_lots/`: This directory stores the *coordinate data*. When you save positions in the `car_park_coordinate_generator.py` tool, it creates a file (e.g., `mall_parking_positions`) containing the list of all coordinates (for spots and route points) for that specific lot.

---

## 🙏 Acknowledgements

This project was significantly expanded and refactored with features like multi-lot management, A\* pathfinding, and an automated setup wizard.

The initial foundation, including the core OpenCV image processing pipeline (blur, thresholding) and the original OOP structure for classification, was inspired by the `car-parking-finder` project by **Noor Khokhar**. Thank you for sharing your work!

You can find the original repository here:
<https://github.com/noorkhokhar99/car-parking-finder.git>



## ***Happy parking monitoring! 🚗🅿️***
