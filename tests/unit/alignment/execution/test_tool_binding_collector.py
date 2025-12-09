"""Unit tests for ToolBindingCollector."""

import pytest
from uuid import uuid4

from focal.alignment.execution.tool_binding_collector import ToolBindingCollector
from focal.alignment.filtering.models import MatchedRule
from focal.alignment.models.tool_binding import ToolBinding
from focal.alignment.planning.models import ScenarioContributionPlan, ScenarioContribution
from tests.factories.alignment import RuleFactory


@pytest.fixture
def collector() -> ToolBindingCollector:
    return ToolBindingCollector()


@pytest.fixture
def sample_contribution_plan() -> ScenarioContributionPlan:
    """Create a sample contribution plan."""
    from focal.alignment.planning.models import ContributionType

    scenario_id = uuid4()
    step_id = uuid4()
    return ScenarioContributionPlan(
        contributions=[
            ScenarioContribution(
                scenario_id=scenario_id,
                scenario_name="Test Scenario",
                current_step_id=step_id,
                current_step_name="Test Step",
                contribution_type=ContributionType.INFORM,
            )
        ]
    )


@pytest.mark.asyncio
async def test_collect_from_rules_only(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test collecting tool bindings from rules only."""
    binding1 = ToolBinding(tool_id="tool_1", when="BEFORE_STEP")
    binding2 = ToolBinding(tool_id="tool_2", when="DURING_STEP")

    rule1 = RuleFactory.create(tool_bindings=[binding1])
    rule2 = RuleFactory.create(tool_bindings=[binding2])

    matched_rules = [
        MatchedRule(rule=rule1, match_score=1.0, relevance_score=1.0, reasoning="test"),
        MatchedRule(rule=rule2, match_score=1.0, relevance_score=1.0, reasoning="test"),
    ]

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=None,
    )

    assert len(bindings) == 2
    assert binding1 in bindings
    assert binding2 in bindings


@pytest.mark.asyncio
async def test_collect_from_scenario_steps_only(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test collecting tool bindings from scenario steps only."""
    from focal.alignment.models.scenario import ScenarioStep

    binding1 = ToolBinding(tool_id="step_tool_1", when="DURING_STEP")

    scenario_id = sample_contribution_plan.contributions[0].scenario_id
    step_id = sample_contribution_plan.contributions[0].current_step_id

    step = ScenarioStep(
        id=step_id,
        scenario_id=scenario_id,
        name="Test Step",
        description="Test",
        tool_bindings=[binding1],
    )

    scenario_steps = {(scenario_id, step_id): step}

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=[],
        scenario_steps=scenario_steps,
    )

    assert len(bindings) == 1
    assert binding1 in bindings


@pytest.mark.asyncio
async def test_collect_from_both_rules_and_steps(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test collecting from both rules and scenario steps."""
    from focal.alignment.models.scenario import ScenarioStep

    rule_binding = ToolBinding(tool_id="rule_tool", when="BEFORE_STEP")
    step_binding = ToolBinding(tool_id="step_tool", when="DURING_STEP")

    rule = RuleFactory.create(tool_bindings=[rule_binding])
    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    scenario_id = sample_contribution_plan.contributions[0].scenario_id
    step_id = sample_contribution_plan.contributions[0].current_step_id

    step = ScenarioStep(
        id=step_id,
        scenario_id=scenario_id,
        name="Test Step",
        description="Test",
        tool_bindings=[step_binding],
    )

    scenario_steps = {(scenario_id, step_id): step}

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=scenario_steps,
    )

    assert len(bindings) == 2
    assert rule_binding in bindings
    assert step_binding in bindings


@pytest.mark.asyncio
async def test_deduplication_of_duplicate_bindings(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test that duplicate bindings (same tool_id and when) are deduplicated."""
    binding1 = ToolBinding(tool_id="duplicate_tool", when="DURING_STEP")
    binding2 = ToolBinding(tool_id="duplicate_tool", when="DURING_STEP")  # Same tool_id and when

    rule1 = RuleFactory.create(tool_bindings=[binding1])
    rule2 = RuleFactory.create(tool_bindings=[binding2])

    matched_rules = [
        MatchedRule(rule=rule1, match_score=1.0, relevance_score=1.0, reasoning="test"),
        MatchedRule(rule=rule2, match_score=1.0, relevance_score=1.0, reasoning="test"),
    ]

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=None,
    )

    # Should only have one binding despite two rules having the same tool
    assert len(bindings) == 1
    assert bindings[0].tool_id == "duplicate_tool"


@pytest.mark.asyncio
async def test_empty_collection_no_tools(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test collection when no tools are present."""
    rule = RuleFactory.create(tool_bindings=[])
    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=None,
    )

    assert len(bindings) == 0


@pytest.mark.asyncio
async def test_multiple_before_during_after_bindings(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test collecting multiple bindings with different timing phases."""
    binding_before = ToolBinding(tool_id="before_tool", when="BEFORE_STEP")
    binding_during = ToolBinding(tool_id="during_tool", when="DURING_STEP")
    binding_after = ToolBinding(tool_id="after_tool", when="AFTER_STEP")

    rule = RuleFactory.create(tool_bindings=[binding_before, binding_during, binding_after])
    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=None,
    )

    assert len(bindings) == 3

    # Verify all phases are present
    phases = {b.when for b in bindings}
    assert "BEFORE_STEP" in phases
    assert "DURING_STEP" in phases
    assert "AFTER_STEP" in phases


@pytest.mark.asyncio
async def test_legacy_attached_tool_ids_fallback(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test fallback to legacy attached_tool_ids field."""
    rule = RuleFactory.create(
        tool_bindings=[],  # No new bindings
        attached_tool_ids=["legacy_tool_1", "legacy_tool_2"]
    )
    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=matched_rules,
        scenario_steps=None,
    )

    assert len(bindings) == 2
    assert all(b.when == "DURING_STEP" for b in bindings)
    tool_ids = {b.tool_id for b in bindings}
    assert "legacy_tool_1" in tool_ids
    assert "legacy_tool_2" in tool_ids


@pytest.mark.asyncio
async def test_legacy_tool_ids_on_scenario_step(collector: ToolBindingCollector, sample_contribution_plan: ScenarioContributionPlan) -> None:
    """Test fallback to legacy tool_ids field on scenario step."""
    from focal.alignment.models.scenario import ScenarioStep

    scenario_id = sample_contribution_plan.contributions[0].scenario_id
    step_id = sample_contribution_plan.contributions[0].current_step_id

    step = ScenarioStep(
        id=step_id,
        scenario_id=scenario_id,
        name="Test Step",
        description="Test",
        tool_bindings=[],  # No new bindings
        tool_ids=["legacy_step_tool_1", "legacy_step_tool_2"],
    )

    scenario_steps = {(scenario_id, step_id): step}

    bindings = await collector.collect_bindings(
        contribution_plan=sample_contribution_plan,
        applied_rules=[],
        scenario_steps=scenario_steps,
    )

    assert len(bindings) == 2
    assert all(b.when == "DURING_STEP" for b in bindings)
    tool_ids = {b.tool_id for b in bindings}
    assert "legacy_step_tool_1" in tool_ids
    assert "legacy_step_tool_2" in tool_ids
