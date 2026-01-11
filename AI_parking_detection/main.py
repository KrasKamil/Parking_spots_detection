"""
Główny moduł startowy (Launcher) systemu rekomendacji miejsc parkingowych.

Zarządza interfejsem użytkownika (GUI) opartym na bibliotece tkinter, umożliwiając:
1. Wybór i uruchamianie istniejących konfiguracji monitoringu.
2. Tworzenie nowych projektów poprzez import obrazów lub klatek z wideo/YouTube.
3. Zarządzanie plikami konfiguracji i obrazami (edycja parametrów, usuwanie).
4. Koordynację przepływu danych między modułami kalibracji, edycji geometrii i detekcji.
"""

import os
import sys
import json
import cv2
import datetime
import subprocess
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
from pathlib import Path

# --- KONFIGURACJA ŚCIEŻEK ---
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "source" / "img"
VIDEO_DIR = DATA_DIR / "source" / "video" 
CONFIG_FILE = CONFIG_DIR / "parking_config.json"
TEMP_URL_FILE = CONFIG_DIR / "temp_url_source.json"

sys.path.append(str(SRC_DIR))

try:
    from src.utils import get_direct_youtube_url
except ImportError:
    def get_direct_youtube_url(url): 
        """Fallback w przypadku braku modułu utils."""
        return url 

# --- NAPRAWA SKALOWANIA DPI (WINDOWS) ---
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Tworzenie niezbędnej struktury katalogów
IMG_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# --- KONFIGURACJA WIZUALNA GUI ---
COLOR_BG = "#f4f6f9"
COLOR_HEADER = "#2c3e50"
COLOR_ACCENT = "#3498db"
COLOR_SUCCESS = "#27ae60"
COLOR_TEXT_HEADER = "#ecf0f1"
COLOR_LIST_BG = "#ffffff"
FONT_MAIN = ("Segoe UI", 10)
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_SUBHEADER = ("Segoe UI", 10)

def make_relative(path_str):
    """
    Konwertuje ścieżkę absolutną na relatywną względem katalogu głównego projektu.

    Służy do zachowania przenośności plików konfiguracyjnych JSON między różnymi systemami.

    Args:
        path_str (str): Pełna ścieżka do pliku lub katalogu.

    Returns:
        str: Ścieżka relatywna lub oryginalny ciąg znaków w przypadku błędu.
    """
    if not path_str: return ""
    
    if "://" in str(path_str) or str(path_str).startswith("http"):
        return str(path_str)
    
    try:
        path_obj = Path(path_str).resolve()
        return str(path_obj.relative_to(BASE_DIR))
    except (ValueError, Exception):
        return path_str

def load_config_list():
    """
    Pobiera nazwy wszystkich zdefiniowanych parkingów z pliku parking_config.json.

    Returns:
        list: Lista unikalnych nazw parkingów, z wyłączeniem wpisów technicznych.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                lots = data.get("parking_lots", {})
                return [name for name in lots.keys() if name not in ['default', 'empty_calibration']]
        except json.JSONDecodeError:
            return []
    return []

def get_last_added_lot_name():
    """
    Odczytuje nazwę ostatnio utworzonego projektu z pliku tymczasowego.

    Umożliwia automatyczne przejście do edytora po zakończeniu kroku konfiguracji.

    Returns:
        str|None: Nazwa parkingu lub None, jeśli zapis nie został odnaleziony.
    """
    temp_file = CONFIG_DIR / "temp_last_lot.json"
    if temp_file.exists():
        try:
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('lot_name')
        except Exception:
            return None
    return None

def show_topmost_message(title, message, is_error=False):
    """
    Wyświetla systemowe okno komunikatu wymuszone na wierzch wszystkich okien.

    Args:
        title (str): Tytuł okna dialogowego.
        message (str): Treść wyświetlanej wiadomości.
        is_error (bool): Jeśli True, używa ikony błędu zamiast informacji.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    if is_error:
        messagebox.showerror(title, message, parent=root)
    else:
        messagebox.showinfo(title, message, parent=root)
    root.destroy()

