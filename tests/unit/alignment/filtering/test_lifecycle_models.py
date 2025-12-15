"""Unit tests for scenario lifecycle models."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.filtering.models import (
    ScenarioLifecycleAction,
    ScenarioLifecycleDecision,
    ScenarioStepTransitionDecision,
)


class TestScenarioLifecycleAction:
    """Test ScenarioLifecycleAction enum."""

    def test_all_actions_defined(self):
        """Test that all lifecycle actions are available."""
        assert ScenarioLifecycleAction.START == "start"
        assert ScenarioLifecycleAction.CONTINUE == "continue"
        assert ScenarioLifecycleAction.PAUSE == "pause"
        assert ScenarioLifecycleAction.COMPLETE == "complete"
        assert ScenarioLifecycleAction.CANCEL == "cancel"


class TestScenarioLifecycleDecision:
    """Test ScenarioLifecycleDecision model."""

    def test_create_start_decision(self):
        """Test creating START decision."""
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.START,
            reasoning="User requested refund",
            entry_step_id=uuid4(),
        )
        assert decision.action == ScenarioLifecycleAction.START
        assert decision.entry_step_id is not None
        assert decision.source_step_id is None

    def test_create_continue_decision(self):
        """Test creating CONTINUE decision."""
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.CONTINUE,
            reasoning="Continue active scenario",
        )
        assert decision.action == ScenarioLifecycleAction.CONTINUE
        assert decision.confidence == 1.0

    def test_create_pause_decision(self):
        """Test creating PAUSE decision."""
        source_step = uuid4()
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.PAUSE,
            reasoning="User requested pause",
            source_step_id=source_step,
        )
        assert decision.action == ScenarioLifecycleAction.PAUSE
        assert decision.source_step_id == source_step

    def test_create_complete_decision(self):
        """Test creating COMPLETE decision."""
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.COMPLETE,
            reasoning="Reached terminal step",
            source_step_id=uuid4(),
        )
        assert decision.action == ScenarioLifecycleAction.COMPLETE

    def test_create_cancel_decision(self):
        """Test creating CANCEL decision."""
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.CANCEL,
            reasoning="User cancelled",
            source_step_id=uuid4(),
        )
        assert decision.action == ScenarioLifecycleAction.CANCEL

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid confidence
        decision = ScenarioLifecycleDecision(
            scenario_id=uuid4(),
            action=ScenarioLifecycleAction.START,
            reasoning="Test",
            confidence=0.8,
            entry_step_id=uuid4(),
        )
        assert decision.confidence == 0.8

        # Invalid confidence > 1
        with pytest.raises(Exception):
            ScenarioLifecycleDecision(
                scenario_id=uuid4(),
                action=ScenarioLifecycleAction.START,
                reasoning="Test",
                confidence=1.5,
                entry_step_id=uuid4(),
            )

        # Invalid confidence < 0
        with pytest.raises(Exception):
            ScenarioLifecycleDecision(
                scenario_id=uuid4(),
                action=ScenarioLifecycleAction.START,
                reasoning="Test",
                confidence=-0.1,
                entry_step_id=uuid4(),
            )


class TestScenarioStepTransitionDecision:
    """Test ScenarioStepTransitionDecision model."""

    def test_create_normal_transition(self):
        """Test creating normal transition without skipping."""
        source = uuid4()
        target = uuid4()
        decision = ScenarioStepTransitionDecision(
            scenario_id=uuid4(),
            source_step_id=source,
            target_step_id=target,
            reasoning="Condition met",
        )
        assert decision.source_step_id == source
        assert decision.target_step_id == target
        assert not decision.was_skipped
        assert len(decision.skipped_steps) == 0

    def test_create_transition_with_skipping(self):
        """Test creating transition with step skipping."""
        source = uuid4()
        target = uuid4()
        skipped1 = uuid4()
        skipped2 = uuid4()
        decision = ScenarioStepTransitionDecision(
            scenario_id=uuid4(),
            source_step_id=source,
            target_step_id=target,
            was_skipped=True,
            skipped_steps=[skipped1, skipped2],
            reasoning="Skipped 2 steps with available data",
        )
        assert decision.was_skipped
        assert len(decision.skipped_steps) == 2
        assert skipped1 in decision.skipped_steps
        assert skipped2 in decision.skipped_steps

    def test_same_step_transition(self):
        """Test transition staying at same step."""
        step_id = uuid4()
        decision = ScenarioStepTransitionDecision(
            scenario_id=uuid4(),
            source_step_id=step_id,
            target_step_id=step_id,
            reasoning="Stay at current step",
        )
        assert decision.source_step_id == decision.target_step_id

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid confidence
        decision = ScenarioStepTransitionDecision(
            scenario_id=uuid4(),
            source_step_id=uuid4(),
            target_step_id=uuid4(),
            reasoning="Test",
            confidence=0.95,
        )
        assert decision.confidence == 0.95

        # Invalid confidence
        with pytest.raises(Exception):
            ScenarioStepTransitionDecision(
                scenario_id=uuid4(),
                source_step_id=uuid4(),
                target_step_id=uuid4(),
                reasoning="Test",
                confidence=2.0,
            )

    def test_skipped_steps_default_empty(self):
        """Test skipped_steps defaults to empty list."""
        decision = ScenarioStepTransitionDecision(
            scenario_id=uuid4(),
            source_step_id=uuid4(),
            target_step_id=uuid4(),
            reasoning="Test",
        )
        assert decision.skipped_steps == []
        assert not decision.was_skipped
