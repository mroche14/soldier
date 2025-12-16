"""Tests for CommitPointTracker - irreversibility tracking.

Tests cover:
- Detecting commit points (irreversible side effects)
- Recording side effects on turns
- Tool policy classification
"""

import pytest
from datetime import UTC, datetime
from uuid import uuid4

from ruche.runtime.acf.commit_point import CommitPointTracker
from ruche.runtime.acf.models import (
    LogicalTurn,
    LogicalTurnStatus,
    SideEffect,
    SideEffectPolicy,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tracker():
    """Create CommitPointTracker instance."""
    return CommitPointTracker()


@pytest.fixture
def sample_turn():
    """Create sample LogicalTurn."""
    return LogicalTurn(
        id=uuid4(),
        session_key="tenant:agent:customer:channel",
        messages=[uuid4()],
        first_at=datetime.now(UTC),
        last_at=datetime.now(UTC),
        status=LogicalTurnStatus.PROCESSING,
    )


# =============================================================================
# Tests: CommitPointTracker.has_reached_commit_point()
# =============================================================================


class TestHasReachedCommitPoint:
    """Tests for commit point detection."""

    def test_returns_false_for_empty_side_effects(self, tracker, sample_turn):
        """Returns False when no side effects recorded."""
        assert sample_turn.side_effects == []

        result = tracker.has_reached_commit_point(sample_turn)

        assert result is False

    def test_returns_true_for_irreversible_effect(self, tracker, sample_turn):
        """Returns True when irreversible side effect exists."""
        sample_turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IRREVERSIBLE,
                tool_name="send_email",
            )
        )

        result = tracker.has_reached_commit_point(sample_turn)

        assert result is True

    def test_returns_false_for_reversible_effect(self, tracker, sample_turn):
        """Returns False when only reversible effects exist."""
        sample_turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.REVERSIBLE,
                tool_name="search_products",
            )
        )

        result = tracker.has_reached_commit_point(sample_turn)

        assert result is False

    def test_returns_false_for_idempotent_effect(self, tracker, sample_turn):
        """Returns False when only idempotent effects exist."""
        sample_turn.side_effects.append(
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IDEMPOTENT,
                tool_name="get_order",
                idempotency_key="order:123",
            )
        )

        result = tracker.has_reached_commit_point(sample_turn)

        assert result is False

    def test_returns_true_when_any_effect_is_irreversible(self, tracker, sample_turn):
        """Returns True if any effect is irreversible (mixed effects)."""
        sample_turn.side_effects.extend([
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.REVERSIBLE,
                tool_name="validate_address",
            ),
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IDEMPOTENT,
                tool_name="get_order",
            ),
            SideEffect(
                effect_type="tool_call",
                policy=SideEffectPolicy.IRREVERSIBLE,
                tool_name="process_refund",
            ),
        ])

        result = tracker.has_reached_commit_point(sample_turn)

        assert result is True


# =============================================================================
# Tests: CommitPointTracker.record_side_effect()
# =============================================================================


class TestRecordSideEffect:
    """Tests for recording side effects."""

    def test_records_basic_side_effect(self, tracker, sample_turn):
        """Records side effect with basic fields."""
        effect = tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.REVERSIBLE,
        )

        assert len(sample_turn.side_effects) == 1
        assert effect.effect_type == "tool_call"
        assert effect.policy == SideEffectPolicy.REVERSIBLE

    def test_records_side_effect_with_tool_name(self, tracker, sample_turn):
        """Records side effect with tool name."""
        effect = tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.IRREVERSIBLE,
            tool_name="send_sms",
        )

        assert effect.tool_name == "send_sms"

    def test_records_side_effect_with_idempotency_key(self, tracker, sample_turn):
        """Records side effect with idempotency key."""
        effect = tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.IDEMPOTENT,
            tool_name="create_order",
            idempotency_key="order:user123:cart456",
        )

        assert effect.idempotency_key == "order:user123:cart456"

    def test_records_side_effect_with_details(self, tracker, sample_turn):
        """Records side effect with additional details."""
        details = {
            "order_id": "ord-123",
            "amount": 99.99,
            "timestamp": "2025-01-15T10:00:00Z",
        }

        effect = tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.IRREVERSIBLE,
            tool_name="process_payment",
            details=details,
        )

        assert effect.details == details

    def test_appends_to_existing_side_effects(self, tracker, sample_turn):
        """Appends to list of existing side effects."""
        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.REVERSIBLE,
            tool_name="first_tool",
        )

        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="api_call",
            policy=SideEffectPolicy.IDEMPOTENT,
            tool_name="second_tool",
        )

        assert len(sample_turn.side_effects) == 2
        assert sample_turn.side_effects[0].tool_name == "first_tool"
        assert sample_turn.side_effects[1].tool_name == "second_tool"

    def test_returns_created_side_effect(self, tracker, sample_turn):
        """Returns the created SideEffect object."""
        effect = tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.REVERSIBLE,
        )

        assert isinstance(effect, SideEffect)
        assert effect is sample_turn.side_effects[-1]


