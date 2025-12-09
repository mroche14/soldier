"""Tests for GlossaryItem model."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from focal.alignment.models.glossary import GlossaryItem


class TestGlossaryItem:
    """Test suite for GlossaryItem model."""

    def test_create_with_required_fields(self):
        """Test creating glossary item with required fields."""
        item = GlossaryItem(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            term="CSAT",
            definition="Customer Satisfaction score from 1-5",
        )

        assert item.term == "CSAT"
        assert item.definition == "Customer Satisfaction score from 1-5"
        assert item.enabled is True
        assert item.priority == 0
        assert item.aliases == []

    def test_create_with_all_fields(self):
        """Test creating glossary item with all fields."""
        tenant_id = uuid4()
        agent_id = uuid4()
        item_id = uuid4()

        item = GlossaryItem(
            id=item_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="VIP Customer",
            definition="Customer with lifetime value > $10,000",
            usage_hint="Use when discussing premium features",
            aliases=["Premium Customer", "High Value Customer"],
            category="customer_segments",
            priority=10,
            enabled=True,
        )

        assert item.id == item_id
        assert item.tenant_id == tenant_id
        assert item.agent_id == agent_id
        assert item.term == "VIP Customer"
        assert len(item.aliases) == 2
        assert item.category == "customer_segments"
        assert item.priority == 10

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            GlossaryItem(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                term="CSAT",
                # Missing definition
            )
