"""Tests for SupersedeCoordinator - supersede decision enforcement.

Tests cover:
- Checking if turn can be superseded
- Enforcing supersede decisions
- Supersede, absorb, queue, and force_complete actions
- Building tool idempotency keys
"""

import pytest
from datetime import UTC, datetime
from uuid import uuid4

from ruche.runtime.acf.supersede import (
    SupersedeCoordinator,
    build_tool_idempotency_key,
)
from ruche.runtime.acf.models import (
    LogicalTurn,
    LogicalTurnStatus,
    SideEffect,
    SideEffectPolicy,
    SupersedeAction,
    SupersedeDecision,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def coordinator():
    """Create SupersedeCoordinator instance."""
    return SupersedeCoordinator()


@pytest.fixture
def accumulating_turn():
    """Create turn in ACCUMULATING status."""
    return LogicalTurn(
        id=uuid4(),
        session_key="tenant:agent:customer:channel",
        messages=[uuid4()],
        first_at=datetime.now(UTC),
        last_at=datetime.now(UTC),
        status=LogicalTurnStatus.ACCUMULATING,
    )


@pytest.fixture
def processing_turn():
    """Create turn in PROCESSING status."""
    return LogicalTurn(
        id=uuid4(),
        session_key="tenant:agent:customer:channel",
        messages=[uuid4()],
        first_at=datetime.now(UTC),
        last_at=datetime.now(UTC),
        status=LogicalTurnStatus.PROCESSING,
    )


@pytest.fixture
def complete_turn():
    """Create turn in COMPLETE status."""
    turn = LogicalTurn(
        id=uuid4(),
        session_key="tenant:agent:customer:channel",
        messages=[uuid4()],
        first_at=datetime.now(UTC),
        last_at=datetime.now(UTC),
        status=LogicalTurnStatus.ACCUMULATING,
    )
    turn.mark_complete()
    return turn


# =============================================================================
# Tests: SupersedeCoordinator.can_supersede()
# =============================================================================


class TestCanSupersede:
    """Tests for supersede eligibility check."""

    def test_accumulating_turn_can_be_superseded(self, coordinator, accumulating_turn):
        """Accumulating turns can always be superseded."""
        result = coordinator.can_supersede(accumulating_turn)
        assert result is True

    def test_processing_turn_without_effects_can_be_superseded(
        self, coordinator, processing_turn
    ):
        """Processing turns without irreversible effects can be superseded."""
        assert processing_turn.side_effects == []

        result = coordinator.can_supersede(processing_turn)
        assert result is True

    def test_processing_turn_with_reversible_effects_can_be_superseded(
        self, coordinator, processing_turn
    ):
        """Processing turns with only reversible effects can be superseded."""
        processing_turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.REVERSIBLE,
                tool_name="search_products",
            )
        )

        result = coordinator.can_supersede(processing_turn)
        assert result is True

    def test_processing_turn_with_irreversible_effect_cannot_be_superseded(
        self, coordinator, processing_turn
    ):
        """Processing turns with irreversible effects cannot be superseded."""
        processing_turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IRREVERSIBLE,
                tool_name="send_email",
            )
        )

        result = coordinator.can_supersede(processing_turn)
        assert result is False

    def test_complete_turn_cannot_be_superseded(self, coordinator, complete_turn):
        """Complete turns cannot be superseded."""
        result = coordinator.can_supersede(complete_turn)
        assert result is False

    def test_superseded_turn_cannot_be_superseded_again(self, coordinator):
        """Already superseded turns cannot be superseded again."""
        turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.ACCUMULATING,
        )
        turn.mark_superseded(by_turn_id=uuid4())

        result = coordinator.can_supersede(turn)
        assert result is False


# =============================================================================
# Tests: SupersedeCoordinator.enforce_decision() - SUPERSEDE
# =============================================================================


