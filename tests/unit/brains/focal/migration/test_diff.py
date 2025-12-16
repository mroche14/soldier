"""Tests for migration diff module (content hashing and transformation computation)."""

import pytest
from uuid import uuid4

from ruche.brains.focal.migration.diff import (
    compute_node_content_hash,
    compute_scenario_checksum,
    find_anchor_nodes,
    compute_upstream_changes,
    compute_downstream_changes,
    determine_migration_scenario,
    compute_transformation_map,
)
from ruche.brains.focal.migration.models import (
    MigrationScenario,
    UpstreamChanges,
    DownstreamChanges,
    InsertedNode,
    NewFork,
    ForkBranch,
)
from ruche.brains.focal.models import Scenario, ScenarioStep, StepTransition


# =============================================================================
# Tests: compute_node_content_hash()
# =============================================================================


class TestComputeNodeContentHash:
    """Tests for compute_node_content_hash()."""

    def test_same_semantic_content_produces_same_hash(self, scenario_id):
        """Steps with same semantic content produce identical hashes."""
        step1 = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Ask Email",
            description="Request email address",
            rule_ids=[],
            collects_profile_fields=["email"],
        )

        step2 = ScenarioStep(
            id=uuid4(),  # Different ID
            scenario_id=scenario_id,
            name="Ask Email",  # Same content
            description="Request email address",
            rule_ids=[],
            collects_profile_fields=["email"],
        )

        hash1 = compute_node_content_hash(step1)
        hash2 = compute_node_content_hash(step2)

        assert hash1 == hash2

    def test_different_semantic_content_produces_different_hash(self, scenario_id):
        """Steps with different semantic content produce different hashes."""
        step1 = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Ask Email",
            description="Request email",
            rule_ids=[],
            collects_profile_fields=["email"],
        )

        step2 = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Ask Phone",  # Different name
            description="Request phone",
            rule_ids=[],
            collects_profile_fields=["phone"],
        )

        hash1 = compute_node_content_hash(step1)
        hash2 = compute_node_content_hash(step2)

        assert hash1 != hash2

    def test_hash_is_16_characters(self, scenario_id):
        """Content hash is truncated to 16 characters."""
        step = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Test",
            rule_ids=[],
            collects_profile_fields=[],
        )

        content_hash = compute_node_content_hash(step)

        assert len(content_hash) == 16
        assert all(c in "0123456789abcdef" for c in content_hash)

    def test_hash_ignores_step_id(self, scenario_id):
        """Hash is based on semantic content, not step ID."""
        step_id_a = uuid4()
        step_id_b = uuid4()

        step_a = ScenarioStep(
            id=step_id_a,
            scenario_id=scenario_id,
            name="Same Step",
            rule_ids=[],
            collects_profile_fields=[],
        )

        step_b = ScenarioStep(
            id=step_id_b,
            scenario_id=scenario_id,
            name="Same Step",
            rule_ids=[],
            collects_profile_fields=[],
        )

        assert compute_node_content_hash(step_a) == compute_node_content_hash(step_b)

    def test_hash_includes_checkpoint_flag(self, scenario_id):
        """Checkpoint flag affects hash."""
        step_regular = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Test",
            is_checkpoint=False,
            rule_ids=[],
            collects_profile_fields=[],
        )

        step_checkpoint = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            name="Test",
            is_checkpoint=True,
            checkpoint_description="Test checkpoint",
            rule_ids=[],
            collects_profile_fields=[],
        )

        assert compute_node_content_hash(step_regular) != compute_node_content_hash(step_checkpoint)


# =============================================================================
# Tests: compute_scenario_checksum()
# =============================================================================


class TestComputeScenarioChecksum:
    """Tests for compute_scenario_checksum()."""

    def test_same_scenario_produces_same_checksum(self, simple_scenario_v1):
        """Same scenario produces same checksum."""
        checksum1 = compute_scenario_checksum(simple_scenario_v1)
        checksum2 = compute_scenario_checksum(simple_scenario_v1)

        assert checksum1 == checksum2

    def test_different_scenarios_produce_different_checksums(
        self, simple_scenario_v1, simple_scenario_v2
    ):
        """Different scenarios produce different checksums."""
        checksum1 = compute_scenario_checksum(simple_scenario_v1)
        checksum2 = compute_scenario_checksum(simple_scenario_v2)

        assert checksum1 != checksum2

    def test_checksum_is_16_characters(self, simple_scenario_v1):
        """Checksum is truncated to 16 characters."""
        checksum = compute_scenario_checksum(simple_scenario_v1)

        assert len(checksum) == 16
        assert all(c in "0123456789abcdef" for c in checksum)


