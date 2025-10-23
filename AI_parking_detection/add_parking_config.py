import json
import os

def add_parking_config():
    config_file = "config/parking_config.json"
    
    # Wczytaj istniejący config lub stwórz nowy
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
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
    
    print("Dostępne konfiguracje parkingów:")
    for name in config["parking_lots"].keys():
        print(f"  - {name}")
    
    print("\n=== Dodawanie nowej konfiguracji parkingu ===")
    
    # Zbierz informacje od użytkownika
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
    
    # Stwórz unikalne nazwy plików
    positions_file = f"data/parking_lots/{lot_name}_positions"
    
    # Dodaj nową konfigurację
    config["parking_lots"][lot_name] = {
        "name": display_name,
        "rect_width": rect_width,
        "rect_height": rect_height, 
        "threshold": threshold,
        "positions_file": positions_file,
        "source_image": image_path if image_path else f"data/source/img/{lot_name}.png",
    "video_source": video_path if video_path else f"data/source/video/{lot_name}.mp4"
    }
    
    # Stwórz folder na pozycje jeśli nie istnieje
    os.makedirs("data/parking_lots", exist_ok=True)
    os.makedirs("config", exist_ok=True)
    
    # Zapisz konfigurację
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Dodano konfigurację '{lot_name}'!")
    print(f"📁 Plik pozycji: {positions_file}")
    print(f"🖼️  Obraz: {config['parking_lots'][lot_name]['source_image']}")
    print(f"🎥 Wideo: {config['parking_lots'][lot_name]['video_source']}")
    
    print(f"\n📋 Następne kroki:")
    print(f"1. Oznacz miejsca parkingowe:")
    print(f"   python car_park_coordinate_generator.py --lot {lot_name}")
    print(f"2. Uruchom monitoring:")
    print(f"   python app.py --lot {lot_name}")

if __name__ == "__main__":
    add_parking_config()