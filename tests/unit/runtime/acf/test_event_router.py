"""Unit tests for EventRouter pattern matching and dispatch."""

from uuid import UUID, uuid4

import pytest

from ruche.runtime.acf.event_router import EventRouter
from ruche.runtime.acf.events import ACFEvent, ACFEventType
from ruche.runtime.acf.models import LogicalTurn, LogicalTurnStatus, SideEffect, SideEffectPolicy


@pytest.fixture
def router() -> EventRouter:
    """Create fresh event router."""
    return EventRouter()


@pytest.fixture
def sample_event() -> ACFEvent:
    """Create sample event for testing."""
    return ACFEvent(
        type=ACFEventType.TURN_STARTED,
        logical_turn_id=uuid4(),
        session_key="tenant:agent:customer:web",
        tenant_id=uuid4(),
        agent_id=uuid4(),
        payload={"message_count": 1},
    )


@pytest.fixture
def logical_turn() -> LogicalTurn:
    """Create sample logical turn."""
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    return LogicalTurn(
        session_key="tenant:agent:customer:web",
        first_at=now,
        last_at=now,
    )


class TestEventRouterRegistration:
    """Tests for listener registration and unregistration."""

    async def test_register_listener_adds_to_registry(self, router: EventRouter) -> None:
        """Listener is added to registry after registration."""
        listener_called = []

        async def test_listener(event: ACFEvent) -> None:
            listener_called.append(event)

        await router.register_listener("turn.started", test_listener)

        assert "turn.started" in router._listeners
        assert len(router._listeners["turn.started"]) == 1

    async def test_register_multiple_listeners_for_same_pattern(
        self, router: EventRouter
    ) -> None:
        """Multiple listeners can be registered for same pattern."""

        async def listener1(event: ACFEvent) -> None:
            pass

        async def listener2(event: ACFEvent) -> None:
            pass

        await router.register_listener("turn.*", listener1)
        await router.register_listener("turn.*", listener2)

        assert len(router._listeners["turn.*"]) == 2

    async def test_unregister_listener_removes_from_registry(self, router: EventRouter) -> None:
        """Listener is removed from registry after unregistration."""

        async def test_listener(event: ACFEvent) -> None:
            pass

        await router.register_listener("turn.started", test_listener)
        await router.unregister_listener("turn.started", test_listener)

        assert len(router._listeners["turn.started"]) == 0

    async def test_unregister_nonexistent_listener_logs_warning(
        self, router: EventRouter
    ) -> None:
        """Unregistering nonexistent listener doesn't raise error."""

        async def test_listener(event: ACFEvent) -> None:
            pass

        await router.unregister_listener("nonexistent", test_listener)


class TestPatternMatching:
    """Tests for event pattern matching logic."""

    def test_matches_pattern_exact_match(self, router: EventRouter) -> None:
        """Exact pattern match returns true."""
        assert router._matches_pattern("turn.started", "turn.started")

    def test_matches_pattern_wildcard_match(self, router: EventRouter) -> None:
        """Wildcard pattern matches prefix."""
        assert router._matches_pattern("turn.started", "turn.*")
        assert router._matches_pattern("turn.completed", "turn.*")
        assert router._matches_pattern("turn.failed", "turn.*")

    def test_matches_pattern_wildcard_no_match(self, router: EventRouter) -> None:
        """Wildcard pattern doesn't match different prefix."""
        assert not router._matches_pattern("message.absorbed", "turn.*")
        assert not router._matches_pattern("tool.executed", "turn.*")

    def test_matches_pattern_exact_no_match(self, router: EventRouter) -> None:
        """Exact pattern doesn't match different event."""
        assert not router._matches_pattern("turn.started", "turn.completed")

    def test_matches_pattern_empty_string(self, router: EventRouter) -> None:
        """Empty strings don't match."""
        assert not router._matches_pattern("", "turn.*")
        assert not router._matches_pattern("turn.started", "")


