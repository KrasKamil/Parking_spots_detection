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


def choose_file_interactively(files):
    if not files:
        return None
    while True:
        choice = input("Wybierz plik (numer), wpisz 'latest' (najnowszy) lub 'q' aby anulować: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            return None
        if choice in ("latest", "n", "auto"):
            latest = max(files, key=os.path.getctime)
            print(f"Wybrano najnowszy plik: {os.path.basename(latest)}")
            return latest
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                selected = files[idx]
                print(f"Wybrano: {os.path.basename(selected)}")
                return selected
            else:
                print("Numer poza zakresem. Spróbuj ponownie.")
        else:
            print("Nieprawidłowy wybór. Podaj numer, 'latest' lub 'q'.")


def get_last_added_lot_name():
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"Błąd wczytania pliku konfiguracyjnego: {e}")
        return None

    lots = cfg.get("parking_lots", {})
    if not lots:
        return None
    return list(lots.keys())[-1]


def run_all():
    print("\n=== Rozpoczynam automatyczną konfigurację (Interaktywny tryb) ===")

    # 1) Wybór pliku obrazu
    files = list_files_three_columns(IMG_DIR, pattern="*.png", cols=3)
    if not files:
        print("Brak plików do przetworzenia. Umieść pliki PNG w 'data/source/img'.")
        return

    image_path = choose_file_interactively(files)
    if not image_path:
        print("Anulowano wybór pliku.")
        return

    # 2) Uruchom calculate_dimensions.py
    try:
        print("\n== Uruchamiam calculate_dimensions.py ==")
        subprocess.run(["python", "calculate_dimensions.py", "-i", os.path.basename(image_path)], check=True)
        print("✅ Zakończono calculate_dimensions.py. Prosimy o wprowadzenie zmierzonych wartości w następnym kroku.")
    except subprocess.CalledProcessError as e:
        print("❌ calculate_dimensions.py zakończył się błędem:", e)
        return

    # 3) Uruchom add_parking_config.py (Interaktywnie)
    try:
        print("\n== Uruchamiam add_parking_config.py (wprowadź parametry) ==")
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

    # 5) Uruchom pozostałe kroki
    try:
        print(f"\n== Uruchamiam car_park_coordinate_generator.py --lot {lot_name} ==")
        subprocess.run(["python", "car_park_coordinate_generator.py", "--lot", lot_name], check=True)
        print("✅ Zakończono car_park_coordinate_generator.py")
    except subprocess.CalledProcessError as e:
        print("❌ car_park_coordinate_generator.py zakończył się błędem:", e)
        return

    try:
        print(f"\n== Uruchamiam app.py --lot {lot_name} ==")
        subprocess.run(["python", "app.py", "--lot", lot_name], check=True)
        print("✅ Zakończono app.py")
    except subprocess.CalledProcessError as e:
        print("❌ app.py zakończył się błędem:", e)
        return


if __name__ == "__main__":
    run_all()