# =============================================================================
# Tests: find_anchor_nodes()
# =============================================================================


class TestFindAnchorNodes:
    """Tests for find_anchor_nodes()."""

    def test_finds_unchanged_steps_as_anchors(self, simple_scenario_v1, simple_scenario_v2):
        """Steps with same semantic content are identified as anchors."""
        anchors = find_anchor_nodes(simple_scenario_v1, simple_scenario_v2)

        # ask_question and complete should be anchors (entry changed its transitions)
        assert len(anchors) >= 2
        anchor_names = {v1_step.name for v1_step, v2_step, _ in anchors}
        assert "Ask Question" in anchor_names
        assert "Complete" in anchor_names

    def test_returns_empty_when_no_common_steps(self, scenario_id, tenant_id, agent_id):
        """Returns empty list when scenarios share no common steps."""
        v1 = Scenario(
            id=scenario_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="V1",
            version=1,
            entry_step_id=uuid4(),
            steps=[
                ScenarioStep(
                    id=uuid4(),
                    scenario_id=scenario_id,
                    name="Step A",
                    rule_ids=[],
                    collects_profile_fields=[],
                )
            ],
        )

        v2 = Scenario(
            id=scenario_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="V2",
            version=2,
            entry_step_id=uuid4(),
            steps=[
                ScenarioStep(
                    id=uuid4(),
                    scenario_id=scenario_id,
                    name="Step B",  # Completely different
                    rule_ids=[],
                    collects_profile_fields=[],
                )
            ],
        )

        anchors = find_anchor_nodes(v1, v2)
        assert len(anchors) == 0

    def test_anchor_tuple_format(self, simple_scenario_v1, simple_scenario_v2):
        """Anchor tuples contain (v1_step, v2_step, content_hash)."""
        anchors = find_anchor_nodes(simple_scenario_v1, simple_scenario_v2)

        assert len(anchors) > 0
        v1_step, v2_step, content_hash = anchors[0]

        assert isinstance(v1_step, ScenarioStep)
        assert isinstance(v2_step, ScenarioStep)
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16


# =============================================================================
# Tests: compute_upstream_changes()
# =============================================================================


class TestComputeUpstreamChanges:
    """Tests for compute_upstream_changes()."""

    def test_detects_inserted_upstream_nodes(self, simple_scenario_v1, simple_scenario_v2):
        """Detects nodes inserted upstream of anchor."""
        # Find the "Ask Question" anchor
        anchors = find_anchor_nodes(simple_scenario_v1, simple_scenario_v2)
        ask_anchor = next(
            (v1, v2, h) for v1, v2, h in anchors if v1.name == "Ask Question"
        )
        v1_step, v2_step, _ = ask_anchor

        upstream = compute_upstream_changes(
            simple_scenario_v1,
            simple_scenario_v2,
            v1_step.id,
            v2_step.id,
        )

        # V2 has "Verify Identity" inserted upstream
        assert len(upstream.inserted_nodes) == 1
        assert upstream.inserted_nodes[0].node_name == "Verify Identity"
        assert "user_phone" in upstream.inserted_nodes[0].collects_fields

    def test_detects_removed_upstream_nodes(self, simple_scenario_v2, simple_scenario_v1):
        """Detects nodes removed upstream when going from V2 to V1."""
        # Reverse: V2 -> V1 (removes verify_identity)
        anchors = find_anchor_nodes(simple_scenario_v2, simple_scenario_v1)
        ask_anchor = next(
            (v1, v2, h) for v1, v2, h in anchors if v1.name == "Ask Question"
        )
        v2_step, v1_step, _ = ask_anchor

        upstream = compute_upstream_changes(
            simple_scenario_v2,
            simple_scenario_v1,
            v2_step.id,
            v1_step.id,
        )

        # Going from V2 to V1 removes "Verify Identity"
        assert len(upstream.removed_node_ids) == 1

    def test_detects_upstream_forks(self, simple_scenario_v1, fork_scenario_v2):
        """Detects new forks inserted upstream."""
        anchors = find_anchor_nodes(simple_scenario_v1, fork_scenario_v2)
        ask_anchor = next(
            (v1, v2, h) for v1, v2, h in anchors if v1.name == "Ask Question"
        )
        v1_step, v2_step, _ = ask_anchor

        upstream = compute_upstream_changes(
            simple_scenario_v1,
            fork_scenario_v2,
            v1_step.id,
            v2_step.id,
        )

        # Fork_scenario_v2 has "Route Customer" with 2 branches
        assert len(upstream.new_forks) == 1
        fork = upstream.new_forks[0]
        assert fork.fork_node_name == "Route Customer"
        assert len(fork.branches) == 2

        branch_names = {b.target_step_name for b in fork.branches}
        assert "Premium Path" in branch_names
        assert "Standard Path" in branch_names


