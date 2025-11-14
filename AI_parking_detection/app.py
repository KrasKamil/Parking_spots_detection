import cv2
import argparse
import time
from src.parking_classifier import ParkClassifier
from src.coordinate_denoter import CoordinateDenoter
from src.config_manager import ConfigManager
import os
import numpy as np
import subprocess
import math
# Zakładamy, że te elementy zostały przeniesione do utils.py, aby uniknąć błędu cyklicznego importu.
from src.utils import list_files_three_columns, IMG_DIR, get_direct_youtube_url


# Funkcja get_direct_youtube_url została przeniesiona do src/utils.py, 
# ale ze względu na strukturę pliku musimy ją usunąć stąd, 
# aby użyć tej zaimportowanej z utils. Jeśli była tu zdefiniowana, 
# spowodowałoby to błąd redefinicji (lub cyklicznego importu, jeśli była importowana).
# Ponieważ w przesłanym kodzie funkcja jest nadal zdefiniowana:

# Definicja tej funkcji musi zostać USUNIĘTA Z TEGO PLIKU, 
# aby nie kolidowała z importem z src.utils.

# Poniżej zostawiam ją w komentarzu, aby pokazać, co należy usunąć, jeśli była
# pozostawiona po naszej próbie debugowania:

# def get_direct_youtube_url(youtube_url: str) -> str:
#         """Uses yt-dlp to extract the direct stream URL for a YouTube video."""
#         try:
#             ...
#         except Exception as e:
#             ...
#         return youtube_url 

