"""Unit tests for ResponsePlanner."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.models import Rule, Scope
from ruche.brains.focal.phases.planning.models import (
    ContributionType,
    ResponsePlan,
    ResponseType,
    ScenarioContribution,
    ScenarioContributionPlan,
)
from ruche.brains.focal.phases.planning.planner import ResponsePlanner


class TestResponsePlanner:
    """Test suite for ResponsePlanner."""

    @pytest.fixture
    def planner(self):
        """Create ResponsePlanner instance."""
        return ResponsePlanner()

    @pytest.fixture
    def tenant_id(self):
        """Generate tenant ID."""
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        """Generate agent ID."""
        return uuid4()

    @pytest.fixture
    def snapshot(self):
        """Create a basic snapshot."""
        return SituationSnapshot(
            message="test message",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        )

    @pytest.fixture
    def empty_contribution_plan(self):
        """Create empty contribution plan."""
        return ScenarioContributionPlan(contributions=[])

    @pytest.fixture
    def ask_contribution_plan(self):
        """Create contribution plan with ASK."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
            current_step_id=uuid4(),
            current_step_name="collect_email",
            contribution_type=ContributionType.ASK,
            fields_to_ask=["email", "phone"],
            priority=10,
        )
        return ScenarioContributionPlan(
            contributions=[contribution],
            has_asks=True,
        )

    @pytest.fixture
    def confirm_contribution_plan(self):
        """Create contribution plan with CONFIRM."""
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
            current_step_id=uuid4(),
            current_step_name="confirm_order",
            contribution_type=ContributionType.CONFIRM,
            action_to_confirm="Process order #123",
            priority=5,
        )
        return ScenarioContributionPlan(
            contributions=[contribution],
            has_confirms=True,
        )

    @pytest.fixture
    def escalation_rule(self, tenant_id, agent_id):
        """Create escalation rule."""
        return MatchedRule(
            rule=Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Escalation Rule",
                condition_text="User is angry",
                action_text="Escalate to human agent immediately",
                scope=Scope.GLOBAL,
                is_hard_constraint=True,
            ),
            match_score=0.9,
            relevance_score=0.85,
            reasoning="User is angry, escalate",
        )

    @pytest.fixture
    def handoff_rule(self, tenant_id, agent_id):
        """Create handoff rule."""
        return MatchedRule(
            rule=Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Handoff Rule",
                condition_text="Transfer request",
                action_text="Handoff to sales team",
                scope=Scope.GLOBAL,
            ),
            match_score=0.85,
            relevance_score=0.8,
            reasoning="Transfer requested",
        )

    @pytest.fixture
    def must_include_rule(self, tenant_id, agent_id):
        """Create rule with must_include constraint."""
        return MatchedRule(
            rule=Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Disclosure Rule",
                condition_text="Legal disclaimer needed",
                action_text="Must mention our privacy policy and include link",
                scope=Scope.GLOBAL,
                is_hard_constraint=True,
            ),
            match_score=0.9,
            relevance_score=0.85,
            reasoning="Disclosure required",
        )

    @pytest.fixture
    def must_avoid_rule(self, tenant_id, agent_id):
        """Create rule with must_avoid constraint."""
        return MatchedRule(
            rule=Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Competitor Rule",
                condition_text="Discussing competitors",
                action_text="Never mention competitor names or discuss their products",
                scope=Scope.GLOBAL,
                is_hard_constraint=True,
            ),
            match_score=0.88,
            relevance_score=0.82,
            reasoning="Competitor discussion",
        )

    # P8.1: Response Type Determination Tests

    @pytest.mark.asyncio
    async def test_determine_response_type_escalate_priority(
        self, planner, escalation_rule, ask_contribution_plan, snapshot
    ):
        """Test that ESCALATE takes priority over ASK."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[escalation_rule],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.ESCALATE

    @pytest.mark.asyncio
    async def test_determine_response_type_handoff_priority(
        self, planner, handoff_rule, ask_contribution_plan, snapshot
    ):
        """Test that HANDOFF takes priority over ASK."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[handoff_rule],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.HANDOFF

    @pytest.mark.asyncio
    async def test_determine_response_type_ask(
        self, planner, ask_contribution_plan, snapshot
    ):
        """Test ASK type when scenario has_asks."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.ASK

    @pytest.mark.asyncio
    async def test_determine_response_type_confirm(
        self, planner, confirm_contribution_plan, snapshot
    ):
        """Test CONFIRM type when scenario has_confirms."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=confirm_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.CONFIRM

    @pytest.mark.asyncio
    async def test_determine_response_type_default_answer(
        self, planner, empty_contribution_plan, snapshot
    ):
        """Test default ANSWER type."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.ANSWER

    @pytest.mark.asyncio
    async def test_determine_response_type_mixed(self, planner, snapshot):
        """Test MIXED type when both asking and informing."""
        # Create plan with both ASK and INFORM
        contributions = [
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Scenario 1",
                current_step_id=uuid4(),
                current_step_name="ask_step",
                contribution_type=ContributionType.ASK,
                fields_to_ask=["email"],
                priority=10,
            ),
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Scenario 2",
                current_step_id=uuid4(),
                current_step_name="inform_step",
                contribution_type=ContributionType.INFORM,
                priority=5,
            ),
        ]
        contribution_plan = ScenarioContributionPlan(
            contributions=contributions,
            has_asks=True,
        )

        plan = await planner.build_response_plan(
            scenario_contribution_plan=contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.MIXED

    # P8.2: Template Collection Tests

    @pytest.mark.asyncio
    async def test_collect_templates_with_templates(self, planner, snapshot):
        """Test template collection when scenarios have templates."""
        template_id = uuid4()
        contribution = ScenarioContribution(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
            current_step_id=uuid4(),
            current_step_name="inform_step",
            contribution_type=ContributionType.INFORM,
            inform_template_id=template_id,
        )
        contribution_plan = ScenarioContributionPlan(contributions=[contribution])

        plan = await planner.build_response_plan(
            scenario_contribution_plan=contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert str(template_id) in plan.template_ids

    @pytest.mark.asyncio
    async def test_collect_templates_without_templates(
        self, planner, ask_contribution_plan, snapshot
    ):
        """Test template collection when no templates."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.template_ids) == 0

    # P8.3-P8.4: Synthesis Tests

    @pytest.mark.asyncio
    async def test_synthesize_plan_bullet_points(
        self, planner, ask_contribution_plan, snapshot
    ):
        """Test bullet point generation from contributions."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.bullet_points) > 0
        assert "Ask for:" in plan.bullet_points[0]
        assert "email" in plan.bullet_points[0]

    @pytest.mark.asyncio
    async def test_synthesize_plan_priority_sorting(self, planner, snapshot):
        """Test contributions sorted by priority."""
        contributions = [
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="Low Priority",
                current_step_id=uuid4(),
                current_step_name="step1",
                contribution_type=ContributionType.ASK,
                fields_to_ask=["field1"],
                priority=5,
            ),
            ScenarioContribution(
                scenario_id=uuid4(),
                scenario_name="High Priority",
                current_step_id=uuid4(),
                current_step_name="step2",
                contribution_type=ContributionType.ASK,
                fields_to_ask=["field2"],
                priority=20,
            ),
        ]
        contribution_plan = ScenarioContributionPlan(
            contributions=contributions,
            has_asks=True,
        )

        plan = await planner.build_response_plan(
            scenario_contribution_plan=contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )

        # Higher priority should come first
        assert "field2" in plan.bullet_points[0]
        assert "field1" in plan.bullet_points[1]

    @pytest.mark.asyncio
    async def test_synthesize_plan_scenario_dict(
        self, planner, ask_contribution_plan, snapshot
    ):
        """Test scenario_contributions dict is built."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.scenario_contributions) > 0
        scenario_id = str(ask_contribution_plan.contributions[0].scenario_id)
        assert scenario_id in plan.scenario_contributions
        assert "step_name" in plan.scenario_contributions[scenario_id]
        assert "type" in plan.scenario_contributions[scenario_id]

    # P8.5: Constraint Injection Tests

    @pytest.mark.asyncio
    async def test_inject_must_include(
        self, planner, empty_contribution_plan, must_include_rule, snapshot
    ):
        """Test must_include extraction from rules."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[must_include_rule],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.must_include) > 0
        assert any("privacy policy" in item.lower() for item in plan.must_include)

    @pytest.mark.asyncio
    async def test_inject_must_avoid(
        self, planner, empty_contribution_plan, must_avoid_rule, snapshot
    ):
        """Test must_avoid extraction from rules."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[must_avoid_rule],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.must_avoid) > 0
        assert any("competitor" in item.lower() for item in plan.must_avoid)

    @pytest.mark.asyncio
    async def test_inject_constraints_from_hard_rules(
        self, planner, empty_contribution_plan, must_include_rule, snapshot
    ):
        """Test RuleConstraint objects created for hard constraints."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[must_include_rule],
            tool_results={},
            snapshot=snapshot,
        )
        assert len(plan.constraints_from_rules) > 0
        constraint = plan.constraints_from_rules[0]
        assert constraint.rule_id == str(must_include_rule.rule.id)
        assert constraint.constraint_type in ["must_include", "must_avoid"]
        assert constraint.priority == must_include_rule.rule.priority

    @pytest.mark.asyncio
    async def test_no_constraints_from_soft_rules(
        self, planner, empty_contribution_plan, tenant_id, agent_id, snapshot
    ):
        """Test that soft rules don't create constraint objects."""
        soft_rule = MatchedRule(
            rule=Rule(
                tenant_id=tenant_id,
                agent_id=agent_id,
                name="Soft Rule",
                condition_text="Some condition",
                action_text="Include helpful information",
                scope=Scope.GLOBAL,
                is_hard_constraint=False,  # Soft rule
            ),
            match_score=0.8,
            relevance_score=0.75,
            reasoning="Soft rule match",
        )

        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[soft_rule],
            tool_results={},
            snapshot=snapshot,
        )
        # Soft rules may extract must_include/must_avoid but don't create constraint objects
        assert len(plan.constraints_from_rules) == 0

    # Edge Case Tests

    @pytest.mark.asyncio
    async def test_empty_everything(self, planner, empty_contribution_plan, snapshot):
        """Test with no contributions and no rules."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=empty_contribution_plan,
            matched_rules=[],
            tool_results={},
            snapshot=snapshot,
        )
        assert plan.global_response_type == ResponseType.ANSWER
        assert len(plan.template_ids) == 0
        assert len(plan.bullet_points) == 0
        assert len(plan.must_include) == 0
        assert len(plan.must_avoid) == 0
        assert len(plan.constraints_from_rules) == 0

    @pytest.mark.asyncio
    async def test_multiple_rules_multiple_contributions(
        self,
        planner,
        ask_contribution_plan,
        must_include_rule,
        must_avoid_rule,
        snapshot,
    ):
        """Test complex scenario with multiple rules and contributions."""
        plan = await planner.build_response_plan(
            scenario_contribution_plan=ask_contribution_plan,
            matched_rules=[must_include_rule, must_avoid_rule],
            tool_results={},
            snapshot=snapshot,
        )

        # Should be ASK (no escalation/handoff rules)
        assert plan.global_response_type == ResponseType.ASK

        # Should have bullet points from contributions
        assert len(plan.bullet_points) > 0

        # Should have constraints from both rules
        assert len(plan.must_include) > 0
        assert len(plan.must_avoid) > 0

        # Should have constraint objects for both hard rules
        assert len(plan.constraints_from_rules) > 0