# =============================================================================
# Tests: compute_downstream_changes()
# =============================================================================


class TestComputeDownstreamChanges:
    """Tests for compute_downstream_changes()."""

    def test_detects_inserted_downstream_nodes(self, scenario_id, tenant_id, agent_id):
        """Detects nodes inserted downstream of anchor."""
        entry_id = uuid4()
        anchor_id = uuid4()
        new_id = uuid4()
        complete_id = uuid4()

        # V1: entry -> anchor -> complete
        v1 = Scenario(
            id=scenario_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="V1",
            version=1,
            entry_step_id=entry_id,
            steps=[
                ScenarioStep(
                    id=entry_id,
                    scenario_id=scenario_id,
                    name="Entry",
                    rule_ids=[],
                    collects_profile_fields=[],
                    transitions=[StepTransition(to_step_id=anchor_id, condition_text="", priority=1)],
                ),
                ScenarioStep(
                    id=anchor_id,
                    scenario_id=scenario_id,
                    name="Anchor",
                    rule_ids=[],
                    collects_profile_fields=[],
                    transitions=[StepTransition(to_step_id=complete_id, condition_text="", priority=1)],
                ),
                ScenarioStep(
                    id=complete_id,
                    scenario_id=scenario_id,
                    name="Complete",
                    rule_ids=[],
                    collects_profile_fields=[],
                    is_terminal=True,
                ),
            ],
        )

        # V2: entry -> anchor -> new_step -> complete
        v2 = Scenario(
            id=scenario_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="V2",
            version=2,
            entry_step_id=entry_id,
            steps=[
                ScenarioStep(
                    id=entry_id,
                    scenario_id=scenario_id,
                    name="Entry",
                    rule_ids=[],
                    collects_profile_fields=[],
                    transitions=[StepTransition(to_step_id=anchor_id, condition_text="", priority=1)],
                ),
                ScenarioStep(
                    id=anchor_id,
                    scenario_id=scenario_id,
                    name="Anchor",
                    rule_ids=[],
                    collects_profile_fields=[],
                    transitions=[StepTransition(to_step_id=new_id, condition_text="", priority=1)],
                ),
                ScenarioStep(
                    id=new_id,
                    scenario_id=scenario_id,
                    name="New Step",
                    rule_ids=[],
                    collects_profile_fields=["new_field"],
                ),
                ScenarioStep(
                    id=complete_id,
                    scenario_id=scenario_id,
                    name="Complete",
                    rule_ids=[],
                    collects_profile_fields=[],
                    is_terminal=True,
                ),
            ],
        )

        downstream = compute_downstream_changes(v1, v2, anchor_id, anchor_id)

        assert len(downstream.inserted_nodes) == 1
        assert downstream.inserted_nodes[0].node_name == "New Step"

    def test_no_changes_when_downstream_identical(self, simple_scenario_v1):
        """Returns empty changes when downstream is identical."""
        # Use entry as anchor, downstream is the same in V1 and V1
        entry_id = simple_scenario_v1.entry_step_id

        downstream = compute_downstream_changes(
            simple_scenario_v1,
            simple_scenario_v1,
            entry_id,
            entry_id,
        )

        assert len(downstream.inserted_nodes) == 0
        assert len(downstream.removed_node_ids) == 0


