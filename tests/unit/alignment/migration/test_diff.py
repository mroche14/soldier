"""Tests for migration diff functions."""

from uuid import uuid4

import pytest

from focal.alignment.migration.diff import (
    compute_node_content_hash,
    compute_scenario_checksum,
    compute_transformation_map,
    determine_migration_scenario,
    find_anchor_nodes,
)
from focal.alignment.migration.models import MigrationScenario
from focal.alignment.models import Scenario, ScenarioStep, StepTransition


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


def create_step(
    scenario_id,
    name: str,
    transitions: list[tuple] | None = None,
    collects_fields: list[str] | None = None,
    is_checkpoint: bool = False,
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
        is_checkpoint=is_checkpoint,
    )


class TestContentHashing:
    """Tests for compute_node_content_hash."""

    def test_same_content_same_hash(self, tenant_id, agent_id):
        """Steps with same semantic content have same hash."""
        scenario_id = uuid4()
        step1 = create_step(scenario_id, "Collect Info")
        step2 = create_step(scenario_id, "Collect Info")

        hash1 = compute_node_content_hash(step1)
        hash2 = compute_node_content_hash(step2)

        assert hash1 == hash2

    def test_different_name_different_hash(self, tenant_id, agent_id):
        """Steps with different names have different hashes."""
        scenario_id = uuid4()
        step1 = create_step(scenario_id, "Collect Info")
        step2 = create_step(scenario_id, "Verify Info")

        hash1 = compute_node_content_hash(step1)
        hash2 = compute_node_content_hash(step2)

        assert hash1 != hash2

    def test_hash_length(self, tenant_id, agent_id):
        """Hash is 16 characters (truncated SHA-256)."""
        scenario_id = uuid4()
        step = create_step(scenario_id, "Test Step")
        hash_value = compute_node_content_hash(step)

        assert len(hash_value) == 16
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_different_fields_different_hash(self, tenant_id, agent_id):
        """Steps with different collected fields have different hashes."""
        scenario_id = uuid4()
        step1 = create_step(scenario_id, "Step", collects_fields=["name"])
        step2 = create_step(scenario_id, "Step", collects_fields=["email"])

        hash1 = compute_node_content_hash(step1)
        hash2 = compute_node_content_hash(step2)

        assert hash1 != hash2


class TestScenarioChecksum:
    """Tests for compute_scenario_checksum."""

    def test_same_scenario_same_checksum(self, tenant_id, agent_id):
        """Same scenario structure produces same checksum."""
        entry_id = uuid4()
        scenario1 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test Scenario",
            version=1,
            entry_step_id=entry_id,
            steps=[create_step(uuid4(), "Start")],
        )
        scenario1.id = uuid4()
        scenario1.steps[0].id = entry_id

        scenario2 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test Scenario",
            version=1,
            entry_step_id=entry_id,
            steps=[create_step(uuid4(), "Start")],
        )
        scenario2.id = scenario1.id
        scenario2.steps[0].id = entry_id

        checksum1 = compute_scenario_checksum(scenario1)
        checksum2 = compute_scenario_checksum(scenario2)

        assert checksum1 == checksum2

    def test_different_version_different_checksum(self, tenant_id, agent_id):
        """Different versions produce different checksums."""
        entry_id = uuid4()
        base_scenario = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test Scenario",
            version=1,
            entry_step_id=entry_id,
            steps=[create_step(uuid4(), "Start")],
        )
        base_scenario.steps[0].id = entry_id

        v2_scenario = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test Scenario",
            version=2,
            entry_step_id=entry_id,
            steps=[create_step(uuid4(), "Start")],
        )
        v2_scenario.id = base_scenario.id
        v2_scenario.steps[0].id = entry_id

        checksum1 = compute_scenario_checksum(base_scenario)
        checksum2 = compute_scenario_checksum(v2_scenario)

        assert checksum1 != checksum2


