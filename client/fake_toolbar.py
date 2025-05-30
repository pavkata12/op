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
        # Floating session timer label (upper right)
        self.session_timer_label = QLabel("", parent)
        self.session_timer_label.setStyleSheet("background: rgba(0,0,0,0.5); color: white; font-size: 20px; border-radius: 8px; padding: 6px 18px;")
        self.session_timer_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.session_timer_label.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.session_timer_label.setAttribute(Qt.WA_TranslucentBackground)
        self.session_timer_label.setAttribute(Qt.WA_ShowWithoutActivating)
        self.session_timer_label.setVisible(False)
        self.session_timer_label.installEventFilter(self)

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

    def update_session_time(self, text: str):
        self.session_timer_label.setText(text)
        self.session_timer_label.setVisible(True)
        # Place in upper right corner of parent
        if self.parent():
            parent_geom = self.parent().geometry()
            label_width = self.session_timer_label.sizeHint().width()
            label_height = self.session_timer_label.sizeHint().height()
            x = parent_geom.x() + parent_geom.width() - label_width - 30
            y = parent_geom.y() + 30
            self.session_timer_label.setGeometry(x, y, label_width, label_height)

    def eventFilter(self, obj, event):
        if obj == self.session_timer_label:
            if event.type() == event.Enter:
                self.session_timer_label.setStyleSheet("background: rgba(0,0,0,0.95); color: white; font-size: 20px; border-radius: 8px; padding: 6px 18px;")
            elif event.type() == event.Leave:
                self.session_timer_label.setStyleSheet("background: rgba(0,0,0,0.5); color: white; font-size: 20px; border-radius: 8px; padding: 6px 18px;")
        return super().eventFilter(obj, event)

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