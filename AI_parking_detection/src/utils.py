# -*- coding: utf-8 -*-
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
import re
from PIL import Image, ImageDraw, ImageFont

# Import biblioteki yt_dlp z obsługą błędu braku instalacji
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

IMG_DIR = os.path.join('data', 'source', 'img')

def draw_text_pl(img, text, pos, font_scale, color, thickness=1):
    """
    Renderuje tekst na obrazie z pełną obsługą polskich znaków diakrytycznych.
    """
    x, y = int(pos[0]), int(pos[1])
    
    if isinstance(color, int): 
        bgr_color = (color, color, color)
        rgb_color = (color, color, color)
    else: 
        bgr_color = color
        rgb_color = (color[2], color[1], color[0])

    pl_chars = 'ąęćłńóśźżĄĘĆŁŃÓŚŹŻ'
    has_pl = any(char in text for char in pl_chars)

    if not has_pl:
        cv2.putText(img, text, (x, y + int(font_scale * 25)), 
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
        return img

    try:
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        f_size = int(font_scale * 30)
        
        font = None
        if sys.platform.startswith('win'):
            f_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')
            if os.path.exists(f_path):
                try: 
                    font = ImageFont.truetype(f_path, f_size)
                except: 
                    pass
        
        if font is None:
            font = ImageFont.load_default()
        
        draw.text((x, y), text, font=font, fill=rgb_color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
    except Exception:
        cv2.putText(img, text, (x, y + 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
        return img

def list_files_three_columns(folder, pattern='*.png', cols=3):
    """
    Wyświetla listę plików z folderu w trzech kolumnach w terminalu.
    """
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files: 
        return []
    names = [os.path.basename(p) for p in files]
    rows = math.ceil(len(names) / cols)
    
    print('\nAvailable files:')
    max_n = max(len(n) for n in names) if names else 0

    for r in range(rows):
        row_str = ''
        for c in range(cols):
            idx = r + c * rows
            if idx < len(names): 
                item = '[{:2d}] {}'.format(idx+1, names[idx])
                row_str += item.ljust(max_n + 4)
        print(row_str)
    return files

def get_direct_youtube_url(youtube_url):
    """
    Pozyskuje bezpośredni URL do strumienia. 
    Jeśli URL już prowadzi do .m3u8 lub .mp4, zwraca go bez zmian.
    """
    if not youtube_url:
        return youtube_url

    # 1. Czyszczenie i naprawa formatu adresu
    youtube_url = youtube_url.strip().replace('\\', '/')
    # Napraw protokół (pilnuj, żeby po http: były dokładnie dwa slashe)
    youtube_url = re.sub(r'^(https?:)/+', r'\1//', youtube_url)

    url_lower = youtube_url.lower()
    
    # 2. Zabezpieczenie dla gotowych strumieni (np. Jasło .m3u8)
    if '.m3u8' in url_lower or '.mp4' in url_lower:
        print("[SUCCESS] Rozpoznano bezpośredni link do strumienia.")
        return youtube_url

    if yt_dlp is None:
        return youtube_url

    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            video_data = info['entries'][0] if 'entries' in info else info
            direct_url = video_data.get('url')
            
            final_url = None
            # Jeśli URL prowadzi do strony YouTube, szukamy w dostępnych formatach
            if not direct_url or 'youtube.com' in direct_url:
                formats = video_data.get('formats', [])
                for f in reversed(formats):
                    if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                        final_url = f.get('url')
                        break
            else:
                final_url = direct_url
            
            if final_url:
                print("[SUCCESS] Pomyślnie załadowano bezpośredni link YouTube.")
                return final_url
            
            return youtube_url
    except Exception:
        return youtube_url

class OverlayConsole:
    """
    Graficzna konsola renderowana jako nakładka na obraz wideo.
    """

    def __init__(self, title='LOG SYSTEMOWY', max_lines=50, visible_by_default=False):
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
        self.cwd = os.getcwd().replace('\\', '/')

    def _shorten_path(self, text):
        """Bezpiecznie skraca ścieżki, ignorując URL-e."""
        if not text: 
            return ''
        
        # Jeśli string zawiera ślady URL, nie dotykaj go w ogóle
        if '://' in text or 'http:/' in text or 'https:/' in text:
            return text

        try:
            t_fixed = text.replace('\\', '/')
            cwd_l = self.cwd.lower()
            t_l = t_fixed.lower()
            if cwd_l in t_l:
                idx = t_l.find(cwd_l)
                suffix = t_fixed[idx + len(cwd_l):]
                if suffix.startswith('/'): 
                    suffix = suffix[1:]
                return './{}'.format(suffix)
            return t_fixed
        except: 
            return text

    def write(self, message):
        """Zapisuje wiadomość do bufora konsoli."""
        if message and message.strip():
            msg = self._shorten_path(message.strip())
            t_stamp = time.strftime('%H:%M:%S')
            self.buffer.append('[{}] {}'.format(t_stamp, msg))
            self.scroll_offset = 0
            while len(self.buffer) > self.max_lines:
                self.buffer.pop(0)

    def toggle(self):
        self.visible = not self.visible

    def clear(self):
        self.buffer = []
        self.scroll_offset = 0

    def handle_mouse(self, event, x, y, flags, param=None):
        if not self.visible: 
            return False
        self.mouse_x, self.mouse_y = x, y
        
        is_h = False
        if self.current_rect:
            cx, cy, cw, ch = self.current_rect
            if cx <= x <= cx + cw and cy <= y <= cy + ch: 
                is_h = True

        if is_h:
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
        if not self.visible: 
            self.current_rect = None
            return
        
        h_f, w_f, _ = frame.shape
        start_x = max(0, w_f - self.width - 10)
        start_y = 60 
        self.current_rect = (start_x, start_y, self.width, self.height)
        
        ov = frame.copy()
        cv2.rectangle(ov, (start_x, start_y), (start_x + self.width, start_y + self.height), self.bg_color, -1)
        h_h = 30
        cv2.rectangle(ov, (start_x, start_y), (start_x + self.width, start_y + h_h), (50, 50, 50), -1)
        
        alpha = 0.85
        cv2.addWeighted(ov, alpha, frame, 1 - alpha, 0, frame)

        h_txt = '{} (H: ukryj)'.format(self.title)
        cv2.putText(frame, h_txt, (start_x + 10, start_y + 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        b_w, b_h = 60, 20
        b_x = start_x + self.width - b_w - 5
        b_y = start_y + 5
        self.btn_clear_rect = (b_x, b_y, b_w, b_h)
        
        hov = (b_x <= self.mouse_x <= b_x + b_w) and (b_y <= self.mouse_y <= b_y + b_h)
        b_c = (0, 0, 200) if hov else (0, 0, 100)
        
        cv2.rectangle(frame, (b_x, b_y), (b_x + b_w, b_y + b_h), b_c, -1)
        cv2.putText(frame, 'CLEAR', (b_x + 10, b_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        l_h = 25
        max_v = (self.height - h_h) // l_h - 1
        total = len(self.buffer)
        
        if total == 0: 
            return

        end_i = total - self.scroll_offset
        st_i = max(0, end_i - max_v)
        v_lines = self.buffer[st_i:end_i]

        for i, line in enumerate(v_lines):
            y_p = start_y + h_h + 5 + (i * l_h)
            
            c = (200, 200, 200)
            if any(x in line for x in ['[+]', 'Saved', 'SUCCESS']): c = (0, 255, 0)
            if any(x in line for x in ['[-]', 'ERROR', 'Exception']): c = (0, 0, 255)
            if any(x in line for x in ['[EDIT]', 'MODE', 'INFO']): c = (0, 255, 255)
            if 'RESET' in line: c = (255, 0, 255)
            
            disp = line if len(line) < 60 else line[:60] + '...'
            frame = draw_text_pl(frame, disp, (start_x + 10, y_p), 0.5, c)
        
        if self.scroll_offset > 0:
            h_t = '^^^ HISTORIA (+{})'.format(self.scroll_offset)
            cv2.putText(frame, h_t, (start_x + self.width - 150, start_y + h_h + 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)