class ParkingMonitor:
    """Generic parking monitoring application"""
    
    def __init__(self, parking_lot_name: str = "default"):
        self.config_manager = ConfigManager()
        self.lot_config = self.config_manager.get_parking_lot_config(parking_lot_name)
        self.processing_params = self.config_manager.get_processing_params()
        
        # Initialize classifier
        self.classifier = ParkClassifier(
            car_park_positions_path=self.lot_config["positions_file"],
            rect_width=self.lot_config["rect_width"],
            rect_height=self.lot_config["rect_height"],
            processing_params=self.processing_params
        )
        
        print(f"Initialized monitor for: {self.lot_config['name']}")
        print(f"Total parking spaces: {len(self.classifier.car_park_positions)}")
    

    def apply_overrides(self, args):
        """Override processing parameters from CLI"""
        if args.blur_kernel:
            self.processing_params["gaussian_blur_kernel"] = args.blur_kernel
        if args.blur_sigma:
            self.processing_params["gaussian_blur_sigma"] = args.blur_sigma
        if args.threshold_block:
            self.processing_params["adaptive_threshold_block_size"] = args.threshold_block
        if args.threshold_c:
            self.processing_params["adaptive_threshold_c"] = args.threshold_c
        if args.median_blur_kernel:
            self.processing_params["median_blur_kernel"] = args.median_blur_kernel
        if args.dilate_kernel:
            self.processing_params["dilate_kernel_size"] = args.dilate_kernel
        if args.dilate_iterations:
            self.processing_params["dilate_iterations"] = args.dilate_iterations

        # Reinitialize classifier with updated parameters
        self.classifier.processing_params = self.processing_params

    def _scale_frame(self, frame: np.ndarray, scale_percent: int) -> np.ndarray:
        """Helper function for scaling the image."""
        if scale_percent == 100 or scale_percent <= 0:
            return frame
        
        width = int(frame.shape[1] * scale_percent / 100)
        height = int(frame.shape[0] * scale_percent / 100)
        dim = (width, height)
        # Use INTER_AREA for downscaling (better quality)
        return cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)


    def monitor_video(self, video_source: str = None, output_path: str = None, scale_percent: int = 100, duration_minutes: float = 0.0):
        """Monitor parking from video source, with optional time limit"""
        if video_source is None:
            video_source = self.lot_config["video_source"]
        
        # 💡 NOWA LOGIKA: Check and get direct URL from YouTube
        final_video_source = video_source
        if "youtube.com" in video_source or "youtu.be" in video_source:
             final_video_source = get_direct_youtube_url(video_source) # <-- Użycie z utils.py

        # KEY CHANGE: Try using FFMPEG backend
        cap = cv2.VideoCapture(final_video_source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            print(f"Warning: Could not open video source/IP stream using FFMPEG. Trying default backend...")
            
            # Try with default backend
            cap = cv2.VideoCapture(final_video_source) # <-- Using final_video_source
            
            if not cap.isOpened():
                print(f"Error: Could not open video source/IP stream: {final_video_source}")
                return
        
        # Writer must be configured for SCALED output image
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Writer dimensions are scaled
            width_orig = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height_orig = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            width_out = int(width_orig * scale_percent / 100)
            height_out = int(height_orig * scale_percent / 100)
            
            writer = cv2.VideoWriter("data/results/"+output_path, fourcc, fps, (width_out, height_out))
        
        print("Controls: 'q' quit | 's' save frame | 'p' pause/resume | SPACE step frame")
        
        # TIME LIMIT LOGIC INITIALIZATION
        start_time = time.time()
        # Set a finite end time only if duration_minutes > 0, otherwise it's infinity
        end_time = start_time + (duration_minutes * 60) if duration_minutes > 0.0 else float('inf')
        
        paused = False
        frame_count = 0
        
        while True:
            # Check for time limit only if duration_minutes > 0.0
            if duration_minutes > 0.0 and time.time() > end_time:
                print(f"\nTime limit of {duration_minutes} minutes reached. Stopping video processing.")
                break
                
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("End of video or failed to read frame")
                    break
                frame_count += 1
            
            # KEY CHANGE: Processing is done on the ORIGINAL, large 'frame'
            processed_frame = self.classifier.implement_process(frame)
            annotated_frame, stats = self.classifier.classify(
                image=frame.copy(),  # Using original frame for drawing
                processed_image=processed_frame,  # Using originally processed frame
                threshold=self.lot_config["threshold"]
            )
            
            # Scale only for display/output
            display_frame = self._scale_frame(annotated_frame, scale_percent)

            # Display information
            info_text = f"Frame: {frame_count}"
            if duration_minutes > 0.0:
                time_remaining = max(0, int(end_time - time.time()))
                info_text += f" | Time Left: {time_remaining // 60:02d}:{time_remaining % 60:02d}"

            
            (text_w, text_h), baseline = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

        
            cv2.rectangle(display_frame, 
                          (5, 5), # Górny lewy róg tła (z marginesem 5px)
                          (10 + text_w, 15 + text_h), # Dolny prawy róg tła
                          (0, 0, 0), -1) # Kolor czarny, wypełniony

            # 3. Rysowanie białego tekstu
            # Używamy (10, 20) jako stałej pozycji bazowej tekstu (X=10, Y=20)
            cv2.putText(display_frame, info_text, 
                        (10, 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            # ========================================================
            
            cv2.imshow(f"Parking Monitor - {self.lot_config['name']}", display_frame)
            
            if writer:
                writer.write(display_frame) # Zapisujemy skalowany obraz
            
            """if frame_count % 30 == 0:
                print(f"Frame {frame_count}: {stats['empty_spaces']}/{stats['total_spaces']} free "
                      f"({stats['occupancy_rate']:.1f}% occupied)")
            """
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"parking_snapshot_{timestamp}.jpg"
                folder = 'results'
                os.makedirs(folder, exist_ok=True)
                filepath = os.path.join(folder, filename)
                cv2.imwrite(filepath, display_frame)
                print(f"Saved snapshot: {filepath}")
            elif key == ord('p'):
                paused = not paused
                print("Paused" if paused else "Resumed")
            elif key == ord(' ') and paused:
                # IF paused and step, read a new frame and continue with it
                ret, frame_step = cap.read() 
                if ret:
                    frame = frame_step 
                    frame_count += 1
        
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
    
    def monitor_image(self, image_path: str = None, scale_percent: int = 100):
        """Monitor parking from static image"""
        if image_path is None:
            image_path = self.lot_config["source_image"]
        
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image: {image_path}")
            return
        
        # KLUCZOWA ZMIANA: Przetwarzanie i klasyfikacja na ORYGINALNYM obrazie
        processed_image = self.classifier.implement_process(image)
        annotated_image, stats = self.classifier.classify(
            image=image.copy(),
            processed_image=processed_image,
            threshold=self.lot_config["threshold"]
        )
        
        # Scale only for display/output
        display_image = self._scale_frame(annotated_image, scale_percent)
        
        print("\nParking Statistics:")
        print(f"Total spaces: {stats['total_spaces']}")
        print(f"Empty spaces: {stats['empty_spaces']}")
        print(f"Occupied spaces: {stats['occupied_spaces']}")
        print(f"Occupancy rate: {stats['occupancy_rate']:.1f}%")
        
        cv2.imshow(f"Parking Analysis - {self.lot_config['name']}", display_image)
        print("Press any key to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description='Generic Parking Space Monitor')
    parser.add_argument('--list', '-L', action='store_true', help='List all available parking lot configuration names and exit.')
    parser.add_argument('--lot', '-l', default='default', help='Parking lot configuration name')
    parser.add_argument('--video', '-v', default=None, help='Video source (file path or camera index)')
    parser.add_argument('--image', '-i', default=None, help='Static image path')
    parser.add_argument('--output', '-o', default=None, help='Output video path')
    parser.add_argument('--mode', '-m', choices=['video', 'image'], default='video', help='Monitoring mode')
    
    # NEW ARGUMENT FOR VIDEO DURATION / ENDLESS MODE
    parser.add_argument('--duration_minutes', type=float, default=0.0,
                        help='Video recording duration in minutes. 0.0 means endless until stopped by user (q key).')
    
    # ARGUMENT DLA SKALOWANIA
    parser.add_argument('--scale_percent', type=int, default=100, 
                        help='Scale output image/video in percent (e.g., 50 for 50% size).')

    # Image processing overrides
    parser.add_argument('--blur_kernel', type=int, nargs=2, help='Gaussian blur kernel size, e.g., 3 3')
    parser.add_argument('--blur_sigma', type=float, help='Gaussian blur sigma')
    parser.add_argument('--threshold_block', type=int, help='Adaptive threshold block size')
    parser.add_argument('--threshold_c', type=int, help='Adaptive threshold C value')
    parser.add_argument('--median_blur_kernel', type=int, help='Median blur kernel size')
    parser.add_argument('--dilate_kernel', type=int, nargs=2, help='Dilation kernel size, e.g., 3 3')
    parser.add_argument('--dilate_iterations', type=int, help='Number of dilation iterations')

    args = parser.parse_args()

    config_manager = ConfigManager()
    
    if args.list:
        available_lots = config_manager.list_parking_lots()
        
        names = [lot for lot in available_lots if lot != 'default'] # <-- Zmienna z listą konfiguracji
        
        print("\nLista dostępnych konfiguracji parkingów (z config/parking_config.json):")
        
        if names:
            cols = 3
            maxlen = max(len(n) for n in names) + 4
            rows = math.ceil(len(names) / cols)

            for r in range(rows):
                row_str = ""
                for c in range(cols):
                    idx = r + c * rows
                    if idx < len(names):
                        entry = f"{names[idx]}"
                        row_str += entry.ljust(maxlen)
                print(row_str)
        else:
            print("  Brak dostępnych konfiguracji. Sprawdź pliki konfiguracyjne.")
            
        print("\n---")
        
        print("Pliki źródłowe do ewentualnej kalibracji (data/source/img):")
        list_files_three_columns(IMG_DIR, pattern="*.png", cols=3)
        
        print("") 
        return
    
    # Blocks above execute if --list is  not provided
    available_lots = config_manager.list_parking_lots()
    
    display_lots = [lot for lot in available_lots if lot != 'default']
    print(f"Available parking lot configurations: {display_lots}")

    monitor = ParkingMonitor(args.lot)
    monitor.apply_overrides(args)

    scale_percent = args.scale_percent
    duration_minutes = args.duration_minutes # Capture the new argument

    if args.mode == 'video':
        # Pass the new duration_minutes argument
        monitor.monitor_video(args.video, args.output, scale_percent, duration_minutes) 
    else:
        monitor.monitor_image(args.image, scale_percent)

if __name__ == "__main__":
    main()