"""Unit tests for ChannelGateway routing."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from ruche.runtime.channels.gateway import ChannelGateway
from ruche.runtime.channels.models import ChannelPolicy


class MockChannelAdapter:
    """Mock channel adapter for testing."""

    def __init__(self, channel_name: str):
        self._channel_name = channel_name
        self.send_message = AsyncMock()
        self.get_capabilities = AsyncMock()

    @property
    def channel_name(self) -> str:
        return self._channel_name


class MockOutboundMessage:
    """Mock outbound message."""

    def __init__(self, channel: str, tenant_id=None, agent_id=None):
        self.channel = channel
        self.channel_user_id = "+1234567890"
        self.content = "Test message"
        self.metadata = {}
        self.tenant_id = tenant_id or uuid4()
        self.agent_id = agent_id or uuid4()


class MockDeliveryResult:
    """Mock delivery result."""

    def __init__(self, success: bool = True):
        self.success = success
        self.provider_message_id = "msg-123" if success else None
        self.error_message = None if success else "Delivery failed"


@pytest.fixture
def gateway() -> ChannelGateway:
    """Create channel gateway."""
    return ChannelGateway()


@pytest.fixture
def whatsapp_adapter() -> MockChannelAdapter:
    """Create WhatsApp adapter."""
    return MockChannelAdapter("whatsapp")


@pytest.fixture
def webchat_adapter() -> MockChannelAdapter:
    """Create webchat adapter."""
    return MockChannelAdapter("webchat")


class TestRegisterAdapter:
    """Tests for adapter registration."""

    def test_register_adapter_adds_to_registry(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Adapter is added to registry."""
        gateway.register_adapter("whatsapp", whatsapp_adapter)

        assert "whatsapp" in gateway._adapters
        assert gateway._adapters["whatsapp"] == whatsapp_adapter

    def test_register_multiple_adapters(
        self,
        gateway: ChannelGateway,
        whatsapp_adapter: MockChannelAdapter,
        webchat_adapter: MockChannelAdapter,
    ) -> None:
        """Multiple adapters can be registered."""
        gateway.register_adapter("whatsapp", whatsapp_adapter)
        gateway.register_adapter("webchat", webchat_adapter)

        assert len(gateway._adapters) == 2
        assert gateway._adapters["whatsapp"] == whatsapp_adapter
        assert gateway._adapters["webchat"] == webchat_adapter

    def test_register_adapter_overwrites_existing(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Registering same channel overwrites previous adapter."""
        adapter1 = MockChannelAdapter("whatsapp")
        adapter2 = MockChannelAdapter("whatsapp")

        gateway.register_adapter("whatsapp", adapter1)
        gateway.register_adapter("whatsapp", adapter2)

        assert gateway._adapters["whatsapp"] == adapter2


class TestLoadPolicy:
    """Tests for channel policy loading."""

    async def test_load_policy_returns_adapter_capabilities(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Returns adapter capabilities as policy."""
        expected_policy = ChannelPolicy(
            channel="whatsapp",
            max_message_length=4096,
        )
        whatsapp_adapter.get_capabilities.return_value = expected_policy

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        policy = await gateway.load_policy("whatsapp", uuid4(), uuid4())

        assert policy == expected_policy
        whatsapp_adapter.get_capabilities.assert_called_once()

    async def test_load_policy_caches_result(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Caches policy for same channel/tenant/agent."""
        policy_obj = ChannelPolicy(channel="whatsapp")
        whatsapp_adapter.get_capabilities.return_value = policy_obj

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        tenant_id = uuid4()
        agent_id = uuid4()

        policy1 = await gateway.load_policy("whatsapp", tenant_id, agent_id)
        policy2 = await gateway.load_policy("whatsapp", tenant_id, agent_id)

        assert policy1 == policy2
        whatsapp_adapter.get_capabilities.assert_called_once()

    async def test_load_policy_different_context_not_cached(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Different tenant/agent loads separate policy."""
        policy_obj = ChannelPolicy(channel="whatsapp")
        whatsapp_adapter.get_capabilities.return_value = policy_obj

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        await gateway.load_policy("whatsapp", uuid4(), uuid4())
        await gateway.load_policy("whatsapp", uuid4(), uuid4())

        assert whatsapp_adapter.get_capabilities.call_count == 2

    async def test_load_policy_adapter_not_found_returns_default(
        self, gateway: ChannelGateway
    ) -> None:
        """Returns default policy when adapter not found."""
        policy = await gateway.load_policy("nonexistent", uuid4(), uuid4())

        assert policy.channel == "nonexistent"


class TestSend:
    """Tests for sending messages."""

    async def test_send_calls_adapter_send_message(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Calls adapter send_message method."""
        result = MockDeliveryResult(success=True)
        whatsapp_adapter.send_message.return_value = result
        whatsapp_adapter.get_capabilities.return_value = ChannelPolicy(channel="whatsapp")

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        message = MockOutboundMessage("whatsapp")
        delivery_result = await gateway.send(message)

        whatsapp_adapter.send_message.assert_called_once()
        assert delivery_result.success is True

    async def test_send_loads_policy_if_not_provided(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Loads policy if not provided."""
        result = MockDeliveryResult(success=True)
        policy_obj = ChannelPolicy(channel="whatsapp")
        whatsapp_adapter.send_message.return_value = result
        whatsapp_adapter.get_capabilities.return_value = policy_obj

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        message = MockOutboundMessage("whatsapp")
        await gateway.send(message)

        whatsapp_adapter.get_capabilities.assert_called_once()

    async def test_send_uses_provided_policy(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Uses provided policy without loading."""
        result = MockDeliveryResult(success=True)
        whatsapp_adapter.send_message.return_value = result

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        message = MockOutboundMessage("whatsapp")
        policy = ChannelPolicy(channel="whatsapp")
        await gateway.send(message, policy=policy)

        whatsapp_adapter.get_capabilities.assert_not_called()
        call_args = whatsapp_adapter.send_message.call_args[0]
        assert call_args[1] == policy

    async def test_send_adapter_not_found_returns_failed_result(
        self, gateway: ChannelGateway
    ) -> None:
        """Returns failed result when adapter not found."""
        message = MockOutboundMessage("nonexistent")

        result = await gateway.send(message)

        assert result.success is False
        assert result.error_message == "Channel adapter not found"

    async def test_send_handles_adapter_exception(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Handles adapter exceptions gracefully."""
        whatsapp_adapter.send_message.side_effect = RuntimeError("Adapter failed")
        whatsapp_adapter.get_capabilities.return_value = ChannelPolicy(channel="whatsapp")

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        message = MockOutboundMessage("whatsapp")
        result = await gateway.send(message)

        assert result.success is False
        assert "Adapter failed" in result.error_message


class TestListChannels:
    """Tests for listing registered channels."""

    def test_list_channels_empty_initially(self, gateway: ChannelGateway) -> None:
        """Returns empty list when no adapters registered."""
        channels = gateway.list_channels()
        assert channels == []

    def test_list_channels_returns_registered_channels(
        self,
        gateway: ChannelGateway,
        whatsapp_adapter: MockChannelAdapter,
        webchat_adapter: MockChannelAdapter,
    ) -> None:
        """Returns list of registered channel identifiers."""
        gateway.register_adapter("whatsapp", whatsapp_adapter)
        gateway.register_adapter("webchat", webchat_adapter)

        channels = gateway.list_channels()

        assert len(channels) == 2
        assert "whatsapp" in channels
        assert "webchat" in channels


class TestHasChannel:
    """Tests for checking channel registration."""

    def test_has_channel_returns_true_for_registered(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Returns True for registered channel."""
        gateway.register_adapter("whatsapp", whatsapp_adapter)

        assert gateway.has_channel("whatsapp") is True

    def test_has_channel_returns_false_for_unregistered(
        self, gateway: ChannelGateway
    ) -> None:
        """Returns False for unregistered channel."""
        assert gateway.has_channel("nonexistent") is False


class TestFailedResult:
    """Tests for failed result creation."""

    def test_failed_result_has_correct_attributes(
        self, gateway: ChannelGateway
    ) -> None:
        """Failed result has expected attributes."""
        result = gateway._failed_result("Test error")

        assert result.success is False
        assert result.provider_message_id is None
        assert result.error_message == "Test error"


class TestIntegration:
    """Integration tests for ChannelGateway."""

    async def test_send_message_end_to_end(
        self, gateway: ChannelGateway, whatsapp_adapter: MockChannelAdapter
    ) -> None:
        """Full message send flow works."""
        result_obj = MockDeliveryResult(success=True)
        policy_obj = ChannelPolicy(
            channel="whatsapp",
            max_message_length=4096,
        )
        whatsapp_adapter.send_message.return_value = result_obj
        whatsapp_adapter.get_capabilities.return_value = policy_obj

        gateway.register_adapter("whatsapp", whatsapp_adapter)

        message = MockOutboundMessage("whatsapp")
        result = await gateway.send(message)

        assert result.success is True
        assert result.provider_message_id == "msg-123"

    async def test_multiple_channels_isolated(
        self,
        gateway: ChannelGateway,
        whatsapp_adapter: MockChannelAdapter,
        webchat_adapter: MockChannelAdapter,
    ) -> None:
        """Messages route to correct adapters."""
        whatsapp_result = MockDeliveryResult(success=True)
        webchat_result = MockDeliveryResult(success=True)

        whatsapp_adapter.send_message.return_value = whatsapp_result
        whatsapp_adapter.get_capabilities.return_value = ChannelPolicy(channel="whatsapp")
        webchat_adapter.send_message.return_value = webchat_result
        webchat_adapter.get_capabilities.return_value = ChannelPolicy(channel="webchat")

        gateway.register_adapter("whatsapp", whatsapp_adapter)
        gateway.register_adapter("webchat", webchat_adapter)

        whatsapp_msg = MockOutboundMessage("whatsapp")
        webchat_msg = MockOutboundMessage("webchat")

        await gateway.send(whatsapp_msg)
        await gateway.send(webchat_msg)

        whatsapp_adapter.send_message.assert_called_once()
        webchat_adapter.send_message.assert_called_once()
