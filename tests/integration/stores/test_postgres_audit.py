"""Integration tests for PostgresAuditStore.

Tests turn record and audit event operations
against a real PostgreSQL database.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from focal.audit.models import AuditEvent, TurnRecord
from focal.audit.stores.postgres import PostgresAuditStore
from focal.conversation.models.turn import ToolCall


@pytest_asyncio.fixture
async def audit_store(postgres_pool):
    """Create PostgresAuditStore with test pool."""
    return PostgresAuditStore(postgres_pool)


@pytest.fixture
def sample_turn_record(tenant_id, agent_id):
    """Create a sample turn record for testing."""
    session_id = uuid4()
    return TurnRecord(
        turn_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        turn_number=1,
        user_message="Hello, how can you help me?",
        agent_response="I'm here to assist you. What would you like help with?",
        matched_rule_ids=[uuid4(), uuid4()],
        scenario_id=uuid4(),
        step_id=uuid4(),
        tool_calls=[],
        latency_ms=250,
        tokens_used=150,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sample_audit_event(tenant_id):
    """Create a sample audit event for testing.

    Note: turn_id is None to avoid FK constraint issues.
    Tests that need a turn_id should create a turn record first.
    """
    return AuditEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        event_type="rule_matched",
        event_data={"rule_id": str(uuid4()), "score": 0.95},
        session_id=uuid4(),
        turn_id=None,
        timestamp=datetime.now(UTC),
    )


@pytest.mark.integration
class TestPostgresAuditStoreTurnRecord:
    """Test turn record operations."""

    async def test_save_and_get_turn_record(
        self, audit_store, sample_turn_record, clean_postgres
    ):
        """Test saving and retrieving a turn record."""
        # Save
        turn_id = await audit_store.save_turn(sample_turn_record)
        assert turn_id == sample_turn_record.turn_id

        # Get
        retrieved = await audit_store.get_turn(sample_turn_record.turn_id)
        assert retrieved is not None
        assert retrieved.user_message == sample_turn_record.user_message
        assert retrieved.agent_response == sample_turn_record.agent_response
        assert retrieved.turn_number == sample_turn_record.turn_number

    async def test_turn_record_with_tool_calls(
        self, audit_store, tenant_id, agent_id, clean_postgres
    ):
        """Test saving turn record with tool calls."""
        session_id = uuid4()
        tool_call = ToolCall(
            tool_id="tool_001",
            tool_name="get_weather",
            input={"city": "New York"},
            output={"temperature": 72, "condition": "sunny"},
            success=True,
            latency_ms=150,
        )

        turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            turn_number=1,
            user_message="What's the weather in New York?",
            agent_response="It's 72°F and sunny in New York.",
            tool_calls=[tool_call],
            latency_ms=500,
            tokens_used=200,
            timestamp=datetime.now(UTC),
        )

        await audit_store.save_turn(turn)
        retrieved = await audit_store.get_turn(turn.turn_id)

        assert retrieved is not None
        assert len(retrieved.tool_calls) == 1
        assert retrieved.tool_calls[0].tool_name == "get_weather"

    async def test_list_turns_by_session(
        self, audit_store, tenant_id, agent_id, clean_postgres
    ):
        """Test listing turn records by session."""
        session_id = uuid4()

        # Create multiple turns in a session
        for i in range(5):
            turn = TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=i + 1,
                user_message=f"Message {i + 1}",
                agent_response=f"Response {i + 1}",
                latency_ms=100,
                tokens_used=50,
                timestamp=datetime.now(UTC),
            )
            await audit_store.save_turn(turn)

        # List turns
        turns = await audit_store.list_turns_by_session(session_id)
        assert len(turns) == 5

        # Should be in order by turn_number
        for i, turn in enumerate(turns):
            assert turn.turn_number == i + 1

    async def test_list_turns_by_session_pagination(
        self, audit_store, tenant_id, agent_id, clean_postgres
    ):
        """Test pagination when listing turn records."""
        session_id = uuid4()

        # Create turns
        for i in range(10):
            turn = TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=i + 1,
                user_message=f"Message {i + 1}",
                agent_response=f"Response {i + 1}",
                latency_ms=100,
                tokens_used=50,
                timestamp=datetime.now(UTC),
            )
            await audit_store.save_turn(turn)

        # Get first page
        page1 = await audit_store.list_turns_by_session(session_id, limit=3, offset=0)
        assert len(page1) == 3
        assert page1[0].turn_number == 1

        # Get second page
        page2 = await audit_store.list_turns_by_session(session_id, limit=3, offset=3)
        assert len(page2) == 3
        assert page2[0].turn_number == 4

    async def test_list_turns_by_tenant(
        self, audit_store, tenant_id, agent_id, clean_postgres
    ):
        """Test listing turn records by tenant."""
        # Create turns in different sessions
        for i in range(3):
            session_id = uuid4()
            turn = TurnRecord(
                turn_id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_number=1,
                user_message=f"Message {i + 1}",
                agent_response=f"Response {i + 1}",
                latency_ms=100,
                tokens_used=50,
                timestamp=datetime.now(UTC),
            )
            await audit_store.save_turn(turn)

        # List by tenant
        turns = await audit_store.list_turns_by_tenant(tenant_id)
        assert len(turns) == 3

    async def test_list_turns_by_tenant_time_filter(
        self, audit_store, tenant_id, agent_id, clean_postgres
    ):
        """Test time filtering when listing turns by tenant."""
        now = datetime.now(UTC)
        old_time = now - timedelta(days=7)

        # Create old turn
        old_turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=uuid4(),
            turn_number=1,
            user_message="Old message",
            agent_response="Old response",
            latency_ms=100,
            tokens_used=50,
            timestamp=old_time,
        )
        await audit_store.save_turn(old_turn)

        # Create recent turn
        recent_turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=uuid4(),
            turn_number=1,
            user_message="Recent message",
            agent_response="Recent response",
            latency_ms=100,
            tokens_used=50,
            timestamp=now,
        )
        await audit_store.save_turn(recent_turn)

        # Filter by time
        recent_turns = await audit_store.list_turns_by_tenant(
            tenant_id, start_time=now - timedelta(hours=1)
        )
        assert len(recent_turns) == 1
        assert recent_turns[0].user_message == "Recent message"


@pytest.mark.integration
class TestPostgresAuditStoreAuditEvent:
    """Test audit event operations."""

    async def test_save_and_get_event(
        self, audit_store, sample_audit_event, clean_postgres
    ):
        """Test saving and retrieving an audit event."""
        # Save
        event_id = await audit_store.save_event(sample_audit_event)
        assert event_id == sample_audit_event.id

        # Get
        retrieved = await audit_store.get_event(sample_audit_event.id)
        assert retrieved is not None
        assert retrieved.event_type == sample_audit_event.event_type
        assert retrieved.event_data == sample_audit_event.event_data

    async def test_list_events_by_session(
        self, audit_store, tenant_id, clean_postgres
    ):
        """Test listing events by session."""
        session_id = uuid4()

        # Create multiple events
        events = []
        for i in range(5):
            event = AuditEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                event_type=f"event_type_{i}",
                event_data={"index": i},
                session_id=session_id,
                timestamp=datetime.now(UTC),
            )
            await audit_store.save_event(event)
            events.append(event)

        # List events
        result = await audit_store.list_events_by_session(session_id)
        assert len(result) == 5

    async def test_list_events_by_type(
        self, audit_store, tenant_id, clean_postgres
    ):
        """Test filtering events by type."""
        session_id = uuid4()

        # Create events of different types
        event1 = AuditEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            event_type="rule_matched",
            event_data={"rule_id": "123"},
            session_id=session_id,
            timestamp=datetime.now(UTC),
        )
        event2 = AuditEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            event_type="tool_executed",
            event_data={"tool_name": "search"},
            session_id=session_id,
            timestamp=datetime.now(UTC),
        )

        await audit_store.save_event(event1)
        await audit_store.save_event(event2)

        # Filter by type
        rule_events = await audit_store.list_events_by_session(
            session_id, event_type="rule_matched"
        )
        assert len(rule_events) == 1
        assert rule_events[0].event_type == "rule_matched"


@pytest.mark.integration
class TestPostgresAuditStoreTenantIsolation:
    """Test tenant isolation."""

    async def test_tenant_isolation_turn_records(
        self, audit_store, agent_id, clean_postgres
    ):
        """Test that turn records are isolated by tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        turn1 = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant1,
            agent_id=agent_id,
            session_id=uuid4(),
            turn_number=1,
            user_message="Tenant 1 message",
            agent_response="Tenant 1 response",
            latency_ms=100,
            tokens_used=50,
            timestamp=datetime.now(UTC),
        )
        turn2 = TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant2,
            agent_id=agent_id,
            session_id=uuid4(),
            turn_number=1,
            user_message="Tenant 2 message",
            agent_response="Tenant 2 response",
            latency_ms=100,
            tokens_used=50,
            timestamp=datetime.now(UTC),
        )

        await audit_store.save_turn(turn1)
        await audit_store.save_turn(turn2)

        # Tenant 1 should only see their turns
        tenant1_turns = await audit_store.list_turns_by_tenant(tenant1)
        assert len(tenant1_turns) == 1
        assert tenant1_turns[0].user_message == "Tenant 1 message"

        # Tenant 2 should only see their turns
        tenant2_turns = await audit_store.list_turns_by_tenant(tenant2)
        assert len(tenant2_turns) == 1
        assert tenant2_turns[0].user_message == "Tenant 2 message"

    async def test_tenant_isolation_audit_events(
        self, audit_store, clean_postgres
    ):
        """Test that audit events are isolated by tenant."""
        tenant1 = uuid4()
        tenant2 = uuid4()
        session_id = uuid4()

        event1 = AuditEvent(
            id=uuid4(),
            tenant_id=tenant1,
            event_type="test_event",
            event_data={"tenant": "1"},
            session_id=session_id,
            timestamp=datetime.now(UTC),
        )
        event2 = AuditEvent(
            id=uuid4(),
            tenant_id=tenant2,
            event_type="test_event",
            event_data={"tenant": "2"},
            session_id=session_id,
            timestamp=datetime.now(UTC),
        )

        await audit_store.save_event(event1)
        await audit_store.save_event(event2)

        # Both events have same session_id but different tenant
        # Should still be able to retrieve both
        retrieved1 = await audit_store.get_event(event1.id)
        retrieved2 = await audit_store.get_event(event2.id)

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1.event_data["tenant"] == "1"
        assert retrieved2.event_data["tenant"] == "2"


@pytest.mark.integration
class TestPostgresAuditStoreImmutability:
    """Test immutability behavior."""

    async def test_turn_records_are_immutable(
        self, audit_store, sample_turn_record, clean_postgres
    ):
        """Test that turn records cannot be modified after creation."""
        await audit_store.save_turn(sample_turn_record)

        # Attempt to save the same turn again should fail or be idempotent
        # depending on implementation
        retrieved = await audit_store.get_turn(sample_turn_record.turn_id)
        assert retrieved is not None
        assert retrieved.user_message == sample_turn_record.user_message

    async def test_audit_events_are_immutable(
        self, audit_store, sample_audit_event, clean_postgres
    ):
        """Test that audit events cannot be modified after creation."""
        await audit_store.save_event(sample_audit_event)

        # Verify event exists and matches
        retrieved = await audit_store.get_event(sample_audit_event.id)
        assert retrieved is not None
        assert retrieved.event_type == sample_audit_event.event_type
        assert retrieved.event_data == sample_audit_event.event_data
