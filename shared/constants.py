"""
Shared constants for the kiosk system.
"""

# Network
DEFAULT_SERVER_PORT = 5000
DEFAULT_SERVER_HOST = "0.0.0.0"
HEARTBEAT_INTERVAL = 5  # seconds
RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 2  # seconds

# Session
DEFAULT_SESSION_DURATION = 3600  # 1 hour in seconds
MIN_SESSION_DURATION = 300  # 5 minutes
MAX_SESSION_DURATION = 86400  # 24 hours

# Window Management
TOOLBAR_HEIGHT = 40
ICON_SIZE = 32
GRID_SPACING = 20
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# Security
BLOCKED_PROCESSES = [
    "explorer.exe",
    "taskmgr.exe",
    "cmd.exe",
    "powershell.exe",
    "regedit.exe",
    "msconfig.exe",
]

# Message Types
class MessageType:
    HEARTBEAT = "heartbeat"
    SESSION_START = "session_start"
    SESSION_PAUSE = "session_pause"
    SESSION_RESUME = "session_resume"
    SESSION_END = "session_end"
    SESSION_EXTEND = "session_extend"
    ALLOWED_APPS = "allowed_apps"
    CLIENT_STATUS = "client_status"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"

# Session States
class SessionState:
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    MAINTENANCE = "maintenance" 