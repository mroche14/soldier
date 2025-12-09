"""Tests for InMemoryCustomerDataStore."""

from uuid import uuid4

import pytest

from focal.conversation.models import Channel
from focal.customer_data.enums import VariableSource
from focal.customer_data.models import (
    ChannelIdentity,
    CustomerDataStore,
    ProfileAsset,
    VariableEntry,
)
from focal.customer_data.stores import InMemoryCustomerDataStore


@pytest.fixture
def store() -> InMemoryCustomerDataStore:
    """Create a fresh store for each test."""
    return InMemoryCustomerDataStore()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def sample_profile(tenant_id) -> CustomerDataStore:
    """Create a sample customer profile."""
    identity = ChannelIdentity(
        channel=Channel.WEBCHAT,
        channel_user_id="user123",
        primary=True,
    )
    return CustomerDataStore(
        tenant_id=tenant_id,
        channel_identities=[identity],
    )


class TestProfileOperations:
    """Tests for profile CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, store, sample_profile, tenant_id):
        """Should save and retrieve a profile by ID."""
        profile_id = await store.save(sample_profile)
        retrieved = await store.get_by_id(tenant_id, profile_id)

        assert retrieved is not None
        assert retrieved.id == sample_profile.id

    @pytest.mark.asyncio
    async def test_get_by_customer_id(self, store, sample_profile, tenant_id):
        """Should retrieve profile by customer ID."""
        await store.save(sample_profile)
        retrieved = await store.get_by_customer_id(
            tenant_id, sample_profile.customer_id
        )

        assert retrieved is not None
        assert retrieved.customer_id == sample_profile.customer_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, store, tenant_id):
        """Should return None for nonexistent profile."""
        result = await store.get_by_id(tenant_id, uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, store, sample_profile, tenant_id):
        """Should not return profiles from other tenants."""
        await store.save(sample_profile)
        other_tenant = uuid4()
        result = await store.get_by_id(other_tenant, sample_profile.id)
        assert result is None


class TestChannelIdentityLookup:
    """Tests for channel identity lookup."""

    @pytest.mark.asyncio
    async def test_get_by_channel_identity(self, store, sample_profile, tenant_id):
        """Should find profile by channel identity."""
        await store.save(sample_profile)

        retrieved = await store.get_by_channel_identity(
            tenant_id, Channel.WEBCHAT, "user123"
        )

        assert retrieved is not None
        assert retrieved.id == sample_profile.id

    @pytest.mark.asyncio
    async def test_get_by_channel_identity_not_found(self, store, tenant_id):
        """Should return None when no matching identity."""
        result = await store.get_by_channel_identity(
            tenant_id, Channel.WEBCHAT, "unknown"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, store, sample_profile, tenant_id):
        """Should return existing profile for known identity."""
        await store.save(sample_profile)

        retrieved = await store.get_or_create(tenant_id, Channel.WEBCHAT, "user123")

        assert retrieved.id == sample_profile.id

    @pytest.mark.asyncio
    async def test_get_or_create_new(self, store, tenant_id):
        """Should create new profile for unknown identity."""
        profile = await store.get_or_create(tenant_id, Channel.WEBCHAT, "new_user")

        assert profile is not None
        assert profile.tenant_id == tenant_id
        assert len(profile.channel_identities) == 1
        assert profile.channel_identities[0].channel_user_id == "new_user"


class TestFieldOperations:
    """Tests for profile field operations."""

    @pytest.mark.asyncio
    async def test_update_field(self, store, sample_profile, tenant_id):
        """Should update a profile field and return field ID."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="user@example.com",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        field_id = await store.update_field(tenant_id, sample_profile.id, field)
        assert field_id == field.id

        retrieved = await store.get_by_id(tenant_id, sample_profile.id)
        assert "email" in retrieved.fields
        assert retrieved.fields["email"].value == "user@example.com"

    @pytest.mark.asyncio
    async def test_update_field_nonexistent_profile(self, store, tenant_id):
        """Should raise ValueError for nonexistent profile."""
        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        with pytest.raises(ValueError):
            await store.update_field(tenant_id, uuid4(), field)


