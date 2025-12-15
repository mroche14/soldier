"""Migration executor for JIT session migration.

Applies migration scenarios (clean graft, gap fill, re-route) when
customers return after a scenario version change.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ruche.brains.focal.migration.composite import CompositeMapper
from ruche.brains.focal.migration.diff import (
    compute_node_content_hash,
    compute_scenario_checksum,
)
from ruche.brains.focal.migration.field_resolver import MissingFieldResolver
from ruche.brains.focal.migration.models import (
    AnchorTransformation,
    MigrationPlan,
    MigrationScenario,
    ReconciliationAction,
    ReconciliationResult,
)
from ruche.config.models.migration import ScenarioMigrationConfig
from ruche.conversation.models import Session, StepVisit
from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.brains.focal.models import Scenario
    from ruche.brains.focal.stores.agent_config_store import AgentConfigStore
    from ruche.conversation.store import SessionStore
    from ruche.memory.profile import InterlocutorDataStoreInterface

logger = get_logger(__name__)


class MigrationExecutor:
    """Execute JIT migrations for sessions with pending migrations.

    Handles three migration scenarios:
    - Clean Graft: Silent teleport to equivalent V2 step
    - Gap Fill: Collect missing data before teleport
    - Re-Route: Evaluate upstream fork and potentially block at checkpoint
    """

    def __init__(
        self,
        config_store: "AgentConfigStore",
        session_store: "SessionStore",
        config: ScenarioMigrationConfig | None = None,
        profile_store: "InterlocutorDataStoreInterface | None" = None,
        llm_executor: Any = None,
    ) -> None:
        """Initialize the migration executor.

        Args:
            config_store: Store for scenarios and migration plans
            session_store: Store for sessions
            config: Migration configuration
            profile_store: Optional profile store for gap fill
            llm_executor: Optional LLM executor for conversation extraction
        """
        self._config_store = config_store
        self._session_store = session_store
        self._config = config or ScenarioMigrationConfig()
        self._composite_mapper = CompositeMapper(config_store)
        self._missing_field_resolver = MissingFieldResolver(
            profile_store=profile_store,
            llm_executor=llm_executor,
        )

    async def reconcile(
        self,
        session: Session,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Perform pre-turn reconciliation for a session.

        Checks for pending migrations or version mismatches and applies
        the appropriate migration scenario.

        Args:
            session: Current session
            current_scenario: Current version of the scenario

        Returns:
            ReconciliationResult indicating what action to take
        """
        # Check if no migration needed
        if (
            session.pending_migration is None
            and session.active_scenario_version == current_scenario.version
        ):
            return ReconciliationResult(action=ReconciliationAction.CONTINUE)

        # Check for version mismatch without pending_migration flag (late arrival)
        if session.pending_migration is None:
            logger.info(
                "version_mismatch_detected",
                session_id=str(session.session_id),
                session_version=session.active_scenario_version,
                current_version=current_scenario.version,
            )
            return await self._fallback_reconciliation(session, current_scenario)

        # Load migration plan
        plan = await self._config_store.get_migration_plan(
            session.tenant_id,
            session.pending_migration.migration_plan_id,
        )

        if plan is None:
            logger.warning(
                "migration_plan_not_found",
                session_id=str(session.session_id),
                plan_id=str(session.pending_migration.migration_plan_id),
            )
            return await self._fallback_reconciliation(session, current_scenario)

        # Check for multi-version gap (customer missed multiple updates)
        anchor_hash = session.pending_migration.anchor_content_hash
        if plan.to_version < current_scenario.version:
            logger.info(
                "multi_version_gap_detected",
                session_id=str(session.session_id),
                plan_to_version=plan.to_version,
                current_version=current_scenario.version,
            )
            return await self._execute_composite_migration(
                session=session,
                start_version=plan.from_version,
                end_version=current_scenario.version,
                anchor_hash=anchor_hash,
                current_scenario=current_scenario,
            )

        # Find the anchor transformation for this session
        anchor_transform = self._find_anchor_transformation(plan, anchor_hash)

        if anchor_transform is None:
            logger.warning(
                "anchor_transformation_not_found",
                session_id=str(session.session_id),
                anchor_hash=anchor_hash,
            )
            return await self._fallback_reconciliation(session, current_scenario)

        # Execute based on migration scenario
        result = await self._execute_migration(session, plan, anchor_transform, current_scenario)

        # Clear pending migration and update checksum on success
        if result.action in (
            ReconciliationAction.CONTINUE,
            ReconciliationAction.TELEPORT,
        ):
            await self._finalize_migration(session, current_scenario)

        return result

    async def _execute_migration(
        self,
        session: Session,
        plan: MigrationPlan,
        anchor_transform: AnchorTransformation,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Execute migration based on the scenario type.

        Args:
            session: Current session
            plan: Migration plan
            anchor_transform: Transformation for this anchor
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with migration outcome
        """
        # Get policy for this anchor
        anchor_hash = anchor_transform.anchor_content_hash
        policy = plan.anchor_policies.get(anchor_hash)

        # Check update_downstream=false - skip teleport, just update version
        if policy and not policy.update_downstream:
            logger.info(
                "skip_downstream_update",
                session_id=str(session.session_id),
                anchor_name=anchor_transform.anchor_name,
            )
            # Update version only, keep at current step
            session.active_scenario_version = current_scenario.version
            await self._session_store.save(session)
            return ReconciliationResult(
                action=ReconciliationAction.CONTINUE,
                teleport_reason="update_downstream_false",
            )

        # Determine scenario - use force_scenario if set, otherwise computed
        scenario = anchor_transform.migration_scenario
        if policy and policy.force_scenario:
            try:
                scenario = MigrationScenario(policy.force_scenario)
                logger.info(
                    "force_scenario_applied",
                    session_id=str(session.session_id),
                    original=anchor_transform.migration_scenario.value,
                    forced=scenario.value,
                )
            except ValueError:
                logger.warning(
                    "invalid_force_scenario",
                    session_id=str(session.session_id),
                    force_scenario=policy.force_scenario,
                )

        logger.info(
            "executing_migration",
            session_id=str(session.session_id),
            scenario=scenario.value,
            anchor_name=anchor_transform.anchor_name,
        )

        if scenario == MigrationScenario.CLEAN_GRAFT:
            return await self._execute_clean_graft(session, anchor_transform, current_scenario)
        elif scenario == MigrationScenario.GAP_FILL:
            return await self._execute_gap_fill(session, anchor_transform, current_scenario)
        elif scenario == MigrationScenario.RE_ROUTE:
            return await self._execute_re_route(session, anchor_transform, current_scenario)
        else:
            logger.error(
                "unknown_migration_scenario",
                session_id=str(session.session_id),
                scenario=scenario.value,
            )
            return await self._fallback_reconciliation(session, current_scenario)

    async def _execute_clean_graft(
        self,
        session: Session,
        anchor_transform: AnchorTransformation,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Execute clean graft migration - silent teleport to V2 anchor.

        This is the simplest migration: customer was at a step that exists
        identically in the new version. Just update the step ID.

        Args:
            session: Current session
            anchor_transform: Transformation for this anchor
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with TELEPORT action
        """
        target_step_id = anchor_transform.anchor_node_id_v2

        logger.info(
            "clean_graft_teleport",
            session_id=str(session.session_id),
            from_step=str(session.active_step_id),
            to_step=str(target_step_id),
        )

        # Update session step
        await self._teleport_session(
            session=session,
            target_step_id=target_step_id,
            reason="clean_graft",
            scenario_version=current_scenario.version,
        )

        return ReconciliationResult(
            action=ReconciliationAction.TELEPORT,
            target_step_id=target_step_id,
            teleport_reason="clean_graft",
        )

    async def _execute_gap_fill(
        self,
        session: Session,
        anchor_transform: AnchorTransformation,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Execute gap fill migration - collect missing data then teleport.

        Upstream nodes in V2 collect data that the customer hasn't provided.
        We try to fill from profile/history before asking the customer.

        Args:
            session: Current session
            anchor_transform: Transformation for this anchor
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with COLLECT or TELEPORT action
        """
        # Collect all fields that upstream nodes need
        required_fields: list[str] = []
        for node in anchor_transform.upstream_changes.inserted_nodes:
            for field in node.collects_fields:
                if field not in required_fields:
                    required_fields.append(field)

        # Try to fill missing fields using MissingFieldResolver
        still_missing: list[str] = []
        filled_results = []

        for field in required_fields:
            # Check session first (fast path)
            if field in session.variables:
                continue

            # Try gap fill service
            result = await self._missing_field_resolver.fill_gap(
                field_name=field,
                session=session,
            )

            if result.filled:
                # Add to session variables for this turn
                session.variables[field] = result.value
                filled_results.append(result)
                logger.info(
                    "gap_fill_auto_filled",
                    session_id=str(session.session_id),
                    field_name=field,
                    source=result.source.value,
                    confidence=result.confidence,
                )
            else:
                still_missing.append(field)

        # Persist any extracted values to profile
        if filled_results:
            await self._missing_field_resolver.persist_extracted_values(
                session=session,
                results=filled_results,
            )

        if still_missing:
            logger.info(
                "gap_fill_collect_required",
                session_id=str(session.session_id),
                missing_fields=still_missing,
            )
            return ReconciliationResult(
                action=ReconciliationAction.COLLECT,
                collect_fields=still_missing,
                user_message=f"Before we continue, I need to collect some information: {', '.join(still_missing)}",
            )

        # All fields filled - can teleport
        target_step_id = anchor_transform.anchor_node_id_v2

        logger.info(
            "gap_fill_teleport",
            session_id=str(session.session_id),
            to_step=str(target_step_id),
            auto_filled_count=len(filled_results),
        )

        await self._teleport_session(
            session=session,
            target_step_id=target_step_id,
            reason="gap_fill",
            scenario_version=current_scenario.version,
        )

        return ReconciliationResult(
            action=ReconciliationAction.TELEPORT,
            target_step_id=target_step_id,
            teleport_reason="gap_fill",
        )

    async def _execute_re_route(
        self,
        session: Session,
        anchor_transform: AnchorTransformation,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Execute re-route migration - evaluate fork and check checkpoints.

        An upstream fork was added that may redirect the customer to a
        different branch. We need to evaluate where they should go and
        check if any checkpoints block the teleport.

        Args:
            session: Current session
            anchor_transform: Transformation for this anchor
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with appropriate action
        """
        # Check for blocking checkpoints
        checkpoint_info = self._find_last_checkpoint(session)
        if checkpoint_info:
            # Check if target is upstream of checkpoint (would require backtracking)
            anchor_target = anchor_transform.anchor_node_id_v2
            if self._is_upstream_of_checkpoint(
                current_scenario, anchor_target, checkpoint_info.step_id
            ):
                logger.warning(
                    "checkpoint_blocks_migration",
                    session_id=str(session.session_id),
                    checkpoint_step=str(checkpoint_info.step_id),
                    target_step=str(anchor_target),
                )
                return ReconciliationResult(
                    action=ReconciliationAction.CONTINUE,
                    blocked_by_checkpoint=True,
                    checkpoint_warning=f"Cannot migrate past checkpoint: {checkpoint_info.checkpoint_description}",
                )

        # Evaluate fork conditions to determine target
        target_step_id = await self._evaluate_fork_target(
            session, anchor_transform, current_scenario
        )

        if target_step_id is None:
            # No valid target from fork evaluation - stay at current position
            logger.warning(
                "re_route_no_valid_target",
                session_id=str(session.session_id),
            )
            return ReconciliationResult(
                action=ReconciliationAction.CONTINUE,
                user_message="We need some additional information to continue.",
            )

        logger.info(
            "re_route_teleport",
            session_id=str(session.session_id),
            to_step=str(target_step_id),
        )

        await self._teleport_session(
            session=session,
            target_step_id=target_step_id,
            reason="re_route",
            scenario_version=current_scenario.version,
        )

        return ReconciliationResult(
            action=ReconciliationAction.TELEPORT,
            target_step_id=target_step_id,
            teleport_reason="re_route",
        )

    async def _execute_composite_migration(
        self,
        session: Session,
        start_version: int,
        end_version: int,
        anchor_hash: str,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Execute composite migration for multi-version gaps.

        When a customer skipped multiple versions, we use CompositeMapper
        to compute the net effect and apply a single migration.

        Args:
            session: Current session
            start_version: Customer's original version
            end_version: Target version
            anchor_hash: Content hash of anchor
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with composite migration outcome
        """
        # Load the plan chain
        plan_chain = await self._composite_mapper.get_plan_chain(
            tenant_id=session.tenant_id,
            scenario_id=current_scenario.id,
            start_version=start_version,
            end_version=end_version,
        )

        if not plan_chain:
            logger.warning(
                "composite_migration_no_plan_chain",
                session_id=str(session.session_id),
                start_version=start_version,
                end_version=end_version,
            )
            return await self._fallback_reconciliation(session, current_scenario)

        # Execute composite migration
        result = await self._composite_mapper.execute_composite_migration(
            session=session,
            plan_chain=plan_chain,
            _final_scenario=current_scenario,
            anchor_hash=anchor_hash,
        )

        # If teleporting, update the session
        if result.action == ReconciliationAction.TELEPORT and result.target_step_id:
            await self._teleport_session(
                session=session,
                target_step_id=result.target_step_id,
                reason=result.teleport_reason or "composite",
                scenario_version=end_version,
            )
            await self._finalize_migration(session, current_scenario)

        return result

    async def _fallback_reconciliation(
        self,
        session: Session,
        current_scenario: "Scenario",
    ) -> ReconciliationResult:
        """Handle reconciliation when no migration plan exists.

        Uses content hashing to find the best matching step in the
        current scenario version.

        Args:
            session: Current session
            current_scenario: Current scenario version

        Returns:
            ReconciliationResult with TELEPORT or EXIT action
        """
        logger.info(
            "fallback_reconciliation",
            session_id=str(session.session_id),
            scenario_id=str(current_scenario.id),
        )

        # Try to find matching step by content hash
        if session.active_step_id:
            # Get the old step's content hash from step history
            current_step_hash = None
            for visit in reversed(session.step_history):
                if visit.step_id == session.active_step_id:
                    current_step_hash = visit.step_content_hash
                    break

            if current_step_hash:
                # Find step in new version with same hash
                for step in current_scenario.steps:
                    step_hash = compute_node_content_hash(step)
                    if step_hash == current_step_hash:
                        logger.info(
                            "fallback_found_matching_step",
                            session_id=str(session.session_id),
                            step_id=str(step.id),
                        )
                        await self._teleport_session(
                            session=session,
                            target_step_id=step.id,
                            reason="fallback_hash_match",
                            scenario_version=current_scenario.version,
                        )
                        return ReconciliationResult(
                            action=ReconciliationAction.TELEPORT,
                            target_step_id=step.id,
                            teleport_reason="fallback_hash_match",
                        )

        # No matching step found - relocalize to entry step
        entry_step_id = current_scenario.entry_step_id

        if entry_step_id:
            logger.info(
                "fallback_relocalize_to_entry",
                session_id=str(session.session_id),
                entry_step=str(entry_step_id),
            )
            await self._teleport_session(
                session=session,
                target_step_id=entry_step_id,
                reason="fallback_entry",
                scenario_version=current_scenario.version,
            )
            return ReconciliationResult(
                action=ReconciliationAction.TELEPORT,
                target_step_id=entry_step_id,
                teleport_reason="fallback_entry",
            )

        # No valid target - exit scenario
        logger.warning(
            "fallback_exit_scenario",
            session_id=str(session.session_id),
        )
        session.active_scenario_id = None
        session.active_step_id = None
        session.active_scenario_version = None
        await self._session_store.save(session)

        return ReconciliationResult(
            action=ReconciliationAction.EXIT_SCENARIO,
            user_message="We've updated our process. Let me help you get started fresh.",
        )

    async def _teleport_session(
        self,
        session: Session,
        target_step_id: UUID,
        reason: str,
        scenario_version: int,
    ) -> None:
        """Update session to new step.

        Args:
            session: Session to update
            target_step_id: New step ID
            reason: Why we're teleporting
            scenario_version: New scenario version
        """
        now = datetime.now(UTC)

        # Update session state
        session.active_step_id = target_step_id
        session.active_scenario_version = scenario_version

        # Add step visit
        session.step_history.append(
            StepVisit(
                step_id=target_step_id,
                entered_at=now,
                turn_number=session.turn_count,
                transition_reason=f"migration:{reason}",
                confidence=1.0,
            )
        )

        await self._session_store.save(session)

    async def _finalize_migration(
        self,
        session: Session,
        current_scenario: "Scenario",
    ) -> None:
        """Clear pending migration and update scenario checksum.

        Args:
            session: Session to finalize
            current_scenario: Current scenario version
        """
        session.pending_migration = None
        session.scenario_checksum = compute_scenario_checksum(current_scenario)
        await self._session_store.save(session)

        logger.info(
            "migration_finalized",
            session_id=str(session.session_id),
            new_checksum=session.scenario_checksum,
        )

    def _find_anchor_transformation(
        self,
        plan: MigrationPlan,
        anchor_hash: str,
    ) -> AnchorTransformation | None:
        """Find anchor transformation by content hash.

        Args:
            plan: Migration plan
            anchor_hash: Content hash to find

        Returns:
            AnchorTransformation if found, None otherwise
        """
        for anchor in plan.transformation_map.anchors:
            if anchor.anchor_content_hash == anchor_hash:
                return anchor
        return None

    def _find_last_checkpoint(self, session: Session) -> StepVisit | None:
        """Find the last checkpoint passed by the customer.

        Args:
            session: Current session

        Returns:
            StepVisit for the last checkpoint, or None
        """
        for visit in reversed(session.step_history):
            if visit.is_checkpoint:
                return visit
        return None

    def _is_upstream_of_checkpoint(
        self,
        scenario: "Scenario",
        target_step_id: UUID,
        checkpoint_step_id: UUID,
    ) -> bool:
        """Check if target step is upstream of checkpoint.

        If true, teleporting would mean going "backwards" past the checkpoint.

        Args:
            scenario: Current scenario
            target_step_id: Where we want to teleport
            checkpoint_step_id: The checkpoint step

        Returns:
            True if target is upstream of checkpoint
        """
        # Build reverse adjacency list
        reverse_adj: dict[UUID, list[UUID]] = {}
        for step in scenario.steps:
            for transition in step.transitions:
                if transition.to_step_id not in reverse_adj:
                    reverse_adj[transition.to_step_id] = []
                reverse_adj[transition.to_step_id].append(step.id)

        # BFS from checkpoint backwards to see if we reach target
        visited: set[UUID] = set()
        queue = [checkpoint_step_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current == target_step_id:
                return True

            for predecessor in reverse_adj.get(current, []):
                if predecessor not in visited:
                    queue.append(predecessor)

        return False

    async def _evaluate_fork_target(
        self,
        session: Session,
        anchor_transform: AnchorTransformation,
        _current_scenario: "Scenario",
    ) -> UUID | None:
        """Evaluate fork conditions to determine target step.

        For re-route scenarios, we need to evaluate the new fork's conditions
        based on the customer's profile to determine where they should go.

        Args:
            session: Current session
            anchor_transform: Transformation with fork info
            current_scenario: Current scenario

        Returns:
            Target step ID or None if no valid target
        """
        # For now, use simple variable matching for fork evaluation
        # In a full implementation, this would use the LLM to evaluate conditions

        for fork in anchor_transform.upstream_changes.new_forks:
            for branch in fork.branches:
                # Check if branch condition fields are satisfied
                if branch.condition_fields:
                    all_present = all(
                        field in session.variables for field in branch.condition_fields
                    )
                    if all_present:
                        return branch.target_step_id

        # Default to anchor if no fork branch matched
        return anchor_transform.anchor_node_id_v2
