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
    
    def monitor_video(self, video_source: str = None, output_path: str = None):
        """Monitor parking from video source"""
        
        if video_source is None:
            video_source = self.lot_config["video_source"]
        
        # Try to open video source (file or camera)
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print(f"Error: Could not open video source: {video_source}")
            return
        
        # Setup video writer if output path provided
        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        print("Controls:")
        print("- 'q': Quit")
        print("- 's': Save current frame")
        print("- 'p': Pause/Resume")
        print("- SPACE: Step frame (when paused)")
        
        paused = False
        frame_count = 0
        
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("End of video or failed to read frame")
                    break
                
                frame_count += 1
            
            # Process frame
            processed_frame = self.classifier.implement_process(frame)
            
            # Classify and get statistics
            annotated_frame, stats = self.classifier.classify(
                image=frame.copy(),
                processed_image=processed_frame,
                threshold=self.lot_config["threshold"]
            )
            
            # Add frame counter
            cv2.putText(annotated_frame, f"Frame: {frame_count}", 
                       (10, annotated_frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display result
            cv2.imshow(f"Parking Monitor - {self.lot_config['name']}", annotated_frame)
            
            # Write to output if specified
            if writer:
                writer.write(annotated_frame)
            
            # Print statistics periodically
            if frame_count % 30 == 0:  # Every 30 frames
                print(f"Frame {frame_count}: {stats['empty_spaces']}/{stats['total_spaces']} "
                      f"spaces free ({stats['occupancy_rate']:.1f}% occupied)")
            
            # Handle key presses
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
                # Step one frame when paused
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
        
        # Cleanup
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
    
    def monitor_image(self, image_path: str = None):
        """Monitor parking from static image"""
        
        if image_path is None:
            image_path = self.lot_config["source_image"]
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not load image: {image_path}")
            return
        
        # Process and classify
        processed_image = self.classifier.implement_process(image)
        annotated_image, stats = self.classifier.classify(
            image=image.copy(),
            processed_image=processed_image,
            threshold=self.lot_config["threshold"]
        )
        
        # Display results
        print("\nParking Statistics:")
        print(f"Total spaces: {stats['total_spaces']}")
        print(f"Empty spaces: {stats['empty_spaces']}")
        print(f"Occupied spaces: {stats['occupied_spaces']}")
        print(f"Occupancy rate: {stats['occupancy_rate']:.1f}%")
        
        # Show image
        cv2.imshow(f"Parking Analysis - {self.lot_config['name']}", annotated_image)
        print("Press any key to exit...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser(description='Generic Parking Space Monitor')
    parser.add_argument('--lot', '-l', default='default',
                       help='Parking lot configuration name')
    parser.add_argument('--video', '-v', default=None,
                       help='Video source (file path or camera index)')
    parser.add_argument('--image', '-i', default=None,
                       help='Static image path')
    parser.add_argument('--output', '-o', default=None,
                       help='Output video path')
    parser.add_argument('--mode', '-m', choices=['video', 'image'], default='video',
                       help='Monitoring mode')
    
    args = parser.parse_args()
    
    # List available configurations
    config_manager = ConfigManager()
    available_lots = config_manager.list_parking_lots()
    print(f"Available parking lot configurations: {available_lots}")
    
    # Initialize monitor
    monitor = ParkingMonitor(args.lot)
    
    # Run appropriate mode
    if args.mode == 'video':
        monitor.monitor_video(args.video, args.output)
    else:
        monitor.monitor_image(args.image)

if __name__ == "__main__":
    main()