class TestAssetOperations:
    """Tests for profile asset operations."""

    @pytest.mark.asyncio
    async def test_add_asset(self, store, sample_profile, tenant_id):
        """Should add an asset to profile and return asset ID."""
        await store.save(sample_profile)

        asset = ProfileAsset(
            name="id_document.pdf",
            asset_type="pdf",
            storage_provider="s3",
            storage_path="bucket/path/doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum="abc123",
        )
        asset_id = await store.add_asset(tenant_id, sample_profile.id, asset)
        assert asset_id == asset.id

        retrieved = await store.get_by_id(tenant_id, sample_profile.id)
        assert len(retrieved.assets) == 1
        assert retrieved.assets[0].name == "id_document.pdf"

    @pytest.mark.asyncio
    async def test_add_asset_nonexistent_profile(self, store, tenant_id):
        """Should raise ValueError for nonexistent profile."""
        asset = ProfileAsset(
            name="doc.pdf",
            asset_type="pdf",
            storage_provider="s3",
            storage_path="path",
            mime_type="application/pdf",
            size_bytes=100,
            checksum="hash",
        )
        with pytest.raises(ValueError):
            await store.add_asset(tenant_id, uuid4(), asset)


class TestChannelLinking:
    """Tests for channel identity linking."""

    @pytest.mark.asyncio
    async def test_link_channel(self, store, sample_profile, tenant_id):
        """Should link new channel identity to profile."""
        await store.save(sample_profile)

        new_identity = ChannelIdentity(
            channel=Channel.WHATSAPP,
            channel_user_id="whatsapp123",
        )
        result = await store.link_channel(tenant_id, sample_profile.id, new_identity)
        assert result is True

        retrieved = await store.get_by_id(tenant_id, sample_profile.id)
        assert len(retrieved.channel_identities) == 2

    @pytest.mark.asyncio
    async def test_link_channel_already_linked(self, store, tenant_id):
        """Should not link identity already linked to different profile."""
        profile1 = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="shared_id")
            ],
        )
        profile2 = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WHATSAPP, channel_user_id="other_id")
            ],
        )
        await store.save(profile1)
        await store.save(profile2)

        # Try to link profile1's identity to profile2
        identity = ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="shared_id")
        result = await store.link_channel(tenant_id, profile2.id, identity)
        assert result is False


class TestProfileMerging:
    """Tests for profile merging."""

    @pytest.mark.asyncio
    async def test_merge_profiles(self, store, tenant_id):
        """Should merge source profile into target."""
        source = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="source_web")
            ],
        )
        source.fields["name"] = VariableEntry(
            name="name",
            value="John",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )

        target = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WHATSAPP, channel_user_id="target_wa")
            ],
        )

        await store.save(source)
        await store.save(target)

        result = await store.merge_profiles(tenant_id, source.id, target.id)
        assert result is True

        # Source should be deleted
        source_check = await store.get_by_id(tenant_id, source.id)
        assert source_check is None

        # Target should have merged data
        merged = await store.get_by_id(tenant_id, target.id)
        assert len(merged.channel_identities) == 2
        assert "name" in merged.fields

    @pytest.mark.asyncio
    async def test_merge_profiles_nonexistent(self, store, tenant_id):
        """Should return False if source or target doesn't exist."""
        profile = CustomerDataStore(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="user")
            ],
        )
        await store.save(profile)

        result = await store.merge_profiles(tenant_id, uuid4(), profile.id)
        assert result is False

        result = await store.merge_profiles(tenant_id, profile.id, uuid4())
        assert result is False


