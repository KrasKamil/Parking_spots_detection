import cv2
import argparse
import time
import os
import numpy as np
import sys
import json
import tkinter as tk 
from src.parking_classifier import ParkClassifier
from src.config_manager import ConfigManager
from src.utils import IMG_DIR, get_direct_youtube_url, OverlayConsole

# Ścieżka bazowa projektu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "parking_config.json")

class ParkingMonitor:
    def __init__(self, parking_lot_name: str = "default"):
        self.lot_name = parking_lot_name
        self.config_manager = ConfigManager()
        self.lot_config = self.config_manager.get_parking_lot_config(parking_lot_name)
        
        # --- FIX: Naprawa ścieżki do pliku pozycji ---
        pos_file = self.lot_config["positions_file"]
        if not os.path.isabs(pos_file):
            pos_file = os.path.join(BASE_DIR, pos_file)
            
        self.processing_params = self.config_manager.get_processing_params()
        
        # --- ZAPAMIĘTANIE WARTOŚCI DOMYŚLNYCH (DLA RESETU) ---
        self.default_threshold = self.lot_config["threshold"]
        self.current_threshold = self.default_threshold # Aktualny próg
        
        # Kopiujemy słownik, żeby zmiany na żywo nie nadpisały "backupu"
        self.default_params = self.processing_params.copy()
        
        self.classifier = ParkClassifier(
            car_park_positions_path=pos_file,
            rect_width=self.lot_config["rect_width"],
            rect_height=self.lot_config["rect_height"],
            processing_params=self.processing_params
        )
        print(f"Monitor: {self.lot_config['name']} | Miejsca: {len(self.classifier.car_park_positions)}")

    def get_screen_resolution(self):
        try:
            root = tk.Tk(); root.withdraw()
            w, h = root.winfo_screenwidth(), root.winfo_screenheight()
            root.destroy(); return w, h
        except: return 1920, 1080 

    def calculate_optimal_scale(self, frame_w, frame_h):
        screen_w, screen_h = self.get_screen_resolution()
        target_w, target_h = screen_w - 60, screen_h - 120
        return min(target_w / frame_w, target_h / frame_h, 1.0)

    def apply_overrides(self, args):
        if args.blur_kernel: self.processing_params["gaussian_blur_kernel"] = args.blur_kernel
        if args.blur_sigma: self.processing_params["gaussian_blur_sigma"] = args.blur_sigma
        if args.threshold_block: self.processing_params["adaptive_threshold_block_size"] = args.threshold_block
        if args.threshold_c: self.processing_params["adaptive_threshold_c"] = args.threshold_c
        self.classifier.processing_params = self.processing_params
        
        # Aktualizujemy też defaulty, jeśli użytkownik podał flagi przy starcie
        self.default_params = self.processing_params.copy()

    # --- FUNKCJE TUNINGU ---
    def nothing(self, x): pass

    def setup_trackbars(self, win_name="TUNING"):
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_name, 400, 350)
        self.force_focus(win_name)
        cv2.createTrackbar("Threshold (Pix)", win_name, self.current_threshold, 2000, self.nothing)
        
        # 1. Próg detekcji (Używamy self.current_threshold)
        cv2.createTrackbar("Threshold (Pix)", win_name, self.current_threshold, 2000, self.nothing)
        
        # 2. Block Size
        curr_block = self.processing_params.get("adaptive_threshold_block_size", 25)
        cv2.createTrackbar("Block Size", win_name, curr_block, 100, self.nothing)
        
        # 3. Constant C
        curr_c = self.processing_params.get("adaptive_threshold_c", 15)
        cv2.createTrackbar("Constant C", win_name, curr_c, 50, self.nothing)
        
        # 4. Blur Kernel
        curr_blur = self.processing_params.get("gaussian_blur_kernel", [5, 5])[0]
        cv2.createTrackbar("Blur Kernel", win_name, curr_blur, 30, self.nothing)

    def get_trackbar_values(self, win_name="TUNING"):
        try:
            th = cv2.getTrackbarPos("Threshold (Pix)", win_name)
            bs = cv2.getTrackbarPos("Block Size", win_name)
            c = cv2.getTrackbarPos("Constant C", win_name)
            bk = cv2.getTrackbarPos("Blur Kernel", win_name)
            
            # Walidacja (nieparzyste > 1)
            if bs < 3: bs = 3
            if bs % 2 == 0: bs += 1
            
            if bk < 1: bk = 1
            if bk % 2 == 0: bk += 1
            
            return th, bs, c, bk
        except:
            return self.current_threshold, 25, 15, 5

    def reset_trackbars(self, win_name="TUNING"):
        """Przywraca suwaki do pozycji startowych."""
        def_block = self.default_params.get("adaptive_threshold_block_size", 25)
        def_c = self.default_params.get("adaptive_threshold_c", 15)
        def_blur = self.default_params.get("gaussian_blur_kernel", [5, 5])[0]
        
        try:
            cv2.setTrackbarPos("Threshold (Pix)", win_name, self.default_threshold)
            cv2.setTrackbarPos("Block Size", win_name, def_block)
            cv2.setTrackbarPos("Constant C", win_name, def_c)
            cv2.setTrackbarPos("Blur Kernel", win_name, def_blur)
            print("[INFO] Zresetowano parametry do domyslnych.")
        except: pass

    def save_current_config(self, threshold, block, c, blur):
        """Zapisuje parametry suwaków do pliku JSON w odpowiednie miejsca."""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 1. Zapis Threshold do konkretnego parkingu ("rynek")
            if self.lot_name in data["parking_lots"]:
                data["parking_lots"][self.lot_name]["threshold"] = threshold
                print(f"[SAVE] Zapisano threshold={threshold} dla parkingu '{self.lot_name}'")
            
            # 2. Zapis reszty parametrów globalnie (lub per-parking jeśli wolisz)
            data["processing_params"]["adaptive_threshold_block_size"] = block
            data["processing_params"]["adaptive_threshold_c"] = c
            data["processing_params"]["gaussian_blur_kernel"] = [blur, blur]
            print(f"[SAVE] Zapisano parametry przetwarzania (Block={block}, C={c}, Blur={blur})")
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Błąd zapisu: {e}")
            return False

    def monitor_video(self, video_source: str = None, output_path: str = None, user_scale_percent: int = 100, duration_minutes: float = 0.0):
        if video_source is None: 
            video_source = self.lot_config["video_source"]
            
        if video_source.startswith("http") and "://" not in video_source:
            video_source = video_source.replace(":/", "://")
        
        if "http" in video_source and ("youtube.com" in video_source or "youtu.be" in video_source):
             print(f"[INFO] Pobieranie URL strumienia z: {video_source}")
             video_source = get_direct_youtube_url(video_source)
        
        elif not video_source.startswith("http") and not os.path.exists(video_source):
            potential_path = os.path.join(BASE_DIR, video_source)
            if os.path.exists(potential_path):
                video_source = potential_path
            else:
                print(f"[ERROR] Nie znaleziono pliku wideo: {video_source}")

        cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)
        if not cap.isOpened(): cap = cv2.VideoCapture(video_source)
        if not cap.isOpened(): 
            print(f"[FATAL] Nie można otworzyć źródła wideo: {video_source}")
            return
        
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if user_scale_percent == 100: scale_factor = self.calculate_optimal_scale(orig_w, orig_h)
        else: scale_factor = user_scale_percent / 100.0

        disp_w, disp_h = int(orig_w * scale_factor), int(orig_h * scale_factor)

        window_name = f"Monitoring - {self.lot_config['name']}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, disp_w, disp_h)
        cv2.moveWindow(window_name, 30, 30)

        # --- ZMIENNA STANU TUNINGU ---
        tuning_active = False # Domyślnie ukryte
        tuning_win = "TUNING"
        # -----------------------------

        console = OverlayConsole(title=f"LOG: {self.lot_config['name']}", visible_by_default=False)
        sys.stdout = console 
        
        ui_state = {'should_quit': False, 'btn_rect': (0,0,0,0)}

        def mouse_callback(event, x, y, flags, param):
            console.handle_mouse(event, x, y, flags)
            if event == cv2.EVENT_LBUTTONDOWN:
                bx, by, bw, bh = param['btn_rect']
                if bx <= x <= bx + bw and by <= y <= by + bh: param['should_quit'] = True
        
        cv2.setMouseCallback(window_name, mouse_callback, ui_state)

        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, 25.0, (disp_w, disp_h))
        
        print("System ON.")
        print("[INFO]: 'H'-Logi | 'Ctrl+T'-Tuning | 'Q'-Wyjście")
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60) if duration_minutes > 0.0 else float('inf')
        paused = False
        frame_count = 0
        
        try:
            while True:
                if ui_state['should_quit'] or (duration_minutes > 0 and time.time() > end_time): break
                
                # --- LOGIKA TUNINGU ---
                if tuning_active:
                    try:
                        # Odczyt suwaków
                        th, bs, c, bk = self.get_trackbar_values(tuning_win)
                        
                        # Aktualizacja parametrów na żywo
                        self.classifier.processing_params["adaptive_threshold_block_size"] = bs
                        self.classifier.processing_params["adaptive_threshold_c"] = c
                        self.classifier.processing_params["gaussian_blur_kernel"] = [bk, bk]
                        self.current_threshold = th # Zapisz aktualny próg do klasy
                    except:
                        tuning_active = False
                
                current_thresh_limit = self.current_threshold
                # ----------------------

                if not paused:
                    ret, frame = cap.read()
                    if not ret: 
                        print("[INFO] Pętla wideo...")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    frame_count += 1
                
                processed = self.classifier.implement_process(frame)
                annotated, stats = self.classifier.classify(frame.copy(), processed, current_thresh_limit)
                
                display_frame = cv2.resize(annotated, (disp_w, disp_h), interpolation=cv2.INTER_AREA)

                # INFO BAR
                info_text = f"Klatka: {frame_count} | Wolne: {stats['empty_spaces']}/{len(self.classifier.car_park_positions)}"
                if tuning_active:
                    info_text += " [TUNING: W=Zapisz]"
                
                (tw, th_txt), _ = cv2.getTextSize(info_text, 0, 0.6, 1)
                cv2.rectangle(display_frame, (5, disp_h-35), (15+tw, disp_h-5), (0,0,0), -1)
                cv2.putText(display_frame, info_text, (10, disp_h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

                # PRZYCISK ZAMKNIJ
                btn_w, btn_h = 100, 30
                btn_x, btn_y = disp_w - btn_w - 10, 10
                ui_state['btn_rect'] = (btn_x, btn_y, btn_w, btn_h)
                
                cv2.rectangle(display_frame, (btn_x, btn_y), (btn_x+btn_w, btn_y+btn_h), (0,0,180), -1)
                cv2.rectangle(display_frame, (btn_x, btn_y), (btn_x+btn_w, btn_y+btn_h), (200,200,200), 1)
                cv2.putText(display_frame, "WYJSCIE", (btn_x+15, btn_y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

                display_frame = console.draw(display_frame) 

                cv2.imshow(window_name, display_frame)
                
                if tuning_active:
                    preview = cv2.resize(processed, (400, 300))
                    cv2.imshow(tuning_win, preview)

                if writer: writer.write(display_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'): break
                elif key == ord('h'): 
                    console.toggle()
                elif key == ord('p'): 
                    paused = not paused
                    print("PAUZA" if paused else "WZNOWIONO")
                
                # --- PRZEŁĄCZANIE TUNINGU (Ctrl+T) ---
                elif key == 20: # Kod ASCII dla Ctrl+T
                    tuning_active = not tuning_active
                    if tuning_active:
                        self.setup_trackbars(tuning_win)
                        print("[INFO] Tuning wlaczony. Wcisnij 'W' aby zapisac.")
                    else:
                        try: 
                            cv2.destroyWindow(tuning_win)
                            self.force_focus(window_name)
                        except: pass
                        print("[INFO] Tuning ukryty")
                
                # --- ZAPIS (W) - Tylko gdy Tuning aktywny ---
                elif tuning_active and key == ord('w'):
                    th, bs, c, bk = self.get_trackbar_values(tuning_win)
                    if self.save_current_config(th, bs, c, bk):
                        pass # Komunikat jest wewnątrz save_current_config
                    else:
                        print("[ERROR] Błąd zapisu")
                
                elif tuning_active and key == ord('r'):
                    self.reset_trackbars(tuning_win)
        
        except KeyboardInterrupt: pass
        finally:
            sys.stdout = sys.__stdout__
            cap.release()
            if writer: writer.release()
            cv2.destroyAllWindows()

    def monitor_image(self, image_path: str = None, scale_percent: int = 100):
        if image_path is None: image_path = self.lot_config["source_image"]
        if not os.path.exists(image_path):
            potential = os.path.join(BASE_DIR, image_path)
            if os.path.exists(potential): image_path = potential

        image = cv2.imread(image_path)
        if image is None: print(f"[ERROR] Nie można wczytać obrazu: {image_path}"); return
        
        orig_h, orig_w = image.shape[:2]
        scale_factor = self.calculate_optimal_scale(orig_w, orig_h) if scale_percent == 100 else scale_percent/100.0
        disp_w, disp_h = int(orig_w * scale_factor), int(orig_h * scale_factor)

        processed = self.classifier.implement_process(image)
        annotated, stats = self.classifier.classify(image.copy(), processed, self.lot_config["threshold"])
        display = cv2.resize(annotated, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
        
        console = OverlayConsole(title="ANALIZA OBRAZU", visible_by_default=True)
        sys.stdout = console
        print(f"Wolne: {stats['empty_spaces']} | Zajęte: {stats['occupied_spaces']}")
        
        win_name = f"Image - {self.lot_config['name']}"
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_name, disp_w, disp_h)
        
        def mouse_cb(event, x, y, flags, param): console.handle_mouse(event, x, y, flags)
        cv2.setMouseCallback(win_name, mouse_cb)

        while True:
            frame_copy = display.copy()
            frame_copy = console.draw(frame_copy)
            cv2.imshow(win_name, frame_copy)
            k = cv2.waitKey(20) & 0xFF
            if k == ord('q'): break
            elif k == ord('h'): console.toggle()
        
        sys.stdout = sys.__stdout__
        cv2.destroyAllWindows()
        
    def force_focus(self, win_name):
        """Wymusza skupienie uwagi systemu na konkretnym oknie."""
    try:
        # Ustawienie okna na wierzch (wymusza focus w większości OS)
        cv2.setWindowProperty(win_name, cv2.WND_PROP_TOPMOST, 1)
        # Od razu wyłączamy "zawsze na wierzchu", żeby nie blokowało innych okien
        cv2.setWindowProperty(win_name, cv2.WND_PROP_TOPMOST, 0)
    except:
        pass
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lot', '-l', default='default')
    parser.add_argument('--mode', '-m', choices=['video', 'image'], default='video')
    parser.add_argument('--video', '-v', default=None)
    parser.add_argument('--image', '-i', default=None)
    parser.add_argument('--output', '-o', default=None)
    parser.add_argument('--scale_percent', type=int, default=100) 
    parser.add_argument('--duration_minutes', '-t', type=float, default=0.0)
    
    # Tuning domyślnie wyłączony, włączany skrótem Ctrl+T
    parser.add_argument('--blur_kernel', type=int, nargs=2)
    parser.add_argument('--blur_sigma', type=float)
    parser.add_argument('--threshold_block', type=int)
    parser.add_argument('--threshold_c', type=int)
    
    args = parser.parse_args()
    
    try:
        monitor = ParkingMonitor(args.lot)
        monitor.apply_overrides(args)
        
        if args.mode == 'video':
            monitor.monitor_video(args.video, args.output, args.scale_percent, args.duration_minutes) 
        else:
            monitor.monitor_image(args.image, args.scale_percent)
            
    except Exception as e:
        print(f"[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()