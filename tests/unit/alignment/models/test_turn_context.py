"""Tests for TurnContext model."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from ruche.alignment.models.turn_context import TurnContext


class TestTurnContext:
    """Test suite for TurnContext model."""

    def test_create_with_all_required_fields(self):
        """Test that TurnContext can be created with all required fields."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        turn_context = TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            customer_id=customer_id,
            session_id=session_id,
            turn_number=1,
            session={"session_id": str(session_id), "turn_count": 0},
            customer_data={"customer_id": str(customer_id), "fields": {}},
            pipeline_config={"generation": {"enabled": True}},
            customer_data_fields={},
            glossary={},
            reconciliation_result=None,
            turn_started_at=now,
        )

        assert turn_context.tenant_id == tenant_id
        assert turn_context.agent_id == agent_id
        assert turn_context.customer_id == customer_id
        assert turn_context.session_id == session_id
        assert turn_context.turn_number == 1
        assert turn_context.turn_started_at == now

    def test_create_with_optional_fields(self):
        """Test that TurnContext can be created with optional fields populated."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        glossary = {
            "CSAT": {
                "term": "CSAT",
                "definition": "Customer Satisfaction Score",
            }
        }

        customer_data_fields = {
            "email": {
                "name": "email",
                "value_type": "string",
                "scope": "IDENTITY",
            }
        }

        reconciliation = {
            "action": "GRAFT",
            "applied": True,
        }

        turn_context = TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            customer_id=customer_id,
            session_id=session_id,
            turn_number=5,
            session={"session_id": str(session_id), "turn_count": 4},
            customer_data={"customer_id": str(customer_id), "fields": {"email": "test@example.com"}},
            pipeline_config={"generation": {"enabled": True}},
            customer_data_fields=customer_data_fields,
            glossary=glossary,
            reconciliation_result=reconciliation,
            turn_started_at=now,
        )

        assert len(turn_context.glossary) == 1
        assert len(turn_context.customer_data_fields) == 1
        assert turn_context.reconciliation_result is not None
        assert turn_context.reconciliation_result["action"] == "GRAFT"

    def test_empty_optional_fields_default_to_empty_dicts(self):
        """Test that optional dict fields default to empty dicts."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        turn_context = TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            customer_id=customer_id,
            session_id=session_id,
            turn_number=1,
            session={"session_id": str(session_id)},
            customer_data={"customer_id": str(customer_id)},
            pipeline_config={},
            turn_started_at=now,
        )

        assert turn_context.customer_data_fields == {}
        assert turn_context.glossary == {}
        assert turn_context.reconciliation_result is None

    def test_serialization(self):
        """Test that TurnContext can be serialized to dict and back."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        original = TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            customer_id=customer_id,
            session_id=session_id,
            turn_number=1,
            session={"session_id": str(session_id)},
            customer_data={"customer_id": str(customer_id)},
            pipeline_config={},
            turn_started_at=now,
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = TurnContext(**data)

        assert restored.tenant_id == original.tenant_id
        assert restored.agent_id == original.agent_id
        assert restored.customer_id == original.customer_id
        assert restored.session_id == original.session_id
        assert restored.turn_number == original.turn_number
        assert restored.turn_started_at == original.turn_started_at

    def test_turn_context_contains_routing_info(self):
        """Test that TurnContext provides all routing identifiers."""
        tenant_id = uuid4()
        agent_id = uuid4()
        customer_id = uuid4()
        session_id = uuid4()
        now = datetime.now(UTC)

        turn_context = TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            customer_id=customer_id,
            session_id=session_id,
            turn_number=3,
            session={},
            customer_data={},
            pipeline_config={},
            turn_started_at=now,
        )

        # All routing IDs should be accessible
        assert turn_context.tenant_id == tenant_id
        assert turn_context.agent_id == agent_id
        assert turn_context.customer_id == customer_id
        assert turn_context.session_id == session_id
        assert turn_context.turn_number == 3
