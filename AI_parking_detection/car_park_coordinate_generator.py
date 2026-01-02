import cv2
import pickle
import sys
import os
import argparse
import numpy as np
import json
import time
import tkinter as tk
from src.utils import OverlayConsole, draw_text_pl

# --- KONFIGURACJA ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLYGON_DIR = os.path.join(BASE_DIR, "data", "parking_lots")
CONFIG_FILE = os.path.join(BASE_DIR, "config", "parking_config.json")
TEMP_CALIB_FILE = os.path.join(BASE_DIR, "config", "temp_calibration.json")

def get_positions_file(lot_name):
    os.makedirs(POLYGON_DIR, exist_ok=True)
    return os.path.join(POLYGON_DIR, f"{lot_name}_positions")

def load_config_dims(lot_name):
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lot = data.get("parking_lots", {}).get(lot_name)
                if lot: 
                    return int(lot.get("rect_width", 50)), int(lot.get("rect_height", 100))
        except: pass
    return 50, 100

def get_image_path_from_config(lot_name):
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lot = data.get("parking_lots", {}).get(lot_name)
                if lot:
                    src = lot.get("source_image", "")
                    if src and not os.path.isabs(src):
                        return os.path.join(BASE_DIR, src)
                    return src
        except: pass
    return None

def get_screen_resolution():
    try:
        root = tk.Tk(); root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy(); return w, h
    except: return 1920, 1080

# --- ZMIENNE STANU ---
car_park_positions = []; route_points = []; temp_points = []
mode = 'p'; console_ui = None; scale_factor = 1.0
rect_w, rect_h = 50, 100; current_angle = 0; input_buffer = ""; is_editing_id = False
edit_target_index = -1; blink_state = True; mouse_curr_x, mouse_curr_y = 0, 0
should_exit = False
last_action_time = 0 
ui_force_hidden = False 
show_help_panel = False 
positions_file = "" 
last_h_press_time = 0 

# --- FUNKCJA LOGOWANIA (GWARANTOWANA) ---
def log(msg):
    """Loguje do terminala oraz do konsoli ekranowej."""
    # 1. Terminal systemowy
    try: sys.__stdout__.write(f"{msg}\n")
    except: pass
    
    # 2. Konsola na ekranie (Overlay) - BEZPOŚREDNIO
    if console_ui:
        console_ui.write(str(msg))

def get_next_id():
    existing = {int(p['id']) for p in car_park_positions if str(p['id']).isdigit()}
    cand = 1
    while cand in existing: cand += 1
    return str(cand)

def create_rotated_rect(center, w, h, angle):
    cx, cy = center; theta = np.radians(angle); cos_a, sin_a = np.cos(theta), np.sin(theta)
    hw, hh = w/2, h/2
    corners = [(-hw,-hh), (hw,-hh), (hw,hh), (-hw,hh)]
    return [(int(cx + px*cos_a - py*sin_a), int(cy + px*sin_a + py*cos_a)) for px, py in corners]

def save_data(filepath):
    data = {'car_park_positions': car_park_positions, 'route_points': route_points}
    with open(filepath, 'wb') as f: pickle.dump(data, f)
    log(f"[SUCCESS] Zapisano {len(car_park_positions)} miejsc.")

