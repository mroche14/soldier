"""Tests for scope pre-filter (P5.1)."""

import pytest
from uuid import uuid4

from ruche.brains.focal.models import Rule
from ruche.brains.focal.models.enums import Scope
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.filtering.scope_filter import ScopePreFilter
from ruche.conversation.models import Session


@pytest.fixture
def pre_filter():
    """Create a scope pre-filter instance."""
    return ScopePreFilter()


@pytest.fixture
def tenant_id():
    """Generate a tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Generate an agent ID."""
    return uuid4()


@pytest.fixture
def scenario_id():
    """Generate a scenario ID."""
    return uuid4()


@pytest.fixture
def step_id():
    """Generate a step ID."""
    return uuid4()


@pytest.fixture
def session(tenant_id, agent_id):
    """Create a basic session."""
    return Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel="api",
        user_channel_id="test_user",
        config_version=1,
        turn_count=0,
    )


def create_rule(
    tenant_id,
    agent_id,
    name="Test Rule",
    scope=Scope.GLOBAL,
    scope_id=None,
    enabled=True,
    cooldown_turns=0,
    max_fires_per_session=0,
):
    """Helper to create a rule."""
    return Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        condition_text="Test condition",
        action_text="Test action",
        scope=scope,
        scope_id=scope_id,
        enabled=enabled,
        cooldown_turns=cooldown_turns,
        max_fires_per_session=max_fires_per_session,
    )


