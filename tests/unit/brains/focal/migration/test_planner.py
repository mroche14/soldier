"""Tests for migration planner (plan generation and deployment)."""

import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from ruche.brains.focal.migration.planner import MigrationPlanner
from ruche.brains.focal.migration.models import MigrationPlanStatus, MigrationScenario
from ruche.config.models.migration import ScenarioMigrationConfig


# =============================================================================
# Tests: MigrationPlanner.generate_plan()
# =============================================================================


class TestMigrationPlannerGeneratePlan:
    """Tests for MigrationPlanner.generate_plan()."""

    @pytest.fixture
    def planner(self, mock_config_store, mock_session_store):
        """Create a migration planner instance."""
        config = ScenarioMigrationConfig()
        return MigrationPlanner(
            config_store=mock_config_store,
            session_store=mock_session_store,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_generates_plan_for_version_transition(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Generates migration plan for scenario version transition."""
        # Setup: Store V1 as current
        simple_scenario_v1.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        # Act: Generate plan for V1 -> V2
        simple_scenario_v2.tenant_id = tenant_id
        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
            created_by="test_operator",
        )

        # Assert
        assert plan is not None
        assert plan.tenant_id == tenant_id
        assert plan.scenario_id == scenario_id
        assert plan.from_version == 1
        assert plan.to_version == 2
        assert plan.status == MigrationPlanStatus.PENDING
        assert plan.created_by == "test_operator"

    @pytest.mark.asyncio
    async def test_computes_transformation_map(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Plan includes computed transformation map."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        # Transformation map should have anchors
        assert len(plan.transformation_map.anchors) > 0

        # Should have at least one GAP_FILL anchor (Verify Identity inserted)
        gap_fill_anchors = [
            a
            for a in plan.transformation_map.anchors
            if a.migration_scenario == MigrationScenario.GAP_FILL
        ]
        assert len(gap_fill_anchors) > 0

    @pytest.mark.asyncio
    async def test_creates_default_anchor_policies(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Creates default policies for each anchor."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        # Each anchor should have a policy
        assert len(plan.anchor_policies) == len(plan.transformation_map.anchors)

        for anchor in plan.transformation_map.anchors:
            policy = plan.anchor_policies.get(anchor.anchor_content_hash)
            assert policy is not None
            assert policy.anchor_content_hash == anchor.anchor_content_hash
            assert policy.update_downstream is True  # Default

    @pytest.mark.asyncio
    async def test_builds_migration_summary(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Plan includes migration summary."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        summary = plan.summary
        assert summary.total_anchors > 0
        assert summary.total_anchors == len(plan.transformation_map.anchors)

    @pytest.mark.asyncio
    async def test_sets_plan_expiration(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Plan has expiration date based on config."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        before = datetime.now(UTC)
        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )
        after = datetime.now(UTC)

        # Should expire in retention_days (default 30)
        assert plan.expires_at is not None
        expected_days = planner._config.retention.plan_retention_days
        min_expiry = before + timedelta(days=expected_days - 1)
        max_expiry = after + timedelta(days=expected_days + 1)
        assert min_expiry <= plan.expires_at <= max_expiry

    @pytest.mark.asyncio
    async def test_archives_current_scenario_version(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Archives current scenario version during plan generation."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        # Check archived
        archived_key = (tenant_id, scenario_id, 1)
        assert archived_key in mock_config_store.archived_scenarios

    @pytest.mark.asyncio
    async def test_saves_plan_to_store(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Saves generated plan to config store."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        # Check stored
        retrieved = await mock_config_store.get_migration_plan(tenant_id, plan.id)
        assert retrieved is not None
        assert retrieved.id == plan.id

    @pytest.mark.asyncio
    async def test_raises_when_scenario_not_found(
        self, planner, tenant_id, scenario_id, simple_scenario_v2
    ):
        """Raises ValueError when current scenario not found."""
        simple_scenario_v2.tenant_id = tenant_id

        with pytest.raises(ValueError, match="not found"):
            await planner.generate_plan(
                tenant_id=tenant_id,
                scenario_id=scenario_id,
                new_scenario=simple_scenario_v2,
            )

    @pytest.mark.asyncio
    async def test_raises_when_new_version_not_greater(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
    ):
        """Raises ValueError when new version <= current version."""
        simple_scenario_v1.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        # Try to "upgrade" to same version
        simple_scenario_v1_dup = simple_scenario_v1.model_copy()

        with pytest.raises(ValueError, match="must be greater than"):
            await planner.generate_plan(
                tenant_id=tenant_id,
                scenario_id=scenario_id,
                new_scenario=simple_scenario_v1_dup,
            )

    @pytest.mark.asyncio
    async def test_raises_when_plan_already_exists(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Raises ValueError when plan already exists for this transition."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        # Generate first plan
        await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        # Try to generate again
        with pytest.raises(ValueError, match="Plan already exists"):
            await planner.generate_plan(
                tenant_id=tenant_id,
                scenario_id=scenario_id,
                new_scenario=simple_scenario_v2,
            )

    @pytest.mark.asyncio
    async def test_allows_regeneration_after_rejection(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Allows regeneration if previous plan was rejected."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        # Generate and reject
        plan1 = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )
        plan1.status = MigrationPlanStatus.REJECTED
        await mock_config_store.save_migration_plan(plan1)

        # Should allow regeneration
        plan2 = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        assert plan2.id != plan1.id
        assert plan2.status == MigrationPlanStatus.PENDING


# =============================================================================
# Tests: Summary Building
# =============================================================================


class TestBuildSummary:
    """Tests for summary generation."""

    @pytest.fixture
    def planner(self, mock_config_store, mock_session_store):
        """Create a migration planner instance."""
        return MigrationPlanner(
            config_store=mock_config_store,
            session_store=mock_session_store,
        )

    @pytest.mark.asyncio
    async def test_summary_counts_scenario_types(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        fork_scenario_v2,
    ):
        """Summary counts anchors by migration scenario type."""
        simple_scenario_v1.tenant_id = tenant_id
        fork_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=fork_scenario_v2,
        )

        summary = plan.summary

        # Should have at least one re-route (fork inserted)
        assert summary.anchors_with_re_route > 0

    @pytest.mark.asyncio
    async def test_summary_tracks_fields_to_collect(
        self,
        planner,
        mock_config_store,
        tenant_id,
        scenario_id,
        simple_scenario_v1,
        simple_scenario_v2,
    ):
        """Summary tracks fields that need collection."""
        simple_scenario_v1.tenant_id = tenant_id
        simple_scenario_v2.tenant_id = tenant_id
        await mock_config_store.save_scenario(simple_scenario_v1)

        plan = await planner.generate_plan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            new_scenario=simple_scenario_v2,
        )

        summary = plan.summary

        # V2 adds "user_phone" collection
        field_names = [f.field_name for f in summary.fields_to_collect]
        assert "user_phone" in field_names