class TestFindAnchors:
    """Tests for find_anchor_nodes."""

    def test_find_matching_anchors(self, tenant_id, agent_id):
        """Finds steps that exist in both versions with same content."""
        # Create V1 scenario
        step_a_v1 = create_step(uuid4(), "Collect Name")
        step_b_v1 = create_step(uuid4(), "Verify")

        v1 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=1,
            entry_step_id=step_a_v1.id,
            steps=[step_a_v1, step_b_v1],
        )

        # Create V2 scenario with same steps + new step
        step_a_v2 = create_step(uuid4(), "Collect Name")  # Same as V1
        step_b_v2 = create_step(uuid4(), "Verify")  # Same as V1
        step_c_v2 = create_step(uuid4(), "New Step")  # New in V2

        v2 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=2,
            entry_step_id=step_a_v2.id,
            steps=[step_a_v2, step_b_v2, step_c_v2],
        )

        anchors = find_anchor_nodes(v1, v2)

        assert len(anchors) == 2
        anchor_names = {a[0].name for a in anchors}
        assert "Collect Name" in anchor_names
        assert "Verify" in anchor_names

    def test_no_anchors_all_changed(self, tenant_id, agent_id):
        """No anchors if all steps changed."""
        step_v1 = create_step(uuid4(), "Old Step")
        v1 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=1,
            entry_step_id=step_v1.id,
            steps=[step_v1],
        )

        step_v2 = create_step(uuid4(), "New Step")
        v2 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=2,
            entry_step_id=step_v2.id,
            steps=[step_v2],
        )

        anchors = find_anchor_nodes(v1, v2)

        assert len(anchors) == 0


class TestMigrationScenarioDetermination:
    """Tests for determine_migration_scenario."""

    def test_clean_graft_no_changes(self):
        """Clean graft when no upstream changes."""
        from focal.alignment.migration.models import DownstreamChanges, UpstreamChanges

        upstream = UpstreamChanges()
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.CLEAN_GRAFT

    def test_gap_fill_upstream_data_collection(self):
        """Gap fill when upstream node collects data."""
        from focal.alignment.migration.models import (
            DownstreamChanges,
            InsertedNode,
            UpstreamChanges,
        )

        upstream = UpstreamChanges(
            inserted_nodes=[
                InsertedNode(
                    node_id=uuid4(),
                    node_name="Collect Email",
                    collects_fields=["email"],
                )
            ]
        )
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.GAP_FILL

    def test_re_route_upstream_fork(self):
        """Re-route when upstream has new fork."""
        from focal.alignment.migration.models import (
            DownstreamChanges,
            NewFork,
            UpstreamChanges,
        )

        upstream = UpstreamChanges(
            new_forks=[
                NewFork(
                    fork_node_id=uuid4(),
                    fork_node_name="Decision",
                    branches=[],
                )
            ]
        )
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.RE_ROUTE


class TestTransformationMap:
    """Tests for compute_transformation_map."""

    def test_transformation_map_with_anchors(self, tenant_id, agent_id):
        """Computes transformation map with anchors and deleted nodes."""
        # V1: A -> B
        step_a_v1 = create_step(uuid4(), "Step A")
        step_b_v1 = create_step(uuid4(), "Step B")
        step_a_v1.transitions = [
            StepTransition(to_step_id=step_b_v1.id, condition_text="next")
        ]

        v1 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=1,
            entry_step_id=step_a_v1.id,
            steps=[step_a_v1, step_b_v1],
        )

        # V2: A -> C (B removed, C added)
        step_a_v2 = create_step(uuid4(), "Step A")  # Anchor
        step_c_v2 = create_step(uuid4(), "Step C")  # New
        step_a_v2.transitions = [
            StepTransition(to_step_id=step_c_v2.id, condition_text="next")
        ]

        v2 = Scenario(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Test",
            version=2,
            entry_step_id=step_a_v2.id,
            steps=[step_a_v2, step_c_v2],
        )

        trans_map = compute_transformation_map(v1, v2)

        # Step A is an anchor
        assert len(trans_map.anchors) == 1
        assert trans_map.anchors[0].anchor_name == "Step A"

        # Step B was deleted
        assert len(trans_map.deleted_nodes) == 1
        assert trans_map.deleted_nodes[0].node_name == "Step B"

        # Step C is new
        assert len(trans_map.new_node_ids) == 1