class TestEnforceSupersede:
    """Tests for enforcing SUPERSEDE action."""

    def test_creates_new_turn_on_supersede(self, coordinator, accumulating_turn):
        """Creates new turn when superseding."""
        new_message_id = uuid4()
        decision = SupersedeDecision(action=SupersedeAction.SUPERSEDE, reason="correction")

        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=new_message_id,
            new_message_timestamp=datetime.now(UTC),
        )

        assert new_turn.id != accumulating_turn.id
        assert new_message_id in new_turn.messages
        assert new_turn.superseded_from == accumulating_turn.id

    def test_marks_current_turn_as_superseded(self, coordinator, accumulating_turn):
        """Marks current turn as superseded."""
        decision = SupersedeDecision(action=SupersedeAction.SUPERSEDE, reason="correction")

        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        assert accumulating_turn.status == LogicalTurnStatus.SUPERSEDED
        assert accumulating_turn.superseded_by == new_turn.id

    def test_new_turn_inherits_turn_group_id(self, coordinator, accumulating_turn):
        """New turn inherits turn_group_id for idempotency."""
        decision = SupersedeDecision(action=SupersedeAction.SUPERSEDE, reason="correction")

        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        assert new_turn.turn_group_id == accumulating_turn.turn_group_id

    def test_new_turn_starts_accumulating(self, coordinator, processing_turn):
        """New turn starts in ACCUMULATING status."""
        decision = SupersedeDecision(action=SupersedeAction.SUPERSEDE, reason="correction")

        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=processing_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        assert new_turn.status == LogicalTurnStatus.ACCUMULATING


# =============================================================================
# Tests: SupersedeCoordinator.enforce_decision() - ABSORB
# =============================================================================


class TestEnforceAbsorb:
    """Tests for enforcing ABSORB action."""

    def test_absorbs_message_into_current_turn(self, coordinator, accumulating_turn):
        """Absorbs new message into current turn."""
        new_message_id = uuid4()
        initial_count = len(accumulating_turn.messages)
        decision = SupersedeDecision(action=SupersedeAction.ABSORB, reason="clarification")

        result_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=new_message_id,
            new_message_timestamp=datetime.now(UTC),
        )

        assert result_turn is accumulating_turn
        assert len(result_turn.messages) == initial_count + 1
        assert new_message_id in result_turn.messages

    def test_updates_last_at_timestamp(self, coordinator, accumulating_turn):
        """Updates last_at when absorbing message."""
        original_last_at = accumulating_turn.last_at
        new_timestamp = datetime.now(UTC)
        decision = SupersedeDecision(action=SupersedeAction.ABSORB, reason="clarification")

        coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=uuid4(),
            new_message_timestamp=new_timestamp,
        )

        assert accumulating_turn.last_at >= original_last_at


# =============================================================================
# Tests: SupersedeCoordinator.enforce_decision() - QUEUE
# =============================================================================


class TestEnforceQueue:
    """Tests for enforcing QUEUE action."""

    def test_returns_current_turn_unchanged(self, coordinator, processing_turn):
        """Returns current turn without modification."""
        initial_message_count = len(processing_turn.messages)
        decision = SupersedeDecision(action=SupersedeAction.QUEUE, reason="commit_point_reached")

        result_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=processing_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        assert result_turn is processing_turn
        assert len(result_turn.messages) == initial_message_count

    def test_does_not_absorb_queued_message(self, coordinator, processing_turn):
        """Does not absorb the message (caller handles queuing)."""
        new_message_id = uuid4()
        decision = SupersedeDecision(action=SupersedeAction.QUEUE, reason="commit_point_reached")

        coordinator.enforce_decision(
            decision=decision,
            current_turn=processing_turn,
            new_message_id=new_message_id,
            new_message_timestamp=datetime.now(UTC),
        )

        assert new_message_id not in processing_turn.messages


# =============================================================================
# Tests: SupersedeCoordinator.enforce_decision() - FORCE_COMPLETE
# =============================================================================


class TestEnforceForceComplete:
    """Tests for enforcing FORCE_COMPLETE action."""

    def test_returns_current_turn_unchanged(self, coordinator, processing_turn):
        """Returns current turn without modification."""
        decision = SupersedeDecision(action=SupersedeAction.FORCE_COMPLETE, reason="near_completion")

        result_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=processing_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        assert result_turn is processing_turn

    def test_does_not_absorb_ignored_message(self, coordinator, processing_turn):
        """Does not absorb the ignored message."""
        new_message_id = uuid4()
        decision = SupersedeDecision(action=SupersedeAction.FORCE_COMPLETE, reason="near_completion")

        coordinator.enforce_decision(
            decision=decision,
            current_turn=processing_turn,
            new_message_id=new_message_id,
            new_message_timestamp=datetime.now(UTC),
        )

        assert new_message_id not in processing_turn.messages


# =============================================================================
# Tests: Invalid Actions
# =============================================================================


