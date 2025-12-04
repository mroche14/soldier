"""Migration planner and deployer for scenario version transitions.

Implements MigrationPlanner for plan generation and MigrationDeployer
for session marking during deployment.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from soldier.alignment.migration.diff import (
    compute_scenario_checksum,
    compute_transformation_map,
)
from soldier.alignment.migration.models import (
    AnchorMigrationPolicy,
    FieldCollectionInfo,
    MigrationPlan,
    MigrationPlanStatus,
    MigrationScenario,
    MigrationSummary,
    MigrationWarning,
    ScopeFilter,
    TransformationMap,
)
from soldier.config.models.migration import ScenarioMigrationConfig
from soldier.conversation.models import PendingMigration
from soldier.observability.logging import get_logger

if TYPE_CHECKING:
    from soldier.alignment.models import Scenario
    from soldier.alignment.stores.agent_config_store import AgentConfigStore
    from soldier.conversation.store import SessionStore

logger = get_logger(__name__)


class MigrationPlanner:
    """Generates migration plans for scenario version transitions."""

    def __init__(
        self,
        config_store: "AgentConfigStore",
        session_store: "SessionStore",
        config: ScenarioMigrationConfig | None = None,
    ) -> None:
        """Initialize planner.

        Args:
            config_store: Store for scenarios and migration plans
            session_store: Store for session queries (affected count)
            config: Migration configuration
        """
        self._config_store = config_store
        self._session_store = session_store
        self._config = config or ScenarioMigrationConfig()

    async def generate_plan(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        new_scenario: "Scenario",
        created_by: str | None = None,
    ) -> MigrationPlan:
        """Generate a migration plan for a scenario update.

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario being updated
            new_scenario: New scenario version
            created_by: Operator creating the plan

        Returns:
            Generated MigrationPlan

        Raises:
            ValueError: If current scenario not found or versions invalid
        """
        # Get current scenario version
        current_scenario = await self._config_store.get_scenario(tenant_id, scenario_id)
        if not current_scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        if new_scenario.version <= current_scenario.version:
            raise ValueError(
                f"New version ({new_scenario.version}) must be greater than "
                f"current version ({current_scenario.version})"
            )

        # Check for existing plan for this version transition
        existing = await self._config_store.get_migration_plan_for_versions(
            tenant_id,
            scenario_id,
            current_scenario.version,
            new_scenario.version,
        )
        if existing and existing.status not in (
            MigrationPlanStatus.REJECTED,
            MigrationPlanStatus.SUPERSEDED,
        ):
            raise ValueError(
                f"Plan already exists for {current_scenario.version} -> "
                f"{new_scenario.version} transition"
            )

        # Compute transformation map
        transformation_map = compute_transformation_map(current_scenario, new_scenario)

        # Generate default policies for each anchor
        anchor_policies = {}
        for anchor in transformation_map.anchors:
            anchor_policies[anchor.anchor_content_hash] = AnchorMigrationPolicy(
                anchor_content_hash=anchor.anchor_content_hash,
                anchor_name=anchor.anchor_name,
                scope_filter=ScopeFilter(),
                update_downstream=True,
            )

        # Build migration summary
        summary = await self._build_summary(
            tenant_id,
            scenario_id,
            current_scenario.version,
            transformation_map,
        )

        # Compute expiration
        expires_at = datetime.now(UTC) + timedelta(days=self._config.retention.plan_retention_days)

        # Create plan
        plan = MigrationPlan(
            tenant_id=tenant_id,
            scenario_id=scenario_id,
            from_version=current_scenario.version,
            to_version=new_scenario.version,
            scenario_checksum_v1=compute_scenario_checksum(current_scenario),
            scenario_checksum_v2=compute_scenario_checksum(new_scenario),
            transformation_map=transformation_map,
            anchor_policies=anchor_policies,
            summary=summary,
            status=MigrationPlanStatus.PENDING,
            created_by=created_by,
            expires_at=expires_at,
        )

        # Archive current scenario version
        await self._config_store.archive_scenario_version(tenant_id, current_scenario)

        # Save plan
        await self._config_store.save_migration_plan(plan)

        logger.info(
            "migration_plan_generated",
            plan_id=str(plan.id),
            scenario_id=str(scenario_id),
            from_version=current_scenario.version,
            to_version=new_scenario.version,
            total_anchors=summary.total_anchors,
        )

        return plan

    async def _build_summary(
        self,
        _tenant_id: UUID,
        _scenario_id: UUID,
        _from_version: int,
        transformation_map: TransformationMap,
    ) -> MigrationSummary:
        """Build migration summary for operator review."""
        warnings: list[MigrationWarning] = []
        fields_to_collect: list[FieldCollectionInfo] = []
        sessions_by_anchor: dict[str, int] = {}

        # Count scenarios by type
        clean_graft_count = 0
        gap_fill_count = 0
        re_route_count = 0

        # Track fields that need collection
        field_anchors: dict[str, list[str]] = {}

        for anchor in transformation_map.anchors:
            if anchor.migration_scenario == MigrationScenario.CLEAN_GRAFT:
                clean_graft_count += 1
            elif anchor.migration_scenario == MigrationScenario.GAP_FILL:
                gap_fill_count += 1
            elif anchor.migration_scenario == MigrationScenario.RE_ROUTE:
                re_route_count += 1

            # Track fields to collect from gap fill anchors
            for node in anchor.upstream_changes.inserted_nodes:
                for field in node.collects_fields:
                    if field not in field_anchors:
                        field_anchors[field] = []
                    field_anchors[field].append(anchor.anchor_name)

            # Add warnings for re-route anchors with checkpoints
            if anchor.migration_scenario == MigrationScenario.RE_ROUTE:
                # Check if any upstream node is a checkpoint
                for node in anchor.upstream_changes.inserted_nodes:
                    if node.is_checkpoint:
                        warnings.append(
                            MigrationWarning(
                                severity="warning",
                                anchor_name=anchor.anchor_name,
                                message=(
                                    f"Re-route anchor has upstream checkpoint "
                                    f"'{node.node_name}'. Customers who passed "
                                    f"checkpoints may be blocked."
                                ),
                            )
                        )

            # Estimate affected sessions (would require actual query)
            sessions_by_anchor[anchor.anchor_content_hash] = 0

        # Build field collection info
        for field, anchors in field_anchors.items():
            fields_to_collect.append(
                FieldCollectionInfo(
                    field_name=field,
                    display_name=field.replace("_", " ").title(),
                    affected_anchors=anchors,
                    reason="Required by new upstream step",
                    can_extract_from_conversation=True,
                )
            )

        # Add warning for gap fill fields
        if fields_to_collect:
            warnings.append(
                MigrationWarning(
                    severity="info",
                    anchor_name="Multiple",
                    message=(
                        f"{len(fields_to_collect)} field(s) may need to be "
                        f"collected from customers during migration."
                    ),
                )
            )

        # Estimate total affected sessions
        estimated_total = sum(sessions_by_anchor.values())

        return MigrationSummary(
            total_anchors=len(transformation_map.anchors),
            anchors_with_clean_graft=clean_graft_count,
            anchors_with_gap_fill=gap_fill_count,
            anchors_with_re_route=re_route_count,
            nodes_deleted=len(transformation_map.deleted_nodes),
            estimated_sessions_affected=estimated_total,
            sessions_by_anchor=sessions_by_anchor,
            warnings=warnings,
            fields_to_collect=fields_to_collect,
        )

    async def approve_plan(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        approved_by: str | None = None,
    ) -> MigrationPlan:
        """Approve a migration plan for deployment.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan to approve
            approved_by: Approver identifier

        Returns:
            Updated plan

        Raises:
            ValueError: If plan not found or not in PENDING status
        """
        plan = await self._config_store.get_migration_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Migration plan {plan_id} not found")

        if plan.status != MigrationPlanStatus.PENDING:
            raise ValueError(f"Plan is not pending (status: {plan.status})")

        plan.status = MigrationPlanStatus.APPROVED
        plan.approved_at = datetime.now(UTC)
        plan.approved_by = approved_by

        await self._config_store.save_migration_plan(plan)

        logger.info(
            "migration_plan_approved",
            plan_id=str(plan_id),
            approved_by=approved_by,
        )

        return plan

    async def reject_plan(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        rejected_by: str | None = None,
        reason: str | None = None,
    ) -> MigrationPlan:
        """Reject a migration plan.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan to reject
            rejected_by: Rejector identifier
            reason: Rejection reason

        Returns:
            Updated plan

        Raises:
            ValueError: If plan not found or not in PENDING status
        """
        plan = await self._config_store.get_migration_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Migration plan {plan_id} not found")

        if plan.status != MigrationPlanStatus.PENDING:
            raise ValueError(f"Plan is not pending (status: {plan.status})")

        plan.status = MigrationPlanStatus.REJECTED

        await self._config_store.save_migration_plan(plan)

        logger.info(
            "migration_plan_rejected",
            plan_id=str(plan_id),
            rejected_by=rejected_by,
            reason=reason,
        )

        return plan

    async def update_policies(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        policies: dict[str, AnchorMigrationPolicy],
    ) -> MigrationPlan:
        """Update per-anchor policies for a migration plan.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan to update
            policies: New policies by anchor hash

        Returns:
            Updated plan

        Raises:
            ValueError: If plan not found or not in PENDING status
        """
        plan = await self._config_store.get_migration_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Migration plan {plan_id} not found")

        if plan.status != MigrationPlanStatus.PENDING:
            raise ValueError(f"Plan is not pending (status: {plan.status})")

        # Validate anchor hashes exist
        valid_hashes = {a.anchor_content_hash for a in plan.transformation_map.anchors}
        for anchor_hash in policies:
            if anchor_hash not in valid_hashes:
                raise ValueError(f"Invalid anchor hash: {anchor_hash}")

        # Update policies
        plan.anchor_policies.update(policies)

        await self._config_store.save_migration_plan(plan)

        logger.info(
            "migration_policies_updated",
            plan_id=str(plan_id),
            policies_updated=len(policies),
        )

        return plan


class MigrationDeployer:
    """Deploys migration plans by marking eligible sessions."""

    def __init__(
        self,
        config_store: "AgentConfigStore",
        session_store: "SessionStore",
        config: ScenarioMigrationConfig | None = None,
    ) -> None:
        """Initialize deployer.

        Args:
            config_store: Store for migration plans
            session_store: Store for session marking
            config: Migration configuration
        """
        self._config_store = config_store
        self._session_store = session_store
        self._config = config or ScenarioMigrationConfig()

    async def deploy(
        self,
        tenant_id: UUID,
        plan_id: UUID,
    ) -> dict[str, Any]:
        """Deploy a migration plan by marking eligible sessions.

        Phase 1 of two-phase deployment: marks sessions with pending_migration.
        Actual migration happens at JIT when customer returns.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan to deploy

        Returns:
            Deployment result with counts

        Raises:
            ValueError: If plan not found or not in APPROVED status
        """
        plan = await self._config_store.get_migration_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Migration plan {plan_id} not found")

        if plan.status != MigrationPlanStatus.APPROVED:
            raise ValueError(f"Plan is not approved (status: {plan.status})")

        marked_count = 0
        sessions_by_anchor: dict[str, int] = {}

        # Mark sessions for each anchor
        for anchor in plan.transformation_map.anchors:
            policy = plan.anchor_policies.get(anchor.anchor_content_hash)
            scope_filter = policy.scope_filter if policy else None

            # Find sessions at this anchor
            sessions = await self._session_store.find_sessions_by_step_hash(
                tenant_id=plan.tenant_id,
                scenario_id=plan.scenario_id,
                scenario_version=plan.from_version,
                step_content_hash=anchor.anchor_content_hash,
                scope_filter=scope_filter,
            )

            anchor_count = 0
            for session in sessions:
                # Skip if already has pending migration
                if session.pending_migration is not None:
                    continue

                # Mark session for migration
                session.pending_migration = PendingMigration(
                    target_version=plan.to_version,
                    anchor_content_hash=anchor.anchor_content_hash,
                    migration_plan_id=plan.id,
                )

                await self._session_store.save(session)
                marked_count += 1
                anchor_count += 1

            sessions_by_anchor[anchor.anchor_content_hash] = anchor_count

        # Update plan status to deployed
        plan.status = MigrationPlanStatus.DEPLOYED
        plan.deployed_at = datetime.now(UTC)

        # Update summary with actual counts
        plan.summary.sessions_by_anchor = sessions_by_anchor
        plan.summary.estimated_sessions_affected = marked_count

        await self._config_store.save_migration_plan(plan)

        logger.info(
            "migration_plan_deployed",
            plan_id=str(plan_id),
            sessions_marked=marked_count,
        )

        return {
            "plan_id": plan_id,
            "sessions_marked": marked_count,
            "sessions_by_anchor": sessions_by_anchor,
            "deployed_at": plan.deployed_at,
        }

    async def get_deployment_status(
        self,
        tenant_id: UUID,
        plan_id: UUID,
    ) -> dict[str, Any]:
        """Get deployment status for a migration plan.

        Args:
            tenant_id: Tenant identifier
            plan_id: Plan to check

        Returns:
            Status dict with counts

        Raises:
            ValueError: If plan not found
        """
        plan = await self._config_store.get_migration_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Migration plan {plan_id} not found")

        # Count sessions still pending vs migrated
        # In a real implementation, we'd track this in the audit store
        # For now, return summary data
        return {
            "plan_id": plan_id,
            "status": plan.status.value,
            "sessions_marked": plan.summary.estimated_sessions_affected,
            "migrations_applied": 0,  # Would come from audit store
            "migrations_pending": plan.summary.estimated_sessions_affected,
            "migrations_by_scenario": {
                "clean_graft": 0,
                "gap_fill": 0,
                "re_route": 0,
            },
            "checkpoint_blocks": 0,
            "deployed_at": plan.deployed_at,
            "last_migration_at": None,
        }

    async def cleanup_old_plans(
        self,
        tenant_id: UUID,
        retention_days: int = 30,
    ) -> int:
        """Clean up old migration plans.

        Removes migration plans that have been deployed for longer
        than the retention period.

        Args:
            tenant_id: Tenant to clean up
            retention_days: Days to retain deployed plans (default 30)

        Returns:
            Number of plans deleted
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        plans = await self._config_store.list_migration_plans(tenant_id=tenant_id)

        deleted = 0
        for plan in plans:
            # Only cleanup deployed/superseded plans older than cutoff
            if plan.status not in (
                MigrationPlanStatus.DEPLOYED,
                MigrationPlanStatus.SUPERSEDED,
            ):
                continue

            if plan.deployed_at and plan.deployed_at < cutoff:
                await self._config_store.delete_migration_plan(tenant_id, plan.id)
                deleted += 1
                logger.info(
                    "migration_plan_cleaned_up",
                    tenant_id=str(tenant_id),
                    plan_id=str(plan.id),
                    deployed_at=plan.deployed_at.isoformat(),
                )

        return deleted
