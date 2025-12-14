"""ChannelGateway for routing messages to/from channels.

Routes inbound messages to agents and outbound messages to channel adapters.
"""

from typing import Any

from focal.infrastructure.channels.models import (
    ChannelType,
    InboundMessage,
    OutboundMessage,
)
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class ChannelGateway:
    """Routes messages to/from channel adapters.

    Manages adapter registration and delegates send/receive operations.
    """

    def __init__(self) -> None:
        """Initialize the gateway with empty adapter registry."""
        self._adapters: dict[ChannelType, Any] = {}

    def register_adapter(self, channel_type: ChannelType, adapter: Any) -> None:
        """Register a channel adapter.

        Args:
            channel_type: Channel type identifier
            adapter: Adapter instance with send() method
        """
        self._adapters[channel_type] = adapter
        logger.info("channel_adapter_registered", channel_type=channel_type.value)

    async def send(self, message: OutboundMessage) -> bool:
        """Send a message via a channel.

        Args:
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        adapter = self._adapters.get(message.channel_type)
        if not adapter:
            logger.error(
                "channel_adapter_not_found",
                channel_type=message.channel_type.value,
            )
            return False

        try:
            await adapter.send(message)
            logger.debug(
                "message_sent",
                channel_type=message.channel_type.value,
                channel_user_id=message.channel_user_id,
            )
            return True
        except Exception as e:
            logger.error(
                "message_send_failed",
                channel_type=message.channel_type.value,
                error=str(e),
            )
            return False

    async def receive(self, message: InboundMessage) -> dict[str, Any]:
        """Process an inbound message.

        Args:
            message: Inbound message from channel

        Returns:
            Processing result (stub - would route to AlignmentEngine)
        """
        logger.info(
            "message_received",
            channel_type=message.channel_type.value,
            channel_user_id=message.channel_user_id,
        )

        # Stub - would route to AlignmentEngine
        return {
            "status": "received",
            "message": "Channel gateway stub - implementation pending",
        }

    def list_adapters(self) -> list[ChannelType]:
        """Get list of registered adapter types."""
        return list(self._adapters.keys())
