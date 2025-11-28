"""Tests for InMemoryProfileStore."""

from uuid import uuid4

import pytest

from soldier.conversation.models import Channel
from soldier.profile.enums import ProfileFieldSource
from soldier.profile.models import (
    ChannelIdentity,
    CustomerProfile,
    ProfileAsset,
    ProfileField,
)
from soldier.profile.stores import InMemoryProfileStore


@pytest.fixture
def store() -> InMemoryProfileStore:
    """Create a fresh store for each test."""
    return InMemoryProfileStore()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def sample_profile(tenant_id) -> CustomerProfile:
    """Create a sample customer profile."""
    identity = ChannelIdentity(
        channel=Channel.WEBCHAT,
        channel_user_id="user123",
        primary=True,
    )
    return CustomerProfile(
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
        """Should update a profile field."""
        await store.save(sample_profile)

        field = ProfileField(
            name="email",
            value="user@example.com",
            value_type="string",
            source=ProfileFieldSource.USER_PROVIDED,
        )
        result = await store.update_field(tenant_id, sample_profile.id, field)
        assert result is True

        retrieved = await store.get_by_id(tenant_id, sample_profile.id)
        assert "email" in retrieved.fields
        assert retrieved.fields["email"].value == "user@example.com"

    @pytest.mark.asyncio
    async def test_update_field_nonexistent_profile(self, store, tenant_id):
        """Should return False for nonexistent profile."""
        field = ProfileField(
            name="email",
            value="test@example.com",
            value_type="string",
            source=ProfileFieldSource.USER_PROVIDED,
        )
        result = await store.update_field(tenant_id, uuid4(), field)
        assert result is False


class TestAssetOperations:
    """Tests for profile asset operations."""

    @pytest.mark.asyncio
    async def test_add_asset(self, store, sample_profile, tenant_id):
        """Should add an asset to profile."""
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
        result = await store.add_asset(tenant_id, sample_profile.id, asset)
        assert result is True

        retrieved = await store.get_by_id(tenant_id, sample_profile.id)
        assert len(retrieved.assets) == 1
        assert retrieved.assets[0].name == "id_document.pdf"

    @pytest.mark.asyncio
    async def test_add_asset_nonexistent_profile(self, store, tenant_id):
        """Should return False for nonexistent profile."""
        asset = ProfileAsset(
            name="doc.pdf",
            asset_type="pdf",
            storage_provider="s3",
            storage_path="path",
            mime_type="application/pdf",
            size_bytes=100,
            checksum="hash",
        )
        result = await store.add_asset(tenant_id, uuid4(), asset)
        assert result is False


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
        profile1 = CustomerProfile(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="shared_id")
            ],
        )
        profile2 = CustomerProfile(
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
        source = CustomerProfile(
            tenant_id=tenant_id,
            channel_identities=[
                ChannelIdentity(channel=Channel.WEBCHAT, channel_user_id="source_web")
            ],
        )
        source.fields["name"] = ProfileField(
            name="name",
            value="John",
            value_type="string",
            source=ProfileFieldSource.USER_PROVIDED,
        )

        target = CustomerProfile(
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
        profile = CustomerProfile(
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
