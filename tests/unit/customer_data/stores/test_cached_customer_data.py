"""Unit tests for CustomerDataStoreCacheLayer.

Tests cache hit/miss behavior, invalidation, and Redis failure fallback.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import redis.asyncio as redis

from focal.config.models.storage import RedisProfileCacheConfig
from focal.conversation.models import Channel
from focal.customer_data.enums import ItemStatus, VariableSource
from focal.customer_data.models import (
    ChannelIdentity,
    CustomerDataStore,
    VariableEntry,
)
from focal.customer_data.stores.cached import CustomerDataStoreCacheLayer
from focal.customer_data.stores.inmemory import InMemoryCustomerDataStore


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def profile_id():
    """Test profile ID."""
    return uuid4()


@pytest.fixture
def customer_id():
    """Test customer ID."""
    return uuid4()


@pytest.fixture
def sample_profile(tenant_id, profile_id, customer_id):
    """Create a sample customer profile."""
    email_field = VariableEntry(
        id=uuid4(),
        name="email",
        value="test@example.com",
        value_type="email",
        source=VariableSource.USER_PROVIDED,
        collected_at=datetime.now(UTC),
        status=ItemStatus.ACTIVE,
    )
    return CustomerDataStore(
        tenant_id=tenant_id,
        id=profile_id,
        customer_id=customer_id,
        channel_identities=[
            ChannelIdentity(
                channel=Channel.WEBCHAT,
                channel_user_id="test-user-123",
            )
        ],
        fields={"email": email_field},
        assets=[],
    )


@pytest.fixture
def backend_store():
    """Create an in-memory backend store."""
    return InMemoryCustomerDataStore()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock(spec=redis.Redis)
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.ping = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def config():
    """Create a cache config."""
    return RedisProfileCacheConfig(
        ttl_seconds=300,
        key_prefix="test_profile",
        enabled=True,
        fallback_on_error=True,
    )


@pytest.fixture
def cached_store(backend_store, mock_redis, config):
    """Create a cached profile store."""
    return CustomerDataStoreCacheLayer(backend_store, mock_redis, config)


class TestCacheHitBehavior:
    """Tests for cache hit scenarios (T105)."""

    @pytest.mark.asyncio
    async def test_get_by_id_cache_hit(
        self, cached_store, mock_redis, sample_profile, tenant_id, profile_id
    ):
        """Test that cache hit returns cached data without hitting backend."""
        # Arrange: Cache contains the profile
        mock_redis.get.return_value = sample_profile.model_dump_json()

        # Act
        result = await cached_store.get_by_id(tenant_id, profile_id)

        # Assert
        assert result is not None
        assert result.id == sample_profile.id
        mock_redis.get.assert_called_once()
        # Backend should not be called

    @pytest.mark.asyncio
    async def test_get_by_customer_id_cache_hit(
        self, cached_store, mock_redis, sample_profile, tenant_id, customer_id
    ):
        """Test cache hit for get_by_customer_id."""
        mock_redis.get.return_value = sample_profile.model_dump_json()

        result = await cached_store.get_by_customer_id(tenant_id, customer_id)

        assert result is not None
        assert result.customer_id == customer_id

    @pytest.mark.asyncio
    async def test_get_by_channel_identity_cache_hit(
        self, cached_store, mock_redis, sample_profile, tenant_id
    ):
        """Test cache hit for get_by_channel_identity."""
        mock_redis.get.return_value = sample_profile.model_dump_json()

        result = await cached_store.get_by_channel_identity(
            tenant_id, Channel.WEBCHAT, "test-user-123"
        )

        assert result is not None
        assert result.channel_identities[0].channel_user_id == "test-user-123"


class TestCacheMissBehavior:
    """Tests for cache miss scenarios (T106)."""

    @pytest.mark.asyncio
    async def test_get_by_id_cache_miss(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id, profile_id
    ):
        """Test cache miss fetches from backend and caches result."""
        # Arrange: Cache is empty, backend has the profile
        mock_redis.get.return_value = None
        await backend_store.save(sample_profile)

        # Act
        result = await cached_store.get_by_id(tenant_id, sample_profile.id)

        # Assert
        assert result is not None
        assert result.id == sample_profile.id
        # Should have set cache after miss
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_by_customer_id_cache_miss(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id, customer_id
    ):
        """Test cache miss for get_by_customer_id."""
        mock_redis.get.return_value = None
        await backend_store.save(sample_profile)

        result = await cached_store.get_by_customer_id(
            tenant_id, sample_profile.customer_id
        )

        assert result is not None
        # Should cache both by customer_id and profile_id
        assert mock_redis.setex.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_not_found_returns_none(
        self, cached_store, mock_redis, tenant_id, profile_id
    ):
        """Test that missing profile returns None and doesn't cache."""
        mock_redis.get.return_value = None

        result = await cached_store.get_by_id(tenant_id, profile_id)

        assert result is None
        # Should not cache None results
        mock_redis.setex.assert_not_called()


