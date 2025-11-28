"""Unit tests for ScenarioFilter."""

from uuid import uuid4

import pytest

from soldier.alignment.context.models import Context, ScenarioSignal
from soldier.alignment.filtering.models import ScenarioAction
from soldier.alignment.filtering.scenario_filter import ScenarioFilter
from soldier.alignment.models.scenario import Scenario, ScenarioStep
from soldier.alignment.retrieval.models import ScoredScenario
from soldier.alignment.stores import InMemoryConfigStore


@pytest.mark.asyncio
async def test_start_new_scenario_when_no_active() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    step_id = uuid4()
    scenario = Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Return Flow",
        entry_step_id=step_id,
        steps=[ScenarioStep(id=step_id, scenario_id=step_id, name="entry", transitions=[])],
    )

    store = InMemoryConfigStore()
    await store.save_scenario(scenario)

    filter = ScenarioFilter(store)
    context = Context(message="start return", scenario_signal=ScenarioSignal.START)
    result = await filter.evaluate(
        tenant_id,
        context,
        candidates=[ScoredScenario(scenario_id=scenario.id, scenario_name="Return Flow", score=0.9)],
    )

    assert result.action == ScenarioAction.START
    assert result.scenario_id == scenario.id
    assert result.target_step_id == scenario.entry_step_id


@pytest.mark.asyncio
async def test_exit_active_scenario_on_signal() -> None:
    tenant_id = uuid4()
    store = InMemoryConfigStore()
    filter = ScenarioFilter(store)

    context = Context(message="stop", scenario_signal=ScenarioSignal.EXIT)

    result = await filter.evaluate(
        tenant_id,
        context,
        candidates=[],
        active_scenario_id=uuid4(),
        current_step_id=uuid4(),
    )

    assert result.action == ScenarioAction.EXIT


@pytest.mark.asyncio
async def test_loop_detection_triggers_relocalize() -> None:
    tenant_id = uuid4()
    store = InMemoryConfigStore()
    filter = ScenarioFilter(store, max_loop_count=2)
    current_step = uuid4()

    context = Context(message="looping", scenario_signal=ScenarioSignal.CONTINUE)

    result = await filter.evaluate(
        tenant_id,
        context,
        candidates=[],
        active_scenario_id=uuid4(),
        current_step_id=current_step,
        visited_steps={current_step: 2},
    )

    assert result.action == ScenarioAction.RELOCALIZE
    assert result.was_relocalized is True
