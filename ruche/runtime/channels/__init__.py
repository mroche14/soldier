"""Channel policy models and configuration.

This module defines policies for how agents behave on different channels,
the ChannelGateway for routing messages, and the ChannelAdapter protocol.
"""

from ruche.runtime.channels.adapter import ChannelAdapter
from ruche.runtime.channels.adapters import WebchatAdapter
from ruche.runtime.channels.gateway import ChannelGateway
from ruche.runtime.channels.models import (
    ChannelBinding,
    ChannelPolicy,
    SupersedeMode,
)

__all__ = [
    # Models
    "ChannelBinding",
    "ChannelPolicy",
    "SupersedeMode",
    # Core
    "ChannelAdapter",
    "ChannelGateway",
    # Adapters
    "WebchatAdapter",
]
