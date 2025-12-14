"""Enums for conversation domain."""

from enum import Enum


class Channel(str, Enum):
    """Communication channels.

    Represents the medium through which the conversation
    is taking place.
    """

    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBCHAT = "webchat"
    EMAIL = "email"
    VOICE = "voice"
    SMS = "sms"
    API = "api"


class SessionStatus(str, Enum):
    """Session lifecycle states.

    - ACTIVE: Session is in active use
    - IDLE: Session is idle, waiting for input
    - PROCESSING: Currently processing a message
    - INTERRUPTED: Session was interrupted (e.g., by handoff)
    - CLOSED: Session is closed and no longer accepting messages
    """

    ACTIVE = "active"
    IDLE = "idle"
    PROCESSING = "processing"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"
