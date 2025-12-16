"""Tests for composite migration (multi-version gap handling)."""

import pytest
from uuid import uuid4

from ruche.brains.focal.migration.composite import CompositeMapper
from ruche.brains.focal.migration.models import (
    MigrationPlan,
    TransformationMap,
    AnchorTransformation,
    UpstreamChanges,
    InsertedNode,
    DownstreamChanges,
    MigrationScenario,
)
from ruche.brains.focal.migration.diff import compute_scenario_checksum


# =============================================================================
# Tests: CompositeMapper.get_plan_chain()
# =============================================================================


class TestCompositeMapperGetPlanChain:
    """Tests for CompositeMapper.get_plan_chain()."""

    @pytest.fixture
    def mapper(self, mock_config_store):
        """Create a composite mapper instance."""
        return CompositeMapper(config_store=mock_config_store)

    @pytest.mark.asyncio
    async def test_loads_plan_chain_for_version_range(
        self,
        mapper,
        mock_config_store,
        tenant_id,
        scenario_id,
    ):
        """Loads chain of migration plans between versions."""
        # Create plans: V1->V2, V2->V3, V3->V4
        plan_v1_v2 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="v1_checksum",
            scenario_checksum_v2="v2_checksum",
        )
        plan_v2_v3 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=2,
            to_version=3,
            scenario_checksum_v1="v2_checksum",
            scenario_checksum_v2="v3_checksum",
        )
        plan_v3_v4 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=3,
            to_version=4,
            scenario_checksum_v1="v3_checksum",
            scenario_checksum_v2="v4_checksum",
        )

        await mock_config_store.save_migration_plan(plan_v1_v2)
        await mock_config_store.save_migration_plan(plan_v2_v3)
        await mock_config_store.save_migration_plan(plan_v3_v4)

        # Get chain from V1 to V4
        chain = await mapper.get_plan_chain(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            start_version=1,
            end_version=4,
        )

        # Should get all three plans
        assert len(chain) == 3
        assert chain[0].from_version == 1
        assert chain[0].to_version == 2
        assert chain[1].from_version == 2
        assert chain[1].to_version == 3
        assert chain[2].from_version == 3
        assert chain[2].to_version == 4

    @pytest.mark.asyncio
    async def test_handles_broken_chain(
        self,
        mapper,
        mock_config_store,
        tenant_id,
        scenario_id,
    ):
        """Handles broken plan chain gracefully."""
        # Create plans with gap: V1->V2, skip V2->V3, V3->V4
        plan_v1_v2 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="v1_checksum",
            scenario_checksum_v2="v2_checksum",
        )
        plan_v3_v4 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=3,
            to_version=4,
            scenario_checksum_v1="v3_checksum",
            scenario_checksum_v2="v4_checksum",
        )

        await mock_config_store.save_migration_plan(plan_v1_v2)
        await mock_config_store.save_migration_plan(plan_v3_v4)

        # Try to get chain from V1 to V4
        chain = await mapper.get_plan_chain(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            start_version=1,
            end_version=4,
        )

        # Should stop at broken link
        assert len(chain) == 1  # Only V1->V2
        assert chain[0].from_version == 1

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_plans(
        self,
        mapper,
        tenant_id,
        scenario_id,
    ):
        """Returns empty list when no plans exist."""
        chain = await mapper.get_plan_chain(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            start_version=1,
            end_version=3,
        )

        assert len(chain) == 0


# =============================================================================
# Tests: CompositeMapper.accumulate_requirements()
# =============================================================================


