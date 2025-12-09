"""Tests for TurnInput model."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from soldier.alignment.models.turn_input import TurnInput
from soldier.conversation.models.enums import Channel


class TestTurnInput:
    """Test suite for TurnInput model."""

    def test_create_with_required_fields(self):
        """Test creating turn input with required fields."""
        turn_input = TurnInput(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            channel=Channel.WEBCHAT,
            channel_user_id="user_123",
            message="Hello, I need help",
        )

        assert turn_input.channel == Channel.WEBCHAT
        assert turn_input.channel_user_id == "user_123"
        assert turn_input.message == "Hello, I need help"
        assert turn_input.customer_id is None
        assert turn_input.session_id is None
        assert turn_input.metadata == {}

    def test_create_with_all_fields(self):
        """Test creating turn input with all fields."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()

        turn_input = TurnInput(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WHATSAPP,
            channel_user_id="+1234567890",
            customer_id=customer_id,
            session_id=session_id,
            message="I want a refund",
            message_id="msg_abc123",
            language="en",
            metadata={"source": "mobile_app"},
        )

        assert turn_input.tenant_id == tenant_id
        assert turn_input.customer_id == customer_id
        assert turn_input.session_id == session_id
        assert turn_input.message_id == "msg_abc123"
        assert turn_input.language == "en"
        assert turn_input.metadata["source"] == "mobile_app"

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            TurnInput(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                channel=Channel.WEBCHAT,
                # Missing channel_user_id and message
            )
