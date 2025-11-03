import json
import os

CONFIG_FILE = "config/parking_config.json"
CALIBRATION_OUTPUT_FILE = "config/temp_calibration_data.json" 
TEMP_LOT_FILE = "config/temp_last_lot.json"

def load_or_create_config():
    """Wczytuje istniejący plik konfiguracyjny lub tworzy nowy z domyślną strukturą."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        return {
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


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
def save_last_lot_name(lot_name: str):
    """Saves the name of the last successfully created lot to a temporary file."""
    try:
        os.makedirs(os.path.dirname(TEMP_LOT_FILE), exist_ok=True)
        with open(TEMP_LOT_FILE, 'w') as f:
            json.dump({"lot_name": lot_name}, f)
        print(f"✅ Nazwa parkingu '{lot_name}' zapisana tymczasowo.")
    except Exception as e:
        print(f"❌ Błąd zapisu nazwy parkingu: {e}")


def create_parking_lot(config, name, rect_width, rect_height, threshold, image_path, video_path):
    """Dodaje nową konfigurację parkingu do config.json"""
    positions_file = f"data/parking_lots/{name}_positions"
    
    new_lot = {
        "name": name.replace('_', ' ').title(),
        "rect_width": rect_width,
        "rect_height": rect_height,
        "threshold": threshold,
        "positions_file": positions_file,
        "source_image": image_path or f"data/source/img/{name}.png",
        "video_source": video_path or f"data/source/video/{name}.mp4"
    }
    
    config["parking_lots"][name] = new_lot
    os.makedirs("data/parking_lots", exist_ok=True)
    save_config(config)
    save_last_lot_name(name)
    
    print(f"\n✅ Dodano konfigurację '{name}'!")
    print(f"📁 Plik pozycji: {positions_file}")
    print(f"🖼️  Obraz: {new_lot['source_image']}")
    print(f"🎥  Wideo: {new_lot['video_source']}")
    print(f"\n📋 Następne kroki:")
    print(f"1. Oznacz miejsca parkingowe:")
    print(f"   python car_park_coordinate_generator.py --lot {name}")
    print(f"2. Uruchom monitoring:")
    print(f"   python app.py --lot {name}")

def read_and_clean_calibration_data():
    """Odczytuje tymczasowe dane kalibracji i usuwa plik."""
    if os.path.exists(CALIBRATION_OUTPUT_FILE):
        try:
            with open(CALIBRATION_OUTPUT_FILE, 'r') as f:
                data = json.load(f)
            os.remove(CALIBRATION_OUTPUT_FILE) # Usuwamy plik, aby nie używać starych danych
            print(f"✅ Automatycznie wczytano wymiary z kalibracji: W={data.get('rect_width')}, H={data.get('rect_height')}")
            return data.get('rect_width'), data.get('rect_height')
        except Exception as e:
            print(f"❌ Błąd odczytu/usuwania pliku kalibracji: {e}")
            return None, None
    return None, None


def interactive_mode():
    """Uruchamia tryb interaktywny (z pytaniami w konsoli)."""
    config = load_or_create_config()
    print("Dostępne konfiguracje parkingów:")
    for n in config["parking_lots"].keys():
        print(f"  - {n}")

    print("\n=== Dodawanie nowej konfiguracji parkingu ===")
    
    # === AUTOMATYCZNE POBIERANIE DANYCH KALIBRACJI ===
    default_width = 107
    default_height = 48
    
    calibrated_width, calibrated_height = read_and_clean_calibration_data()
    
    if calibrated_width is not None and calibrated_height is not None:
        default_width = calibrated_width
        default_height = calibrated_height
    
    print(f"--- Wymiary do wprowadzenia (domyślnie: {default_width}x{default_height}px) ---")
    # =========================================
    
    lot_name = input("Podaj nazwę nowego parkingu (np. 'mall_parking'): ").strip()

    if lot_name in config["parking_lots"]:
        overwrite = input(f"Konfiguracja '{lot_name}' już istnieje. Nadpisać? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Anulowano.")
            return

    display_name = input(f"Podaj wyświetlaną nazwę (domyślnie '{lot_name.replace('_', ' ').title()}'): ").strip()
    if not display_name:
        display_name = lot_name.replace('_', ' ').title()

    try:
        rect_width = int(input(f"Szerokość prostokąta miejsca parkingowego (domyślnie {default_width}): ") or str(default_width))
        rect_height = int(input(f"Wysokość prostokąta miejsca parkingowego (domyślnie {default_height}): ") or str(default_height))
        threshold = int(input("Próg klasyfikacji (domyślnie 900): ") or "900")
    except ValueError:
        print("Błędne wartości liczbowe. Używam domyślnych.")
        rect_width, rect_height, threshold = default_width, default_height, 900

    image_path = 'data/source/img/'+input("Ścieżka do obrazu referencyjnego:(w folderze data/source/img) e.g plik.png ").strip()
    
    video_path = input("Ścieżka do wideo (plik) lub URL kamery IP (np. rtsp://user:pass@ip:port/stream): ").strip()

    create_parking_lot(config, lot_name, rect_width, rect_height, threshold, image_path, video_path)


if __name__ == "__main__":
    interactive_mode()
