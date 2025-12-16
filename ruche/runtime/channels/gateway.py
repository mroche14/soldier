"""Channel gateway for routing messages to/from channels.

Routes inbound messages to agents and outbound messages to channel adapters.
"""

from typing import Any
from uuid import UUID

from ruche.observability.logging import get_logger
from ruche.runtime.channels.adapter import (
    ChannelAdapter,
    DeliveryResult,
    OutboundMessage,
)
from ruche.runtime.channels.models import ChannelPolicy

logger = get_logger(__name__)


class ChannelGateway:
    """Routes messages to/from channel adapters.

    Manages adapter registration and delegates send/receive operations.
    This is the runtime gateway that ACF and Agent use to interact with channels.
    """

    def __init__(self) -> None:
        """Initialize the gateway with empty adapter registry."""
        self._adapters: dict[str, ChannelAdapter] = {}
        self._policies: dict[str, ChannelPolicy] = {}

    def register_adapter(
        self,
        channel: str,
        adapter: ChannelAdapter,
    ) -> None:
        """Register a channel adapter.

        Args:
            channel: Channel identifier (e.g., 'whatsapp', 'webchat')
            adapter: Adapter instance implementing ChannelAdapter protocol
        """
        self._adapters[channel] = adapter
        logger.info("channel_adapter_registered", channel=channel)

    async def load_policy(
        self,
        channel: str,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> ChannelPolicy:
        """Load channel policy for a tenant/agent.

        Resolution order:
        1. Check cache
        2. Get adapter default capabilities
        3. Apply tenant/agent overrides (if any)

        Args:
            channel: Channel identifier
            tenant_id: Tenant context
            agent_id: Agent context

        Returns:
            ChannelPolicy with resolved configuration
        """
        cache_key = f"{channel}:{tenant_id}:{agent_id}"
        if cache_key in self._policies:
            return self._policies[cache_key]

        adapter = self._adapters.get(channel)
        if not adapter:
            logger.warning(
                "channel_adapter_not_found",
                channel=channel,
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
            )
            # Return default policy
            policy = ChannelPolicy(channel=channel)
        else:
            # Get adapter's default policy
            policy = await adapter.get_capabilities()

        # Cache and return
        self._policies[cache_key] = policy
        return policy

    async def send(
        self,
        message: OutboundMessage,
        policy: ChannelPolicy | None = None,
    ) -> DeliveryResult:
        """Send message to appropriate channel.

        Applies channel policy for formatting before delivery.

        Args:
            message: Outbound message to send
            policy: Channel policy (will be loaded if not provided)

        Returns:
            DeliveryResult with success status and provider message ID
        """
        adapter = self._adapters.get(message.channel)
        if not adapter:
            logger.error(
                "channel_adapter_not_found",
                channel=message.channel,
                channel_user_id=message.channel_user_id,
            )
            return self._failed_result("Channel adapter not found")

        # Load policy if not provided
        if policy is None:
            policy = await self.load_policy(
                channel=message.channel,
                tenant_id=message.tenant_id,
                agent_id=message.agent_id,
            )

        try:
            result = await adapter.send_message(message, policy)
            logger.info(
                "message_sent",
                channel=message.channel,
                channel_user_id=message.channel_user_id,
                success=result.success,
                provider_message_id=result.provider_message_id,
            )
            return result
        except Exception as e:
            logger.error(
                "message_send_failed",
                channel=message.channel,
                channel_user_id=message.channel_user_id,
                error=str(e),
            )
            return self._failed_result(str(e))

    def list_channels(self) -> list[str]:
        """Get list of registered channels.

        Returns:
            List of channel identifiers
        """
        return list(self._adapters.keys())

    def has_channel(self, channel: str) -> bool:
        """Check if a channel adapter is registered.

        Args:
            channel: Channel identifier

        Returns:
            True if adapter is registered
        """
        return channel in self._adapters

    def _failed_result(self, error: str) -> Any:
        """Create a failed delivery result.

        Args:
            error: Error message

        Returns:
            DeliveryResult indicating failure
        """

        class FailedResult:
            success = False
            provider_message_id = None
            error_message = error

        return FailedResult()
