import os
import glob
import subprocess
import json
import math

IMG_DIR = os.path.join("data", "source", "img")
CONFIG_PATH = os.path.join("config", "parking_config.json")


def list_files_three_columns(folder, pattern="*.png", cols=3):
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files:
        print(f"Brak plików pasujących do {pattern} w folderze: {folder}")
        return []
    names = [os.path.basename(p) for p in files]
    maxlen = max(len(n) for n in names) + 4
    rows = math.ceil(len(names) / cols)

    print("\nDostępne pliki:")
    for r in range(rows):
        row_str = ""
        for c in range(cols):
            idx = r + c * rows
            if idx < len(names):
                entry = f"[{idx+1:2d}] {names[idx]}"
                row_str += entry.ljust(maxlen)
        print(row_str)
    print("")
    return files


def choose_file_interaktywnie(files):
    if not files:
        return None
    while True:
        choice = input("Wybierz plik (numer), wpisz 'latest' (najnowszy) lub 'q' aby anulować: ").strip().lower()
        if choice == 'q':
            return None
        elif choice == 'latest':
            image_path = files[-1]
            print(f"Wybrano najnowszy plik: {os.path.basename(image_path)}")
            return image_path
        try:
            index = int(choice) - 1
            if 0 <= index < len(files):
                image_path = files[index]
                print(f"Wybrano plik: {os.path.basename(image_path)}")
                return image_path
            else:
                print("Nieprawidłowy numer.")
        except ValueError:
            print("Nieprawidłowy wybór. Wpisz numer, 'latest' lub 'q'.")


def get_last_added_lot_name():
    """Reads the last lot name saved by add_parking_config.py"""
    temp_file = os.path.join("config", "temp_last_lot.json")
    if os.path.exists(temp_file):
        with open(temp_file, 'r') as f:
            data = json.load(f)
            return data.get('lot_name')
    return None


def main():
    print("=== Rozpoczynam automatyczną konfigurację (Interaktywny tryb) ===")
    
    # 1) Wybór pliku referencyjnego
    files = list_files_three_columns(IMG_DIR)
    if not files:
        return

    image_path = choose_file_interaktywnie(files)
    if not image_path:
        print("Anulowano przez użytkownika.")
        return

    # 2) Kalibracja W/H (Uruchom generator w trybie 'c')
    try:
        print("\n== Uruchamiam narzędzie do adnotacji W TRYBIE KALIBRACJI ==")
        print("💡 INSTRUKCJA: Otwórz okno, naciśnij 'c', zmierz wymiary W/H (klikając dwa rogi) i zamknij okno.")
        
        subprocess.run(["python", "car_park_coordinate_generator.py", 
                "--lot", "default", 
                "--image", image_path, 
                "--mode", "c"], 
               check=True)
        print("✅ Zakończono kalibrację. Zanotuj wyświetlone wymiary W/H przed przejściem dalej.")

    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py zakończył się błędem w trybie kalibracji. Anulowano dalsze kroki.")
        return

    # 3) Dodawanie/modyfikacja konfiguracji (Interaktywnie)
    try:
        print("\n== Uruchamiam add_parking_config.py (wprowadź zmierzone parametry) ==")
        # Uruchamiamy bez argumentów, wymuszając interaktywne zbieranie danych.
        subprocess.run(["python", "add_parking_config.py"], check=True)

    except subprocess.CalledProcessError as e:
        print("❌ add_parking_config.py zakończył się błędem. Anulowano dalsze kroki.")
        return

    # 4) Odczytaj nazwę parkingu
    lot_name = get_last_added_lot_name()
    if not lot_name:
        print("❌ Nie udało się odczytać nazwy parkingu. Sprawdź, czy add_parking_config.py poprawnie zapisał dane.")
        return

    print(f"\n📦 Wykryto nazwę parkingu: {lot_name}")

    # 5) Uruchom pozostałe kroki (Adnotacja i Monitoring)
    # Wywołanie generatora po raz drugi - tym razem do oznaczania pozycji dla utworzonego 'lot_name'.
    try:
        print(f"\n== Uruchamiam car_park_coordinate_generator.py --lot {lot_name} ==")
        print("📌 Teraz możesz oznaczyć wszystkie miejsca parkingowe (tryby 'p', 'i').")
        subprocess.run(["python", "car_park_coordinate_generator.py", "--lot", lot_name], check=True)
        print("✅ Zakończono car_park_coordinate_generator.py")
    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py zakończył się błędem:", e)
        return

    try:
        print(f"\n== Uruchamiam app.py --lot {lot_name} (Monitoring) ==")
        print("🎥 Uruchamiam podgląd monitoringu. Zamknij okno, aby zakończyć.")
        subprocess.run(["python", "app.py", "--lot", lot_name], check=True)
        print("✅ Zakończono monitoring.")
    except subprocess.CalledProcessError as e:
        print("❌ app.py zakończył się błędem:", e)
        return
        
    print("\n=== Sekwencja automatycznej konfiguracji zakończona powodzeniem! ===")

if __name__ == "__main__":
    main()
