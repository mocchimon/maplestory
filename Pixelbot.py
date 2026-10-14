import ctypes
import time
import re
import pytesseract
from PIL import Image, ImageOps, ImageGrab
from pynput import keyboard
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

TARGET_HWND = 19531744

# Locked-in coordinates
HP_REL_X, HP_REL_Y, HP_W, HP_H = 450, 950, 145, 24
MP_REL_X, MP_REL_Y, MP_W, MP_H = 560, 950, 166, 24

COOLDOWN_DURATION = 5.0
last_hp_heal_time = 0.0
last_mp_heal_time = 0.0

is_running = False

# Virtual key codes and scan codes for END and DEL
VK_END = 0x23
VK_DEL = 0x2E

def send_key_direct(vk_code):
    """Sends low-level key down and up events that games running via DirectInput/Wrappers can detect."""
    try:
        scan_code = win32api.MapVirtualKey(vk_code, 0)
        # Key down
        win32api.keybd_event(vk_code, scan_code, 0, 0)
        time.sleep(0.05)
        # Key up
        win32api.keybd_event(vk_code, scan_code, win32con.KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[Input Error]: {e}")

def get_absolute_bbox(rel_x, rel_y, width, height):
    try:
        if not win32gui.IsWindow(TARGET_HWND):
            return None
        if win32gui.IsIconic(TARGET_HWND):
            return None
            
        screen_x, screen_y = win32gui.ClientToScreen(TARGET_HWND, (rel_x, rel_y))
        
        if screen_x < -30000 or screen_y < -30000:
            return None
            
        return (screen_x, screen_y, screen_x + width, screen_y + height)
    except Exception:
        return None

def capture_and_read_values(rel_x, rel_y, width, height, label):
    bbox = get_absolute_bbox(rel_x, rel_y, width, height)
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

def bot_loop():
    global last_hp_heal_time, last_mp_heal_time, is_running
    print("Bot initialized (Admin Mode). Press F6 to toggle, ESC to quit.")
    
    test_bbox = get_absolute_bbox(HP_REL_X, HP_REL_Y, HP_W, HP_H)
    if test_bbox:
        print(f"[Success] Locked to HWND {TARGET_HWND}!")
    else:
        print(f"[Warning] Target HWND {TARGET_HWND} is currently minimized or hidden.")

    while True:
        if not is_running:
            time.sleep(0.1)
            continue

        current_time = time.time()

        # --- HP Check (< 40%) ---
        if current_time - last_hp_heal_time >= COOLDOWN_DURATION:
            hp_curr, hp_max = capture_and_read_values(HP_REL_X, HP_REL_Y, HP_W, HP_H, "HP")
            if hp_curr is not None and hp_max > 0:
                pct = (hp_curr / hp_max) * 100
                print(f"[HP Status] Read: {hp_curr}/{hp_max} -> {pct:.1f}%")
                if pct <= 40.0:
                    send_key_direct(VK_END)
                    last_hp_heal_time = time.time()
                    print(f"--> [HEAL TRIGGER] HP is {pct:.1f}%, sent 'END'")

        # --- MP Check (< 30%) ---
        if current_time - last_mp_heal_time >= COOLDOWN_DURATION:
            mp_curr, mp_max = capture_and_read_values(MP_REL_X, MP_REL_Y, MP_W, MP_H, "MP")
            if mp_curr is not None and mp_max > 0:
                pct = (mp_curr / mp_max) * 100
                print(f"[MP Status] Read: {mp_curr}/{mp_max} -> {pct:.1f}%")
                if pct <= 30.0:
                    send_key_direct(VK_DEL)
                    last_mp_heal_time = time.time()
                    print(f"--> [HEAL TRIGGER] MP is {pct:.1f}%, sent 'DEL'")

        time.sleep(0.3)

def on_press(key):
    global is_running
    try:
        if key == keyboard.Key.f6:
            is_running = not is_running
            status = "RESUMED" if is_running else "PAUSED"
            print(f"\n[HOTKEY] Bot status: {status}")
        elif key == keyboard.Key.esc:
            print("\n[HOTKEY] Terminating bot script.")
            return False
    except Exception:
        pass

if __name__ == "__main__":
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    try:
        bot_loop()
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()