"""Unit tests for turn resolution determination."""

import pytest

from ruche.brains.focal.models.outcome import OutcomeCategory, TurnOutcome
from ruche.brains.focal.phases.generation.resolution import (
    build_turn_outcome,
    determine_resolution,
)


class TestDetermineResolution:
    """Tests for determine_resolution function."""

    def test_returns_blocked_when_policy_restriction(self):
        """Returns BLOCKED when policy restriction category present."""
        categories = [
            OutcomeCategory.POLICY_RESTRICTION,
            OutcomeCategory.ANSWERED,
        ]

        result = determine_resolution(categories)

        assert result == "BLOCKED"

    def test_returns_error_when_system_error(self):
        """Returns ERROR when system error category present."""
        categories = [OutcomeCategory.SYSTEM_ERROR]

        result = determine_resolution(categories)

        assert result == "ERROR"

    def test_returns_redirected_when_escalate_response_type(self):
        """Returns REDIRECTED when response type is ESCALATE."""
        categories = [OutcomeCategory.ANSWERED]

        result = determine_resolution(categories, response_type="ESCALATE")

        assert result == "REDIRECTED"

    def test_returns_partial_when_awaiting_user_input(self):
        """Returns PARTIAL when awaiting user input."""
        categories = [OutcomeCategory.AWAITING_USER_INPUT]

        result = determine_resolution(categories)

        assert result == "PARTIAL"

    def test_returns_answered_when_answered_category(self):
        """Returns ANSWERED when answered category present."""
        categories = [OutcomeCategory.ANSWERED]

        result = determine_resolution(categories)

        assert result == "ANSWERED"

    def test_returns_answered_as_default(self):
        """Returns ANSWERED as default when no specific categories."""
        categories = []

        result = determine_resolution(categories)

        assert result == "ANSWERED"

    def test_priority_order_blocked_over_error(self):
        """Policy restriction takes priority over system error."""
        categories = [
            OutcomeCategory.SYSTEM_ERROR,
            OutcomeCategory.POLICY_RESTRICTION,
        ]

        result = determine_resolution(categories)

        assert result == "BLOCKED"

    def test_priority_order_error_over_escalate(self):
        """System error takes priority over escalate."""
        categories = [OutcomeCategory.SYSTEM_ERROR]

        result = determine_resolution(categories, response_type="ESCALATE")

        assert result == "ERROR"


class TestBuildTurnOutcome:
    """Tests for build_turn_outcome function."""

    def test_builds_outcome_with_all_fields(self):
        """Builds complete TurnOutcome with all fields."""
        categories = [OutcomeCategory.ANSWERED]

        outcome = build_turn_outcome(
            categories=categories,
            response_type="ANSWER",
            escalation_reason=None,
            blocking_rule_id=None,
        )

        assert isinstance(outcome, TurnOutcome)
        assert outcome.resolution == "ANSWERED"
        assert outcome.categories == categories
        assert outcome.escalation_reason is None
        assert outcome.blocking_rule_id is None

    def test_builds_outcome_for_escalation(self):
        """Builds outcome for escalation case."""
        categories = [OutcomeCategory.ANSWERED]

        outcome = build_turn_outcome(
            categories=categories,
            response_type="ESCALATE",
            escalation_reason="User requested supervisor",
            blocking_rule_id=None,
        )

        assert outcome.resolution == "REDIRECTED"
        assert outcome.escalation_reason == "User requested supervisor"

    def test_builds_outcome_for_blocked(self):
        """Builds outcome for blocked case."""
        categories = [OutcomeCategory.POLICY_RESTRICTION]

        outcome = build_turn_outcome(
            categories=categories,
            response_type=None,
            escalation_reason=None,
            blocking_rule_id="rule-123",
        )

        assert outcome.resolution == "BLOCKED"
        assert outcome.blocking_rule_id == "rule-123"

    def test_builds_outcome_for_partial(self):
        """Builds outcome for partial completion."""
        categories = [OutcomeCategory.AWAITING_USER_INPUT]

        outcome = build_turn_outcome(
            categories=categories,
            response_type=None,
        )

        assert outcome.resolution == "PARTIAL"
        assert outcome.escalation_reason is None
