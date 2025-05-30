"""
Main client application for the kiosk system.
"""
import sys
import os
import asyncio
import logging
import json
import psutil
import win32gui
import win32con
import win32process
import socket
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer, QRect
from shared.constants import (
    DEFAULT_SERVER_PORT,
    HEARTBEAT_INTERVAL, RECONNECT_ATTEMPTS,
    RECONNECT_DELAY, BLOCKED_PROCESSES
)
from shared.protocol import (
    Message, MessageType, SessionState,
    create_heartbeat, create_client_status
)
from .kiosk_desktop import KioskDesktop
from .fake_toolbar import FakeToolbar
import qasync
import argparse
import shared.protocol as protocol

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'client_config.json')

# Add file logging for persistent error tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('client_error.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Parse --dev flag for developer mode
parser = argparse.ArgumentParser()
parser.add_argument('--dev', action='store_true', help='Run in developer (windowed) mode')
args, _ = parser.parse_known_args()

def get_server_ip():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get('server_ip')
    return None

def save_server_ip(ip):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'server_ip': ip}, f)

class BlankDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #111;")
        self.showFullScreen()

class KioskClient(QMainWindow):
    def __init__(self, server_ip):
        super().__init__()
        self.server_ip = server_ip
        self.client_ip = self._get_local_ip()
        if not args.dev:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.showFullScreen()
        else:
            self.setWindowTitle('Kiosk Client (DEV MODE)')
            self.resize(1200, 800)
            self.show()
        self.desktop = KioskDesktop(self)
        self.toolbar = FakeToolbar(self)
        self.blank_desktop = QMainWindow()
        self.blank_desktop.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.blank_desktop.setStyleSheet("background-color: #111;")
        self.blank_label = QLabel("Waiting for session to start...", self.blank_desktop)
        self.blank_label.setStyleSheet("color: white; font-size: 24px;")
        self.blank_label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addWidget(self.blank_label)
        container = QWidget()
        container.setLayout(layout)
        self.blank_desktop.setCentralWidget(container)
        self.blank_desktop.hide()
        self.desktop.hide()
        self.toolbar.hide()
        self.active_windows = {}
        self.window_timer = QTimer()
        self.window_timer.timeout.connect(self._check_windows)
        self.window_timer.start(1000)
        self.reader = None
        self.writer = None
        self.client_id = None
        self.state = SessionState.INACTIVE
        self.remaining_time = None
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._send_heartbeat)
        self.session_timer = None
        self.desktop.app_launched.connect(self._handle_app_launched)
        self.toolbar.app_activated.connect(self._handle_app_activated)
        self.toolbar.app_minimized.connect(self._handle_app_minimized)
        self.toolbar.app_restored.connect(self._handle_app_restored)
        self.toolbar.app_closed.connect(self._handle_app_closed)
        self.connection_status = 'Disconnected'
        self.toolbar.update_session_time('Status: Disconnected')
        QTimer.singleShot(0, lambda: asyncio.create_task(self._connect_to_server()))
        self._show_blank()

    def _show_blank(self):
        self.desktop.hide()
        self.toolbar.hide()
        msg = "Waiting for session to start..." if self.connection_status == 'Connected' else "Not connected to server"
        self.blank_label.setText(msg)
        if not args.dev:
            self.blank_desktop.showFullScreen()
        else:
            self.blank_desktop.show()
        self.blank_desktop.raise_()

    def _show_kiosk(self):
        self.blank_desktop.hide()
        if not args.dev:
            self.desktop.showFullScreen()
        else:
            self.desktop.show()
        self.toolbar.show()
        self.desktop.raise_()
        self.toolbar.raise_()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.server_ip, DEFAULT_SERVER_PORT))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return 'Unknown'

    async def _connect_to_server(self):
        for attempt in range(RECONNECT_ATTEMPTS):
            try:
                self.reader, self.writer = await asyncio.open_connection(
                    self.server_ip,
                    DEFAULT_SERVER_PORT
                )
                self.connection_status = 'Connected'
                self.toolbar.update_session_time(f'Status: Connected ({self.client_ip})')
                # Send handshake with client_ip
                hello = {'client_ip': self.client_ip}
                self.writer.write(json.dumps(hello).encode() + b'\n')
                await self.writer.drain()
                self.heartbeat_timer.start(HEARTBEAT_INTERVAL * 1000)
                asyncio.create_task(self._receive_messages())
                return
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                self.connection_status = 'Disconnected'
                self.toolbar.update_session_time('Status: Disconnected')
                if attempt < RECONNECT_ATTEMPTS - 1:
                    await asyncio.sleep(RECONNECT_DELAY)
        QMessageBox.critical(
            self,
            "Connection Error",
            f"Failed to connect to server at {self.server_ip}. Please check your network connection."
        )
        sys.exit(1)

    async def _receive_messages(self):
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                try:
                    raw = data.decode().strip()
                    logger.info(f"Received: {raw}")
                    msg_dict = json.loads(raw)
                    msg_type = msg_dict.get('type')
                    if msg_type in [MessageType.SESSION_START, MessageType.SESSION_PAUSE, MessageType.SESSION_RESUME, MessageType.SESSION_END]:
                        message = protocol.SessionMessage(**msg_dict)
                    elif msg_type == MessageType.ALLOWED_APPS:
                        message = protocol.AllowedAppsMessage(**msg_dict)
                    elif msg_type == MessageType.CLIENT_STATUS:
                        message = protocol.ClientStatusMessage(**msg_dict)
                    else:
                        message = protocol.Message(**msg_dict)
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self._handle_disconnect()

    async def _handle_message(self, message: Message):
        if message.type == MessageType.SESSION_START:
            self.state = SessionState.ACTIVE
            self.remaining_time = getattr(message, 'duration', 0)
            # Only set allowed apps if present
            if hasattr(message, 'apps') and message.apps:
                self.desktop.set_allowed_apps(message.apps)
            self._show_kiosk()
            self._start_session_timer()
        elif message.type == MessageType.SESSION_PAUSE:
            self.state = SessionState.PAUSED
            self._pause_session()
        elif message.type == MessageType.SESSION_RESUME:
            self.state = SessionState.ACTIVE
            self._resume_session()
        elif message.type == MessageType.SESSION_END:
            self.state = SessionState.ENDED
            self._end_session()
        elif message.type == MessageType.ALLOWED_APPS:
            if hasattr(message, 'apps') and message.apps:
                self.desktop.set_allowed_apps(message.apps)
        elif message.type == MessageType.REMOVE_CLIENT:
            self._remove_client()

    def _handle_disconnect(self):
        self.heartbeat_timer.stop()
        self.connection_status = 'Disconnected'
        self.toolbar.update_session_time('Status: Disconnected')
        QMessageBox.warning(
            self,
            "Connection Lost",
            f"Lost connection to server at {self.server_ip}. Attempting to reconnect..."
        )
        QTimer.singleShot(0, lambda: asyncio.create_task(self._connect_to_server()))

    def _send_heartbeat(self):
        if self.writer and not self.writer.is_closing():
            message = create_heartbeat(self.client_id)
            self.writer.write(message.to_json().encode() + b'\n')
            asyncio.create_task(self.writer.drain())

    def _start_session_timer(self):
        if self.session_timer:
            self.session_timer.stop()
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self._update_session_time)
        self.session_timer.start(1000)
        self._update_session_time()

    def _update_session_time(self):
        if self.state == SessionState.PAUSED:
            self.toolbar.update_session_time(f'Status: Paused ({self.client_ip})')
        elif self.state == SessionState.ACTIVE and self.remaining_time is not None:
            hours = self.remaining_time // 3600
            minutes = (self.remaining_time % 3600) // 60
            seconds = self.remaining_time % 60
            self.toolbar.update_session_time(f'Time left: {hours:02d}:{minutes:02d}:{seconds:02d}')
            self.remaining_time -= 1
            if self.remaining_time < 0:
                self._end_session()
        else:
            self.toolbar.update_session_time(f'No session')

    def _end_session(self):
        if self.session_timer:
            self.session_timer.stop()
        self._close_all_apps()
        self.state = SessionState.ENDED
        self._show_blank()
        QMessageBox.information(
            self,
            "Session Ended",
            "Your session has ended. The desktop is now locked."
        )

    def _handle_app_launched(self, app_name: str, app_path: str):
        self.toolbar.add_app(app_name, app_path)
        self._check_windows()

    def _handle_app_activated(self, app_name: str):
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    def _handle_app_minimized(self, app_name: str):
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    def _handle_app_restored(self, app_name: str):
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    def _handle_app_closed(self, app_name: str):
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            del self.active_windows[app_name]

    def _check_windows(self):
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    if process.name() in BLOCKED_PROCESSES:
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                        return True
                    for app_name, app_hwnd in self.active_windows.items():
                        if app_hwnd == hwnd:
                            self.toolbar.update_app_state(
                                app_name,
                                win32gui.IsWindowVisible(hwnd)
                            )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True
        win32gui.EnumWindows(callback, None)

    def _close_all_apps(self):
        for app_name in list(self.active_windows.keys()):
            self._handle_app_closed(app_name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        toolbar_height = self.toolbar.height()
        self.toolbar.setGeometry(
            0,
            self.height() - toolbar_height,
            self.width(),
            toolbar_height
        )
        self.desktop.setGeometry(
            0,
            0,
            self.width(),
            self.height() - toolbar_height
        )
        self.blank_desktop.setGeometry(0, 0, self.width(), self.height())

    def _pause_session(self):
        self.desktop.hide()
        self.toolbar.hide()
        self.blank_desktop.setStyleSheet("background-color: #222; color: white;")
        self.blank_desktop.setWindowTitle("Session Paused")
        if not args.dev:
            self.blank_desktop.showFullScreen()
        else:
            self.blank_desktop.show()
        self.blank_desktop.raise_()
        if self.session_timer:
            self.session_timer.stop()

    def _resume_session(self):
        self.blank_desktop.hide()
        if not args.dev:
            self.desktop.showFullScreen()
        else:
            self.desktop.show()
        self.toolbar.show()
        self.desktop.raise_()
        self.toolbar.raise_()
        if self.session_timer:
            self.session_timer.start(1000)

    def _remove_client(self):
        self._close_all_apps()
        self.blank_desktop.setStyleSheet("background-color: #111;")
        self.blank_desktop.setWindowTitle("")
        self.desktop.hide()
        self.toolbar.hide()
        self.blank_desktop.showFullScreen()
        self.blank_desktop.raise_()
        QMessageBox.information(self, "Removed", "This client has been removed by the admin. Exiting.")
        QApplication.quit()

async def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    # Get or prompt for server IP
    server_ip = get_server_ip()
    if not server_ip:
        ip, ok = QInputDialog.getText(None, "Server IP", "Enter the server IP address:")
        if not ok or not ip:
            QMessageBox.critical(None, "No IP Entered", "No server IP entered. Exiting.")
            sys.exit(1)
        save_server_ip(ip)
        server_ip = ip
    window = KioskClient(server_ip)
    window.show()
    with loop:
        await loop.run_forever()

if __name__ == "__main__":
    asyncio.run(main()) 