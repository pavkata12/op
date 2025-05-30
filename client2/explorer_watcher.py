import win32gui
import win32process
import psutil
import time
import threading

def is_explorer_folder(hwnd):
    # Check if the window belongs to explorer.exe and is not the desktop shell
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        if proc.name().lower() != 'explorer.exe':
            return False
        # Ignore the desktop shell window (class 'Progman' or 'WorkerW')
        class_name = win32gui.GetClassName(hwnd)
        if class_name in ('Progman', 'WorkerW'):
            return False
        # Only visible windows
        if not win32gui.IsWindowVisible(hwnd):
            return False
        # Only windows with a title (folders have titles)
        if not win32gui.GetWindowText(hwnd):
            return False
        return True
    except Exception:
        return False

def close_explorer_folders():
    def callback(hwnd, _):
        if is_explorer_folder(hwnd):
            try:
                win32gui.PostMessage(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
        return True
    win32gui.EnumWindows(callback, None)

def start_watcher(interval=1.0):
    def loop():
        while True:
            close_explorer_folders()
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True)
    t.start() 