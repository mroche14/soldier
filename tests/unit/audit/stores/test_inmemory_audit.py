"""Tests for InMemoryAuditStore."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from soldier.audit.models import AuditEvent, TurnRecord
from soldier.audit.stores import InMemoryAuditStore


@pytest.fixture
def store() -> InMemoryAuditStore:
    """Create a fresh store for each test."""
    return InMemoryAuditStore()


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def sample_turn(tenant_id, session_id, agent_id) -> TurnRecord:
    """Create a sample turn record."""
    return TurnRecord(
        turn_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        turn_number=1,
        user_message="Hello",
        agent_response="Hi there!",
        latency_ms=150,
        tokens_used=50,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_event(tenant_id, session_id) -> AuditEvent:
    """Create a sample audit event."""
    return AuditEvent(
        tenant_id=tenant_id,
        event_type="rule_matched",
        event_data={"rule_id": str(uuid4()), "score": 0.95},
        session_id=session_id,
    )


class TestTurnRecordOperations:
    """Tests for turn record CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_turn(self, store, sample_turn):
        """Should save and retrieve a turn record."""
        turn_id = await store.save_turn(sample_turn)
        retrieved = await store.get_turn(turn_id)

        assert retrieved is not None
        assert retrieved.turn_id == sample_turn.turn_id
        assert retrieved.user_message == "Hello"

    @pytest.mark.asyncio
    async def test_get_nonexistent_turn(self, store):
        """Should return None for nonexistent turn."""
        result = await store.get_turn(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_turns_by_session(
        self, store, tenant_id, session_id, agent_id
    ):
        """Should list turns for a session in chronological order."""
        base_time = datetime.now(timezone.utc)
        turns = [
            TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=i,
                user_message=f"Message {i}",
                agent_response=f"Response {i}",
                latency_ms=100,
                tokens_used=50,
                timestamp=base_time + timedelta(seconds=i),
            )
            for i in range(3)
        ]
        for turn in turns:
            await store.save_turn(turn)

        results = await store.list_turns_by_session(session_id)
        assert len(results) == 3
        # Should be in chronological order
        assert results[0].turn_number == 0
        assert results[2].turn_number == 2

    @pytest.mark.asyncio
    async def test_list_turns_by_session_pagination(
        self, store, tenant_id, session_id, agent_id
    ):
        """Should support pagination."""
        base_time = datetime.now(timezone.utc)
        turns = [
            TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=i,
                user_message=f"Message {i}",
                agent_response=f"Response {i}",
                latency_ms=100,
                tokens_used=50,
                timestamp=base_time + timedelta(seconds=i),
            )
            for i in range(5)
        ]
        for turn in turns:
            await store.save_turn(turn)

        results = await store.list_turns_by_session(session_id, limit=2, offset=2)
        assert len(results) == 2
        assert results[0].turn_number == 2

    @pytest.mark.asyncio
    async def test_list_turns_by_tenant(self, store, tenant_id, agent_id):
        """Should list turns for a tenant."""
        session1 = uuid4()
        session2 = uuid4()
        base_time = datetime.now(timezone.utc)

        turn1 = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session1,
            turn_number=1,
            user_message="Message 1",
            agent_response="Response 1",
            latency_ms=100,
            tokens_used=50,
            timestamp=base_time,
        )
        turn2 = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session2,
            turn_number=1,
            user_message="Message 2",
            agent_response="Response 2",
            latency_ms=100,
            tokens_used=50,
            timestamp=base_time + timedelta(hours=1),
        )
        await store.save_turn(turn1)
        await store.save_turn(turn2)

        results = await store.list_turns_by_tenant(tenant_id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_turns_by_tenant_time_filter(
        self, store, tenant_id, agent_id, session_id
    ):
        """Should filter turns by time range."""
        base_time = datetime.now(timezone.utc)
        old_turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            turn_number=1,
            user_message="Old message",
            agent_response="Old response",
            latency_ms=100,
            tokens_used=50,
            timestamp=base_time - timedelta(days=2),
        )
        recent_turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            turn_number=2,
            user_message="Recent message",
            agent_response="Recent response",
            latency_ms=100,
            tokens_used=50,
            timestamp=base_time,
        )
        await store.save_turn(old_turn)
        await store.save_turn(recent_turn)

        results = await store.list_turns_by_tenant(
            tenant_id, start_time=base_time - timedelta(hours=1)
        )
        assert len(results) == 1
        assert results[0].user_message == "Recent message"


class TestAuditEventOperations:
    """Tests for audit event CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_and_get_event(self, store, sample_event):
        """Should save and retrieve an audit event."""
        event_id = await store.save_event(sample_event)
        retrieved = await store.get_event(event_id)

        assert retrieved is not None
        assert retrieved.id == sample_event.id
        assert retrieved.event_type == "rule_matched"

    @pytest.mark.asyncio
    async def test_get_nonexistent_event(self, store):
        """Should return None for nonexistent event."""
        result = await store.get_event(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_events_by_session(self, store, tenant_id, session_id):
        """Should list events for a session."""
        events = [
            AuditEvent(
                tenant_id=tenant_id,
                event_type=f"event_{i}",
                event_data={"index": i},
                session_id=session_id,
            )
            for i in range(3)
        ]
        for event in events:
            await store.save_event(event)

        results = await store.list_events_by_session(session_id)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_events_by_session_type_filter(
        self, store, tenant_id, session_id
    ):
        """Should filter events by type."""
        event1 = AuditEvent(
            tenant_id=tenant_id,
            event_type="rule_matched",
            event_data={},
            session_id=session_id,
        )
        event2 = AuditEvent(
            tenant_id=tenant_id,
            event_type="tool_executed",
            event_data={},
            session_id=session_id,
        )
        await store.save_event(event1)
        await store.save_event(event2)

        results = await store.list_events_by_session(
            session_id, event_type="rule_matched"
        )
        assert len(results) == 1
        assert results[0].event_type == "rule_matched"

    @pytest.mark.asyncio
    async def test_list_events_respects_limit(self, store, tenant_id, session_id):
        """Should respect limit parameter."""
        events = [
            AuditEvent(
                tenant_id=tenant_id,
                event_type=f"event_{i}",
                event_data={},
                session_id=session_id,
            )
            for i in range(5)
        ]
        for event in events:
            await store.save_event(event)

        results = await store.list_events_by_session(session_id, limit=2)
        assert len(results) == 2