class TestLineageOperations:
    """Tests for lineage tracking (US1)."""

    @pytest.mark.asyncio
    async def test_get_derivation_chain_single_item(self, store, sample_profile, tenant_id):
        """Should return single-item chain for root field."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        chain = await store.get_derivation_chain(tenant_id, field.id, "profile_field")
        assert len(chain) == 1
        assert chain[0]["name"] == "email"

    @pytest.mark.asyncio
    async def test_get_derived_items_empty(self, store, sample_profile, tenant_id):
        """Should return empty lists when no items derived from source."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        derived = await store.get_derived_items(tenant_id, field.id)
        assert derived["fields"] == []
        assert derived["assets"] == []

    @pytest.mark.asyncio
    async def test_check_has_dependents_no_dependents(self, store, sample_profile, tenant_id):
        """Should return False when no dependents."""
        await store.save(sample_profile)

        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        has_deps = await store.check_has_dependents(tenant_id, field.id)
        assert has_deps is False

    @pytest.mark.asyncio
    async def test_field_supersession(self, store, sample_profile, tenant_id):
        """Should supersede existing field when updating."""
        await store.save(sample_profile)

        # Add first field
        field1 = VariableEntry(
            name="email",
            value="old@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field1)

        # Add second field with same name
        field2 = VariableEntry(
            name="email",
            value="new@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        await store.update_field(tenant_id, sample_profile.id, field2)

        # Get field history
        history = await store.get_field_history(tenant_id, sample_profile.id, "email")
        assert len(history) == 2

        # Current field should be the new one
        from focal.customer_data.enums import ItemStatus
        current = await store.get_field(tenant_id, sample_profile.id, "email")
        assert current.value == "new@example.com"
        assert current.status == ItemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_expire_stale_fields(self, store, sample_profile, tenant_id):
        """Should expire fields past expires_at."""
        from datetime import UTC, datetime, timedelta
        await store.save(sample_profile)

        # Add a field that's already expired
        field = VariableEntry(
            name="temp_code",
            value="123456",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        await store.update_field(tenant_id, sample_profile.id, field)

        # Expire stale fields
        count = await store.expire_stale_fields(tenant_id)
        assert count == 1

        # Verify field is now expired
        from focal.customer_data.enums import ItemStatus
        expired_field = await store.get_field(
            tenant_id, sample_profile.id, "temp_code", status=ItemStatus.EXPIRED
        )
        assert expired_field is not None
        assert expired_field.status == ItemStatus.EXPIRED


class TestSchemaOperations:
    """Tests for schema management (US3)."""

    @pytest.mark.asyncio
    async def test_save_and_get_field_definition(self, store, tenant_id):
        """Should save and retrieve field definition."""
        from focal.customer_data.models import CustomerDataField

        agent_id = uuid4()
        definition = CustomerDataField(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            value_type="email",
        )
        await store.save_field_definition(definition)

        retrieved = await store.get_field_definition(tenant_id, agent_id, "email")
        assert retrieved is not None
        assert retrieved.name == "email"

    @pytest.mark.asyncio
    async def test_get_field_definitions(self, store, tenant_id):
        """Should get all field definitions for agent."""
        from focal.customer_data.models import CustomerDataField

        agent_id = uuid4()
        for name in ["email", "phone", "name"]:
            definition = CustomerDataField(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=name,
                display_name=name.title(),
                value_type="string",
            )
            await store.save_field_definition(definition)

        definitions = await store.get_field_definitions(tenant_id, agent_id)
        assert len(definitions) == 3

    @pytest.mark.asyncio
    async def test_save_and_get_scenario_requirement(self, store, tenant_id):
        """Should save and retrieve scenario requirement."""
        from focal.customer_data.models import ScenarioFieldRequirement

        agent_id = uuid4()
        scenario_id = uuid4()
        requirement = ScenarioFieldRequirement(
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
            field_name="email",
        )
        await store.save_scenario_requirement(requirement)

        requirements = await store.get_scenario_requirements(tenant_id, scenario_id)
        assert len(requirements) == 1
        assert requirements[0].field_name == "email"