def capture_frame_from_source(video_source, lot_name_prefix):
    """
    Pobiera pojedynczą klatkę ze źródła wideo i zapisuje ją jako obraz referencyjny PNG.

    Obsługuje pliki lokalne oraz strumienie sieciowe (YouTube, RTSP, HTTP) przy użyciu OpenCV.

    Args:
        video_source (str): Ścieżka do pliku wideo lub adres URL strumienia.
        lot_name_prefix (str): Nazwa projektu używana jako podstawa nazwy pliku.

    Returns:
        str|None: Ścieżka do zapisanego pliku .png lub None w przypadku niepowodzenia.
    """
    cap = None
    try:
        final_source = get_direct_youtube_url(video_source)
        cap = cv2.VideoCapture(final_source, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(final_source)
        
        if not cap.isOpened():
            show_topmost_message("Błąd", f"Nie można otworzyć źródła: {video_source}", is_error=True)
            return None
        
        ret, frame = cap.read()
        if ret:
            safe_name = "".join([c if c.isalnum() or c in (' ', '_', '-') else "" for c in lot_name_prefix]).strip().replace(' ', '_')
            filename = f"{safe_name}.png"
            filepath = IMG_DIR / filename
            
            if filepath.exists():
                root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                response = messagebox.askyesnocancel(
                    "Plik istnieje", 
                    f"Plik '{filename}' już istnieje.\n\nTAK - Nadpisz\nNIE - Dodaj datę\nANULUJ - Przerwij",
                    parent=root
                )
                root.destroy()
                if response is None: return None
                elif response is False:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{safe_name}_{timestamp}.png"
                    filepath = IMG_DIR / filename
            
            cv2.imwrite(str(filepath), frame)
            return str(filepath)
        else:
            show_topmost_message("Błąd", "Nie udało się pobrać klatki (strumień pusty).", is_error=True)
            return None
    except Exception as e:
        show_topmost_message("Wyjątek", f"Błąd OpenCV: {e}", is_error=True)
        return None
    finally:
        if cap: cap.release()

def delete_parking_lot(lot_name):
    """
    Usuwa parking z konfiguracji systemowej oraz powiązany z nim plik pozycji.

    Args:
        lot_name (str): Unikalna nazwa parkingu do usunięcia.

    Returns:
        bool: True, jeśli proces usuwania zakończył się sukcesem.
    """
    if not CONFIG_FILE.exists(): return False
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if lot_name in data["parking_lots"]:
            pos_file = data["parking_lots"][lot_name].get("positions_file", "")
            if pos_file:
                pos_path = Path(pos_file) if os.path.isabs(pos_file) else BASE_DIR / pos_file
                try:
                    if pos_path.exists(): os.remove(pos_path)
                except OSError: pass

            del data["parking_lots"][lot_name]
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return True
    except Exception:
        return False
    return False

def open_config_editor(root, lot_name):
    """
    Wyświetla okno edycji parametrów technicznych zapisanego projektu.

    Umożliwia zmianę źródła wideo, obrazu referencyjnego, wymiarów miejca i progu detekcji.

    Args:
        root (tk.Tk): Obiekt nadrzędny dla okna modalnego (Toplevel).
        lot_name (str): Nazwa parkingu pobrana z listy konfiguracji.
    """
    if not CONFIG_FILE.exists(): return
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        full_config = json.load(f)
    
    lot_data = full_config["parking_lots"].get(lot_name)
    if not lot_data: return

    edit_win = tk.Toplevel(root)
    edit_win.title(f"Edycja: {lot_name}")
    edit_win.geometry("600x480")
    edit_win.configure(bg=COLOR_BG)
    edit_win.grab_set()

    tk.Label(edit_win, text=f"Konfiguracja: {lot_name}", font=("Segoe UI", 12, "bold"), bg=COLOR_BG).pack(pady=10)
    form_frame = tk.Frame(edit_win, bg=COLOR_BG)
    form_frame.pack(fill="both", expand=True, padx=20)

    entries = {}

    def add_field(label_text, key, read_only=False, is_path=False):
        """Pomocnicza funkcja generująca wiersz formularza edycji."""
        row = tk.Frame(form_frame, bg=COLOR_BG)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label_text, width=20, anchor="w", bg=COLOR_BG).pack(side="left")
        raw_val = lot_data.get(key, "")
        display_val = make_relative(str(raw_val)) if is_path else str(raw_val)
        var = tk.StringVar(value=display_val)
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        if read_only: entry.config(state="readonly")
        entries[key] = var

    # Pola formularza
    add_field("Nazwa (ID):", "name", read_only=True)

    row_src = tk.Frame(form_frame, bg=COLOR_BG)
    row_src.pack(fill="x", pady=5)
    tk.Label(row_src, text="Źródło (Plik/URL):", width=20, anchor="w", bg=COLOR_BG).pack(side="left")
    val_src = lot_data.get("video_source", "")
    var_src = tk.StringVar(value=make_relative(val_src))
    ent_src = ttk.Entry(row_src, textvariable=var_src)
    ent_src.pack(side="left", fill="x", expand=True)
    
    def browse_source():
        """Otwiera eksplorator plików dla wyboru źródła wideo."""
        f = filedialog.askopenfilename(title="Wybierz wideo", initialdir=str(VIDEO_DIR), 
                                       filetypes=(("Wideo", "*.mp4 *.avi"), ("Wszystkie", "*.*")))
        if f: var_src.set(make_relative(f))
            
    ttk.Button(row_src, text="...", width=3, command=browse_source).pack(side="right", padx=(5,0))
    entries["video_source"] = var_src

    add_field("Szerokość miejsca:", "rect_width")
    add_field("Wysokość miejsca:", "rect_height")
    add_field("Czułość (Threshold):", "threshold")
    
    row_ref = tk.Frame(form_frame, bg=COLOR_BG)
    row_ref.pack(fill="x", pady=5)
    tk.Label(row_ref, text="Obraz Bazowy:", width=20, anchor="w", bg=COLOR_BG).pack(side="left")
    val_ref = lot_data.get("source_image", "")
    var_ref = tk.StringVar(value=make_relative(val_ref))
    ent_ref = ttk.Entry(row_ref, textvariable=var_ref)
    ent_ref.pack(side="left", fill="x", expand=True)
    
    def browse_ref():
        """Otwiera eksplorator plików dla wyboru obrazu referencyjnego."""
        f = filedialog.askopenfilename(title="Wybierz obraz bazowy", initialdir=str(IMG_DIR))
        if f: var_ref.set(make_relative(f))
            
    ttk.Button(row_ref, text="...", width=3, command=browse_ref).pack(side="right", padx=(5,0))
    entries["source_image"] = var_ref

    def save_changes():
        """Waliduje i zapisuje wprowadzone zmiany do głównego pliku JSON."""
        try:
            w, h, t = int(entries["rect_width"].get()), int(entries["rect_height"].get()), int(entries["threshold"].get())
            lot_data.update({
                "video_source": entries["video_source"].get(),
                "source_image": entries["source_image"].get(),
                "rect_width": w, "rect_height": h, "threshold": t
            })
            full_config["parking_lots"][lot_name] = lot_data
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=4)
            messagebox.showinfo("Sukces", "Zapisano zmiany!", parent=edit_win)
            edit_win.destroy()
        except ValueError:
            messagebox.showerror("Błąd", "Wymiary muszą być liczbami!", parent=edit_win)

    tk.Button(edit_win, text="💾 ZAPISZ ZMIANY", bg=COLOR_SUCCESS, fg="white", 
              font=("Segoe UI", 10, "bold"), command=save_changes).pack(pady=20, ipadx=20)