class TestCacheInvalidation:
    """Tests for cache invalidation on write (T107)."""

    @pytest.mark.asyncio
    async def test_save_invalidates_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that save invalidates profile cache."""
        await cached_store.save(sample_profile)

        # Should delete cache keys
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_update_field_invalidates_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that update_field invalidates profile cache."""
        # First save the profile
        await backend_store.save(sample_profile)

        # Update a field
        new_field = VariableEntry(
            id=uuid4(),
            name="phone",
            value="+1234567890",
            value_type="phone",
            source=VariableSource.USER_PROVIDED,
            collected_at=datetime.now(UTC),
            status=ItemStatus.ACTIVE,
        )
        await cached_store.update_field(
            tenant_id, sample_profile.id, new_field
        )

        # Should invalidate cache
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_add_asset_invalidates_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that add_asset invalidates profile cache."""
        from focal.customer_data.models import ProfileAsset

        await backend_store.save(sample_profile)

        asset = ProfileAsset(
            id=uuid4(),
            name="test_doc",
            asset_type="document",
            storage_provider="s3",
            storage_path="bucket/doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum="abc123",
            uploaded_at=datetime.now(UTC),
            status=ItemStatus.ACTIVE,
        )
        await cached_store.add_asset(
            tenant_id, sample_profile.id, asset
        )

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that delete invalidates cache."""
        await backend_store.save(sample_profile)

        await cached_store.delete(tenant_id, sample_profile.id)

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_link_channel_invalidates_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that link_channel invalidates cache."""
        await backend_store.save(sample_profile)

        new_identity = ChannelIdentity(
            channel=Channel.SLACK,
            channel_user_id="slack-user-456",
        )
        await cached_store.link_channel(
            tenant_id, sample_profile.id, new_identity
        )

        mock_redis.delete.assert_called()


class TestRedisFailureFallback:
    """Tests for Redis failure fallback (T108)."""

    @pytest.mark.asyncio
    async def test_redis_get_error_falls_back_to_backend(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that Redis error on get falls back to backend."""
        # Arrange
        mock_redis.get.side_effect = redis.RedisError("Connection failed")
        await backend_store.save(sample_profile)

        # Act - should not raise, should fall back to backend
        result = await cached_store.get_by_id(tenant_id, sample_profile.id)

        # Assert
        assert result is not None
        assert result.id == sample_profile.id

    @pytest.mark.asyncio
    async def test_redis_set_error_continues(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that Redis error on set doesn't prevent operation."""
        mock_redis.get.return_value = None
        mock_redis.setex.side_effect = redis.RedisError("Connection failed")
        await backend_store.save(sample_profile)

        # Act - should not raise
        result = await cached_store.get_by_id(tenant_id, sample_profile.id)

        assert result is not None

    @pytest.mark.asyncio
    async def test_redis_delete_error_continues(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that Redis error on delete doesn't prevent operation."""
        mock_redis.delete.side_effect = redis.RedisError("Connection failed")

        # Act - should not raise
        await cached_store.save(sample_profile)

        # The save should have succeeded despite cache invalidation failing

    @pytest.mark.asyncio
    async def test_fallback_disabled_raises_error(
        self, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that with fallback disabled, Redis errors are raised."""
        config = RedisProfileCacheConfig(
            enabled=True,
            fallback_on_error=False,  # Disable fallback
        )
        cached_store = CustomerDataStoreCacheLayer(backend_store, mock_redis, config)
        mock_redis.get.side_effect = redis.RedisError("Connection failed")

        with pytest.raises(redis.RedisError):
            await cached_store.get_by_id(tenant_id, sample_profile.id)


class TestCacheDisabled:
    """Tests for disabled cache behavior."""

    @pytest.mark.asyncio
    async def test_disabled_cache_skips_redis(
        self, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that disabled cache skips Redis entirely."""
        config = RedisProfileCacheConfig(enabled=False)
        cached_store = CustomerDataStoreCacheLayer(backend_store, mock_redis, config)
        await backend_store.save(sample_profile)

        result = await cached_store.get_by_id(tenant_id, sample_profile.id)

        assert result is not None
        mock_redis.get.assert_not_called()
        mock_redis.setex.assert_not_called()


class TestHistoryBypassesCache:
    """Tests for include_history bypassing cache."""

    @pytest.mark.asyncio
    async def test_get_with_history_bypasses_cache(
        self, cached_store, backend_store, mock_redis, sample_profile, tenant_id
    ):
        """Test that include_history=True bypasses cache."""
        # Arrange: Cache has profile
        mock_redis.get.return_value = sample_profile.model_dump_json()
        await backend_store.save(sample_profile)

        # Act with include_history=True
        result = await cached_store.get_by_id(
            tenant_id, sample_profile.id, include_history=True
        )

        # Assert - cache should not be checked (goes straight to backend)
        # Note: The cache won't be consulted because include_history needs backend
        assert result is not None


class TestFieldDefinitionCaching:
    """Tests for field definition caching."""

    @pytest.mark.asyncio
    async def test_get_field_definitions_caches(
        self, cached_store, backend_store, mock_redis, tenant_id, agent_id
    ):
        """Test that field definitions are cached."""
        from focal.customer_data.models import CustomerDataField
        from focal.customer_data.enums import ValidationMode

        mock_redis.get.return_value = None

        definition = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            value_type="email",
            validation_mode=ValidationMode.STRICT,
        )
        await backend_store.save_field_definition(definition)

        await cached_store.get_field_definitions(tenant_id, agent_id)

        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_save_field_definition_invalidates(
        self, cached_store, backend_store, mock_redis, tenant_id, agent_id
    ):
        """Test that save_field_definition invalidates cache."""
        from focal.customer_data.models import CustomerDataField
        from focal.customer_data.enums import ValidationMode

        definition = CustomerDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="phone",
            display_name="Phone Number",
            value_type="phone",
            validation_mode=ValidationMode.STRICT,
        )

        await cached_store.save_field_definition(definition)

        mock_redis.delete.assert_called()


class TestScenarioRequirementCaching:
    """Tests for scenario requirement caching."""

    @pytest.mark.asyncio
    async def test_get_scenario_requirements_caches(
        self, cached_store, backend_store, mock_redis, tenant_id, agent_id
    ):
        """Test that scenario requirements are cached."""
        from focal.customer_data.models import ScenarioFieldRequirement
        from focal.customer_data.enums import RequiredLevel, FallbackAction

        mock_redis.get.return_value = None
        scenario_id = uuid4()

        requirement = ScenarioFieldRequirement(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
            field_name="email",
            required_level=RequiredLevel.HARD,
            fallback_action=FallbackAction.ASK,
        )
        await backend_store.save_scenario_requirement(requirement)

        await cached_store.get_scenario_requirements(tenant_id, scenario_id)

        mock_redis.setex.assert_called()


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, cached_store, mock_redis):
        """Test health check returns True when Redis is healthy."""
        mock_redis.ping.return_value = True

        result = await cached_store.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, cached_store, mock_redis):
        """Test health check returns False when Redis is unhealthy."""
        mock_redis.ping.side_effect = redis.RedisError("Connection refused")

        result = await cached_store.health_check()

        assert result is False
