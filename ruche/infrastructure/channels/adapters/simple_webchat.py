"""Simple webchat channel adapter.

Plain WebSocket-based chat without rich features.
Stub implementation - to be completed when simple webchat is needed.
"""

from ruche.infrastructure.channels.models import OutboundMessage
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class SimpleWebchatAdapter:
    """Simple WebSocket webchat adapter.

    Plain text chat over WebSocket.
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize simple webchat adapter.

        Args:
            config: WebSocket configuration
        """
        self._config = config or {}

    async def send(self, message: OutboundMessage) -> None:
        """Send a message via WebSocket.

        Args:
            message: Message to send
        """
        logger.warning(
            "simple_webchat_stub",
            message="Simple webchat adapter not yet implemented",
        )
        # Stub - would send via WebSocket
