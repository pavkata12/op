"""
Protocol definitions for client-server communication.
"""
import json
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from datetime import datetime
from .constants import MessageType, SessionState

@dataclass
class Message:
    """Base message class for all communications."""
    type: str
    timestamp: str = None
    client_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

@dataclass
class SessionMessage(Message):
    """Message for session control."""
    duration: Optional[int] = None
    state: Optional[str] = None

@dataclass
class AllowedAppsMessage(Message):
    """Message containing allowed applications configuration."""
    apps: List[Dict[str, str]] = field(default_factory=list)  # List of dicts with name, path, icon_path

@dataclass
class ClientStatusMessage(Message):
    """Message containing client status information."""
    state: str = ""
    active_apps: List[str] = field(default_factory=list)
    remaining_time: Optional[int] = None
    error: Optional[str] = None

@dataclass
class ErrorMessage(Message):
    """Message for error reporting."""
    error: str = ""
    details: Optional[str] = None

def create_heartbeat(client_id: str) -> Message:
    """Create a heartbeat message."""
    return Message(type=MessageType.HEARTBEAT, client_id=client_id)

def create_session_start(client_id: str, duration: int) -> SessionMessage:
    """Create a session start message."""
    return SessionMessage(
        type=MessageType.SESSION_START,
        client_id=client_id,
        duration=duration,
        state=SessionState.ACTIVE
    )

def create_allowed_apps(client_id: str, apps: List[Dict[str, str]]) -> AllowedAppsMessage:
    """Create an allowed apps message."""
    return AllowedAppsMessage(
        type=MessageType.ALLOWED_APPS,
        client_id=client_id,
        apps=apps
    )

def create_client_status(
    client_id: str,
    state: str,
    active_apps: List[str],
    remaining_time: Optional[int] = None,
    error: Optional[str] = None
) -> ClientStatusMessage:
    """Create a client status message."""
    return ClientStatusMessage(
        type=MessageType.CLIENT_STATUS,
        client_id=client_id,
        state=state,
        active_apps=active_apps,
        remaining_time=remaining_time,
        error=error
    ) 