def gui_main_menu():
    """
    Tworzy i uruchamia główne okno aplikacji Launcher.

    Returns:
        dict: Słownik akcji zawierający 'action' (np. 'run', 'create') i powiązane 'data'.
    """
    selection = {"action": None, "data": None}
    root = tk.Tk()
    root.title("System Rekomendacji Miejsc Parkingowych")
    
    w, h = 950, 600
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'{w}x{h}+{int((ws/2)-(w/2))}+{int((hs/2)-(h/2))}')
    root.configure(bg=COLOR_BG)

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TButton", font=FONT_MAIN, padding=6, relief="flat")
    style.configure("Run.TButton", background=COLOR_SUCCESS, foreground="white", font=("Segoe UI", 10, "bold"))
    style.map("Run.TButton", background=[("active", "#219150")])
    style.configure("Create.TButton", background=COLOR_ACCENT, foreground="white", font=("Segoe UI", 10, "bold"))
    style.map("Create.TButton", background=[("active", "#2980b9")])

    def save_temp_url(url):
        """Zapisuje adres URL do pliku tymczasowego dla modułu konfiguracji."""
        try:
            with open(TEMP_URL_FILE, 'w', encoding='utf-8') as f:
                json.dump({"url": url}, f)
        except Exception: pass

    def clear_temp_url():
        """Usuwa pozostałości po zapisach tymczasowych adresów URL."""
        if TEMP_URL_FILE.exists():
            try: os.remove(TEMP_URL_FILE)
            except: pass

    # Header GUI
    header_frame = tk.Frame(root, bg=COLOR_HEADER, height=80)
    header_frame.pack(side="top", fill="x")
    tk.Label(header_frame, text="SYSTEM REKOMENDACJI MIEJSC PARKINGOWYCH", 
             bg=COLOR_HEADER, fg=COLOR_TEXT_HEADER, font=FONT_HEADER).pack(pady=(15, 0))
    tk.Label(header_frame, text="Panel Sterowania | Praca Inżynierska", 
             bg=COLOR_HEADER, fg="#bdc3c7", font=FONT_SUBHEADER).pack(pady=(0, 15))

    main_frame = tk.Frame(root, bg=COLOR_BG)
    main_frame.pack(fill="both", expand=True, padx=20, pady=20)

    # Panel lewy: Zapisane konfiguracje
    left_frame = tk.LabelFrame(main_frame, text=" ✅ Zapisane Konfiguracje ", 
                               bg=COLOR_BG, font=("Segoe UI", 11, "bold"), fg=COLOR_SUCCESS)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    list_saved = tk.Listbox(left_frame, font=("Consolas", 11), bg=COLOR_LIST_BG, 
                            selectbackground=COLOR_SUCCESS, borderwidth=0, highlightthickness=1, relief="solid")
    list_saved.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    def refresh_saved_list():
        """Odświeża listę dostępnych projektów w komponencie Listbox."""
        list_saved.delete(0, tk.END)
        saved_lots = load_config_list()
        if saved_lots:
            for lot in saved_lots: list_saved.insert(tk.END, f"🅿 {lot}")
        else:
            list_saved.insert(tk.END, "(Brak konfiguracji)")
    refresh_saved_list()

    def get_selected_lot():
        """Zwraca nazwę projektu wybranego przez użytkownika w Listboxie."""
        try:
            sel = list_saved.curselection()[0]
            name = list_saved.get(sel).replace("🅿 ", "")
            return name if name != "(Brak konfiguracji)" else None
        except IndexError: return None

    def on_delete_config(event=None):
        """Obsługuje proces usuwania wybranej konfiguracji po potwierdzeniu."""
        name = get_selected_lot()
        if not name: return
        if messagebox.askyesno("Usuwanie", f"Czy usunąć konfigurację '{name}'?", parent=root):
            if delete_parking_lot(name): refresh_saved_list()
    list_saved.bind("<Delete>", on_delete_config)

    # Menu kontekstowe Listboxa
    context_menu_config = tk.Menu(root, tearoff=0)
    context_menu_config.add_command(label="⚙ Edytuj Ustawienia", command=lambda: open_config_editor(root, get_selected_lot()))
    context_menu_config.add_command(label="❌ Usuń Konfigurację", command=on_delete_config)

    def on_right_click_config(event):
        """Wyświetla menu kontekstowe po kliknięciu PPM na konfigurację."""
        try:
            list_saved.selection_clear(0, tk.END)
            idx = list_saved.nearest(event.y)
            list_saved.selection_set(idx)
            list_saved.activate(idx)
            if get_selected_lot(): context_menu_config.post(event.x_root, event.y_root)
        except: pass
    list_saved.bind("<Button-3>", on_right_click_config)

    def on_run():
        """Ustawia akcję na uruchomienie monitoringu i zamyka okno GUI."""
        name = get_selected_lot()
        if name:
            selection["action"] = "run"; selection["data"] = name; root.destroy()
        else: messagebox.showwarning("Wybór", "Wybierz parking!", parent=root)

    def on_edit_only():
        """Ustawia akcję na edycję geometrii i zamyka okno GUI."""
        name = get_selected_lot()
        if name:
            selection["action"] = "edit"; selection["data"] = name; root.destroy()
        else: messagebox.showwarning("Wybór", "Wybierz parking!", parent=root)

    ttk.Button(left_frame, text="▶ URUCHOM MONITORING", style="Run.TButton", command=on_run).pack(fill="x", padx=10, pady=5)
    ttk.Button(left_frame, text="✏ Edytuj Miejsca (Geometria)", command=on_edit_only).pack(fill="x", padx=10, pady=(0, 10))

    # Panel prawy: Nowy projekt
    right_frame = tk.LabelFrame(main_frame, text=" 📂 Nowy Projekt (Obrazy) ", 
                                bg=COLOR_BG, font=("Segoe UI", 11, "bold"), fg=COLOR_ACCENT)
    right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))
    
    tk.Label(right_frame, text="Wybierz obraz z listy poniżej:", bg=COLOR_BG, 
             fg="#7f8c8d", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(5,0))
    list_raw = tk.Listbox(right_frame, font=("Consolas", 11), bg=COLOR_LIST_BG, 
                          selectbackground=COLOR_ACCENT, borderwidth=0, highlightthickness=1, relief="solid")
    list_raw.pack(side="left", fill="both", expand=True, padx=10, pady=(5, 10))

    def refresh_raw_list():
        """Odświeża listę dostępnych plików obrazów w folderze źródłowym."""
        list_raw.delete(0, tk.END)
        if IMG_DIR.exists():
            files = sorted([f for f in os.listdir(IMG_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            for f in files: list_raw.insert(tk.END, f"📄 {f}")
        else: list_raw.insert(tk.END, "Brak img")
    refresh_raw_list()

    def on_delete_image():
        """Usuwa fizyczny plik obrazu z folderu source/img."""
        try:
            sel = list_raw.curselection()[0]
            filename = list_raw.get(sel).replace("📄 ", "")
            filepath = IMG_DIR / filename
            if messagebox.askyesno("Usuwanie pliku", f"Czy usunąć plik {filename}?", parent=root):
                try:
                    os.remove(filepath)
                    refresh_raw_list()
                except Exception as e:
                    messagebox.showerror("Błąd", f"Błąd: {e}", parent=root)
        except IndexError: pass

    context_menu_img = tk.Menu(root, tearoff=0)
    context_menu_img.add_command(label="🗑️ Usuń plik obrazu", command=on_delete_image)

    def on_right_click_img(event):
        """Menu kontekstowe dla zarządzania plikami obrazów."""
        try:
            list_raw.selection_clear(0, tk.END); idx = list_raw.nearest(event.y)
            list_raw.selection_set(idx); list_raw.activate(idx)
            context_menu_img.post(event.x_root, event.y_root)
        except: pass
    list_raw.bind("<Button-3>", on_right_click_img)
    list_raw.bind("<Delete>", lambda e: on_delete_image())

    def on_create():
        """Uruchamia kreator konfiguracji na podstawie wybranego pliku obrazu."""
        try:
            sel = list_raw.curselection()[0]
            filename = list_raw.get(sel).replace("📄 ", "")
            clear_temp_url()
            selection["action"] = "create"; selection["data"] = str(IMG_DIR / filename); root.destroy()
        except IndexError: messagebox.showwarning("Wybór", "Wybierz obraz z listy!", parent=root)

    def on_url():
        """Inicjuje pobieranie obrazu ze strumienia wideo (YouTube/RTSP/HTTP)."""
        url = simpledialog.askstring("Pobieranie", "Wklej URL (YouTube/RTSP):", parent=root)
        if url:
            name = simpledialog.askstring("Nazwa", "Podaj nazwę projektu dla pliku graficznego:", parent=root)
            if name:
                loading = tk.Toplevel(root)
                loading.title("Pobieranie..."); loading.geometry("300x100")
                tk.Label(loading, text="⏳ Pobieranie klatki ze źródła...").pack(expand=True)
                loading.update()
                path = capture_frame_from_source(url, name)
                loading.destroy() 
                if path:
                    save_temp_url(url)
                    selection["action"] = "create"; selection["data"] = path; root.destroy()
    
    def on_browse():
        """Pozwala zaimportować plik graficzny z dowolnej lokalizacji na dysku."""
        path = filedialog.askopenfilename(initialdir=str(IMG_DIR), title="Wybierz plik", 
                                          filetypes=(("Obrazy", "*.png *.jpg"), ("Wszystkie", "*.*")))
        if path:
            clear_temp_url(); selection["action"] = "create"; selection["data"] = path; root.destroy()

    # Przyciski sterujące prawym panelem
    btn_box = tk.Frame(right_frame, bg=COLOR_BG)
    btn_box.pack(fill="x", padx=10, pady=10)
    ttk.Button(btn_box, text="📂 Z Pliku...", command=on_browse).pack(side="left", fill="x", expand=True, padx=(0,5))
    ttk.Button(btn_box, text="🌐 Z Wideo...", command=on_url).pack(side="right", fill="x", expand=True, padx=(5,0))
    ttk.Button(right_frame, text="➕ START KREATORA", style="Create.TButton", command=on_create).pack(fill="x", padx=10, pady=(0, 10))

    root.mainloop()
    return selection

def main():
    """
    Główna pętla sterująca cyklem życia aplikacji.
    
    Interpretuje wyniki wybrane w GUI (gui_main_menu) i wywołuje odpowiednie
    podprogramy (app.py, car_park_coordinate_generator.py, add_parking_config.py)
    używając mechanizmu subprocess.
    """
    while True:
        sel = gui_main_menu()
        action, data = sel["action"], sel["data"]
        if not action: sys.exit(0)
        cwd_path = str(BASE_DIR)

        try:
            if action == "run":
                # Uruchomienie głównego systemu detekcji
                subprocess.run([sys.executable, "app.py", "--lot", data], cwd=cwd_path, check=True)

            elif action == "edit":
                # 1. Pobierz ścieżki z konfiguracji
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                lot_info = config_data["parking_lots"].get(data, {})
                img_path = BASE_DIR / lot_info.get("source_image", "")
                pos_path = BASE_DIR / lot_info.get("positions_file", "")

                # 2. Sprawdź czy obraz bazowy w ogóle istnieje
                if not img_path.exists():
                    show_topmost_message("Błąd Krytyczny", 
                        f"Nie znaleziono pliku graficznego: {img_path.name}\n"
                        "Nie można edytować miejsc bez obrazu tła.", is_error=True)
                    continue

                # 3. Jeśli plik pozycji nie istnieje, uprzedź użytkownika
                if not pos_path.exists():
                    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                    messagebox.showinfo("Nowa Geometria", 
                        f"Konfiguracja miejsc dla '{data}' nie istnieje.\n"
                        "Zostanie teraz otwarty edytor, abyś mógł narysować je od zera.", parent=root)
                    root.destroy()

                # 4. Uruchom edytor
                result = subprocess.run([sys.executable, "car_park_coordinate_generator.py", "--lot", data], 
                               cwd=cwd_path)
                
                # 5. Sprawdź efekt końcowy
                if result.returncode == 0 and pos_path.exists():
                    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                    if messagebox.askyesno("Gotowe", f"Zapisano geometrię dla '{data}'. Uruchomić monitoring?", parent=root):
                        root.destroy(); subprocess.run([sys.executable, "app.py", "--lot", data], cwd=cwd_path, check=True)
                    else: root.destroy()
                elif result.returncode != 0:
                    show_topmost_message("Błąd", "Wystąpił problem techniczny podczas uruchamiania edytora.", is_error=True)
            
            elif action == "create":
                # Sekwencja kreatora nowego parkingu
                image_path = data
                default_name = os.path.splitext(os.path.basename(image_path))[0].lower().replace(' ', '_')
                root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                lot_name = simpledialog.askstring("Krok 1/4: Nazwa", "Podaj unikalną nazwę projektu:", 
                                                  initialvalue=default_name, parent=root)
                root.destroy()
                if not lot_name: continue

                # Krok 2: Kalibracja skali
                subprocess.run([sys.executable, "car_park_coordinate_generator.py", "--lot", "empty_calibration", 
                                "--image", image_path, "--mode", "c"], cwd=cwd_path, check=True)
                
                # Krok 3: Konfiguracja parametrów JSON
                subprocess.run([sys.executable, "add_parking_config.py", "--default_name", lot_name, 
                                "--image_path", image_path], cwd=cwd_path, check=True)
                
                # Krok 4: Interaktywne rysowanie
                real_lot_name = get_last_added_lot_name()
                if real_lot_name == lot_name:
                    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                    do_draw = messagebox.askyesno("Krok 4/4: Rysowanie", "Konfiguracja gotowa. Czy chcesz teraz narysować miejsca?", parent=root)
                    root.destroy()
                    if do_draw:
                        subprocess.run([sys.executable, "car_park_coordinate_generator.py", "--lot", real_lot_name], 
                                       cwd=cwd_path, check=True)
                        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                        if messagebox.askyesno("Gotowe", "Czy uruchomić system monitoringu?", parent=root):
                            root.destroy(); subprocess.run([sys.executable, "app.py", "--lot", real_lot_name], cwd=cwd_path, check=True)
                        else: root.destroy()

        except subprocess.CalledProcessError as e:
            show_topmost_message("Błąd procesu", f"Wystąpił błąd podczas pracy podprogramu: {e.returncode}", is_error=True)
        except Exception as e:
            print(f"[CRITICAL ERROR] {e}")

if __name__ == "__main__":
    main()