# =============================================================================
# Tests: determine_migration_scenario()
# =============================================================================


class TestDetermineMigrationScenario:
    """Tests for determine_migration_scenario()."""

    def test_clean_graft_when_no_upstream_changes(self):
        """Returns CLEAN_GRAFT when no upstream changes."""
        upstream = UpstreamChanges()
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.CLEAN_GRAFT

    def test_gap_fill_when_upstream_data_collection(self):
        """Returns GAP_FILL when upstream nodes collect data."""
        upstream = UpstreamChanges(
            inserted_nodes=[
                InsertedNode(
                    node_id=uuid4(),
                    node_name="Collect Data",
                    collects_fields=["email"],  # Collects data
                )
            ]
        )
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.GAP_FILL

    def test_re_route_when_upstream_fork(self):
        """Returns RE_ROUTE when upstream has new fork."""
        upstream = UpstreamChanges(
            new_forks=[
                NewFork(
                    fork_node_id=uuid4(),
                    fork_node_name="Decision Point",
                    branches=[
                        ForkBranch(
                            target_step_id=uuid4(),
                            target_step_name="Branch A",
                            condition_text="condition a",
                        )
                    ],
                )
            ]
        )
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.RE_ROUTE

    def test_re_route_takes_precedence_over_gap_fill(self):
        """RE_ROUTE takes precedence when both fork and data collection exist."""
        upstream = UpstreamChanges(
            inserted_nodes=[
                InsertedNode(
                    node_id=uuid4(),
                    node_name="Collect Data",
                    collects_fields=["email"],
                )
            ],
            new_forks=[
                NewFork(
                    fork_node_id=uuid4(),
                    fork_node_name="Fork",
                    branches=[],
                )
            ],
        )
        downstream = DownstreamChanges()

        scenario = determine_migration_scenario(upstream, downstream)

        assert scenario == MigrationScenario.RE_ROUTE


# =============================================================================
# Tests: compute_transformation_map()
# =============================================================================


class TestComputeTransformationMap:
    """Tests for compute_transformation_map()."""

    def test_computes_complete_transformation_map(
        self, simple_scenario_v1, simple_scenario_v2
    ):
        """Computes transformation map with anchors and changes."""
        tmap = compute_transformation_map(simple_scenario_v1, simple_scenario_v2)

        # Should have at least 2 anchors (Ask Question, Complete)
        assert len(tmap.anchors) >= 2

        # Should have new nodes (Verify Identity)
        assert len(tmap.new_node_ids) >= 1

        # Each anchor should have transformation details
        for anchor in tmap.anchors:
            assert anchor.anchor_content_hash
            assert anchor.anchor_name
            assert anchor.migration_scenario in MigrationScenario

    def test_identifies_deleted_nodes(self, simple_scenario_v2, simple_scenario_v1):
        """Identifies nodes deleted in new version."""
        # V2 -> V1 deletes "Verify Identity"
        tmap = compute_transformation_map(simple_scenario_v2, simple_scenario_v1)

        # Should have deleted nodes
        assert len(tmap.deleted_nodes) >= 1

        # Deleted node should have relocation suggestion
        deleted = tmap.deleted_nodes[0]
        assert deleted.node_name == "Verify Identity"
        assert deleted.nearest_anchor_hash is not None

    def test_get_anchor_by_hash(self, simple_scenario_v1, simple_scenario_v2):
        """Can retrieve anchor by content hash."""
        tmap = compute_transformation_map(simple_scenario_v1, simple_scenario_v2)

        # Get first anchor
        first_anchor = tmap.anchors[0]
        content_hash = first_anchor.anchor_content_hash

        # Retrieve by hash
        retrieved = tmap.get_anchor_by_hash(content_hash)

        assert retrieved is not None
        assert retrieved.anchor_content_hash == content_hash
        assert retrieved.anchor_name == first_anchor.anchor_name

    def test_get_anchor_by_hash_returns_none_for_unknown(
        self, simple_scenario_v1, simple_scenario_v2
    ):
        """Returns None for unknown hash."""
        tmap = compute_transformation_map(simple_scenario_v1, simple_scenario_v2)

        retrieved = tmap.get_anchor_by_hash("unknown_hash_1234")

        assert retrieved is None