class TestEventRouting:
    """Tests for event routing and dispatch."""

    async def test_route_calls_matching_listener(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Matching listener is called with event."""
        listener_called = []

        async def test_listener(event: ACFEvent) -> None:
            listener_called.append(event)

        await router.register_listener("turn.started", test_listener)
        await router.route(sample_event)

        assert len(listener_called) == 1
        assert listener_called[0] == sample_event

    async def test_route_calls_wildcard_listener(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Wildcard listener matches event."""
        listener_called = []

        async def test_listener(event: ACFEvent) -> None:
            listener_called.append(event)

        await router.register_listener("turn.*", test_listener)
        await router.route(sample_event)

        assert len(listener_called) == 1

    async def test_route_calls_all_matching_listeners(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """All matching listeners are called."""
        exact_called = []
        wildcard_called = []

        async def exact_listener(event: ACFEvent) -> None:
            exact_called.append(event)

        async def wildcard_listener(event: ACFEvent) -> None:
            wildcard_called.append(event)

        await router.register_listener("turn.started", exact_listener)
        await router.register_listener("turn.*", wildcard_listener)
        await router.route(sample_event)

        assert len(exact_called) == 1
        assert len(wildcard_called) == 1

    async def test_route_no_matching_listeners(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Route completes without error when no listeners match."""
        await router.route(sample_event)

    async def test_route_handles_listener_exception(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Listener exceptions are caught and logged."""

        async def failing_listener(event: ACFEvent) -> None:
            raise ValueError("Test error")

        await router.register_listener("turn.started", failing_listener)
        await router.route(sample_event)


class TestSideEffectRecording:
    """Tests for side effect recording in LogicalTurn."""

    async def test_record_side_effect_for_tool_executed_event(
        self, router: EventRouter, logical_turn: LogicalTurn
    ) -> None:
        """Tool execution events are recorded as side effects."""
        event = ACFEvent(
            type=ACFEventType.TOOL_EXECUTED,
            logical_turn_id=logical_turn.id,
            session_key=logical_turn.session_key,
            payload={
                "tool_name": "send_email",
                "policy": "irreversible",
                "idempotency_key": "test-key",
            },
        )

        await router._record_side_effect(event, logical_turn)

        assert len(logical_turn.side_effects) == 1
        side_effect = logical_turn.side_effects[0]
        assert side_effect.effect_type == "tool_call"
        assert side_effect.tool_name == "send_email"
        assert side_effect.policy == SideEffectPolicy.IRREVERSIBLE
        assert side_effect.idempotency_key == "test-key"

    async def test_record_side_effect_idempotent_policy(
        self, router: EventRouter, logical_turn: LogicalTurn
    ) -> None:
        """Idempotent policy is recorded correctly."""
        event = ACFEvent(
            type=ACFEventType.TOOL_EXECUTED,
            logical_turn_id=logical_turn.id,
            session_key=logical_turn.session_key,
            payload={
                "tool_name": "get_weather",
                "policy": "idempotent",
            },
        )

        await router._record_side_effect(event, logical_turn)

        assert len(logical_turn.side_effects) == 1
        assert logical_turn.side_effects[0].policy == SideEffectPolicy.IDEMPOTENT

    async def test_record_side_effect_reversible_policy(
        self, router: EventRouter, logical_turn: LogicalTurn
    ) -> None:
        """Reversible policy is recorded correctly."""
        event = ACFEvent(
            type=ACFEventType.TOOL_EXECUTED,
            logical_turn_id=logical_turn.id,
            session_key=logical_turn.session_key,
            payload={
                "tool_name": "reserve_temp_slot",
                "policy": "reversible",
            },
        )

        await router._record_side_effect(event, logical_turn)

        assert len(logical_turn.side_effects) == 1
        assert logical_turn.side_effects[0].policy == SideEffectPolicy.REVERSIBLE

    async def test_no_side_effect_for_non_tool_events(
        self, router: EventRouter, logical_turn: LogicalTurn
    ) -> None:
        """Non-tool events don't create side effects."""
        event = ACFEvent(
            type=ACFEventType.TURN_STARTED,
            logical_turn_id=logical_turn.id,
            session_key=logical_turn.session_key,
            payload={"message_count": 1},
        )

        await router._record_side_effect(event, logical_turn)

        assert len(logical_turn.side_effects) == 0


class TestFindMatchingListeners:
    """Tests for finding matching listeners."""

    async def test_find_matching_listeners_exact_match(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Finds listeners with exact match."""

        async def test_listener(event: ACFEvent) -> None:
            pass

        await router.register_listener("turn.started", test_listener)

        matching = await router._find_matching_listeners(sample_event)
        assert len(matching) == 1
        assert matching[0] == test_listener

    async def test_find_matching_listeners_wildcard(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Finds listeners with wildcard pattern."""

        async def test_listener(event: ACFEvent) -> None:
            pass

        await router.register_listener("turn.*", test_listener)

        matching = await router._find_matching_listeners(sample_event)
        assert len(matching) == 1

    async def test_find_matching_listeners_multiple_patterns(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Finds listeners from multiple matching patterns."""

        async def listener1(event: ACFEvent) -> None:
            pass

        async def listener2(event: ACFEvent) -> None:
            pass

        await router.register_listener("turn.started", listener1)
        await router.register_listener("turn.*", listener2)

        matching = await router._find_matching_listeners(sample_event)
        assert len(matching) == 2

    async def test_find_matching_listeners_no_match(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Returns empty list when no listeners match."""

        async def test_listener(event: ACFEvent) -> None:
            pass

        await router.register_listener("tool.*", test_listener)

        matching = await router._find_matching_listeners(sample_event)
        assert len(matching) == 0


class TestDispatchToListener:
    """Tests for single listener dispatch."""

    async def test_dispatch_to_listener_calls_listener(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Listener is called with event."""
        listener_called = []

        async def test_listener(event: ACFEvent) -> None:
            listener_called.append(event)

        await router._dispatch_to_listener(test_listener, sample_event)

        assert len(listener_called) == 1
        assert listener_called[0] == sample_event

    async def test_dispatch_to_listener_catches_exception(
        self, router: EventRouter, sample_event: ACFEvent
    ) -> None:
        """Listener exceptions are caught and logged."""

        async def failing_listener(event: ACFEvent) -> None:
            raise RuntimeError("Listener failed")

        await router._dispatch_to_listener(failing_listener, sample_event)


class TestCategorySupport:
    """Test category extraction and pattern matching."""

    async def test_category_extraction(self):
        """Test that category is correctly extracted from event type."""
        event = ACFEvent(
            type=ACFEventType.TURN_STARTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
        )
        assert event.category == "turn"
        assert event.event_name == "started"

    async def test_tool_category(self):
        """Test tool event category."""
        event = ACFEvent(
            type=ACFEventType.TOOL_EXECUTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
        )
        assert event.category == "tool"
        assert event.event_name == "executed"

    async def test_matches_pattern_wildcard(self):
        """Test wildcard pattern matching."""
        event = ACFEvent(
            type=ACFEventType.TURN_STARTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
        )
        assert event.matches_pattern("*") is True
        assert event.matches_pattern("turn.*") is True
        assert event.matches_pattern("turn.started") is True
        assert event.matches_pattern("tool.*") is False
        assert event.matches_pattern("turn.completed") is False

    async def test_router_category_pattern(self, router: EventRouter):
        """Test router with category wildcard pattern."""
        received = []

        async def listener(event: ACFEvent) -> None:
            received.append(event)

        await router.register_listener("turn.*", listener)

        # Should match
        turn_event = ACFEvent(
            type=ACFEventType.TURN_STARTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
        )
        await router.route(turn_event, None)

        # Should not match
        tool_event = ACFEvent(
            type=ACFEventType.TOOL_EXECUTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
        )
        await router.route(tool_event, None)

        assert len(received) == 1
        assert received[0].type == ACFEventType.TURN_STARTED
