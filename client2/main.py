import sys
import os
import asyncio
import logging
import json
from datetime import datetime
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QSystemTrayIcon, QMenu, QPushButton, QLineEdit, QMessageBox, QDialog
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QAction
import qasync
import socket
from explorer_watcher import start_watcher
import ctypes
import win32con
import win32api
import win32gui
import win32process
import threading

# Overlay timer widget
class TimerOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle('Session Timer')
        self.label = QLabel('', self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            'background: rgba(0,0,0,0.7); color: white; font-size: 60px; border-radius: 24px; padding: 40px 0px;'
        )
        self.min_btn = QPushButton('Minimize to tray', self)
        self.min_btn.setStyleSheet('font-size: 18px; padding: 8px 24px; margin-top: 16px;')
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.min_btn)
        self.resize(800, 200)
        self.move(200, 40)  # Top center-ish
    def set_time(self, text):
        self.label.setText(text)

# Blank lock screen
class BlankScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet('background-color: #111;')
        self.label = QLabel('Session not active', self)
        self.label.setStyleSheet('color: white; font-size: 36px;')
        self.label.setAlignment(Qt.AlignCenter)
        self.status_label = QLabel('', self)
        self.status_label.setStyleSheet('color: #aaa; font-size: 22px; margin-top: 24px;')
        self.status_label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.status_label)
    def show_blank(self, msg='Session not active', status=''):
        self.label.setText(msg)
        self.status_label.setText(status)
        self.showFullScreen()
        self.raise_()
    def hide_blank(self):
        self.hide()
    def set_status(self, status):
        self.status_label.setText(status)
    def closeEvent(self, event):
        # Block Alt+F4 when blank is active
        if self.isVisible():
            event.ignore()
    def keyPressEvent(self, event):
        # Block Alt+F4
        if event.key() == Qt.Key_F4 and (event.modifiers() & Qt.AltModifier):
            return
        super().keyPressEvent(event)

SERVER_CONFIG = 'client2_config.json'
DEFAULT_SERVER_PORT = 8765

# --- Keyboard hook for blocking Windows key ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_ESCAPE = 0x1B
VK_F4 = 0x73
VK_MENU = 0x12  # Alt

class KeyboardBlocker:
    def __init__(self):
        self.hooked = None
        self.enabled = False
    def install(self):
        if self.hooked:
            return
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
        def low_level_keyboard_proc(nCode, wParam, lParam):
            if nCode == 0:
                vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong * 6))[0][0]
                # Block Windows keys and Ctrl+Esc
                if vk_code in (VK_LWIN, VK_RWIN):
                    return 1
                if vk_code == VK_ESCAPE and (win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000):
                    return 1
            return user32.CallNextHookEx(self.hooked, nCode, wParam, lParam)
        self.pointer = CMPFUNC(low_level_keyboard_proc)
        self.hooked = user32.SetWindowsHookExA(WH_KEYBOARD_LL, self.pointer, kernel32.GetModuleHandleW(None), 0)
        self.enabled = True
        # Keep message loop in a thread
        def msg_loop():
            while self.enabled:
                user32.PeekMessageW(None, 0, 0, 0, 0)
        self.thread = threading.Thread(target=msg_loop, daemon=True)
        self.thread.start()
    def uninstall(self):
        if self.hooked:
            user32.UnhookWindowsHookEx(self.hooked)
            self.hooked = None
            self.enabled = False

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Login')
        self.setFixedSize(300, 150)
        layout = QVBoxLayout(self)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Username')
        layout.addWidget(self.username_input)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Password')
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        self.login_btn = QPushButton('Login')
        self.login_btn.clicked.connect(self.try_login)
        layout.addWidget(self.login_btn)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint)
        self.accepted = False
    def try_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Please enter both username and password')
            return
        self.accepted = True
        self.accept()
    def get_credentials(self):
        return self.username_input.text(), self.password_input.text()
    def closeEvent(self, event):
        # Prevent closing the dialog with X
        event.ignore()

keyboard_blocker = KeyboardBlocker()

