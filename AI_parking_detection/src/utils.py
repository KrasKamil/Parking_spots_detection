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
import textwrap
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
    """Renderuje tekst z ujednoliconym pozycjonowaniem dla CV2 i PIL."""
    x, y = int(pos[0]), int(pos[1])
    if isinstance(color, int): 
        bgr_color = (color, color, color); rgb_color = (color, color, color)
    else: 
        bgr_color = color; rgb_color = (color[2], color[1], color[0])

    pl_chars = 'ąęćłńóśźżĄĘĆŁŃÓŚŹŻ'
    has_pl = any(char in text for char in pl_chars)
    cv2_y_offset = int(font_scale * 25)

    if not has_pl:
        cv2.putText(img, text, (x, y + cv2_y_offset), cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
        return img
    try:
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        f_size = int(font_scale * 30)
        font = None
        if sys.platform.startswith('win'):
            f_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')
            if os.path.exists(f_path):
                try: font = ImageFont.truetype(f_path, f_size)
                except: pass
        if font is None: font = ImageFont.load_default()
        # Korekta pionowa dla PIL
        draw.text((x, y + (cv2_y_offset // 5)), text, font=font, fill=rgb_color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    except:
        cv2.putText(img, text, (x, y + cv2_y_offset), cv2.FONT_HERSHEY_SIMPLEX, font_scale, bgr_color, thickness)
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
    def __init__(self, title='LOG SYSTEMOWY', max_lines=200, visible_by_default=False, log_file="session.log"):
        self.buffer = []
        self.title = title
        self.visible = visible_by_default
        self.max_lines = max_lines
        self.log_file = log_file
        self.scroll_offset = 0 
        self.height = 350
        self.width = 400
        self.bg_color = (0, 0, 0)
        self.mouse_x = 0
        self.mouse_y = 0
        self.btn_clear_rect = None 
        self.current_rect = None 
        self.cwd = os.getcwd().replace('\\', '/')
        self.line_limit = 50
        
        if log_file:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("--- START SESJI ---\n")
            except: pass

    def write(self, message):
        """Dzieli tekst (Word Wrap) i przypisuje typ koloru."""
        try:
            sys.__stdout__.write(message)
            sys.__stdout__.flush()
        except: pass

        if not message or message.isspace(): return
        
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(message)
            except: pass

        lines = message.splitlines()
        for line in lines:
            clean = line.strip()
            if not clean: continue

            # 1. Rozpoznawanie typu wiadomości
            m_type = 'normal' # Domyślnie szary
            if '[+]' in clean or 'SUCCESS' in clean: m_type = 'success'
            elif '[-]' in clean or 'ERROR' in clean: m_type = 'error'
            elif 'INFO' in clean: m_type = 'info'
            elif 'MODE' in clean: m_type = 'mode'
            elif 'EDIT' in clean: m_type = 'edit'
            elif 'RESET' in clean: m_type = 'reset'

            # 2. Inteligentne zawijanie (Word Wrap)
            wrap_width = self.line_limit - 12
            chunks = textwrap.wrap(clean, width=wrap_width, break_long_words=False)
            
            t = time.strftime('%H:%M:%S')
            for i, chunk in enumerate(chunks):
                prefix = f'[{t}] ' if i == 0 else ' ' * 11
                self.buffer.append((f'{prefix}{chunk}', m_type))
                
                if len(self.buffer) > self.max_lines:
                    self.buffer.pop(0)
            
            self.scroll_offset = 0
            
    def flush(self): pass
    def toggle(self): self.visible = not self.visible
    def clear(self):
        self.buffer = []
        self.scroll_offset = 0

    def handle_mouse(self, event, x, y, flags, param=None):
        if not self.visible: return False
        self.mouse_x, self.mouse_y = x, y
        
        if self.current_rect:
            cx, cy, cw, ch = self.current_rect
            if cx <= x <= cx + cw and cy <= y <= cy + ch: 
                l_h = 22
                max_v = (self.height - 40) // l_h
                total = len(self.buffer)
                
                if event == cv2.EVENT_MOUSEWHEEL:
                    # Jeśli mamy mniej linii niż mieści okno, nie scrollujemy wcale
                    if total <= max_v:
                        self.scroll_offset = 0
                        return True
                    
                    if flags > 0: # W górę (historia)
                        self.scroll_offset = min(self.scroll_offset + 2, total - max_v)
                    else: # W dół (do nowych)
                        self.scroll_offset = max(0, self.scroll_offset - 2)
                    return True 
                
                elif event == cv2.EVENT_LBUTTONDOWN and self.btn_clear_rect:
                    bx, by, bw, bh = self.btn_clear_rect
                    if bx <= x <= bx+bw and by <= y <= by+bh:
                        self.clear(); return True
        return False

    def draw(self, frame):
        """Rysuje konsolę na klatce wideo."""
        if not self.visible: 
            self.current_rect = None
            return frame 
        
        h_f, w_f, _ = frame.shape
        start_x, start_y = max(0, w_f - self.width - 10), 60 
        self.current_rect = (start_x, start_y, self.width, self.height)
        
        ov = frame.copy()
        cv2.rectangle(ov, (start_x, start_y), (start_x + self.width, start_y + self.height), self.bg_color, -1)
        cv2.rectangle(ov, (start_x, start_y), (start_x + self.width, start_y + 30), (40, 40, 40), -1)
        frame = cv2.addWeighted(ov, 0.8, frame, 0.2, 0)
        cv2.putText(frame, self.title, (start_x + 10, start_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        l_h = 22
        max_v = (self.height - 40) // l_h
        total = len(self.buffer)

        if total > 0:
            end_i = total - self.scroll_offset
            st_i = max(0, end_i - max_v)
            visible_lines = self.buffer[st_i:end_i]

            for i, (line_text, m_type) in enumerate(visible_lines):
                y_p = start_y + 50 + (i * l_h)
                
                # PALETA KOLORÓW (BGR)
                colors = {
                    'success': (0, 255, 0),      # ZIELONY [+]
                    'error':   (0, 0, 255),      # CZERWONY [-]
                    'info':    (255, 0, 0),      # NIEBIESKI (INFO)
                    'mode':    (0, 255, 255),    # ŻÓŁTY (MODE)
                    'edit':    (255, 255, 0),    # CYJAN (EDIT)
                    'reset':   (128, 128, 255),  # RÓŻOWY (RESET)
                    'normal':  (200, 200, 200)   # SZARY (zwykły tekst)
                }
                c = colors.get(m_type, (200, 200, 200))
                
                frame = draw_text_pl(frame, line_text, (start_x + 10, y_p - 15), 0.4, c)

        return frame