class TestInvalidActions:
    """Tests for handling invalid actions."""

    def test_raises_for_unknown_action(self, coordinator, accumulating_turn):
        """Raises ValueError for unknown action."""
        # Create decision with valid action value
        decision = SupersedeDecision(action=SupersedeAction.ABSORB, reason="test")
        # Manually override to an invalid value using object.__setattr__
        object.__setattr__(decision, "action", "INVALID_ACTION")

        with pytest.raises(ValueError, match="Unknown supersede action"):
            coordinator.enforce_decision(
                decision=decision,
                current_turn=accumulating_turn,
                new_message_id=uuid4(),
                new_message_timestamp=datetime.now(UTC),
            )


# =============================================================================
# Tests: build_tool_idempotency_key()
# =============================================================================


class TestBuildToolIdempotencyKey:
    """Tests for tool idempotency key builder."""

    def test_builds_key_with_turn_group(self, accumulating_turn):
        """Builds key scoped to turn group."""
        key = build_tool_idempotency_key(
            tool_name="create_order",
            business_key="user123:cart456",
            turn=accumulating_turn,
        )

        expected = f"create_order:user123:cart456:turn_group:{accumulating_turn.turn_group_id}"
        assert key == expected

    def test_supersede_chain_shares_key(self, coordinator, accumulating_turn):
        """Superseded turns share idempotency key via turn_group_id."""
        # Create original key
        original_key = build_tool_idempotency_key(
            tool_name="send_email",
            business_key="order:123",
            turn=accumulating_turn,
        )

        # Supersede the turn
        decision = SupersedeDecision(action=SupersedeAction.SUPERSEDE, reason="correction")
        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=accumulating_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        # Build key for new turn
        new_key = build_tool_idempotency_key(
            tool_name="send_email",
            business_key="order:123",
            turn=new_turn,
        )

        # Should share the same key (same turn_group_id)
        assert original_key == new_key

    def test_different_business_keys_produce_different_keys(self, accumulating_turn):
        """Different business keys produce different idempotency keys."""
        key1 = build_tool_idempotency_key(
            tool_name="process_refund",
            business_key="order:123",
            turn=accumulating_turn,
        )

        key2 = build_tool_idempotency_key(
            tool_name="process_refund",
            business_key="order:456",
            turn=accumulating_turn,
        )

        assert key1 != key2

    def test_different_tools_produce_different_keys(self, accumulating_turn):
        """Different tool names produce different idempotency keys."""
        key1 = build_tool_idempotency_key(
            tool_name="send_email",
            business_key="notification:123",
            turn=accumulating_turn,
        )

        key2 = build_tool_idempotency_key(
            tool_name="send_sms",
            business_key="notification:123",
            turn=accumulating_turn,
        )

        assert key1 != key2


# =============================================================================
# Tests: Integration Scenarios
# =============================================================================


class TestSupersedeIntegration:
    """Integration tests for common supersede scenarios."""

    def test_correction_scenario(self, coordinator):
        """User corrects themselves - supersede original turn."""
        # User sends "I want to order a pizza"
        original_turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.ACCUMULATING,
        )

        # User quickly corrects: "I meant a burger"
        decision = SupersedeDecision(
            action=SupersedeAction.SUPERSEDE,
            reason="correction",
        )

        new_turn = coordinator.enforce_decision(
            decision=decision,
            current_turn=original_turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        # Original is superseded, new turn created
        assert original_turn.status == LogicalTurnStatus.SUPERSEDED
        assert new_turn.superseded_from == original_turn.id
        assert new_turn.turn_group_id == original_turn.turn_group_id

    def test_clarification_scenario(self, coordinator):
        """User adds clarification - absorb into turn."""
        # User sends "I want to order"
        turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.ACCUMULATING,
        )

        # User adds: "a large pizza with extra cheese"
        decision = SupersedeDecision(
            action=SupersedeAction.ABSORB,
            reason="clarification",
        )

        result = coordinator.enforce_decision(
            decision=decision,
            current_turn=turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        # Same turn with additional message
        assert result is turn
        assert len(turn.messages) == 2

    def test_commit_point_scenario(self, coordinator):
        """New message after irreversible action - queue it."""
        # Turn has executed irreversible action
        turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.PROCESSING,
        )
        turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IRREVERSIBLE,
                tool_name="process_payment",
            )
        )

        # Cannot supersede anymore
        assert coordinator.can_supersede(turn) is False

        # Should queue for next turn
        decision = SupersedeDecision(
            action=SupersedeAction.QUEUE,
            reason="commit_point_reached",
        )

        result = coordinator.enforce_decision(
            decision=decision,
            current_turn=turn,
            new_message_id=uuid4(),
            new_message_timestamp=datetime.now(UTC),
        )

        # Turn unchanged, caller handles queuing
        assert result is turn
