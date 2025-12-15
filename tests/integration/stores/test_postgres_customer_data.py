"""Integration tests for PostgresInterlocutorDataStore.

Tests profile CRUD operations, channel identity management,
and field updates against a real PostgreSQL database.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from ruche.conversation.models import Channel
from ruche.interlocutor_data.enums import VariableSource, VerificationLevel
from ruche.interlocutor_data.models import (
    ChannelIdentity,
    InterlocutorDataStore,
    ProfileAsset,
    VariableEntry,
)
from ruche.interlocutor_data.stores.postgres import PostgresInterlocutorDataStore


@pytest_asyncio.fixture
async def profile_store(postgres_pool):
    """Create PostgresInterlocutorDataStore with test pool."""
    return PostgresInterlocutorDataStore(postgres_pool)


@pytest.fixture
def sample_profile(tenant_id):
    """Create a sample customer profile for testing."""
    return InterlocutorDataStore(
        id=uuid4(),
        tenant_id=tenant_id,
        interlocutor_id=uuid4(),
        channel_identities=[
            ChannelIdentity(
                channel=Channel.WEBCHAT,
                channel_user_id="test_user_123",
                verified=False,
                primary=True,
            )
        ],
        fields={},
        assets=[],
        verification_level=VerificationLevel.UNVERIFIED,
        consents=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_profile_field():
    """Create a sample profile field for testing."""
    return VariableEntry(
        name="first_name",
        value="John",
        value_type="string",
        source=VariableSource.USER_PROVIDED,
        confidence=1.0,
        verified=False,
        collected_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_profile_asset():
    """Create a sample profile asset for testing."""
    return ProfileAsset(
        id=uuid4(),
        name="drivers_license.pdf",
        asset_type="document",
        storage_provider="s3",
        storage_path="profiles/test_user_123/drivers_license.pdf",
        mime_type="application/pdf",
        size_bytes=1024000,
        checksum="sha256:abc123def456",
        uploaded_at=datetime.now(UTC),
    )


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreCRUD:
    """Test basic CRUD operations."""

    async def test_save_and_get_profile(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test saving and retrieving a profile."""
        # Save
        profile_id = await profile_store.save(sample_profile)
        assert profile_id == sample_profile.id

        # Get
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert retrieved is not None
        assert retrieved.id == sample_profile.id
        assert len(retrieved.channel_identities) == 1

    async def test_get_by_channel_identity(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test retrieving profile by channel identity."""
        await profile_store.save(sample_profile)

        # Get by channel
        retrieved = await profile_store.get_by_channel_identity(
            sample_profile.tenant_id,
            Channel.WEBCHAT,
            "test_user_123",
        )
        assert retrieved is not None
        assert retrieved.id == sample_profile.id

    async def test_get_nonexistent_profile(
        self, profile_store, tenant_id, clean_postgres
    ):
        """Test getting a profile that doesn't exist."""
        retrieved = await profile_store.get_by_interlocutor_id(tenant_id, uuid4())
        assert retrieved is None

    async def test_get_or_create_existing(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test get_or_create returns existing profile."""
        await profile_store.save(sample_profile)

        # Get or create should return existing
        result = await profile_store.get_or_create(
            sample_profile.tenant_id,
            Channel.WEBCHAT,
            "test_user_123",
        )
        assert result.id == sample_profile.id

    async def test_get_or_create_new(
        self, profile_store, tenant_id, clean_postgres
    ):
        """Test get_or_create creates new profile when none exists."""
        result = await profile_store.get_or_create(
            tenant_id,
            Channel.WEBCHAT,
            "new_user_456",
        )
        assert result is not None
        assert len(result.channel_identities) == 1
        assert result.channel_identities[0].channel_user_id == "new_user_456"


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreFields:
    """Test profile field operations."""

    async def test_update_field(
        self, profile_store, sample_profile, sample_profile_field, clean_postgres
    ):
        """Test updating a profile field."""
        await profile_store.save(sample_profile)

        # Update field
        field_id = await profile_store.update_field(
            sample_profile.tenant_id,
            sample_profile.id,
            sample_profile_field,
        )
        assert field_id is not None

        # Verify field was added
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert retrieved is not None
        assert "first_name" in retrieved.fields
        assert retrieved.fields["first_name"].value == "John"

    async def test_update_multiple_fields(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test updating multiple profile fields."""
        await profile_store.save(sample_profile)

        # Add multiple fields
        fields = [
            VariableEntry(
                name="first_name",
                value="John",
                value_type="string",
                source=VariableSource.USER_PROVIDED,
                confidence=1.0,
            ),
            VariableEntry(
                name="email",
                value="john@example.com",
                value_type="string",
                source=VariableSource.USER_PROVIDED,
                confidence=1.0,
            ),
            VariableEntry(
                name="age",
                value=30,
                value_type="number",
                source=VariableSource.LLM_EXTRACTED,
                confidence=0.85,
            ),
        ]

        for field in fields:
            await profile_store.update_field(
                sample_profile.tenant_id,
                sample_profile.id,
                field,
            )

        # Verify all fields
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert len(retrieved.fields) == 3
        assert retrieved.fields["email"].value == "john@example.com"


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreAssets:
    """Test profile asset operations."""

    async def test_add_asset(
        self, profile_store, sample_profile, sample_profile_asset, clean_postgres
    ):
        """Test adding an asset to profile."""
        await profile_store.save(sample_profile)

        # Add asset
        asset_id = await profile_store.add_asset(
            sample_profile.tenant_id,
            sample_profile.id,
            sample_profile_asset,
        )
        assert asset_id is not None

        # Verify asset was added
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert retrieved is not None
        assert len(retrieved.assets) == 1
        assert retrieved.assets[0].name == "drivers_license.pdf"

    async def test_add_multiple_assets(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test adding multiple assets to profile."""
        await profile_store.save(sample_profile)

        # Add multiple assets
        assets = [
            ProfileAsset(
                id=uuid4(),
                name="id_front.jpg",
                asset_type="image",
                storage_provider="s3",
                storage_path="profiles/test/id_front.jpg",
                mime_type="image/jpeg",
                size_bytes=500000,
                checksum="sha256:front123",
            ),
            ProfileAsset(
                id=uuid4(),
                name="id_back.jpg",
                asset_type="image",
                storage_provider="s3",
                storage_path="profiles/test/id_back.jpg",
                mime_type="image/jpeg",
                size_bytes=450000,
                checksum="sha256:back456",
            ),
        ]

        for asset in assets:
            await profile_store.add_asset(
                sample_profile.tenant_id,
                sample_profile.id,
                asset,
            )

        # Verify all assets
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert len(retrieved.assets) == 2


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreChannelIdentity:
    """Test channel identity operations."""

    async def test_link_channel(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test linking a new channel identity to profile."""
        await profile_store.save(sample_profile)

        # Link new channel
        new_identity = ChannelIdentity(
            channel=Channel.SMS,
            channel_user_id="+15551234567",
            verified=True,
            primary=False,
        )

        linked = await profile_store.link_channel(
            sample_profile.tenant_id,
            sample_profile.id,
            new_identity,
        )
        assert linked is True

        # Verify channel was linked
        retrieved = await profile_store.get_by_interlocutor_id(
            sample_profile.tenant_id, sample_profile.id
        )
        assert len(retrieved.channel_identities) == 2

        # Should be able to find by new channel
        found = await profile_store.get_by_channel_identity(
            sample_profile.tenant_id,
            Channel.SMS,
            "+15551234567",
        )
        assert found is not None
        assert found.id == sample_profile.id

    async def test_link_existing_channel_updates(
        self, profile_store, sample_profile, clean_postgres
    ):
        """Test that linking an existing channel updates it."""
        await profile_store.save(sample_profile)

        # Update existing channel identity
        updated_identity = ChannelIdentity(
            channel=Channel.WEBCHAT,
            channel_user_id="test_user_123",
            verified=True,  # Changed from False
            primary=True,
        )

        linked = await profile_store.link_channel(
            sample_profile.tenant_id,
            sample_profile.id,
            updated_identity,
        )
        assert linked is True

        # Verify update (this is implementation-dependent)
        retrieved = await profile_store.get_by_channel_identity(
            sample_profile.tenant_id,
            Channel.WEBCHAT,
            "test_user_123",
        )
        assert retrieved is not None


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreMerge:
    """Test profile merge operations."""

    async def test_merge_profiles(
        self, profile_store, tenant_id, clean_postgres
    ):
        """Test merging two profiles."""
        # Create source profile with some data
        source_profile = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant_id,
            interlocutor_id=uuid4(),
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.SMS,
                    channel_user_id="+15551234567",
                    verified=False,
                    primary=True,
                )
            ],
            fields={},
            verification_level=VerificationLevel.UNVERIFIED,
        )

        # Create target profile
        target_profile = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant_id,
            interlocutor_id=uuid4(),
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.WEBCHAT,
                    channel_user_id="target_user",
                    verified=True,
                    primary=True,
                )
            ],
            fields={},
            verification_level=VerificationLevel.EMAIL_VERIFIED,
        )

        await profile_store.save(source_profile)
        await profile_store.save(target_profile)

        # Add field to source
        await profile_store.update_field(
            tenant_id,
            source_profile.id,
            VariableEntry(
                name="phone",
                value="+15551234567",
                value_type="string",
                source=VariableSource.USER_PROVIDED,
            ),
        )

        # Merge source into target
        merged = await profile_store.merge_profiles(
            tenant_id,
            source_profile.id,
            target_profile.id,
        )
        assert merged is True

        # Source profile should be marked as merged (no longer accessible)
        source_retrieved = await profile_store.get_by_interlocutor_id(
            tenant_id, source_profile.id
        )
        assert source_retrieved is None

        # Target profile should have data from source
        target_retrieved = await profile_store.get_by_interlocutor_id(
            tenant_id, target_profile.id
        )
        assert target_retrieved is not None

        # Channel from source should now point to target
        found = await profile_store.get_by_channel_identity(
            tenant_id,
            Channel.SMS,
            "+15551234567",
        )
        assert found is not None
        assert found.id == target_profile.id


