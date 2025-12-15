"""Unit tests for scenario contribution models."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.planning.models import (
    ContributionType,
    ScenarioContribution,
    ScenarioContributionPlan,
)


class TestContributionType:
    """Test ContributionType enum."""

    def test_all_types_defined(self):
        """Test that all contribution types are available."""
        assert ContributionType.ASK == "ask"
        assert ContributionType.INFORM == "inform"
        assert ContributionType.CONFIRM == "confirm"
        assert ContributionType.ACTION_HINT == "action_hint"
        assert ContributionType.NONE == "none"


class TestScenarioContribution:
    """Test ScenarioContribution model."""

    def test_create_with_required_fields(self):
        """Test creating contribution with required fields."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
            current_step_id=uuid4(),
            current_step_name="Test Step",
            contribution_type=ContributionType.ASK,
        )
        assert contribution.contribution_type == ContributionType.ASK
        assert contribution.priority == 0
        assert contribution.fields_to_ask == []

    def test_ask_contribution_with_fields(self):
        """Test ASK contribution with fields."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Refund Flow",
            current_step_id=uuid4(),
            current_step_name="Collect Order ID",
            contribution_type=ContributionType.ASK,
            fields_to_ask=["order_id", "reason"],
        )
        assert contribution.contribution_type == ContributionType.ASK
        assert len(contribution.fields_to_ask) == 2
        assert "order_id" in contribution.fields_to_ask

    def test_inform_contribution_with_template(self):
        """Test INFORM contribution with template."""
        template_id = uuid4()
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Support Flow",
            current_step_id=uuid4(),
            current_step_name="Provide Info",
            contribution_type=ContributionType.INFORM,
            inform_template_id=template_id,
        )
        assert contribution.contribution_type == ContributionType.INFORM
        assert contribution.inform_template_id == template_id

    def test_confirm_contribution_with_action(self):
        """Test CONFIRM contribution with action description."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Refund Flow",
            current_step_id=uuid4(),
            current_step_name="Confirm Refund",
            contribution_type=ContributionType.CONFIRM,
            action_to_confirm="Process $50 refund to card ending in 1234",
        )
        assert contribution.contribution_type == ContributionType.CONFIRM
        assert "refund" in contribution.action_to_confirm.lower()

    def test_action_hint_contribution_with_tools(self):
        """Test ACTION_HINT contribution with tool suggestions."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Order Lookup",
            current_step_id=uuid4(),
            current_step_name="Fetch Order",
            contribution_type=ContributionType.ACTION_HINT,
            suggested_tools=["order_lookup", "customer_history"],
        )
        assert contribution.contribution_type == ContributionType.ACTION_HINT
        assert len(contribution.suggested_tools) == 2

    def test_priority_ordering(self):
        """Test contributions can be prioritized."""
        high_priority = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Critical",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.ASK,
            priority=10,
        )
        low_priority = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Normal",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.INFORM,
            priority=1,
        )
        assert high_priority.priority > low_priority.priority


class TestScenarioContributionPlan:
    """Test ScenarioContributionPlan model."""

    def test_create_empty_plan(self):
        """Test creating empty contribution plan."""
        plan = ScenarioContributionPlan(contributions=[])
        assert len(plan.contributions) == 0
        assert plan.primary_scenario_id is None
        assert not plan.has_asks
        assert not plan.has_confirms
        assert not plan.has_action_hints

    def test_plan_with_single_contribution(self):
        """Test plan with one contribution."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.ASK,
        )
        plan = ScenarioContributionPlan(contributions=[contribution])
        assert len(plan.contributions) == 1

    def test_plan_flags_asks(self):
        """Test has_asks flag is set correctly."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.ASK,
            fields_to_ask=["field1"],
        )
        plan = ScenarioContributionPlan(
            contributions=[contribution], has_asks=True
        )
        assert plan.has_asks

    def test_plan_flags_confirms(self):
        """Test has_confirms flag is set correctly."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.CONFIRM,
        )
        plan = ScenarioContributionPlan(
            contributions=[contribution], has_confirms=True
        )
        assert plan.has_confirms

    def test_plan_flags_action_hints(self):
        """Test has_action_hints flag is set correctly."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.ACTION_HINT,
            suggested_tools=["tool1"],
        )
        plan = ScenarioContributionPlan(
            contributions=[contribution], has_action_hints=True
        )
        assert plan.has_action_hints

    def test_active_scenario_ids_property(self):
        """Test active_scenario_ids property."""
        scenario_id1 = uuid4()
        scenario_id2 = uuid4()
        contributions = [
            ScenarioContribution(
                scenario_id=scenario_id1,
                scenario_name="Scenario 1",
                current_step_id=uuid4(),
                current_step_name="Step",
                contribution_type=ContributionType.ASK,
            ),
            ScenarioContribution(
                scenario_id=scenario_id2,
                scenario_name="Scenario 2",
                current_step_id=uuid4(),
                current_step_name="Step",
                contribution_type=ContributionType.INFORM,
            ),
        ]
        plan = ScenarioContributionPlan(contributions=contributions)
        scenario_ids = plan.active_scenario_ids
        assert len(scenario_ids) == 2
        assert scenario_id1 in scenario_ids
        assert scenario_id2 in scenario_ids

    def test_primary_scenario_assignment(self):
        """Test primary scenario can be assigned."""
        scenario_id = uuid4()
        contribution = ScenarioContribution(
            scenario_id=scenario_id,
            scenario_name="Primary",
            current_step_id=uuid4(),
            current_step_name="Step",
            contribution_type=ContributionType.ASK,
            priority=10,
        )
        plan = ScenarioContributionPlan(
            contributions=[contribution], primary_scenario_id=scenario_id
        )
        assert plan.primary_scenario_id == scenario_id

    def test_multi_scenario_plan(self):
        """Test plan with multiple scenarios."""
        contributions = [
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Scenario 1",
                current_step_id=uuid4(),
                current_step_name="Step 1",
                contribution_type=ContributionType.ASK,
                priority=5,
            ),
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Scenario 2",
                current_step_id=uuid4(),
                current_step_name="Step 2",
                contribution_type=ContributionType.INFORM,
                priority=3,
            ),
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Scenario 3",
                current_step_id=uuid4(),
                current_step_name="Step 3",
                contribution_type=ContributionType.CONFIRM,
                priority=7,
            ),
        ]
        plan = ScenarioContributionPlan(contributions=contributions)
        assert len(plan.contributions) == 3
        assert len(plan.active_scenario_ids) == 3