class Client2App:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.loop = qasync.QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)
        self.overlay = TimerOverlay()
        self.blank = BlankScreen()
        self.session_active = False
        self.remaining_time = 0
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self._tick)
        self.connection_status = 'Disconnected'
        start_watcher()  # Start closing explorer folders
        self._init_tray()
        self.overlay.min_btn.clicked.connect(self.overlay.hide)
        self._show_blank()
        QTimer.singleShot(0, lambda: asyncio.create_task(self._connect_to_server()))
        self._notified_5min = False
        self._notified_1min = False
        self.receiver_task = None  # Track the message receiver task
    def _init_tray(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        self.tray = QSystemTrayIcon(QIcon(icon_path))
        self.tray.setToolTip('Kiosk Session Timer')
        menu = QMenu()
        show_action = QAction('Show Timer')
        hide_action = QAction('Hide Timer')
        quit_action = QAction('Exit')
        show_action.triggered.connect(self._show_overlay)
        hide_action.triggered.connect(self.overlay.hide)
        quit_action.triggered.connect(self._exit)
        menu.addAction(show_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.overlay.isVisible():
                self.overlay.hide()
            else:
                self._show_overlay()
    def _exit(self):
        self.session_timer.stop()
        self.tray.hide()
        self.app.quit()
    def _get_server_ip(self):
        if os.path.exists(SERVER_CONFIG):
            with open(SERVER_CONFIG, 'r') as f:
                data = json.load(f)
                return data.get('server_ip')
        return None
    def _save_server_ip(self, ip):
        with open(SERVER_CONFIG, 'w') as f:
            json.dump({'server_ip': ip}, f)
    async def _connect_to_server(self):
        server_ip = self._get_server_ip()
        if not server_ip:
            from PySide6.QtWidgets import QInputDialog, QMessageBox
            ip, ok = QInputDialog.getText(None, "Server IP", "Enter the server IP address:")
            if not ok or not ip:
                QMessageBox.critical(None, "No IP Entered", "No server IP entered. Exiting.")
                sys.exit(1)
            self._save_server_ip(ip)
            server_ip = ip
        self.set_connection_status('Connecting...')
        try:
            reader, writer = await asyncio.open_connection(server_ip, DEFAULT_SERVER_PORT)
            self.writer = writer  # Store writer for later closing
            self.set_connection_status('Connected')
            # Cancel previous receiver if any
            if self.receiver_task is not None:
                self.receiver_task.cancel()
            self.receiver_task = asyncio.create_task(self._receive_messages(reader, writer))
            while True:
                login_dialog = LoginDialog()
                if login_dialog.exec() != QDialog.Accepted or not login_dialog.accepted:
                    continue
                username, password = login_dialog.get_credentials()
                if username == 'admin' and password == 'admin123':
                    sys.exit(0)
                auth_data = {
                    'type': 'auth',
                    'username': username,
                    'password': password
                }
                writer.write(json.dumps(auth_data).encode() + b'\n')
                await writer.drain()
                break
        except Exception as e:
            self.set_connection_status('Disconnected')
            QTimer.singleShot(3000, lambda: asyncio.create_task(self._connect_to_server()))
    def _get_local_ip(self, server_ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((server_ip, DEFAULT_SERVER_PORT))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return 'Unknown'
    async def _receive_messages(self, reader, writer):
        while True:
            try:
                data = await reader.readline()
                if not data:
                    break
                msg = data.decode().strip()
                if not msg:
                    continue
                try:
                    msg_dict = json.loads(msg)
                except Exception:
                    continue
                msg_type = msg_dict.get('type')
                if msg_type == 'auth_success':
                    minutes = msg_dict.get('minutes', 0)
                    self.set_connection_status(f'Connected (Available time: {minutes} minutes)')
                elif msg_type == 'auth_error':
                    error_msg = msg_dict.get('message', 'Authentication failed')
                    QMessageBox.critical(None, "Authentication Error", error_msg)
                    writer.close()
                    await writer.wait_closed()
                    sys.exit(1)
                elif msg_type == 'admin_auth_success':
                    QMessageBox.information(None, "Admin Access", "Admin access granted. Closing client.")
                    writer.close()
                    await writer.wait_closed()
                    sys.exit(0)
                elif msg_type == 'session_started':
                    duration = msg_dict.get('duration', 0)
                    self.start_session(duration)
                elif msg_type == 'session_end':
                    self.end_session()
                elif msg_type == 'session_error':
                    error_msg = msg_dict.get('message', 'Session error')
                    QMessageBox.warning(None, "Session Error", error_msg)
            except Exception:
                break
        self.set_connection_status('Disconnected')
        QTimer.singleShot(3000, lambda: asyncio.create_task(self._connect_to_server()))
    def _show_blank(self):
        self.overlay.hide()
        self.blank.show_blank(status=f'Status: {self.connection_status}')
        keyboard_blocker.install()
    def _show_overlay(self):
        self.blank.hide_blank()
        self.overlay.show()
        self.overlay.raise_()
        keyboard_blocker.uninstall()
    def start_session(self, duration):
        self.session_active = True
        self.remaining_time = duration
        self._notified_5min = False
        self._notified_1min = False
        self._show_overlay()
        self._update_timer()
        self.session_timer.start(1000)
    def end_session(self):
        self.session_active = False
        self.session_timer.stop()
        self.remaining_time = 0
        self._notified_5min = False
        self._notified_1min = False
        self._show_blank()
        self.set_connection_status('Disconnected')
        # Cancel the message receiver task if running
        if self.receiver_task is not None:
            self.receiver_task.cancel()
            self.receiver_task = None
        try:
            self.writer.close()
            asyncio.create_task(self.writer.wait_closed())
        except Exception:
            pass
        QTimer.singleShot(300, lambda: asyncio.create_task(self._connect_to_server()))
    def _tick(self):
        if self.session_active:
            self.remaining_time -= 1
            if self.remaining_time <= 0:
                self.end_session()
            else:
                self._update_timer()
                # Balloon notifications
                if not self._notified_5min and self.remaining_time == 300:
                    self.tray.showMessage('Session Timer', 'Остават 5 минути!', QSystemTrayIcon.Information, 5000)
                    self._notified_5min = True
                if not self._notified_1min and self.remaining_time == 60:
                    self.tray.showMessage('Session Timer', 'Остава 1 минута!', QSystemTrayIcon.Information, 5000)
                    self._notified_1min = True
    def _update_timer(self):
        h = self.remaining_time // 3600
        m = (self.remaining_time % 3600) // 60
        s = self.remaining_time % 60
        self.overlay.set_time(f'Time left: {h:02d}:{m:02d}:{s:02d}')
    def set_connection_status(self, status):
        self.connection_status = status
        self.blank.set_status(f'Status: {self.connection_status}')
    def run(self):
        with self.loop:
            self.loop.run_forever()

def main():
    c = Client2App()
    c.run()

if __name__ == '__main__':
    main() 