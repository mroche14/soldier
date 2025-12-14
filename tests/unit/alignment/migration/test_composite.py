"""Tests for composite migration handling multi-version gaps."""

from uuid import uuid4

import pytest

from ruche.alignment.migration.composite import CompositeMapper
from ruche.alignment.migration.models import (
    AnchorTransformation,
    InsertedNode,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationScenario,
    ReconciliationAction,
    TransformationMap,
    UpstreamChanges,
)
from ruche.alignment.models import Scenario, ScenarioStep, StepTransition
from ruche.alignment.stores.inmemory import InMemoryAgentConfigStore
from ruche.conversation.models import Channel, Session


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def config_store():
    return InMemoryAgentConfigStore()


def create_step(
    scenario_id,
    name: str,
    transitions: list[tuple] | None = None,
    collects_fields: list[str] | None = None,
) -> ScenarioStep:
    """Helper to create a step."""
    step_transitions = []
    if transitions:
        for to_id, condition in transitions:
            step_transitions.append(
                StepTransition(to_step_id=to_id, condition_text=condition)
            )
    return ScenarioStep(
        scenario_id=scenario_id,
        name=name,
        transitions=step_transitions,
        collects_profile_fields=collects_fields or [],
    )


def create_scenario(
    tenant_id,
    agent_id,
    name: str,
    version: int,
    steps: list[ScenarioStep],
) -> Scenario:
    """Helper to create a scenario."""
    scenario = Scenario(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        version=version,
        entry_step_id=steps[0].id,
        steps=steps,
    )
    for step in scenario.steps:
        step.scenario_id = scenario.id
    return scenario


def create_migration_plan(
    tenant_id,
    scenario_id,
    from_version: int,
    to_version: int,
    anchors: list[AnchorTransformation] | None = None,
) -> MigrationPlan:
    """Helper to create a migration plan."""
    return MigrationPlan(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        from_version=from_version,
        to_version=to_version,
        status=MigrationPlanStatus.DEPLOYED,
        scenario_checksum_v1=f"checksum_v{from_version}",
        scenario_checksum_v2=f"checksum_v{to_version}",
        transformation_map=TransformationMap(
            anchors=anchors or [],
            deleted_nodes=[],
        ),
    )


class TestCompositeMapperGetPlanChain:
    """Tests for get_plan_chain method."""

    @pytest.mark.asyncio
    async def test_get_plan_chain_single_version(self, tenant_id, config_store):
        """Test loading a single-version plan chain."""
        scenario_id = uuid4()

        # Create V1→V2 plan
        plan = create_migration_plan(tenant_id, scenario_id, 1, 2)
        await config_store.save_migration_plan(plan)

        mapper = CompositeMapper(config_store)
        chain = await mapper.get_plan_chain(tenant_id, scenario_id, 1, 2)

        assert len(chain) == 1
        assert chain[0].from_version == 1
        assert chain[0].to_version == 2

    @pytest.mark.asyncio
    async def test_get_plan_chain_multi_version(self, tenant_id, config_store):
        """Test loading a multi-version plan chain."""
        scenario_id = uuid4()

        # Create plans: V1→V2, V2→V3, V3→V4
        plan1 = create_migration_plan(tenant_id, scenario_id, 1, 2)
        plan2 = create_migration_plan(tenant_id, scenario_id, 2, 3)
        plan3 = create_migration_plan(tenant_id, scenario_id, 3, 4)
        await config_store.save_migration_plan(plan1)
        await config_store.save_migration_plan(plan2)
        await config_store.save_migration_plan(plan3)

        mapper = CompositeMapper(config_store)
        chain = await mapper.get_plan_chain(tenant_id, scenario_id, 1, 4)

        assert len(chain) == 3
        assert chain[0].from_version == 1
        assert chain[1].from_version == 2
        assert chain[2].from_version == 3

    @pytest.mark.asyncio
    async def test_get_plan_chain_broken(self, tenant_id, config_store):
        """Test handling broken plan chain (missing intermediate plan)."""
        scenario_id = uuid4()

        # Create plans: V1→V2, V3→V4 (V2→V3 missing)
        plan1 = create_migration_plan(tenant_id, scenario_id, 1, 2)
        plan3 = create_migration_plan(tenant_id, scenario_id, 3, 4)
        await config_store.save_migration_plan(plan1)
        await config_store.save_migration_plan(plan3)

        mapper = CompositeMapper(config_store)
        chain = await mapper.get_plan_chain(tenant_id, scenario_id, 1, 4)

        # Should stop at the break
        assert len(chain) == 1
        assert chain[0].from_version == 1
        assert chain[0].to_version == 2

    @pytest.mark.asyncio
    async def test_get_plan_chain_empty(self, tenant_id, config_store):
        """Test empty chain when no plans exist."""
        scenario_id = uuid4()

        mapper = CompositeMapper(config_store)
        chain = await mapper.get_plan_chain(tenant_id, scenario_id, 1, 4)

        assert len(chain) == 0