@pytest.mark.asyncio
async def test_filter_disabled_rules(pre_filter, session, tenant_id, agent_id):
    """Disabled rules should be filtered out."""
    enabled_rule = create_rule(tenant_id, agent_id, name="Enabled", enabled=True)
    disabled_rule = create_rule(tenant_id, agent_id, name="Disabled", enabled=False)

    candidates = [
        MatchedRule(rule=enabled_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=disabled_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=0,
    )

    assert len(result) == 1
    assert result[0].rule.name == "Enabled"


@pytest.mark.asyncio
async def test_filter_scenario_scoped_rules(
    pre_filter, session, tenant_id, agent_id, scenario_id
):
    """Scenario-scoped rules should only apply when scenario is active."""
    active_scenario_id = scenario_id
    other_scenario_id = uuid4()

    global_rule = create_rule(tenant_id, agent_id, name="Global", scope=Scope.GLOBAL)
    active_scenario_rule = create_rule(
        tenant_id, agent_id, name="Active Scenario", scope=Scope.SCENARIO, scope_id=active_scenario_id
    )
    inactive_scenario_rule = create_rule(
        tenant_id, agent_id, name="Inactive Scenario", scope=Scope.SCENARIO, scope_id=other_scenario_id
    )

    candidates = [
        MatchedRule(rule=global_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=active_scenario_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=inactive_scenario_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids={active_scenario_id},
        active_step_ids=set(),
        current_turn_number=0,
    )

    assert len(result) == 2
    rule_names = {r.rule.name for r in result}
    assert rule_names == {"Global", "Active Scenario"}


@pytest.mark.asyncio
async def test_filter_step_scoped_rules(
    pre_filter, session, tenant_id, agent_id, step_id
):
    """Step-scoped rules should only apply when step is active."""
    active_step_id = step_id
    other_step_id = uuid4()

    global_rule = create_rule(tenant_id, agent_id, name="Global", scope=Scope.GLOBAL)
    active_step_rule = create_rule(
        tenant_id, agent_id, name="Active Step", scope=Scope.STEP, scope_id=active_step_id
    )
    inactive_step_rule = create_rule(
        tenant_id, agent_id, name="Inactive Step", scope=Scope.STEP, scope_id=other_step_id
    )

    candidates = [
        MatchedRule(rule=global_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=active_step_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=inactive_step_rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids={active_step_id},
        current_turn_number=0,
    )

    assert len(result) == 2
    rule_names = {r.rule.name for r in result}
    assert rule_names == {"Global", "Active Step"}


@pytest.mark.asyncio
async def test_filter_cooldown_rules(pre_filter, session, tenant_id, agent_id):
    """Rules with cooldown should be filtered if fired recently."""
    rule_id = uuid4()
    rule = create_rule(
        tenant_id, agent_id, name="Cooldown Rule", cooldown_turns=3
    )
    rule.id = rule_id

    # Mark rule as fired 2 turns ago
    session.rule_last_fire_turn[str(rule_id)] = 8
    current_turn = 10

    candidates = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    # Should be filtered (2 turns < 3 turn cooldown)
    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=current_turn,
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_allow_after_cooldown(pre_filter, session, tenant_id, agent_id):
    """Rules should be allowed after cooldown expires."""
    rule_id = uuid4()
    rule = create_rule(
        tenant_id, agent_id, name="Cooldown Rule", cooldown_turns=3
    )
    rule.id = rule_id

    # Mark rule as fired 3 turns ago
    session.rule_last_fire_turn[str(rule_id)] = 7
    current_turn = 10

    candidates = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    # Should pass (3 turns >= 3 turn cooldown)
    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=current_turn,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_filter_max_fires_rules(pre_filter, session, tenant_id, agent_id):
    """Rules should be filtered when max fires reached."""
    rule_id = uuid4()
    rule = create_rule(
        tenant_id, agent_id, name="Max Fires Rule", max_fires_per_session=2
    )
    rule.id = rule_id

    # Mark rule as fired 2 times
    session.rule_fires[str(rule_id)] = 2

    candidates = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    # Should be filtered (2 fires >= 2 max)
    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=0,
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_allow_before_max_fires(pre_filter, session, tenant_id, agent_id):
    """Rules should be allowed before max fires reached."""
    rule_id = uuid4()
    rule = create_rule(
        tenant_id, agent_id, name="Max Fires Rule", max_fires_per_session=3
    )
    rule.id = rule_id

    # Mark rule as fired 2 times
    session.rule_fires[str(rule_id)] = 2

    candidates = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    # Should pass (2 fires < 3 max)
    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=0,
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_filter_empty_candidates(pre_filter, session):
    """Empty candidates should return empty result."""
    result = await pre_filter.filter(
        candidates=[],
        session=session,
        active_scenario_ids=set(),
        active_step_ids=set(),
        current_turn_number=0,
    )

    assert len(result) == 0


@pytest.mark.asyncio
async def test_filter_multiple_constraints(
    pre_filter, session, tenant_id, agent_id, scenario_id
):
    """Multiple constraints should be applied together."""
    active_scenario_id = scenario_id

    # Rule 1: Global, enabled, no cooldown, no max fires → PASS
    rule1 = create_rule(tenant_id, agent_id, name="Rule 1", scope=Scope.GLOBAL)

    # Rule 2: Scenario-scoped but inactive → FAIL (scope)
    rule2 = create_rule(
        tenant_id, agent_id, name="Rule 2", scope=Scope.SCENARIO, scope_id=uuid4()
    )

    # Rule 3: Disabled → FAIL (disabled)
    rule3 = create_rule(tenant_id, agent_id, name="Rule 3", enabled=False)

    # Rule 4: Active scenario, enabled, but on cooldown → FAIL (cooldown)
    rule4_id = uuid4()
    rule4 = create_rule(
        tenant_id,
        agent_id,
        name="Rule 4",
        scope=Scope.SCENARIO,
        scope_id=active_scenario_id,
        cooldown_turns=5,
    )
    rule4.id = rule4_id
    session.rule_last_fire_turn[str(rule4_id)] = 8

    # Rule 5: Active scenario, enabled, but max fires reached → FAIL (max fires)
    rule5_id = uuid4()
    rule5 = create_rule(
        tenant_id,
        agent_id,
        name="Rule 5",
        scope=Scope.SCENARIO,
        scope_id=active_scenario_id,
        max_fires_per_session=1,
    )
    rule5.id = rule5_id
    session.rule_fires[str(rule5_id)] = 1

    candidates = [
        MatchedRule(rule=rule1, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=rule2, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=rule3, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=rule4, match_score=1.0, relevance_score=1.0, reasoning="Test"),
        MatchedRule(rule=rule5, match_score=1.0, relevance_score=1.0, reasoning="Test"),
    ]

    result = await pre_filter.filter(
        candidates=candidates,
        session=session,
        active_scenario_ids={active_scenario_id},
        active_step_ids=set(),
        current_turn_number=10,
    )

    # Only Rule 1 should pass
    assert len(result) == 1
    assert result[0].rule.name == "Rule 1"
