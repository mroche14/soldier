"""AG-UI webchat channel adapter.

Integrates with AG-UI for rich web-based chat experiences.
Stub implementation - to be completed when AG-UI integration is needed.
"""

from focal.infrastructure.channels.models import OutboundMessage
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class AGUIWebchatAdapter:
    """AG-UI webchat channel adapter.

    Provides rich web chat with button support, file uploads, etc.
    """

    def __init__(self, config: dict | None = None) -> None:
        """Initialize AG-UI adapter.

        Args:
            config: AG-UI configuration
        """
        self._config = config or {}

    async def send(self, message: OutboundMessage) -> None:
        """Send a message via AG-UI webchat.

        Args:
            message: Message to send
        """
        logger.warning(
            "agui_webchat_stub",
            message="AG-UI webchat adapter not yet implemented",
        )
        # Stub - would send via AG-UI WebSocket/HTTP
