"""
Moduł odpowiedzialny za interfejs graficzny konfiguracji parametrów parkingu.
Umożliwia definiowanie wymiarów miejsc, progów detekcji oraz źródeł strumienia wideo.
"""

import json
import os
import argparse
import sys
import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

# --- KONFIGURACJA ŚCIEŻEK (ABSOLUTNE) ---
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "parking_config.json"
TEMP_CALIB_FILE = CONFIG_DIR / "temp_calibration.json"
TEMP_LOT_FILE = CONFIG_DIR / "temp_last_lot.json"
TEMP_URL_FILE = CONFIG_DIR / "temp_url_source.json" 
VIDEO_DIR = BASE_DIR / "data" / "source" / "video"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

COLOR_BG = "#f4f6f9"
COLOR_SUCCESS = "#27ae60"
FONT_LABEL = ("Segoe UI", 10)
FONT_ENTRY = ("Segoe UI", 11)
FONT_HEADER = ("Segoe UI", 14, "bold")

def make_relative(path_str):
    """
    Konwertuje ścieżkę absolutną na relatywną względem folderu głównego projektu.

    Args:
        path_str (str): Ścieżka wejściowa do konwersji.

    Returns:
        str: Ścieżka relatywna ze znormalizowanymi separatorami '/'.
    """
    if not path_str: return ""
    try:
        path_obj = Path(path_str).resolve()
        if BASE_DIR in path_obj.parents:
            return str(path_obj.relative_to(BASE_DIR)).replace("\\", "/")
        return str(path_str).replace("\\", "/")
    except:
        return str(path_str).replace("\\", "/")

