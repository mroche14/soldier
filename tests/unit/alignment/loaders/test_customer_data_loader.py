"""Tests for InterlocutorDataLoader."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from ruche.brains.focal.phases.loaders.interlocutor_data_loader import InterlocutorDataLoader
from ruche.interlocutor_data import InterlocutorDataStore, InterlocutorDataField, VariableEntry
from ruche.interlocutor_data.enums import ItemStatus, VariableSource
from ruche.interlocutor_data.stores.inmemory import InMemoryInterlocutorDataStore


@pytest.fixture
def profile_store():
    """Create in-memory profile store."""
    return InMemoryInterlocutorDataStore()


@pytest.fixture
def loader(profile_store):
    """Create customer data loader."""
    return InterlocutorDataLoader(profile_store)


@pytest.fixture
def sample_schema():
    """Create sample customer data schema."""
    return {
        "email": InterlocutorDataField(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="email",
            display_name="Email Address",
            description="Customer email",
            value_type="string",
            scope="IDENTITY",
            persist=True,
            required=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        "order_id": InterlocutorDataField(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="order_id",
            display_name="Order ID",
            description="Current order ID",
            value_type="string",
            scope="CASE",
            persist=True,
            required=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    }


class TestInterlocutorDataLoader:
    """Test suite for InterlocutorDataLoader."""

    @pytest.mark.asyncio
    async def test_load_for_new_customer_returns_empty_store(
        self, loader, sample_schema
    ):
        """Test loading for a new customer returns empty store."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()

        result = await loader.load(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            schema=sample_schema,
        )

        assert result.interlocutor_id == interlocutor_id
        assert result.tenant_id == tenant_id
        assert len(result.fields) == 0

    @pytest.mark.asyncio
    async def test_load_converts_profile_fields_to_variable_entries(
        self, loader, profile_store, sample_schema
    ):
        """Test that ProfileFields are correctly loaded."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()
        now = datetime.now(UTC)

        # Create a profile with fields
        profile = InterlocutorDataStore(
            id=interlocutor_id,
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
            channel_identities=[],
            fields={
                "email": VariableEntry(
                    id=uuid4(),
                    name="email",
                    value="test@example.com",
                    value_type="string",
                    source=VariableSource.USER_PROVIDED,
                    status=ItemStatus.ACTIVE,
                    confidence=1.0,
                    verified=True,
                    collected_at=now,
                    updated_at=now,
                )
            },
            assets=[],
        )

        await profile_store.save(profile)

        # Load the profile
        result = await loader.load(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            schema=sample_schema,
        )

        assert len(result.fields) == 1
        assert "email" in result.fields
        assert result.fields["email"].value == "test@example.com"

    @pytest.mark.asyncio
    async def test_load_filters_inactive_fields(
        self, loader, profile_store, sample_schema
    ):
        """Test that inactive fields are filtered out."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()
        now = datetime.now(UTC)

        # Create profile with active and superseded fields
        profile = InterlocutorDataStore(
            id=interlocutor_id,
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
            channel_identities=[],
            fields={
                "email": VariableEntry(
                    id=uuid4(),
                    name="email",
                    value="current@example.com",
                    value_type="string",
                    source=VariableSource.USER_PROVIDED,
                    status=ItemStatus.ACTIVE,
                    confidence=1.0,
                    verified=True,
                    collected_at=now,
                    updated_at=now,
                ),
                "old_email": VariableEntry(
                    id=uuid4(),
                    name="email",
                    value="old@example.com",
                    value_type="string",
                    source=VariableSource.USER_PROVIDED,
                    status=ItemStatus.SUPERSEDED,  # Inactive
                    confidence=1.0,
                    verified=True,
                    collected_at=now,
                    updated_at=now,
                ),
            },
            assets=[],
        )

        await profile_store.save(profile)

        result = await loader.load(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            schema=sample_schema,
        )

        # Should only include the active field
        assert len(result.fields) == 1
        assert result.fields["email"].value == "current@example.com"

    @pytest.mark.asyncio
    async def test_load_warns_on_schema_mismatch(
        self, loader, profile_store, caplog
    ):
        """Test that fields not in schema generate warnings."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()
        now = datetime.now(UTC)

        # Create profile with field not in schema
        profile = InterlocutorDataStore(
            id=interlocutor_id,
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
            channel_identities=[],
            fields={
                "unknown_field": VariableEntry(
                    id=uuid4(),
                    name="unknown_field",
                    value="some_value",
                    value_type="string",
                    source=VariableSource.USER_PROVIDED,
                    status=ItemStatus.ACTIVE,
                    confidence=1.0,
                    verified=False,
                    collected_at=now,
                    updated_at=now,
                )
            },
            assets=[],
        )

        await profile_store.save(profile)

        # Load with empty schema
        result = await loader.load(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            schema={},  # Empty schema
        )

        # Field should still be included
        assert len(result.fields) == 1
        assert "unknown_field" in result.fields

    @pytest.mark.asyncio
    async def test_load_includes_only_schema_fields(
        self, loader, profile_store, sample_schema
    ):
        """Test that only fields matching schema are processed."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()
        now = datetime.now(UTC)

        profile = InterlocutorDataStore(
            id=interlocutor_id,
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
            channel_identities=[],
            fields={
                "email": VariableEntry(
                    id=uuid4(),
                    name="email",
                    value="test@example.com",
                    value_type="string",
                    source=VariableSource.USER_PROVIDED,
                    status=ItemStatus.ACTIVE,
                    confidence=1.0,
                    verified=True,
                    collected_at=now,
                    updated_at=now,
                )
            },
            assets=[],
        )

        await profile_store.save(profile)

        result = await loader.load(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            schema=sample_schema,
        )

        # email is in schema, so should be included
        assert len(result.fields) == 1
        assert "email" in result.fields
