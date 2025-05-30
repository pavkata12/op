"""
Kiosk desktop component for displaying allowed applications.
"""
import os
import subprocess
from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QLabel,
    QScrollArea, QVBoxLayout, QSizePolicy, QToolButton
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon, QPixmap
from shared.constants import ICON_SIZE, GRID_SPACING
from functools import partial

class AppIcon(QToolButton):
    """Icon button for launching applications."""
    def __init__(self, app_name: str, icon_path: str, app_path: str, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.app_path = app_path
        
        # Set icon
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        
        # Set text
        self.setText(app_name)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        
        # Set size and policy
        self.setFixedSize(ICON_SIZE + 40, ICON_SIZE + 40)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Set style
        self.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                color: white;
                padding: 5px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 5px;
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)

class KioskDesktop(QWidget):
    """Kiosk desktop that displays allowed applications."""
    app_launched = Signal(str, str)  # Emitted when an app is launched (app_name, app_path)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add timer banner
        self.timer_label = QLabel("")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("background: rgba(0,0,0,0.7); color: white; font-size: 40px; border-radius: 18px; padding: 24px 0px; margin-bottom: 18px;")
        main_layout.addWidget(self.timer_label)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #3f3f3f;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Create content widget
        content_widget = QWidget()
        self.grid_layout = QGridLayout(content_widget)
        self.grid_layout.setSpacing(GRID_SPACING)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Set background
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        # Store app icons
        self.app_icons: Dict[str, AppIcon] = {}

    def set_allowed_apps(self, apps: List[Dict[str, str]]):
        """Set the list of allowed applications."""
        # Clear existing icons
        for icon in self.app_icons.values():
            self.grid_layout.removeWidget(icon)
            icon.deleteLater()
        self.app_icons.clear()
        
        # Add new icons
        row = 0
        col = 0
        max_cols = self.width() // (ICON_SIZE + 40 + GRID_SPACING)
        
        for app in apps:
            icon = AppIcon(
                app['name'],
                app['icon_path'],
                app['path']
            )
            icon.clicked.connect(partial(self._handle_app_click, app['name'], app['path']))
            
            self.grid_layout.addWidget(icon, row, col)
            self.app_icons[app['name']] = icon
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _handle_app_click(self, app_name: str, app_path: str):
        """Handle app icon click."""
        try:
            subprocess.Popen([app_path])
            self.app_launched.emit(app_name, app_path)
        except Exception as e:
            print(f"Error launching {app_name}: {e}")

    def resizeEvent(self, event):
        """Handle window resize event."""
        super().resizeEvent(event)
        # Recalculate grid layout
        if self.app_icons:
            max_cols = self.width() // (ICON_SIZE + 40 + GRID_SPACING)
            row = 0
            col = 0
            for icon in self.app_icons.values():
                self.grid_layout.removeWidget(icon)
                self.grid_layout.addWidget(icon, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1 

    def update_session_time(self, text: str):
        self.timer_label.setText(text) 