def load_or_create_config():
    """
    Ładuje istniejący plik konfiguracyjny lub inicjalizuje nową strukturę słownika.

    Returns:
        dict: Struktura konfiguracji parkingów i parametrów przetwarzania.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"parking_lots": {}, "processing_params": {"gaussian_blur_kernel": [5, 5]}}

def save_config(config):
    """
    Zapisuje bieżący stan konfiguracji do pliku JSON.

    Args:
        config (dict): Słownik konfiguracyjny do zapisu.
    """
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def save_last_lot_name(lot_name: str):
    """
    Zapisuje nazwę ostatnio edytowanego parkingu do pliku tymczasowego.

    Args:
        lot_name (str): Nazwa parkingu.
    """
    try:
        with open(TEMP_LOT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"lot_name": lot_name}, f)
    except: pass

def load_temp_url():
    """
    Odczytuje adres URL z pliku tymczasowego wygenerowanego przez Launcher.

    Returns:
        str: Adres URL źródła wideo lub pusty ciąg znaków.
    """
    if TEMP_URL_FILE.exists():
        try:
            with open(TEMP_URL_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("url", "")
        except: pass
    return ""

def cleanup_temp_url():
    """Usuwa plik tymczasowy zawierający adres URL źródła."""
    if TEMP_URL_FILE.exists():
        try: os.remove(TEMP_URL_FILE)
        except: pass

def create_parking_lot(config, name, rect_width, rect_height, threshold, image_path, video_path):
    """
    Tworzy nową sekcję parkingu w głównej konfiguracji i zapisuje zmiany.

    Args:
        config (dict): Główny słownik konfiguracji.
        name (str): Nazwa parkingu.
        rect_width (int): Szerokość prostokąta detekcji.
        rect_height (int): Wysokość prostokąta detekcji.
        threshold (int): Próg detekcji pikseli.
        image_path (str): Ścieżka do obrazu referencyjnego.
        video_path (str): Ścieżka do źródła wideo.

    Returns:
        str: Relatywna ścieżka do pliku pozycji .pickle.
    """
    positions_file = f"data/parking_lots/{name}_positions"
    rel_image = make_relative(image_path)
    rel_video = make_relative(video_path)

    new_lot = {
        "name": name,
        "rect_width": int(rect_width),
        "rect_height": int(rect_height),
        "threshold": int(threshold),
        "positions_file": positions_file,
        "source_image": rel_image,
        "video_source": rel_video 
    }
    
    config["parking_lots"][name] = new_lot
    save_config(config)
    save_last_lot_name(name)
    cleanup_temp_url() 
    print(f"[SUCCESS] Zapisano konfigurację: {name}")
    return positions_file

def gui_config_form(default_name, default_img, existing_names, def_w=50, def_h=100):
    """
    Wyświetla formularz GUI do wprowadzania parametrów nowego parkingu.

    Args:
        default_name (str): Sugerowana nazwa parkingu.
        default_img (str): Ścieżka do wybranego obrazu.
        existing_names (list): Lista nazw już istniejących parkingów.
        def_w (int): Domyślna szerokość miejsca.
        def_h (int): Domyślna wysokość miejsca.

    Returns:
        dict: Słownik zawierający wprowadzone dane lub flagę saved=False.
    """
    result = {"saved": False}
    root = tk.Tk()
    root.title("Konfiguracja Parametrów")
    
    ws = root.winfo_screenwidth(); hs = root.winfo_screenheight()
    root.geometry(f'600x600+{int(ws/2-300)}+{int(hs/2-300)}')
    root.configure(bg=COLOR_BG)
    root.attributes("-topmost", True) 

    tk.Label(root, text="Krok 3: Parametry Parkingu", font=FONT_HEADER, bg=COLOR_BG, fg="#2c3e50").pack(pady=20)
    form_frame = tk.Frame(root, bg=COLOR_BG)
    form_frame.pack(fill="both", expand=True, padx=40)

    def create_field(label_text, default_val, field_type="text"):
        tk.Label(form_frame, text=label_text, font=FONT_LABEL, bg=COLOR_BG, anchor="w").pack(fill="x", pady=(10, 0))
        input_frame = tk.Frame(form_frame, bg=COLOR_BG)
        input_frame.pack(fill="x", pady=(5, 0))
        entry = tk.Entry(input_frame, font=FONT_ENTRY, relief="flat", highlightthickness=1)
        entry.insert(0, str(default_val))
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        
        if field_type == "video_picker":
            def browse_file():
                f = filedialog.askopenfilename(initialdir=str(VIDEO_DIR), title="Wybierz wideo", filetypes=(("Wideo", "*.mp4 *.avi"), ("Wszystkie", "*.*")))
                if f: 
                    entry.delete(0, tk.END)
                    entry.insert(0, make_relative(f))
            tk.Button(input_frame, text="📂 Plik", command=browse_file).pack(side="right", padx=5)
        return entry

    calib_w, calib_h = def_w, def_h
    if TEMP_CALIB_FILE.exists():
        try:
            with open(TEMP_CALIB_FILE, 'r') as f:
                cdata = json.load(f)
                calib_w = cdata.get("rect_width", def_w)
                calib_h = cdata.get("rect_height", def_h)
            os.remove(TEMP_CALIB_FILE)
        except: pass

    auto_url = load_temp_url()
    default_video = ""
    if auto_url:
        default_video = auto_url
    else:
        try:
            base = os.path.splitext(os.path.basename(default_img))[0]
            pot_vid = VIDEO_DIR / f"{base}.mp4"
            if pot_vid.exists(): 
                default_video = make_relative(str(pot_vid))
            else:
                default_video = make_relative(default_img)
        except: 
            default_video = default_img

    ent_name = create_field("Nazwa systemowa (np. parking_tyl):", default_name)
    ent_width = create_field("Szerokość miejsca (px):", calib_w)
    ent_height = create_field("Wysokość miejsca (px):", calib_h)
    ent_thresh = create_field("Próg detekcji (Domyślnie 900):", "900")
    ent_video = create_field("Źródło wideo (Plik .mp4 lub URL):", default_video, "video_picker")

    def on_save():
        try:
            name = ent_name.get().strip()
            if not name: messagebox.showerror("Błąd", "Brak nazwy!"); return
            
            if name in existing_names:
                if not messagebox.askyesno("Konflikt", f"'{name}' już istnieje. Nadpisać?"): return
            
            result.update({
                "name": name,
                "w": int(ent_width.get()),
                "h": int(ent_height.get()),
                "t": int(ent_thresh.get()),
                "vid": ent_video.get().strip(),
                "saved": True
            })
            root.destroy()
        except ValueError: messagebox.showerror("Błąd", "Wymiary muszą być liczbami!")

    tk.Button(root, text="ZAPISZ KONFIGURACJĘ", font=("Segoe UI", 12, "bold"), bg=COLOR_SUCCESS, fg="white", command=on_save).pack(pady=30, fill="x", padx=40)
    root.mainloop()
    return result

def main():
    """Główny punkt wejścia modułu. Zarządza parsowaniem argumentów i procesem zapisu."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--default_name', type=str, default='new_parking')
    parser.add_argument('--image_path', type=str, default='')
    args = parser.parse_args()

    config = load_or_create_config()
    existing_names = list(config.get("parking_lots", {}).keys())
    
    data = gui_config_form(args.default_name, args.image_path, existing_names)

    if data["saved"]:
        create_parking_lot(config, data["name"], data["w"], data["h"], data["t"], args.image_path, data["vid"])
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()