class TestCompositeMapperAccumulateRequirements:
    """Tests for accumulate_requirements method."""

    @pytest.mark.asyncio
    async def test_accumulate_single_plan(self, tenant_id, config_store):
        """Test accumulating requirements from single plan."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Create plan with anchor that collects email
        anchor = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Email",
                        node_id=uuid4(),
                        collects_fields=["email"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        plan = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor])

        mapper = CompositeMapper(config_store)
        fields = mapper.accumulate_requirements([plan], anchor_hash)

        assert fields == {"email"}

    @pytest.mark.asyncio
    async def test_accumulate_multi_plan(self, tenant_id, config_store):
        """Test accumulating requirements from multiple plans."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Plan 1: collects email
        anchor1 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Email",
                        node_id=uuid4(),
                        collects_fields=["email"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        plan1 = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor1])

        # Plan 2: collects phone
        anchor2 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Phone",
                        node_id=uuid4(),
                        collects_fields=["phone"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        plan2 = create_migration_plan(tenant_id, scenario_id, 2, 3, [anchor2])

        mapper = CompositeMapper(config_store)
        fields = mapper.accumulate_requirements([plan1, plan2], anchor_hash)

        assert fields == {"email", "phone"}


class TestCompositeMapperPruneRequirements:
    """Tests for prune_requirements method."""

    @pytest.mark.asyncio
    async def test_prune_removes_obsolete_fields(self, tenant_id, config_store):
        """Test that pruning removes fields not needed in final version."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Accumulated: email, phone, address
        accumulated = {"email", "phone", "address"}

        # Final plan only needs email
        final_anchor = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Email",
                        node_id=uuid4(),
                        collects_fields=["email"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        final_plan = create_migration_plan(
            tenant_id, scenario_id, 3, 4, [final_anchor]
        )

        mapper = CompositeMapper(config_store)
        pruned = mapper.prune_requirements(accumulated, final_plan, anchor_hash)

        assert pruned == {"email"}

    @pytest.mark.asyncio
    async def test_prune_keeps_all_when_all_needed(self, tenant_id, config_store):
        """Test that pruning keeps all fields when all still needed."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        accumulated = {"email", "phone"}

        # Final plan needs both
        final_anchor = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Info",
                        node_id=uuid4(),
                        collects_fields=["email", "phone"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        final_plan = create_migration_plan(
            tenant_id, scenario_id, 3, 4, [final_anchor]
        )

        mapper = CompositeMapper(config_store)
        pruned = mapper.prune_requirements(accumulated, final_plan, anchor_hash)

        assert pruned == {"email", "phone"}


class TestCompositeMapperExecute:
    """Tests for execute_composite_migration method."""

    @pytest.mark.asyncio
    async def test_execute_teleports_when_no_missing_fields(
        self, tenant_id, agent_id, config_store
    ):
        """Test teleport when all required fields are present."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"
        target_step_id = uuid4()

        # Create final plan with anchor needing email
        anchor = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=target_step_id,
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Email",
                        node_id=uuid4(),
                        collects_fields=["email"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        plan = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor])

        # Create scenario
        step = create_step(scenario_id, "Step A")
        step.id = target_step_id
        scenario = create_scenario(tenant_id, agent_id, "Test", 2, [step])
        scenario.id = scenario_id

        # Create session with email already present
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=scenario_id,
            active_scenario_version=1,
            variables={"email": "test@example.com"},
        )

        mapper = CompositeMapper(config_store)
        result = await mapper.execute_composite_migration(
            session=session,
            plan_chain=[plan],
            _final_scenario=scenario,
            anchor_hash=anchor_hash,
        )

        assert result.action == ReconciliationAction.TELEPORT
        assert result.target_step_id == target_step_id

    @pytest.mark.asyncio
    async def test_execute_collects_when_missing_fields(
        self, tenant_id, agent_id, config_store
    ):
        """Test collect action when required fields are missing."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Create plan with anchor needing email
        anchor = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
            upstream_changes=UpstreamChanges(
                inserted_nodes=[
                    InsertedNode(
                        node_name="Collect Email",
                        node_id=uuid4(),
                        collects_fields=["email"],
                    ),
                ],
                removed_node_ids=[],
                new_forks=[],
            ),
        )
        plan = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor])

        # Create scenario
        step = create_step(scenario_id, "Step A")
        scenario = create_scenario(tenant_id, agent_id, "Test", 2, [step])
        scenario.id = scenario_id

        # Create session WITHOUT email
        session = Session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            active_scenario_id=scenario_id,
            active_scenario_version=1,
            variables={},
        )

        mapper = CompositeMapper(config_store)
        result = await mapper.execute_composite_migration(
            session=session,
            plan_chain=[plan],
            _final_scenario=scenario,
            anchor_hash=anchor_hash,
        )

        assert result.action == ReconciliationAction.COLLECT
        assert "email" in result.collect_fields