def mouse_events(event, x, y, flags, params):
    global temp_points, is_editing_id, edit_target_index, input_buffer, mouse_curr_x, mouse_curr_y, current_angle
    global car_park_positions, route_points, should_exit, last_action_time, ui_force_hidden, show_help_panel, mode, rect_w, rect_h
    
    if console_ui and console_ui.visible: 
        if console_ui.handle_mouse(event, x, y, flags): return 

    mouse_curr_x, mouse_curr_y = x, y
    real_x, real_y = int(x / scale_factor), int(y / scale_factor)

    if event == cv2.EVENT_MOUSEWHEEL and mode == 'p':
        last_action_time = time.time()
        step = 5
        if flags > 0: current_angle += step
        else: current_angle -= step

    if event == cv2.EVENT_LBUTTONDOWN:
        if not ui_force_hidden:
            if 10 <= x <= 80 and 10 <= y <= 35:
                show_help_panel = not show_help_panel 
                last_action_time = time.time() 
                return

            if show_help_panel:
                if 10 <= x <= 220 and 40 <= y <= 400: return

            if mode != 'c':
                disp_w = params['disp_w']
                btn_w, btn_h = 220, 35
                btn_x, btn_y = disp_w - btn_w - 10, 10
                
                is_auto_hidden = (mode in ['t', 'p', 'i'] and (time.time() - last_action_time < 3.0))
                
                if not is_auto_hidden or show_help_panel:
                    if btn_x <= x <= btn_x+btn_w and btn_y <= y <= btn_y+btn_h: should_exit = True; return

        if is_editing_id: 
            log("(!) Zakończ edycję ENTEREM.")
            return

        if mode == 'p':
            new_id = get_next_id()
            pts = create_rotated_rect((real_x, real_y), rect_w, rect_h, current_angle)
            car_park_positions.append({'id': new_id, 'points': pts, 'irregular': False})
            last_action_time = time.time()
            log(f"[+] Dodano miejsce (ID: {new_id})")
            
        elif mode == 'i':
            temp_points.append((real_x, real_y))
            last_action_time = time.time()
            log(f"[INFO] Punkt {len(temp_points)}/4")
            if len(temp_points) == 4:
                new_id = get_next_id()
                car_park_positions.append({'id': new_id, 'points': temp_points.copy(), 'irregular': True})
                temp_points = []
                log(f"[+] Utworzono wielokąt (ID: {new_id})")
                
        elif mode == 't':
            route_points.append((real_x, real_y))
            last_action_time = time.time()
            log(f"[+] Dodano punkt trasy ({len(route_points)})")
            
        elif mode == 'e':
            found = False
            for i, pos in enumerate(car_park_positions):
                if cv2.pointPolygonTest(np.array(pos['points'], np.int32), (real_x, real_y), False) >= 0:
                    edit_target_index = i
                    input_buffer = str(pos['id'])
                    is_editing_id = True
                    log(f"[EDIT] Edycja ID: {input_buffer}")
                    found = True
                    break
            if not found: log("[-] Brak miejsca w tym punkcie.")
                    
        elif mode == 'c':
            if len(temp_points) >= 2: temp_points = []
            temp_points.append((real_x, real_y))
            log(f"[CALIB] Punkt {len(temp_points)}/2")

    elif event == cv2.EVENT_RBUTTONDOWN:
        last_action_time = time.time()
        if mode == 't' and route_points: 
            route_points.pop(); log("[-] Cofnięto punkt trasy")
        elif mode in ['p','i']:
            deleted = False
            for i, p in enumerate(car_park_positions):
                if cv2.pointPolygonTest(np.array(p['points'],np.int32), (real_x,real_y), False) >= 0:
                    removed_id = p['id']
                    car_park_positions.pop(i)
                    log(f"[-] Usunięto miejsce ID: {removed_id}")
                    deleted = True
                    break
            if not deleted and mode == 'i' and temp_points:
                temp_points.pop(); log("[-] Cofnięto punkt")
        elif temp_points: 
            temp_points = []; log("[-] Wyczyszczono punkty")

