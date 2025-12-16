"""Channels for message routing to external platforms.

Provides channel gateway and adapters for webchat, WhatsApp, email, etc.
"""

from ruche.infrastructure.channels.adapters import (
    AGUIWebchatAdapter,
    SimpleWebchatAdapter,
    SMTPEmailAdapter,
    TwilioWhatsAppAdapter,
)
from ruche.infrastructure.channels.defaults import DEFAULT_CHANNEL_POLICIES
from ruche.infrastructure.channels.gateway import ChannelGateway
from ruche.infrastructure.channels.models import (
    ChannelBinding,
    ChannelPolicy,
    ChannelType,
    InboundMessage,
    OutboundMessage,
    SupersedeMode,
)

__all__ = [
    # Core
    "ChannelGateway",
    # Models
    "ChannelType",
    "ChannelPolicy",
    "ChannelBinding",
    "InboundMessage",
    "OutboundMessage",
    "SupersedeMode",
    # Defaults
    "DEFAULT_CHANNEL_POLICIES",
    # Adapters
    "AGUIWebchatAdapter",
    "SimpleWebchatAdapter",
    "TwilioWhatsAppAdapter",
    "SMTPEmailAdapter",
]
