import json
import os

CONFIG_FILE = "config/parking_config.json"


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
    
    print(f"\n✅ Dodano konfigurację '{name}'!")
    print(f"📁 Plik pozycji: {positions_file}")
    print(f"🖼️  Obraz: {new_lot['source_image']}")
    print(f"🎥  Wideo: {new_lot['video_source']}")
    print(f"\n📋 Następne kroki:")
    print(f"1. Oznacz miejsca parkingowe:")
    print(f"   python car_park_coordinate_generator.py --lot {name}")
    print(f"2. Uruchom monitoring:")
    print(f"   python app.py --lot {name}")


def interactive_mode():
    """Uruchamia tryb interaktywny (z pytaniami w konsoli)."""
    config = load_or_create_config()
    print("Dostępne konfiguracje parkingów:")
    for n in config["parking_lots"].keys():
        print(f"  - {n}")

    print("\n=== Dodawanie nowej konfiguracji parkingu ===")
    
    # === INSTRUKCJA DLA UŻYTKOWNIKA ===
    print("--- Wprowadź wartości zmierzone w calculate_dimensions.py ---")
    print(" (Użyj domyślnej wartości 107x48, jeśli nie wykonywano pomiaru)")
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
        rect_width = int(input("Szerokość prostokąta miejsca parkingowego (domyślnie 107): ") or "107")
        rect_height = int(input("Wysokość prostokąta miejsca parkingowego (domyślnie 48): ") or "48")
        threshold = int(input("Próg klasyfikacji (domyślnie 900): ") or "900")
    except ValueError:
        print("Błędne wartości liczbowe. Używam domyślnych.")
        rect_width, rect_height, threshold = 107, 48, 900

    image_path = input("Ścieżka do obrazu referencyjnego: ").strip()
    video_path = input("Ścieżka do wideo (opcjonalnie): ").strip()

    create_parking_lot(config, lot_name, rect_width, rect_height, threshold, image_path, video_path)



if __name__ == "__main__":
    interactive_mode()