# =============================================================================
# Tests: CommitPointTracker.classify_tool_policy()
# =============================================================================


class TestClassifyToolPolicy:
    """Tests for tool policy classification."""

    def test_classifies_send_email_as_irreversible(self, tracker):
        """Classifies send_email as irreversible."""
        policy = tracker.classify_tool_policy("send_email")
        assert policy == SideEffectPolicy.IRREVERSIBLE

    def test_classifies_send_sms_as_irreversible(self, tracker):
        """Classifies send_sms as irreversible."""
        policy = tracker.classify_tool_policy("send_sms")
        assert policy == SideEffectPolicy.IRREVERSIBLE

    def test_classifies_create_order_as_irreversible(self, tracker):
        """Classifies create_order as irreversible."""
        policy = tracker.classify_tool_policy("create_order")
        assert policy == SideEffectPolicy.IRREVERSIBLE

    def test_classifies_process_refund_as_irreversible(self, tracker):
        """Classifies process_refund as irreversible."""
        policy = tracker.classify_tool_policy("process_refund")
        assert policy == SideEffectPolicy.IRREVERSIBLE

    def test_classifies_cancel_order_as_irreversible(self, tracker):
        """Classifies cancel_order as irreversible."""
        policy = tracker.classify_tool_policy("cancel_order")
        assert policy == SideEffectPolicy.IRREVERSIBLE

    def test_classifies_get_order_as_idempotent(self, tracker):
        """Classifies get_order as idempotent."""
        policy = tracker.classify_tool_policy("get_order")
        assert policy == SideEffectPolicy.IDEMPOTENT

    def test_classifies_search_products_as_idempotent(self, tracker):
        """Classifies search_products as idempotent."""
        policy = tracker.classify_tool_policy("search_products")
        assert policy == SideEffectPolicy.IDEMPOTENT

    def test_classifies_validate_address_as_idempotent(self, tracker):
        """Classifies validate_address as idempotent."""
        policy = tracker.classify_tool_policy("validate_address")
        assert policy == SideEffectPolicy.IDEMPOTENT

    def test_classifies_unknown_tool_as_reversible(self, tracker):
        """Classifies unknown tools as reversible (conservative default)."""
        policy = tracker.classify_tool_policy("unknown_custom_tool")
        assert policy == SideEffectPolicy.REVERSIBLE

    def test_classifies_various_unknown_tools_as_reversible(self, tracker):
        """Unknown tools default to reversible."""
        unknown_tools = [
            "my_custom_tool",
            "some_api_call",
            "internal_function",
            "",
        ]

        for tool in unknown_tools:
            policy = tracker.classify_tool_policy(tool)
            assert policy == SideEffectPolicy.REVERSIBLE, f"Tool {tool!r} should be reversible"


# =============================================================================
# Tests: Integration - Recording and Checking
# =============================================================================


class TestCommitPointIntegration:
    """Integration tests for record + check flow."""

    def test_turn_not_at_commit_after_reversible_effects(self, tracker, sample_turn):
        """Turn not at commit point after only reversible effects."""
        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.REVERSIBLE,
            tool_name="search_products",
        )

        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="api_call",
            policy=SideEffectPolicy.IDEMPOTENT,
            tool_name="get_user_info",
        )

        assert tracker.has_reached_commit_point(sample_turn) is False

    def test_turn_at_commit_after_irreversible_effect(self, tracker, sample_turn):
        """Turn reaches commit point after irreversible effect."""
        # First, some reversible effects
        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.REVERSIBLE,
            tool_name="validate_input",
        )

        assert tracker.has_reached_commit_point(sample_turn) is False

        # Then, an irreversible effect
        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=SideEffectPolicy.IRREVERSIBLE,
            tool_name="send_email",
        )

        assert tracker.has_reached_commit_point(sample_turn) is True

    def test_auto_classify_and_record(self, tracker, sample_turn):
        """Uses classify to determine policy, then records."""
        tool_name = "process_refund"
        policy = tracker.classify_tool_policy(tool_name)

        tracker.record_side_effect(
            turn=sample_turn,
            effect_type="tool_call",
            policy=policy,
            tool_name=tool_name,
        )

        # Should be at commit point since refund is irreversible
        assert tracker.has_reached_commit_point(sample_turn) is True
