import cv2
import argparse
import time
from src.utils import ParkClassifier
from src.config_manager import ConfigManager

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

    def monitor_video(self, video_source: str = None, output_path: str = None):
        """Monitor parking from video source"""
        if video_source is None:
            video_source = self.lot_config["video_source"]

        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print(f"Error: Could not open video source: {video_source}")
            return
        
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        print("Controls: 'q' quit | 's' save frame | 'p' pause/resume | SPACE step frame")
        paused = False
        frame_count = 0
        
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("End of video or failed to read frame")
                    break
                frame_count += 1
            
            processed_frame = self.classifier.implement_process(frame)
            annotated_frame, stats = self.classifier.classify(
                image=frame.copy(),
                processed_image=processed_frame,
                threshold=self.lot_config["threshold"]
            )
            
            cv2.putText(annotated_frame, f"Frame: {frame_count}", 
                       (10, annotated_frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow(f"Parking Monitor - {self.lot_config['name']}", annotated_frame)
            
            if writer:
                writer.write(annotated_frame)
            
            if frame_count % 30 == 0:
                print(f"Frame {frame_count}: {stats['empty_spaces']}/{stats['total_spaces']} free "
                      f"({stats['occupancy_rate']:.1f}% occupied)")
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"parking_snapshot_{timestamp}.jpg"
                cv2.imwrite(filename, annotated_frame)
                print(f"Saved snapshot: {filename}")
            elif key == ord('p'):
                paused = not paused
                print("Paused" if paused else "Resumed")
            elif key == ord(' ') and paused:
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
        
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
    
    def monitor_image(self, image_path: str = None):
        """Monitor parking from static image"""
        if image_path is None:
            image_path = self.lot_config["source_image"]
        
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image: {image_path}")
            return
        
        processed_image = self.classifier.implement_process(image)
        annotated_image, stats = self.classifier.classify(
            image=image.copy(),
            processed_image=processed_image,
            threshold=self.lot_config["threshold"]
        )
        
        print("\nParking Statistics:")
        print(f"Total spaces: {stats['total_spaces']}")
        print(f"Empty spaces: {stats['empty_spaces']}")
        print(f"Occupied spaces: {stats['occupied_spaces']}")
        print(f"Occupancy rate: {stats['occupancy_rate']:.1f}%")
        
        cv2.imshow(f"Parking Analysis - {self.lot_config['name']}", annotated_image)
        print("Press any key to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description='Generic Parking Space Monitor')
    parser.add_argument('--lot', '-l', default='default', help='Parking lot configuration name')
    parser.add_argument('--video', '-v', default=None, help='Video source (file path or camera index)')
    parser.add_argument('--image', '-i', default=None, help='Static image path')
    parser.add_argument('--output', '-o', default=None, help='Output video path')
    parser.add_argument('--mode', '-m', choices=['video', 'image'], default='video', help='Monitoring mode')

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
    available_lots = config_manager.list_parking_lots()
    print(f"Available parking lot configurations: {available_lots}")

    monitor = ParkingMonitor(args.lot)
    monitor.apply_overrides(args)

    if args.mode == 'video':
        monitor.monitor_video(args.video, args.output)
    else:
        monitor.monitor_image(args.image)

if __name__ == "__main__":
    main()
