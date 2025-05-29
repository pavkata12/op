"""
Fake toolbar component that replaces the Windows taskbar.
"""
import os
from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel,
    QToolButton, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QPixmap
from shared.constants import TOOLBAR_HEIGHT, ICON_SIZE

class AppButton(QToolButton):
    """Button representing a running application in the toolbar."""
    def __init__(self, app_name: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setText(app_name)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setMinimumWidth(ICON_SIZE + 20)
        self.setMinimumHeight(TOOLBAR_HEIGHT)

class FakeToolbar(QWidget):
    """Fake toolbar that replaces the Windows taskbar."""
    app_activated = Signal(str)  # Emitted when an app is activated
    app_minimized = Signal(str)  # Emitted when an app is minimized
    app_restored = Signal(str)   # Emitted when an app is restored
    app_closed = Signal(str)     # Emitted when an app is closed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumHeight(TOOLBAR_HEIGHT)
        
        # Create layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(2)
        
        # Create app buttons container
        self.app_buttons: Dict[str, AppButton] = {}
        
        # Create session controls
        self.session_label = QLabel("Session: 00:00:00")
        self.session_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.session_label)
        
        self.layout.addStretch()
        
        # Create minimize/restore/close buttons
        self.minimize_btn = QPushButton()
        self.minimize_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        self.minimize_btn.clicked.connect(self.minimize_all)
        self.layout.addWidget(self.minimize_btn)
        
        self.restore_btn = QPushButton()
        self.restore_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
        self.restore_btn.clicked.connect(self.restore_all)
        self.layout.addWidget(self.restore_btn)
        
        self.close_btn = QPushButton()
        self.close_btn.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.close_btn.clicked.connect(self.close_all)
        self.layout.addWidget(self.close_btn)
        
        # Set stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-top: 1px solid #3f3f3f;
            }
            QPushButton, QToolButton {
                background-color: transparent;
                border: none;
                color: white;
                padding: 2px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #3f3f3f;
            }
            QPushButton:pressed, QToolButton:pressed {
                background-color: #4f4f4f;
            }
        """)

    def add_app(self, app_name: str, icon_path: str):
        """Add an application to the toolbar."""
        if app_name not in self.app_buttons:
            button = AppButton(app_name, icon_path)
            button.clicked.connect(lambda checked, name=app_name: self._handle_app_click(name, checked))
            self.app_buttons[app_name] = button
            self.layout.insertWidget(self.layout.count() - 4, button)  # Insert before session controls

    def remove_app(self, app_name: str):
        """Remove an application from the toolbar."""
        if app_name in self.app_buttons:
            button = self.app_buttons.pop(app_name)
            self.layout.removeWidget(button)
            button.deleteLater()

    def update_app_state(self, app_name: str, is_active: bool):
        """Update the state of an application button."""
        if app_name in self.app_buttons:
            self.app_buttons[app_name].setChecked(is_active)

    def update_session_time(self, remaining_seconds: int):
        """Update the session time display."""
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60
        self.session_label.setText(f"Session: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _handle_app_click(self, app_name: str, checked: bool):
        """Handle app button click."""
        if checked:
            self.app_activated.emit(app_name)
        else:
            self.app_minimized.emit(app_name)

    def minimize_all(self):
        """Minimize all applications."""
        for app_name in self.app_buttons:
            self.app_minimized.emit(app_name)
            self.app_buttons[app_name].setChecked(False)

    def restore_all(self):
        """Restore all applications."""
        for app_name in self.app_buttons:
            self.app_restored.emit(app_name)
            self.app_buttons[app_name].setChecked(True)

    def close_all(self):
        """Close all applications."""
        for app_name in list(self.app_buttons.keys()):
            self.app_closed.emit(app_name)
            self.remove_app(app_name) 