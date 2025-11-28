"""Tests for InMemorySessionStore."""

from uuid import uuid4

import pytest

from soldier.conversation.models import Channel, Session, SessionStatus
from soldier.conversation.stores import InMemorySessionStore


@pytest.fixture
def store() -> InMemorySessionStore:
    """Create a fresh store for each test."""
    return InMemorySessionStore()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def sample_session(tenant_id, agent_id) -> Session:
    """Create a sample session."""
    return Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
    )


class TestSessionOperations:
    """Tests for session CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_session(self, store, sample_session):
        """Should save and retrieve a session."""
        session_id = await store.save(sample_session)
        retrieved = await store.get(session_id)

        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id
        assert retrieved.user_channel_id == "user123"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, store):
        """Should return None for nonexistent session."""
        result = await store.get(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, store, sample_session):
        """Should delete a session."""
        session_id = await store.save(sample_session)

        result = await store.delete(session_id)
        assert result is True

        retrieved = await store.get(session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, store):
        """Should return False when deleting nonexistent session."""
        result = await store.delete(uuid4())
        assert result is False


class TestChannelLookup:
    """Tests for channel-based session lookup."""

    @pytest.mark.asyncio
    async def test_get_by_channel(self, store, sample_session, tenant_id):
        """Should find session by channel identity."""
        await store.save(sample_session)

        retrieved = await store.get_by_channel(
            tenant_id, Channel.WEBCHAT, "user123"
        )

        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id

    @pytest.mark.asyncio
    async def test_get_by_channel_tenant_isolation(
        self, store, sample_session, tenant_id
    ):
        """Should not return sessions from other tenants."""
        await store.save(sample_session)
        other_tenant = uuid4()

        result = await store.get_by_channel(other_tenant, Channel.WEBCHAT, "user123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_channel_not_found(self, store, tenant_id):
        """Should return None when no matching session."""
        result = await store.get_by_channel(tenant_id, Channel.WEBCHAT, "unknown")
        assert result is None


class TestListByAgent:
    """Tests for listing sessions by agent."""

    @pytest.mark.asyncio
    async def test_list_by_agent(self, store, tenant_id, agent_id):
        """Should list all sessions for an agent."""
        sessions = [
            Session(
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=Channel.WEBCHAT,
                user_channel_id=f"user{i}",
                config_version=1,
            )
            for i in range(3)
        ]
        for session in sessions:
            await store.save(session)

        results = await store.list_by_agent(tenant_id, agent_id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_by_agent_with_status_filter(self, store, tenant_id, agent_id):
        """Should filter by status."""
        active = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="active_user",
            config_version=1,
            status=SessionStatus.ACTIVE,
        )
        ended = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="ended_user",
            config_version=1,
            status=SessionStatus.CLOSED,
        )
        await store.save(active)
        await store.save(ended)

        results = await store.list_by_agent(
            tenant_id, agent_id, status=SessionStatus.ACTIVE
        )
        assert len(results) == 1
        assert results[0].user_channel_id == "active_user"

    @pytest.mark.asyncio
    async def test_list_by_agent_tenant_isolation(self, store, tenant_id, agent_id):
        """Should only return sessions for specified tenant."""
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user1",
            config_version=1,
        )
        await store.save(session)
        other_tenant = uuid4()

        results = await store.list_by_agent(other_tenant, agent_id)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_by_agent_respects_limit(self, store, tenant_id, agent_id):
        """Should respect limit parameter."""
        sessions = [
            Session(
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=Channel.WEBCHAT,
                user_channel_id=f"user{i}",
                config_version=1,
            )
            for i in range(5)
        ]
        for session in sessions:
            await store.save(session)

        results = await store.list_by_agent(tenant_id, agent_id, limit=2)
        assert len(results) == 2


class TestListByCustomer:
    """Tests for listing sessions by customer."""

    @pytest.mark.asyncio
    async def test_list_by_customer(self, store, tenant_id, agent_id):
        """Should list all sessions for a customer profile."""
        customer_id = uuid4()
        sessions = [
            Session(
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=Channel.WEBCHAT,
                user_channel_id=f"user{i}",
                config_version=1,
                customer_profile_id=customer_id,
            )
            for i in range(2)
        ]
        for session in sessions:
            await store.save(session)

        results = await store.list_by_customer(tenant_id, customer_id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_by_customer_tenant_isolation(self, store, tenant_id, agent_id):
        """Should only return sessions for specified tenant."""
        customer_id = uuid4()
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user1",
            config_version=1,
            customer_profile_id=customer_id,
        )
        await store.save(session)
        other_tenant = uuid4()

        results = await store.list_by_customer(other_tenant, customer_id)
        assert len(results) == 0
