import ctypes
import time
import re
import pytesseract
from PIL import Image, ImageOps, ImageGrab
import keyboard as kb  # Using the robust keyboard library for hotkeys
import win32gui
import win32api
import win32con

# Fix Windows DPI scaling mismatch
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Point to your tesseract installation if needed
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Window title keyword to search for dynamically on startup
WINDOW_TITLE_PART = "MapleStory Worlds"

# Locked-in coordinates
HP_REL_X, HP_REL_Y, HP_W, HP_H = 450, 950, 145, 24
MP_REL_X, MP_REL_Y, MP_W, MP_H = 560, 950, 166, 24

COOLDOWN_DURATION = 5.0
last_hp_heal_time = 0.0
last_mp_heal_time = 0.0

is_running = False

# Virtual key codes for END and DEL
VK_END = 0x23
VK_DEL = 0x2E

def find_target_hwnd():
    """Dynamically finds the window handle by searching for part of its title."""
    found_hwnd = None
    
    def enum_windows_callback(hwnd, extra):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd):
            text = win32gui.GetWindowText(hwnd)
            if WINDOW_TITLE_PART.lower() in text.lower():
                found_hwnd = hwnd
                return False
        return True

    win32gui.EnumWindows(enum_windows_callback, None)
    return found_hwnd

def send_key_direct(vk_code):
    """Sends low-level key down and up events that games running via DirectInput/Wrappers can detect."""
    try:
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        win32api.keybd_event(vk_code, scan_code, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[Input Error]: {e}")

def get_absolute_bbox(target_hwnd, rel_x, rel_y, width, height):
    try:
        if not win32gui.IsWindow(target_hwnd):
            return None
        if win32gui.IsIconic(target_hwnd):
            return None
            
        screen_x, screen_y = win32gui.ClientToScreen(target_hwnd, (rel_x, rel_y))
        
        if screen_x < -30000 or screen_y < -30000:
            return None
            
        return (screen_x, screen_y, screen_x + width, screen_y + height)
    except Exception:
        return None

def capture_and_read_values(target_hwnd, rel_x, rel_y, width, height, label):
    bbox = get_absolute_bbox(target_hwnd, rel_x, rel_y, width, height)
    if not bbox:
        return None, None

    try:
        img = ImageGrab.grab(bbox=bbox)
        
        gray = ImageOps.grayscale(img)
        scaled = gray.resize((gray.width * 4, gray.height * 4), Image.Resampling.BICUBIC)
        enhanced = ImageOps.autocontrast(scaled)
        
        config = '--psm 7 -c tessedit_char_whitelist=0123456789[]/'
        text = pytesseract.image_to_string(enhanced, config=config)
        clean_text = text.strip()
        
        print(f"[{label} OCR Read]: '{clean_text}'")
        
        match = re.search(r'\[?(\d+)/(\d+)\]?', clean_text)
        if match:
            current = int(match.group(1))
            maximum = int(match.group(2))
            return current, maximum
            
    except Exception as e:
        print(f"[{label} Error]: {e}")
    
    return None, None

def toggle_bot():
    global is_running
    is_running = not is_running
    status = "RESUMED" if is_running else "PAUSED"
    print(f"\n[HOTKEY] Bot status: {status}")

def exit_bot():
    print("\n[HOTKEY] Terminating bot script.")
    import sys
    sys.exit(0)

def bot_loop():
    global last_hp_heal_time, last_mp_heal_time, is_running
    
    target_hwnd = find_target_hwnd()
    if not target_hwnd:
        print(f"[Error] Could not find any window matching '{WINDOW_TITLE_PART}'. Make sure the game is running!")
        return

    print(f"[Success] Automatically locked to HWND {target_hwnd}!")
    print("Bot initialized (Admin Mode). Press F6 to toggle, ESC to quit.")

    while True:
        if not is_running:
            time.sleep(0.1)
            continue

        current_time = time.time()

        # --- HP Check (< 40%) ---
        if current_time - last_hp_heal_time >= COOLDOWN_DURATION:
            hp_curr, hp_max = capture_and_read_values(target_hwnd, HP_REL_X, HP_REL_Y, HP_W, HP_H, "HP")
            if hp_curr is not None and hp_max > 0:
                pct = (hp_curr / hp_max) * 100
                print(f"[HP Status] Read: {hp_curr}/{hp_max} -> {pct:.1f}%")
                if pct <= 40.0:
                    send_key_direct(VK_END)
                    last_hp_heal_time = time.time()
                    print(f"--> [HEAL TRIGGER] HP is {pct:.1f}%, sent 'END'")

        # --- MP Check (< 30%) ---
        if current_time - last_mp_heal_time >= COOLDOWN_DURATION:
            mp_curr, mp_max = capture_and_read_values(target_hwnd, MP_REL_X, MP_REL_Y, MP_W, MP_H, "MP")
            if mp_curr is not None and mp_max > 0:
                pct = (mp_curr / mp_max) * 100
                print(f"[MP Status] Read: {mp_curr}/{mp_max} -> {pct:.1f}%")
                if pct <= 30.0:
                    send_key_direct(VK_DEL)
                    last_mp_heal_time = time.time()
                    print(f"--> [HEAL TRIGGER] MP is {pct:.1f}%, sent 'DEL'")

        time.sleep(0.3)

if __name__ == "__main__":
    # Register global hotkeys using the keyboard library
    kb.add_hotkey('f6', toggle_bot)
    kb.add_hotkey('esc', exit_bot)
    
    try:
        bot_loop()
    except KeyboardInterrupt:
        pass
