"""
Main client application for the kiosk system.
"""
import sys
import os
import asyncio
import logging
import psutil
import win32gui
import win32con
import win32process
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import Qt, QTimer, QRect
from shared.constants import (
    DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT,
    HEARTBEAT_INTERVAL, RECONNECT_ATTEMPTS,
    RECONNECT_DELAY, BLOCKED_PROCESSES
)
from shared.protocol import (
    Message, MessageType, SessionState,
    create_heartbeat, create_client_status
)
from .kiosk_desktop import KioskDesktop
from .fake_toolbar import FakeToolbar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KioskClient(QMainWindow):
    """Main kiosk client window."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.showFullScreen()
        
        # Create desktop and toolbar
        self.desktop = KioskDesktop(self)
        self.toolbar = FakeToolbar(self)
        
        # Connect signals
        self.desktop.app_launched.connect(self._handle_app_launched)
        self.toolbar.app_activated.connect(self._handle_app_activated)
        self.toolbar.app_minimized.connect(self._handle_app_minimized)
        self.toolbar.app_restored.connect(self._handle_app_restored)
        self.toolbar.app_closed.connect(self._handle_app_closed)
        
        # Set up window management
        self.active_windows = {}  # app_name -> hwnd
        self.window_timer = QTimer()
        self.window_timer.timeout.connect(self._check_windows)
        self.window_timer.start(1000)  # Check every second
        
        # Set up network
        self.reader = None
        self.writer = None
        self.client_id = None
        self.state = SessionState.INACTIVE
        self.remaining_time = None
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._send_heartbeat)
        
        # Start connection
        asyncio.create_task(self._connect_to_server())

    async def _connect_to_server(self):
        """Connect to the server."""
        for attempt in range(RECONNECT_ATTEMPTS):
            try:
                self.reader, self.writer = await asyncio.open_connection(
                    DEFAULT_SERVER_HOST,
                    DEFAULT_SERVER_PORT
                )
                logger.info("Connected to server")
                self.heartbeat_timer.start(HEARTBEAT_INTERVAL * 1000)
                asyncio.create_task(self._receive_messages())
                return
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < RECONNECT_ATTEMPTS - 1:
                    await asyncio.sleep(RECONNECT_DELAY)
        
        QMessageBox.critical(
            self,
            "Connection Error",
            "Failed to connect to server. Please check your network connection."
        )
        sys.exit(1)

    async def _receive_messages(self):
        """Receive and handle messages from the server."""
        try:
            while True:
                data = await self.reader.readline()
                if not data:
                    break
                
                message = Message.from_json(data.decode().strip())
                await self._handle_message(message)
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self._handle_disconnect()

    async def _handle_message(self, message: Message):
        """Handle a message from the server."""
        if message.type == MessageType.SESSION_START:
            self.state = SessionState.ACTIVE
            self.remaining_time = message.duration
            self._start_session_timer()
        elif message.type == MessageType.SESSION_END:
            self.state = SessionState.ENDED
            self._end_session()
        elif message.type == MessageType.ALLOWED_APPS:
            self.desktop.set_allowed_apps(message.apps)

    def _handle_disconnect(self):
        """Handle server disconnection."""
        self.heartbeat_timer.stop()
        QMessageBox.warning(
            self,
            "Connection Lost",
            "Lost connection to server. Attempting to reconnect..."
        )
        asyncio.create_task(self._connect_to_server())

    def _send_heartbeat(self):
        """Send heartbeat to server."""
        if self.writer and not self.writer.is_closing():
            message = create_heartbeat(self.client_id)
            self.writer.write(message.to_json().encode() + b'\n')
            asyncio.create_task(self.writer.drain())

    def _start_session_timer(self):
        """Start the session timer."""
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self._update_session_time)
        self.session_timer.start(1000)  # Update every second

    def _update_session_time(self):
        """Update the session time display."""
        if self.remaining_time is not None:
            self.remaining_time -= 1
            self.toolbar.update_session_time(self.remaining_time)
            
            if self.remaining_time <= 0:
                self._end_session()

    def _end_session(self):
        """End the current session."""
        self.session_timer.stop()
        self._close_all_apps()
        self.state = SessionState.ENDED
        QMessageBox.information(
            self,
            "Session Ended",
            "Your session has ended. The system will now lock."
        )
        os.system("rundll32.exe user32.dll,LockWorkStation")

    def _handle_app_launched(self, app_name: str, app_path: str):
        """Handle application launch."""
        self.toolbar.add_app(app_name, app_path)
        self._check_windows()  # Update window list immediately

    def _handle_app_activated(self, app_name: str):
        """Handle application activation."""
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    def _handle_app_minimized(self, app_name: str):
        """Handle application minimization."""
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    def _handle_app_restored(self, app_name: str):
        """Handle application restoration."""
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    def _handle_app_closed(self, app_name: str):
        """Handle application closure."""
        if app_name in self.active_windows:
            hwnd = self.active_windows[app_name]
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            del self.active_windows[app_name]

    def _check_windows(self):
        """Check for running windows and update toolbar."""
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    if process.name() in BLOCKED_PROCESSES:
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                        return True
                    
                    # Update active windows
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
        """Close all running applications."""
        for app_name in list(self.active_windows.keys()):
            self._handle_app_closed(app_name)

    def resizeEvent(self, event):
        """Handle window resize event."""
        super().resizeEvent(event)
        # Update toolbar position
        toolbar_height = self.toolbar.height()
        self.toolbar.setGeometry(
            0,
            self.height() - toolbar_height,
            self.width(),
            toolbar_height
        )
        # Update desktop size
        self.desktop.setGeometry(
            0,
            0,
            self.width(),
            self.height() - toolbar_height
        )

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = KioskClient()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 