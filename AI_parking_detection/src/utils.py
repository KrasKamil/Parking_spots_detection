"""
Zestaw narzędzi pomocniczych do przetwarzania obrazu, obsługi polskich znaków 
oraz interaktywnej konsoli systemowej wyświetlanej na klatkach wideo.
"""

import os
import glob
import subprocess
import sys
import cv2
import numpy as np
import time
import math
from PIL import Image, ImageDraw, ImageFont

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

IMG_DIR = os.path.join("data", "source", "img")

def draw_text_pl(img, text, pos, font_scale, color, thickness=1):
    """
    Renderuje tekst na obrazie z pełną obsługą polskich znaków diakrytycznych.

    Funkcja optymalizuje proces, używając standardowego rysowania OpenCV dla tekstów 
    bez polskich znaków. W przypadku wykrycia znaków diakrytycznych, wykorzystuje 
    bibliotekę PIL do renderowania czcionek TrueType.

    Args:
        img (np.ndarray): Obraz wejściowy w formacie BGR.
        text (str): Tekst do wyświetlenia.
        pos (tuple): Współrzędne (x, y) punktu wstawienia tekstu.
        font_scale (float): Skala czcionki.
        color (tuple/int): Kolor w formacie BGR lub wartość skali szarości.
        thickness (int): Grubość tekstu (używana tylko w trybie fallback OpenCV).

    Returns:
        np.ndarray: Obraz z naniesionym tekstem.
    """
    x, y = int(pos[0]), int(pos[1])
    
    if isinstance(color, int): 
        bgr_color = (color, color, color)
        rgb_color = (color, color, color)
    else: 
        bgr_color = color
        rgb_color = (color[2], color[1], color[0])

    if not any(char in text for char in "ąęćłńóśźżĄĘĆŁŃÓŚŹŻ"):
        cv2.putText(img, text, (x, y + int(font_scale * 25)), 
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
        return img

    try:
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        font_size = int(font_scale * 30)
        
        font = None
        if sys.platform.startswith("win"):
            font_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf")
            if os.path.exists(font_path):
                try: 
                    font = ImageFont.truetype(font_path, font_size)
                except: 
                    pass
        
        if font is None:
            font = ImageFont.load_default()
        
        draw.text((x, y), text, font=font, fill=rgb_color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
    except Exception:
        cv2.putText(img, text, (x, y + 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
        return img

def list_files_three_columns(folder, pattern="*.png", cols=3):
    """
    Wyświetla listę plików z folderu w trzech kolumnach w terminalu.

    Args:
        folder (str): Ścieżka do folderu z plikami.
        pattern (str): Wzorzec rozszerzeń plików. Domyślnie "*.png".
        cols (int): Liczba kolumn wyjściowych.

    Returns:
        list: Lista ścieżek do znalezionych plików.
    """
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files: 
        return []
    names = [os.path.basename(p) for p in files]
    rows = math.ceil(len(names) / cols)
    
    print("\nAvailable files:")
    for r in range(rows):
        row_str = ""
        for c in range(cols):
            idx = r + c * rows
            if idx < len(names): 
                row_str += f"[{idx+1:2d}] {names[idx]}".ljust(max(len(n) for n in names)+4)
        print(row_str)
    return files

def get_direct_youtube_url(youtube_url: str) -> str:
    """
    Pozyskuje bezpośredni URL do strumienia wideo z serwisu YouTube.

    Args:
        youtube_url (str): Pełny adres URL do filmu lub transmisji.

    Returns:
        str: Bezpośredni link do strumienia lub oryginalny URL w przypadku błędu.
    """
    try:
        command = ['yt-dlp', '--get-url', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', youtube_url]
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except: 
        return youtube_url

class OverlayConsole:
    """
    Graficzna konsola renderowana jako nakładka na obraz wideo w czasie rzeczywistym.

    Klasa umożliwia logowanie komunikatów bezpośrednio na ekranie aplikacji OpenCV.
    Obsługuje automatyczne przewijanie, historię logów oraz interaktywne przyciski.
    """

    def __init__(self, title="LOG SYSTEMOWY", max_lines=50, visible_by_default=False):
        """
        Inicjalizuje obiekt konsoli Overlay.

        Args:
            title (str): Tytuł wyświetlany w nagłówku konsoli.
            max_lines (int): Maksymalna liczba przechowywanych linii w buforze.
            visible_by_default (bool): Początkowy stan widoczności konsoli.
        """
        self.buffer = []
        self.title = title
        self.visible = visible_by_default
        self.max_lines = max_lines
        self.scroll_offset = 0 
        self.height = 350
        self.width = 500
        self.bg_color = (0, 0, 0)
        self.mouse_x = 0
        self.mouse_y = 0
        self.btn_clear_rect = None 
        self.current_rect = None 
        self.cwd = os.getcwd().replace("\\", "/")

    def _shorten_path(self, text):
        """Skraca ścieżki bezwzględne do relatywnych dla czytelności logów."""
        if not text: 
            return ""
        try:
            text_fixed = text.replace("\\", "/")
            cwd_lower = self.cwd.lower()
            text_lower = text_fixed.lower()
            if cwd_lower in text_lower:
                idx = text_lower.find(cwd_lower)
                prefix = text_fixed[:idx]
                suffix = text_fixed[idx + len(cwd_lower):]
                if suffix.startswith("/"): 
                    suffix = suffix[1:]
                return f"{prefix}./{suffix}"
            return text_fixed
        except: 
            return text

    def write(self, message):
        """
        Zapisuje wiadomość do bufora konsoli.

        Args:
            message (str): Treść komunikatu do zalogowania.
        """
        if message and message.strip():
            short_msg = self._shorten_path(message.strip())
            timestamp = time.strftime("%H:%M:%S")
            self.buffer.append(f"[{timestamp}] {short_msg}")
            self.scroll_offset = 0
            while len(self.buffer) > self.max_lines:
                self.buffer.pop(0)

    def toggle(self):
        """Przełącza stan widoczności konsoli (Ukryj/Pokaż)."""
        self.visible = not self.visible

    def clear(self):
        """Czyści bufor logów i resetuje widok."""
        self.buffer = []
        self.scroll_offset = 0

    def handle_mouse(self, event, x, y, flags):
        """
        Zarządza interakcjami myszy z panelem konsoli.

        Args:
            event: Typ zdarzenia OpenCV.
            x (int): Współrzędna X kursora.
            y (int): Współrzędna Y kursora.
            flags: Flagi zdarzenia OpenCV.

        Returns:
            bool: True, jeśli zdarzenie zostało przechwycone przez konsolę.
        """
        if not self.visible: 
            return False
        self.mouse_x = x
        self.mouse_y = y
        
        is_hovering = False
        if self.current_rect:
            cx, cy, cw, ch = self.current_rect
            if cx <= x <= cx + cw and cy <= y <= cy + ch: 
                is_hovering = True

        if is_hovering:
            if event == cv2.EVENT_MOUSEWHEEL:
                if flags > 0: 
                    self.scroll_offset = min(self.scroll_offset + 1, max(0, len(self.buffer) - 5))
                else: 
                    self.scroll_offset = max(self.scroll_offset - 1, 0)
                return True 
            elif event == cv2.EVENT_LBUTTONDOWN:
                if self.btn_clear_rect:
                    bx, by, bw, bh = self.btn_clear_rect
                    if bx <= x <= bx+bw and by <= y <= by+bh:
                        self.clear()
                        return True
                return True
        return False

    def draw(self, frame):
        """
        Renderuje graficzny interfejs konsoli na podanej klatce obrazu.

        Args:
            frame (np.ndarray): Klatka obrazu, na której ma zostać narysowana konsola.
        """
        if not self.visible: 
            self.current_rect = None
            return
        
        h, w, _ = frame.shape
        start_x = max(0, w - self.width - 10)
        start_y = 60 
        self.current_rect = (start_x, start_y, self.width, self.height)
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (start_x, start_y), (start_x + self.width, start_y + self.height), self.bg_color, -1)
        header_h = 30
        cv2.rectangle(overlay, (start_x, start_y), (start_x + self.width, start_y + header_h), (50, 50, 50), -1)
        
        alpha = 0.85
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        cv2.putText(frame, f"{self.title} (H: ukryj)", (start_x + 10, start_y + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        btn_w, btn_h = 60, 20
        btn_x = start_x + self.width - btn_w - 5
        btn_y = start_y + 5
        self.btn_clear_rect = (btn_x, btn_y, btn_w, btn_h)
        
        is_hover = (btn_x <= self.mouse_x <= btn_x + btn_w) and (btn_y <= self.mouse_y <= btn_y + btn_h)
        btn_color = (0, 0, 200) if is_hover else (0, 0, 100)
        
        cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), btn_color, -1)
        cv2.putText(frame, "CLEAR", (btn_x + 10, btn_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        line_h = 25
        max_visible_lines = (self.height - header_h) // line_h - 1
        total_lines = len(self.buffer)
        
        if total_lines == 0: 
            return

        end_idx = total_lines - self.scroll_offset
        start_idx = max(0, end_idx - max_visible_lines)
        visible_lines = self.buffer[start_idx:end_idx]

        for i, line in enumerate(visible_lines):
            y_pos = start_y + header_h + 5 + (i * line_h)
            
            color = (200, 200, 200)
            if "[+]" in line or "Saved" in line or "SUCCESS" in line: color = (0, 255, 0)
            if "[-]" in line or "ERROR" in line or "Exception" in line: color = (0, 0, 255)
            if "[EDIT]" in line or "MODE" in line or "INFO" in line: color = (0, 255, 255)
            if "RESET" in line: color = (255, 0, 255)
            
            max_chars = 60
            disp_text = line if len(line) < max_chars else line[:max_chars] + "..."
            
            frame = draw_text_pl(frame, disp_text, (start_x + 10, y_pos), 0.5, color)
        
        if self.scroll_offset > 0:
            cv2.putText(frame, f"^^^ HISTORIA (+{self.scroll_offset})", (start_x + self.width - 150, start_y + header_h + 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)