class TestAccumulateRequirements:
    """Tests for CompositeMapper.accumulate_requirements()."""

    @pytest.fixture
    def mapper(self, mock_config_store):
        """Create a composite mapper instance."""
        return CompositeMapper(config_store=mock_config_store)

    def test_accumulates_fields_across_chain(self, mapper, tenant_id, scenario_id):
        """Accumulates all fields collected across plan chain."""
        anchor_hash = "test_anchor_hash"
        anchor_v1 = uuid4()
        anchor_v2 = uuid4()
        anchor_v3 = uuid4()

        # Plan V1->V2: Collects "email"
        plan_v1_v2 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="v1",
            scenario_checksum_v2="v2",
        )
        plan_v1_v2.transformation_map = TransformationMap(
            anchors=[
                AnchorTransformation(
                    anchor_content_hash=anchor_hash,
                    anchor_name="Anchor",
                    anchor_node_id_v1=anchor_v1,
                    anchor_node_id_v2=anchor_v2,
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="Collect Email",
                                collects_fields=["email"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                    migration_scenario=MigrationScenario.GAP_FILL,
                )
            ]
        )

        # Plan V2->V3: Collects "phone"
        plan_v2_v3 = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=2,
            to_version=3,
            scenario_checksum_v1="v2",
            scenario_checksum_v2="v3",
        )
        plan_v2_v3.transformation_map = TransformationMap(
            anchors=[
                AnchorTransformation(
                    anchor_content_hash=anchor_hash,
                    anchor_name="Anchor",
                    anchor_node_id_v1=anchor_v2,
                    anchor_node_id_v2=anchor_v3,
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="Collect Phone",
                                collects_fields=["phone"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                    migration_scenario=MigrationScenario.GAP_FILL,
                )
            ]
        )

        chain = [plan_v1_v2, plan_v2_v3]

        # Accumulate requirements
        fields = mapper.accumulate_requirements(chain, anchor_hash)

        # Should have both fields
        assert "email" in fields
        assert "phone" in fields

    def test_returns_empty_when_no_matching_anchor(self, mapper, tenant_id, scenario_id):
        """Returns empty set when anchor not found in chain."""
        plan = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=1,
            to_version=2,
            scenario_checksum_v1="v1",
            scenario_checksum_v2="v2",
        )
        plan.transformation_map = TransformationMap()

        chain = [plan]

        fields = mapper.accumulate_requirements(chain, "unknown_anchor")

        assert len(fields) == 0

    def test_handles_empty_chain(self, mapper):
        """Handles empty plan chain gracefully."""
        fields = mapper.accumulate_requirements([], "any_hash")

        assert len(fields) == 0


# =============================================================================
# Tests: CompositeMapper.prune_requirements()
# =============================================================================


class TestPruneRequirements:
    """Tests for CompositeMapper.prune_requirements()."""

    @pytest.fixture
    def mapper(self, mock_config_store):
        """Create a composite mapper instance."""
        return CompositeMapper(config_store=mock_config_store)

    def test_prunes_obsolete_fields(self, mapper, tenant_id, scenario_id):
        """Removes fields no longer needed in final version."""
        anchor_hash = "test_anchor_hash"
        anchor_v3 = uuid4()
        anchor_v4 = uuid4()

        # Accumulated: email, phone, address
        accumulated = {"email", "phone", "address"}

        # Final plan (V3->V4): Only needs email and phone
        final_plan = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=3,
            to_version=4,
            scenario_checksum_v1="v3",
            scenario_checksum_v2="v4",
        )
        final_plan.transformation_map = TransformationMap(
            anchors=[
                AnchorTransformation(
                    anchor_content_hash=anchor_hash,
                    anchor_name="Anchor",
                    anchor_node_id_v1=anchor_v3,
                    anchor_node_id_v2=anchor_v4,
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="Collect Email and Phone",
                                collects_fields=["email", "phone"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                    migration_scenario=MigrationScenario.GAP_FILL,
                )
            ]
        )

        # Prune requirements
        pruned = mapper.prune_requirements(accumulated, final_plan, anchor_hash)

        # Should keep email and phone, remove address
        assert "email" in pruned
        assert "phone" in pruned
        assert "address" not in pruned

    def test_returns_all_when_anchor_not_found(self, mapper, tenant_id, scenario_id):
        """Returns all accumulated fields when anchor not in final plan.

        When we can't find the anchor, we conservatively keep all fields
        rather than dropping them, to avoid losing necessary data.
        """
        accumulated = {"email", "phone"}

        final_plan = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=3,
            to_version=4,
            scenario_checksum_v1="v3",
            scenario_checksum_v2="v4",
        )
        final_plan.transformation_map = TransformationMap()

        pruned = mapper.prune_requirements(accumulated, final_plan, "unknown_anchor")

        assert pruned == accumulated

    def test_keeps_all_fields_when_all_needed(self, mapper, tenant_id, scenario_id):
        """Keeps all fields when final version needs them all."""
        anchor_hash = "test_anchor_hash"
        accumulated = {"email", "phone"}

        final_plan = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=2,
            to_version=3,
            scenario_checksum_v1="v2",
            scenario_checksum_v2="v3",
        )
        final_plan.transformation_map = TransformationMap(
            anchors=[
                AnchorTransformation(
                    anchor_content_hash=anchor_hash,
                    anchor_name="Anchor",
                    anchor_node_id_v1=uuid4(),
                    anchor_node_id_v2=uuid4(),
                    upstream_changes=UpstreamChanges(
                        inserted_nodes=[
                            InsertedNode(
                                node_id=uuid4(),
                                node_name="Collect All",
                                collects_fields=["email", "phone"],
                            )
                        ]
                    ),
                    downstream_changes=DownstreamChanges(),
                    migration_scenario=MigrationScenario.GAP_FILL,
                )
            ]
        )

        pruned = mapper.prune_requirements(accumulated, final_plan, anchor_hash)

        assert pruned == accumulated