class TestCompositeScenarioDetermination:
    """Tests for _determine_composite_scenario method."""

    @pytest.mark.asyncio
    async def test_determines_re_route_highest_priority(
        self, tenant_id, config_store
    ):
        """Test that RE_ROUTE takes precedence."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Plan 1: clean graft
        anchor1 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.CLEAN_GRAFT,
        )
        plan1 = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor1])

        # Plan 2: re-route
        anchor2 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.RE_ROUTE,
        )
        plan2 = create_migration_plan(tenant_id, scenario_id, 2, 3, [anchor2])

        mapper = CompositeMapper(config_store)
        scenario = mapper._determine_composite_scenario([plan1, plan2], anchor_hash)

        assert scenario == MigrationScenario.RE_ROUTE

    @pytest.mark.asyncio
    async def test_determines_gap_fill_over_clean_graft(
        self, tenant_id, config_store
    ):
        """Test that GAP_FILL takes precedence over CLEAN_GRAFT."""
        scenario_id = uuid4()
        anchor_hash = "test_hash"

        # Plan 1: clean graft
        anchor1 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.CLEAN_GRAFT,
        )
        plan1 = create_migration_plan(tenant_id, scenario_id, 1, 2, [anchor1])

        # Plan 2: gap fill
        anchor2 = AnchorTransformation(
            anchor_name="Step A",
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=uuid4(),
            anchor_node_id_v2=uuid4(),
            migration_scenario=MigrationScenario.GAP_FILL,
        )
        plan2 = create_migration_plan(tenant_id, scenario_id, 2, 3, [anchor2])

        mapper = CompositeMapper(config_store)
        scenario = mapper._determine_composite_scenario([plan1, plan2], anchor_hash)

        assert scenario == MigrationScenario.GAP_FILL