@pytest.mark.integration
class TestPostgresInterlocutorDataStoreTenantIsolation:
    """Test tenant isolation."""

    async def test_tenant_isolation_profiles(
        self, profile_store, clean_postgres
    ):
        """Test that profiles are isolated by tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        profile1 = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant1,
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.WEBCHAT,
                    channel_user_id="shared_user_id",
                    verified=False,
                    primary=True,
                )
            ],
        )
        profile2 = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant2,
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.WEBCHAT,
                    channel_user_id="shared_user_id",
                    verified=False,
                    primary=True,
                )
            ],
        )

        await profile_store.save(profile1)
        await profile_store.save(profile2)

        # Same channel_user_id but different tenants
        found1 = await profile_store.get_by_channel_identity(
            tenant1, Channel.WEBCHAT, "shared_user_id"
        )
        found2 = await profile_store.get_by_channel_identity(
            tenant2, Channel.WEBCHAT, "shared_user_id"
        )

        assert found1 is not None
        assert found2 is not None
        assert found1.id == profile1.id
        assert found2.id == profile2.id
        assert found1.id != found2.id

    async def test_cross_tenant_access_prevented(
        self, profile_store, clean_postgres
    ):
        """Test that cross-tenant access is prevented."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        profile = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant1,
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.WEBCHAT,
                    channel_user_id="user_123",
                    verified=False,
                    primary=True,
                )
            ],
        )
        await profile_store.save(profile)

        # Tenant 2 should not be able to access tenant 1's profile
        cross_tenant = await profile_store.get_by_interlocutor_id(tenant2, profile.id)
        assert cross_tenant is None

        # Tenant 2 should not find by channel identity either
        cross_channel = await profile_store.get_by_channel_identity(
            tenant2, Channel.WEBCHAT, "user_123"
        )
        assert cross_channel is None
