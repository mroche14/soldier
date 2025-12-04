"""Integration tests for RedisSessionStore.

Tests two-tier caching, TTL behavior, tier promotion/demotion,
and index operations against a real Redis instance.
"""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio

from soldier.config.models.storage import RedisSessionConfig
from soldier.conversation.models import Channel, Session
from soldier.conversation.stores.redis import RedisSessionStore


@pytest_asyncio.fixture
async def session_store(redis_client):
    """Create RedisSessionStore with test client."""
    config = RedisSessionConfig(
        hot_ttl_seconds=5,  # Short TTL for testing
        persist_ttl_seconds=30,
        key_prefix="test_session",
    )
    return RedisSessionStore(redis_client, config)


@pytest.fixture
def sample_session(tenant_id, agent_id):
    """Create a sample session for testing."""
    return Session(
        session_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=Channel.WEBCHAT,
        user_channel_id="test_user_123",
        config_version=1,
    )


@pytest.mark.integration
class TestRedisSessionStoreCRUD:
    """Test basic CRUD operations."""

    async def test_save_and_get_session(
        self, session_store, sample_session, clean_redis
    ):
        """Test saving and retrieving a session."""
        # Save
        session_id = await session_store.save(sample_session)
        assert session_id == sample_session.session_id

        # Get
        retrieved = await session_store.get(sample_session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id
        assert retrieved.tenant_id == sample_session.tenant_id
        assert retrieved.channel == sample_session.channel

    async def test_get_nonexistent_session(self, session_store, clean_redis):
        """Test getting a session that doesn't exist."""
        retrieved = await session_store.get(uuid4())
        assert retrieved is None

    async def test_delete_session(
        self, session_store, sample_session, clean_redis
    ):
        """Test deleting a session."""
        await session_store.save(sample_session)

        # Delete
        deleted = await session_store.delete(sample_session.session_id)
        assert deleted is True

        # Should not be found
        retrieved = await session_store.get(sample_session.session_id)
        assert retrieved is None

    async def test_delete_nonexistent_session(self, session_store, clean_redis):
        """Test deleting a session that doesn't exist."""
        deleted = await session_store.delete(uuid4())
        assert deleted is False


@pytest.mark.integration
class TestRedisSessionStoreIndexes:
    """Test index-based lookups."""

    async def test_get_by_channel(
        self, session_store, sample_session, clean_redis
    ):
        """Test looking up session by channel identity."""
        await session_store.save(sample_session)

        # Find by channel
        retrieved = await session_store.get_by_channel(
            sample_session.tenant_id,
            sample_session.channel,
            sample_session.user_channel_id,
        )
        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id

    async def test_list_by_agent(
        self, session_store, tenant_id, agent_id, clean_redis
    ):
        """Test listing sessions by agent."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = Session(
                session_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=Channel.WEBCHAT,
                user_channel_id=f"user_{i}",
                config_version=1,
            )
            await session_store.save(session)
            sessions.append(session)

        # List by agent
        result = await session_store.list_by_agent(tenant_id, agent_id)
        assert len(result) == 3

    async def test_list_by_customer(
        self, session_store, tenant_id, agent_id, customer_profile_id, clean_redis
    ):
        """Test listing sessions by customer profile."""
        # Create session with customer link
        session = Session(
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="customer_user",
            customer_profile_id=customer_profile_id,
            config_version=1,
        )
        await session_store.save(session)

        # List by customer
        result = await session_store.list_by_customer(tenant_id, customer_profile_id)
        assert len(result) == 1
        assert result[0].session_id == session.session_id


@pytest.mark.integration
class TestRedisSessionStoreTierBehavior:
    """Test two-tier caching behavior."""

    async def test_session_in_hot_tier_after_save(
        self, session_store, sample_session, redis_client, clean_redis
    ):
        """Test that saved sessions are in hot tier."""
        await session_store.save(sample_session)

        # Check hot tier key exists
        hot_key = session_store._hot_key(sample_session.session_id)
        exists = await redis_client.exists(hot_key)
        assert exists == 1

    async def test_promote_to_hot(
        self, session_store, sample_session, redis_client, clean_redis
    ):
        """Test promoting session to hot tier."""
        # First save to hot tier
        await session_store.save(sample_session)

        # Manually demote to persistent
        await session_store.demote_to_persistent(sample_session)

        # Verify in persistent
        persist_key = session_store._persist_key(sample_session.session_id)
        hot_key = session_store._hot_key(sample_session.session_id)

        assert await redis_client.exists(persist_key) == 1
        assert await redis_client.exists(hot_key) == 0

        # Get should auto-promote to hot
        retrieved = await session_store.get(sample_session.session_id)
        assert retrieved is not None

        # Now should be in hot tier
        assert await redis_client.exists(hot_key) == 1

    async def test_demote_to_persistent(
        self, session_store, sample_session, redis_client, clean_redis
    ):
        """Test demoting session to persistent tier."""
        await session_store.save(sample_session)

        # Demote
        await session_store.demote_to_persistent(sample_session)

        # Verify in persistent, not in hot
        persist_key = session_store._persist_key(sample_session.session_id)
        hot_key = session_store._hot_key(sample_session.session_id)

        assert await redis_client.exists(persist_key) == 1
        assert await redis_client.exists(hot_key) == 0


@pytest.mark.integration
@pytest.mark.slow
class TestRedisSessionStoreTTL:
    """Test TTL expiration behavior."""

    async def test_hot_tier_expiration(
        self, session_store, sample_session, clean_redis
    ):
        """Test that hot tier sessions expire after TTL."""
        await session_store.save(sample_session)

        # Wait for hot TTL to expire (5 seconds in test config)
        await asyncio.sleep(6)

        # Should not be found (expired from hot, not in persistent)
        retrieved = await session_store.get(sample_session.session_id)
        assert retrieved is None


@pytest.mark.integration
class TestRedisSessionStoreHealthCheck:
    """Test health check functionality."""

    async def test_health_check_success(self, session_store, clean_redis):
        """Test health check passes with valid connection."""
        healthy = await session_store.health_check()
        assert healthy is True


@pytest.mark.integration
class TestRedisSessionStoreConcurrency:
    """Test concurrent access patterns."""

    async def test_concurrent_saves(
        self, session_store, tenant_id, agent_id, clean_redis
    ):
        """Test concurrent session saves."""
        sessions = [
            Session(
                session_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=Channel.WEBCHAT,
                user_channel_id=f"concurrent_user_{i}",
                config_version=1,
            )
            for i in range(10)
        ]

        # Save concurrently
        await asyncio.gather(*[session_store.save(s) for s in sessions])

        # Verify all saved
        for session in sessions:
            retrieved = await session_store.get(session.session_id)
            assert retrieved is not None


@pytest.mark.integration
class TestRedisSessionStoreConnectionFailure:
    """Test connection failure handling."""

    async def test_health_check_with_valid_connection(
        self, session_store, clean_redis
    ):
        """Test health check passes with valid connection."""
        healthy = await session_store.health_check()
        assert healthy is True

    async def test_get_returns_none_for_nonexistent(
        self, session_store, clean_redis
    ):
        """Test that getting nonexistent session returns None gracefully."""
        result = await session_store.get(uuid4())
        assert result is None

    async def test_delete_returns_false_for_nonexistent(
        self, session_store, clean_redis
    ):
        """Test that deleting nonexistent session returns False gracefully."""
        result = await session_store.delete(uuid4())
        assert result is False

    async def test_get_by_channel_returns_none_for_nonexistent(
        self, session_store, tenant_id, clean_redis
    ):
        """Test get_by_channel returns None for nonexistent."""
        result = await session_store.get_by_channel(
            tenant_id,
            Channel.WEBCHAT,
            "nonexistent_user",
        )
        assert result is None

    async def test_list_by_agent_returns_empty_for_none(
        self, session_store, tenant_id, agent_id, clean_redis
    ):
        """Test list_by_agent returns empty list when no sessions."""
        result = await session_store.list_by_agent(tenant_id, agent_id)
        assert result == []

    async def test_list_by_customer_returns_empty_for_none(
        self, session_store, tenant_id, customer_profile_id, clean_redis
    ):
        """Test list_by_customer returns empty list when no sessions."""
        result = await session_store.list_by_customer(tenant_id, customer_profile_id)
        assert result == []