def main():
    global mode, car_park_positions, route_points, console_ui, scale_factor, rect_w, rect_h, positions_file
    global is_editing_id, input_buffer, edit_target_index, blink_state, should_exit, last_action_time, ui_force_hidden, temp_points, show_help_panel, last_h_press_time

    parser = argparse.ArgumentParser()
    parser.add_argument("--image"); parser.add_argument("--lot", required=True); parser.add_argument("--mode", default="p")
    args = parser.parse_args()

    current_lot_name = args.lot
    
    if current_lot_name == "empty_calibration":
        positions_file = os.path.join(POLYGON_DIR, "temp_positions") 
    else:
        positions_file = get_positions_file(current_lot_name)
    
    rect_w, rect_h = load_config_dims(current_lot_name)
    
    if current_lot_name != "empty_calibration" and os.path.exists(positions_file):
        try:
            with open(positions_file, 'rb') as f:
                d = pickle.load(f)
                if isinstance(d, dict): 
                    car_park_positions[:] = d.get('car_park_positions', [])
                    route_points[:] = d.get('route_points', [])
                elif isinstance(d, list): 
                    for i, it in enumerate(d):
                        if isinstance(it, dict): car_park_positions.append(it)
                        else: car_park_positions.append({'id':str(i+1), 'points':it[0], 'irregular':it[1]=='i'})
        except: pass

    # POBIERANIE OBRAZU
    img_path = None
    if args.image: img_path = args.image
    if not img_path and current_lot_name != "empty_calibration": img_path = get_image_path_from_config(current_lot_name)
    if not img_path:
        sd = os.path.join(BASE_DIR, "data", "source", "img")
        if os.path.exists(sd):
            m = [os.path.join(sd, f) for f in os.listdir(sd) if current_lot_name in f]
            if m: img_path = m[0]
            elif current_lot_name == "empty_calibration":
                 files = [os.path.join(sd, f) for f in os.listdir(sd) if f.endswith(('.png','.jpg'))]
                 if files: img_path = files[0]

    if not img_path or not os.path.exists(img_path):
        print(f"ERROR: Brak obrazu dla parkingu '{current_lot_name}'"); return

    img_orig = cv2.imread(img_path)
    if img_orig is None: print(f"ERROR: Nie można otworzyć pliku: {img_path}"); return

    oh, ow = img_orig.shape[:2]
    sw, sh = get_screen_resolution()
    scale_factor = min((sw-100)/ow, (sh-150)/oh, 1.0)
    dw, dh = int(ow*scale_factor), int(oh*scale_factor)
    img_stat = cv2.resize(img_orig, (dw, dh))

    mode = args.mode
    title = "KALIBRACJA" if mode=='c' else f"EDYTOR: {current_lot_name}"
    
    # KONSOLA DOMYŚLNIE UKRYTA (False)
    console_ui = OverlayConsole(title=title, visible_by_default=False)
    if mode == 'c': console_ui.visible = False
    
    # UWAGA: Usunąłem sys.stdout = console_ui, bo mamy funkcję log()!

    win = "Edytor"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, dw, dh)
    cv2.moveWindow(win, 50, 50)
    cv2.setMouseCallback(win, mouse_events, {'disp_w': dw, 'disp_h': dh})

    if mode == 'c': log("Zaznacz przekątną miejsca (2 punkty).")
    else: log("Witaj w edytorze! Wciśnij przycisk INFO (lewy górny róg) dla pomocy.")

    frame_cnt = 0

    while True:
        auto_hidden = (mode in ['t', 'p', 'i'] and (time.time() - last_action_time < 3.0))
        status_bars_visible = not ui_force_hidden
        buttons_visible = not ui_force_hidden and (not auto_hidden or show_help_panel or is_editing_id)
        info_btn_visible = not ui_force_hidden 
        
        if should_exit:
            if mode != 'c': save_data(positions_file)
            break

        frame = img_stat.copy()
        frame_cnt += 1
        if frame_cnt % 15 == 0: blink_state = not blink_state 

        def sc(p): return (int(p[0]*scale_factor), int(p[1]*scale_factor))
        def scp(pts): return np.array([sc(p) for p in pts], np.int32)

        # RYSOWANIE
        if mode=='c':
            for p in temp_points: cv2.circle(frame, sc(p), 5, (0,0,255), -1)
            if len(temp_points)==2:
                cv2.rectangle(frame, sc(temp_points[0]), sc(temp_points[1]), (255,0,0), 2)
                frame = draw_text_pl(frame, "Zapisz (ENTER)", (sc(temp_points[0])[0], sc(temp_points[0])[1]-10), 0.7, (0,255,0))
        else:
            if route_points:
                srp = [sc(p) for p in route_points]
                for i in range(len(srp)-1): cv2.line(frame, srp[i], srp[i+1], (255,255,0), 2)
                for p in srp: cv2.circle(frame, p, 5, (255,255,0), -1)

            for i, p in enumerate(car_park_positions):
                col = (0,255,255) if is_editing_id and i==edit_target_index else ((255,0,255) if p.get('irregular') else (0,255,0))
                cv2.polylines(frame, [scp(p['points'])], True, col, 2)
                M = cv2.moments(scp(p['points']))
                if M['m00']: cv2.putText(frame, str(p['id']), (int(M['m10']/M['m00']), int(M['m01']/M['m00'])), 0, 0.5, (255,255,255), 2)

            if mode == 'p' and not is_editing_id:
                real_mx, real_my = int(mouse_curr_x/scale_factor), int(mouse_curr_y/scale_factor)
                pts = create_rotated_rect((real_mx, real_my), rect_w, rect_h, current_angle)
                cv2.polylines(frame, [scp(pts)], True, (0, 255, 255), 1)
            
            elif mode == 'i' and temp_points:
                if len(temp_points) > 1: cv2.polylines(frame, [scp(temp_points)], False, (0,255,255), 2)
                for tp in temp_points: cv2.circle(frame, sc(tp), 5, (0, 0, 255), -1)
                if len(temp_points) > 0:
                    last_pt = sc(temp_points[-1]); curr_pt = (mouse_curr_x, mouse_curr_y)
                    cv2.line(frame, last_pt, curr_pt, (100, 255, 255), 1)

            if is_editing_id:
                cx, cy = dw//2, dh//2
                cv2.rectangle(frame, (cx-120, cy-40), (cx+120, cy+40), (0,0,0), -1)
                cv2.rectangle(frame, (cx-120, cy-40), (cx+120, cy+40), (0,255,255), 2)
                cv2.putText(frame, "EDYCJA ID:", (cx-110, cy-15), 0, 0.6, (200,200,200), 1)
                cv2.putText(frame, f"{input_buffer}{'|' if blink_state else ''}", (cx-50, cy+25), 0, 1.2, (255,255,255), 3)

        # === INTERFEJS ===
        if info_btn_visible:
            btn_ui_color = (0, 100, 0) if show_help_panel else ((30, 30, 30) if auto_hidden else (50, 50, 50))
            cv2.rectangle(frame, (10, 10), (80, 35), btn_ui_color, -1)
            cv2.rectangle(frame, (10, 10), (80, 35), (200, 200, 200), 1)
            frame = draw_text_pl(frame, "POMOC", (18, 18), 0.45, (255,255,255))

        if not ui_force_hidden and show_help_panel and mode != 'c':
            overlay = frame.copy()
            panel_x, panel_y, panel_w, panel_h = 10, 45, 220, 350
            cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (20, 20, 20), -1)
            cv2.rectangle(overlay, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (100, 100, 100), 1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
            frame = draw_text_pl(frame, "SKRÓTY KLAWISZOWE", (panel_x + 30, panel_y + 15), 0.5, (0, 255, 255))
            cv2.line(frame, (panel_x+10, panel_y+35), (panel_x+panel_w-10, panel_y+35), (100,100,100), 1)
            help_list = [("TRYBY:", ""), (" [P]", "Dodaj Prostokąt"), (" [I]", "Dodaj Wielokąt (4 pkt)"), (" [T]", "Rysuj Trasę"), (" [E]", "Edytuj ID miejsca"),
                         ("AKCJE:", ""), (" [R]", "Resetuj wszystko"), (" [S]", "Zapisz zmiany"), (" [H]", "Pokaż/Ukryj Logi"), (" [Q]", "Wyjdź"), (" [U]", "Ukryj interfejs")]
            curr_y = panel_y + 55
            for k_txt, desc in help_list:
                if desc == "": frame = draw_text_pl(frame, k_txt, (panel_x+10, curr_y), 0.45, (150,150,150)); curr_y += 25
                else: frame = draw_text_pl(frame, k_txt, (panel_x+10, curr_y), 0.45, (0,255,0)); frame = draw_text_pl(frame, desc, (panel_x+50, curr_y), 0.45, (220,220,220)); curr_y += 25

        if buttons_visible and mode != 'c':
            btn_w, btn_h = 220, 35; btn_x, btn_y = dw - btn_w - 10, 10
            col = (100,100,100) if is_editing_id else (0,200,0)
            cv2.rectangle(frame, (btn_x, btn_y), (btn_x+btn_w, btn_y+btn_h), col, -1)
            cv2.rectangle(frame, (btn_x, btn_y), (btn_x+btn_w, btn_y+btn_h), (255,255,255), 1)
            frame = draw_text_pl(frame, "ZATWIERDŹ [ENTER]", (btn_x+20, btn_y+8), 0.55, (255,255,255)) 

        if status_bars_visible:
            instruction = ""; sub_instruction = ""
            if mode == 'c': instruction = "Zaznacz przekątną miejsca (2 punkty) i wciśnij ENTER"
            elif mode == 'p': instruction = "TRYB PROSTOKĄT: Kliknij LPM aby dodać miejsce"; sub_instruction = "ROLKA MYSZY: OBRÓT | PPM: USUŃ MIEJSCE"
            elif mode == 'i': instruction = "TRYB WIELOKĄT: Klikaj narożniki miejsca"; sub_instruction = f"ZAZNACZONO: {len(temp_points)}/4 PKT | PPM: COFNIJ"
            elif mode == 'e': instruction = "TRYB EDYCJI: Kliknij na miejsce, aby zmienić ID"
            elif mode == 't': instruction = "TRYB TRASY: Wyznacz ścieżkę dojazdu"; sub_instruction = f"PUNKTY TRASY: {len(route_points)} | PPM: COFNIJ"
            
            if instruction and not is_editing_id:
                bg_w = 550; bg_x = (dw - bg_w) // 2
                overlay = frame.copy()
                cv2.rectangle(overlay, (bg_x, 10), (bg_x + bg_w, 55 if sub_instruction else 35), (0,0,0), -1)
                frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
                frame = draw_text_pl(frame, instruction, (bg_x + 20, 15), 0.5, (0,255,255))
                if sub_instruction: frame = draw_text_pl(frame, sub_instruction, (bg_x + 20, 35), 0.45, (200,200,200))

        if mode != 'c' and status_bars_visible:
            cv2.rectangle(frame, (0, dh-40), (dw, dh), (0,0,0), -1)
            modes_map = {'p': 'PROSTOKĄT', 'i': 'WIELOKĄT', 't': 'TRASA', 'e': 'EDYCJA ID'}
            status_txt = f"TRYB: {modes_map.get(mode, '?')} (Zmień: P, I, T, E)"
            frame = draw_text_pl(frame, status_txt, (10, dh-30), 0.5, (0,255,255))
            
            hint_text = ""
            if not car_park_positions: hint_text = "KROK 1: Dodaj miejsca parkingowe (Wciśnij P lub I)"
            elif not route_points: hint_text = "KROK 2: Wyznacz trasę przejazdu (Wciśnij T)"
            else: hint_text = "GOTOWE. Wciśnij 'ENTER' aby zapisać i wyjść"
            (tw_hint, th_hint), _ = cv2.getTextSize(hint_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            text_x = dw - tw_hint - 20
            frame = draw_text_pl(frame, hint_text, (text_x, dh-30), 0.5, (180, 255, 180))

        # RYSOWANIE KONSOLI
        if mode != 'c' and not ui_force_hidden:
            console_ui.draw(frame)

        cv2.imshow(win, frame)
        k = cv2.waitKey(10) & 0xFF

        if is_editing_id:
            if k==13 and input_buffer:
                for p in car_park_positions: 
                    if str(p['id'])==input_buffer: p['id'] = car_park_positions[edit_target_index]['id']
                car_park_positions[edit_target_index]['id'] = input_buffer
                log(f"[EDIT] Zmieniono ID na: {input_buffer}")
                is_editing_id=False
            elif k==8: input_buffer = input_buffer[:-1]
            elif 48<=k<=122: input_buffer += chr(k).upper()
        else:
            if k==ord('q'): should_exit=True
            elif k==13:
                if mode == 'c' and len(temp_points)==2:
                    w = abs(temp_points[0][0]-temp_points[1][0])
                    h = abs(temp_points[0][1]-temp_points[1][1])
                    try:
                        with open(TEMP_CALIB_FILE, "w") as f: json.dump({"rect_width": w, "rect_height": h}, f)
                    except: pass
                    should_exit = True
                elif mode != 'c': should_exit = True

            elif k==ord('u'): ui_force_hidden = not ui_force_hidden
            elif k==ord('h'):
                if time.time() - last_h_press_time > 0.3:
                     console_ui.toggle()
                     last_h_press_time = time.time()
            
            elif k==ord('s'): save_data(positions_file)
            elif k==ord('p'): mode='p'; show_help_panel = False; log("[MODE] Przełączono na: PROSTOKĄT")
            elif k==ord('i'): mode='i'; show_help_panel = False; temp_points=[]; log("[MODE] Przełączono na: WIELOKĄT")
            elif k==ord('t'): mode='t'; show_help_panel = False; log("[MODE] Przełączono na: TRASA")
            elif k==ord('e'): mode='e'; show_help_panel = False; log("[MODE] Przełączono na: EDYCJA ID")
            elif k==ord('r'): car_park_positions=[]; route_points=[]; log("[RESET] Usunięto wszystkie punkty")

    try: sys.stdout = sys.__stdout__
    except: pass
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()