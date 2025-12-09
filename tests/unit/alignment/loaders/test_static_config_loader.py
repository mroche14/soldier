"""Tests for StaticConfigLoader."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from soldier.alignment.loaders.static_config_loader import StaticConfigLoader
from soldier.alignment.models import GlossaryItem
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore
from soldier.customer_data import CustomerDataField


@pytest.fixture
def config_store():
    """Create in-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def loader(config_store):
    """Create static config loader."""
    return StaticConfigLoader(config_store)


@pytest.fixture
def tenant_id():
    """Create tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Create agent ID."""
    return uuid4()


class TestStaticConfigLoader:
    """Test suite for StaticConfigLoader."""

    @pytest.mark.asyncio
    async def test_load_glossary_returns_empty_dict_when_no_items(
        self, loader, tenant_id, agent_id
    ):
        """Test loading glossary when no items exist returns empty dict."""
        result = await loader.load_glossary(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_glossary_returns_items_keyed_by_term(
        self, loader, config_store, tenant_id, agent_id
    ):
        """Test that glossary items are returned as dict keyed by term."""
        now = datetime.now(UTC)

        # Add glossary items
        item1 = GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="CSAT",
            definition="Customer Satisfaction Score",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        item2 = GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="NPS",
            definition="Net Promoter Score",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        await config_store.save_glossary_item(item1)
        await config_store.save_glossary_item(item2)

        result = await loader.load_glossary(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(result) == 2
        assert "CSAT" in result
        assert "NPS" in result
        assert result["CSAT"].definition == "Customer Satisfaction Score"
        assert result["NPS"].definition == "Net Promoter Score"

    @pytest.mark.asyncio
    async def test_load_glossary_filters_disabled_items(
        self, loader, config_store, tenant_id, agent_id
    ):
        """Test that disabled glossary items are filtered out."""
        now = datetime.now(UTC)

        # Add enabled item
        enabled_item = GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="CSAT",
            definition="Customer Satisfaction Score",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        # Add disabled item
        disabled_item = GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="OLD_TERM",
            definition="Deprecated term",
            enabled=False,
            created_at=now,
            updated_at=now,
        )

        await config_store.save_glossary_item(enabled_item)
        await config_store.save_glossary_item(disabled_item)

        result = await loader.load_glossary(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(result) == 1
        assert "CSAT" in result
        assert "OLD_TERM" not in result

    @pytest.mark.asyncio
    async def test_load_customer_data_schema_returns_empty_dict_when_no_fields(
        self, loader, tenant_id, agent_id
    ):
        """Test loading schema when no fields exist returns empty dict."""
        result = await loader.load_customer_data_schema(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_load_customer_data_schema_returns_fields_keyed_by_name(
        self, loader, config_store, tenant_id, agent_id
    ):
        """Test that customer data fields are returned as dict keyed by name."""
        now = datetime.now(UTC)

        # Add customer data fields
        field1 = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            description="Customer email",
            value_type="string",
            scope="IDENTITY",
            persist=True,
            required=False,
            created_at=now,
            updated_at=now,
        )

        field2 = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="order_id",
            display_name="Order ID",
            description="Current order",
            value_type="string",
            scope="CASE",
            persist=True,
            required=False,
            created_at=now,
            updated_at=now,
        )

        await config_store.save_customer_data_field(field1)
        await config_store.save_customer_data_field(field2)

        result = await loader.load_customer_data_schema(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(result) == 2
        assert "email" in result
        assert "order_id" in result
        assert result["email"].scope == "IDENTITY"
        assert result["order_id"].scope == "CASE"

    @pytest.mark.asyncio
    async def test_load_customer_data_schema_filters_disabled_fields(
        self, loader, config_store, tenant_id, agent_id
    ):
        """Test that disabled fields are filtered out."""
        now = datetime.now(UTC)

        # Add enabled field
        enabled_field = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email",
            description="Customer email",
            value_type="string",
            scope="IDENTITY",
            persist=True,
            required=False,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        # Add disabled field
        disabled_field = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="old_field",
            display_name="Old Field",
            description="Deprecated",
            value_type="string",
            scope="IDENTITY",
            persist=True,
            required=False,
            enabled=False,
            created_at=now,
            updated_at=now,
        )

        await config_store.save_customer_data_field(enabled_field)
        await config_store.save_customer_data_field(disabled_field)

        result = await loader.load_customer_data_schema(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(result) == 1
        assert "email" in result
        assert "old_field" not in result
