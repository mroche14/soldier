"""Composite migration for multi-version gaps.

Handles scenarios where customers missed multiple versions (e.g., V1→V5).
Computes net effect across plan chain to avoid asking for obsolete data.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from ruche.alignment.migration.models import (
    AnchorTransformation,
    InsertedNode,
    MigrationPlan,
    MigrationScenario,
    NewFork,
    ReconciliationAction,
    ReconciliationResult,
    UpstreamChanges,
)
from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.alignment.models import Scenario
    from ruche.alignment.stores.agent_config_store import AgentConfigStore
    from ruche.conversation.models import Session

logger = get_logger(__name__)


class CompositeMapper:
    """Map multi-version migrations to a single composite migration.

    When a customer skipped multiple versions (V1→V5), this class:
    1. Loads the chain of migration plans (V1→V2, V2→V3, V3→V4, V4→V5)
    2. Accumulates all data collection requirements
    3. Prunes requirements to only those needed in final version
    4. Executes a single composite migration
    """

    def __init__(self, config_store: "AgentConfigStore") -> None:
        """Initialize the composite mapper.

        Args:
            config_store: Store for migration plans
        """
        self._config_store = config_store

    async def get_plan_chain(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        start_version: int,
        end_version: int,
    ) -> list[MigrationPlan]:
        """Load the chain of migration plans between versions.

        Args:
            tenant_id: Tenant ID
            scenario_id: Scenario ID
            start_version: Customer's current version
            end_version: Target version

        Returns:
            List of MigrationPlans in order (V1→V2, V2→V3, etc.)
        """
        plans: list[MigrationPlan] = []
        current_version = start_version

        while current_version < end_version:
            next_version = current_version + 1

            # Find plan for this version transition
            plan = await self._config_store.get_migration_plan_for_versions(
                tenant_id=tenant_id,
                scenario_id=scenario_id,
                from_version=current_version,
                to_version=next_version,
            )

            if plan is None:
                logger.warning(
                    "plan_chain_broken",
                    tenant_id=str(tenant_id),
                    scenario_id=str(scenario_id),
                    missing_from=current_version,
                    missing_to=next_version,
                )
                break

            plans.append(plan)
            current_version = next_version

        return plans

    def accumulate_requirements(
        self,
        plan_chain: list[MigrationPlan],
        anchor_hash: str,
    ) -> set[str]:
        """Accumulate all data collection requirements across plan chain.

        Args:
            plan_chain: Chain of migration plans
            anchor_hash: Content hash of customer's current anchor

        Returns:
            Set of all field names collected across chain
        """
        all_fields: set[str] = set()

        # Track anchor hash as it evolves through versions
        current_hash = anchor_hash

        for plan in plan_chain:
            # Find anchor in this plan
            anchor = plan.transformation_map.get_anchor_by_hash(current_hash)
            if anchor is None:
                continue

            # Collect fields from upstream nodes
            if anchor.upstream_changes:
                for node in anchor.upstream_changes.inserted_nodes:
                    all_fields.update(node.collects_fields)

            # Update hash for next plan (anchor in V(n+1) has different ID)
            # The content hash should remain the same if it's truly an anchor
            current_hash = anchor.anchor_content_hash

        return all_fields

    def prune_requirements(
        self,
        accumulated_fields: set[str],
        final_plan: MigrationPlan,
        anchor_hash: str,
    ) -> set[str]:
        """Prune requirements to only those needed in final version.

        Removes fields that were needed in intermediate versions but
        were later removed from the flow.

        Args:
            accumulated_fields: All fields collected across chain
            final_plan: The final migration plan (to target version)
            anchor_hash: Content hash of anchor

        Returns:
            Set of fields actually needed in final version
        """
        # Find what fields the final version actually needs
        final_anchor = final_plan.transformation_map.get_anchor_by_hash(anchor_hash)
        if final_anchor is None:
            return accumulated_fields

        # Only keep fields that the final version collects
        final_fields: set[str] = set()
        if final_anchor.upstream_changes:
            for node in final_anchor.upstream_changes.inserted_nodes:
                final_fields.update(node.collects_fields)

        # Return intersection - fields that were accumulated AND are still needed
        return accumulated_fields & final_fields

    async def execute_composite_migration(
        self,
        session: "Session",
        plan_chain: list[MigrationPlan],
        _final_scenario: "Scenario",
        anchor_hash: str,
    ) -> ReconciliationResult:
        """Execute a composite migration across multiple versions.

        Instead of applying V1→V2→V3→V4 migrations sequentially,
        we compute the net effect and apply it in one step.

        Args:
            session: Current session
            plan_chain: Chain of migration plans
            final_scenario: Final scenario version
            anchor_hash: Content hash of customer's current anchor

        Returns:
            ReconciliationResult with composite migration outcome
        """
        if not plan_chain:
            return ReconciliationResult(
                action=ReconciliationAction.CONTINUE,
                teleport_reason="no_plan_chain",
            )

        start_version = plan_chain[0].from_version
        end_version = plan_chain[-1].to_version

        logger.info(
            "executing_composite_migration",
            session_id=str(session.session_id),
            start_version=start_version,
            end_version=end_version,
            chain_length=len(plan_chain),
        )

        # Accumulate all requirements
        all_fields = self.accumulate_requirements(plan_chain, anchor_hash)

        # Prune to only final requirements
        final_plan = plan_chain[-1]
        required_fields = self.prune_requirements(all_fields, final_plan, anchor_hash)

        # Check which required fields are missing
        missing_fields = [f for f in required_fields if f not in session.variables]

        if missing_fields:
            logger.info(
                "composite_migration_collect",
                session_id=str(session.session_id),
                missing_fields=missing_fields,
            )
            return ReconciliationResult(
                action=ReconciliationAction.COLLECT,
                collect_fields=missing_fields,
                user_message=f"Before we continue, I need to collect: {', '.join(missing_fields)}",
            )

        # Find target step in final version
        final_anchor = final_plan.transformation_map.get_anchor_by_hash(anchor_hash)
        if final_anchor is None:
            logger.warning(
                "composite_migration_no_anchor",
                session_id=str(session.session_id),
            )
            return ReconciliationResult(
                action=ReconciliationAction.CONTINUE,
                teleport_reason="composite_no_anchor",
            )

        target_step_id = final_anchor.anchor_node_id_v2

        logger.info(
            "composite_migration_teleport",
            session_id=str(session.session_id),
            target_step=str(target_step_id),
            from_version=start_version,
            to_version=end_version,
        )

        return ReconciliationResult(
            action=ReconciliationAction.TELEPORT,
            target_step_id=target_step_id,
            teleport_reason=f"composite_v{start_version}_to_v{end_version}",
        )

    async def build_composite_transformation(
        self,
        plan_chain: list[MigrationPlan],
        anchor_hash: str,
    ) -> AnchorTransformation | None:
        """Build a synthetic transformation representing net effect.

        Useful for representing the composite migration in a single
        transformation object.

        Args:
            plan_chain: Chain of migration plans
            anchor_hash: Content hash of anchor

        Returns:
            Synthetic AnchorTransformation or None
        """
        if not plan_chain:
            return None

        # Get first and last anchors
        first_anchor = plan_chain[0].transformation_map.get_anchor_by_hash(anchor_hash)
        last_anchor = plan_chain[-1].transformation_map.get_anchor_by_hash(anchor_hash)

        if first_anchor is None or last_anchor is None:
            return None

        # Accumulate all upstream changes
        all_inserted_nodes: list[InsertedNode] = []
        all_new_forks: list[NewFork] = []

        for plan in plan_chain:
            anchor = plan.transformation_map.get_anchor_by_hash(anchor_hash)
            if anchor and anchor.upstream_changes:
                all_inserted_nodes.extend(anchor.upstream_changes.inserted_nodes)
                all_new_forks.extend(anchor.upstream_changes.new_forks)

        # Prune to what's actually in final version
        final_fields = set()
        if last_anchor.upstream_changes:
            for node in last_anchor.upstream_changes.inserted_nodes:
                final_fields.update(node.collects_fields)

        # Filter nodes to only those collecting final fields
        pruned_nodes = [
            node
            for node in all_inserted_nodes
            if any(f in final_fields for f in node.collects_fields)
        ]

        # Build composite transformation
        return AnchorTransformation(
            anchor_name=first_anchor.anchor_name,
            anchor_content_hash=anchor_hash,
            anchor_node_id_v1=first_anchor.anchor_node_id_v1,
            anchor_node_id_v2=last_anchor.anchor_node_id_v2,
            migration_scenario=self._determine_composite_scenario(plan_chain, anchor_hash),
            upstream_changes=UpstreamChanges(
                inserted_nodes=pruned_nodes,
                removed_node_ids=[],  # Composite doesn't track intermediate removals
                new_forks=all_new_forks,
            ),
        )

    def _determine_composite_scenario(
        self,
        plan_chain: list[MigrationPlan],
        anchor_hash: str,
    ) -> MigrationScenario:
        """Determine the most appropriate scenario for composite migration.

        Uses the "highest priority" scenario from the chain:
        RE_ROUTE > GAP_FILL > CLEAN_GRAFT

        Args:
            plan_chain: Chain of migration plans
            anchor_hash: Content hash of anchor

        Returns:
            MigrationScenario for composite migration
        """
        scenarios: list[MigrationScenario] = []

        for plan in plan_chain:
            anchor = plan.transformation_map.get_anchor_by_hash(anchor_hash)
            if anchor:
                scenarios.append(anchor.migration_scenario)

        # Priority order
        if MigrationScenario.RE_ROUTE in scenarios:
            return MigrationScenario.RE_ROUTE
        if MigrationScenario.GAP_FILL in scenarios:
            return MigrationScenario.GAP_FILL
        return MigrationScenario.CLEAN_GRAFT
