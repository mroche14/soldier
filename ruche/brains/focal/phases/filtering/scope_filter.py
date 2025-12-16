"""Scope and lifecycle pre-filtering for rules.

Pre-filters rules by scope, enabled status, cooldown, and max fires
before expensive LLM filtering (P5.1).
"""

from uuid import UUID

from ruche.brains.focal.models import Rule
from ruche.brains.focal.models.enums import Scope
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.conversation.models import Session
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ScopePreFilter:
    """Pre-filter rules by scope and lifecycle before LLM filtering.

    Deterministically removes rules that cannot apply based on:
    - enabled status
    - scope matching (GLOBAL, SCENARIO, STEP)
    - cooldown periods
    - max fires per session
    """

    def __init__(self) -> None:
        """Initialize the scope pre-filter."""
        pass

    async def filter(
        self,
        candidates: list[MatchedRule],
        session: Session,
        active_scenario_ids: set[UUID],
        active_step_ids: set[UUID],
        current_turn_number: int,
    ) -> list[MatchedRule]:
        """Filter rules by scope and lifecycle constraints.

        Args:
            candidates: Candidate rules from retrieval/selection
            session: Current session state
            active_scenario_ids: IDs of active scenarios
            active_step_ids: IDs of active steps
            current_turn_number: Current turn number

        Returns:
            Filtered list of rules that pass all pre-filter checks
        """
        if not candidates:
            return []

        filtered = []
        stats = {
            "disabled": 0,
            "scope_mismatch": 0,
            "cooldown": 0,
            "max_fires": 0,
            "passed": 0,
        }

        for candidate in candidates:
            rule = candidate.rule

            # Check enabled
            if not rule.enabled:
                stats["disabled"] += 1
                logger.debug(
                    "rule_filtered_disabled",
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                )
                continue

            # Check scope
            if rule.scope == Scope.SCENARIO:
                if rule.scope_id not in active_scenario_ids:
                    stats["scope_mismatch"] += 1
                    logger.debug(
                        "rule_filtered_scope",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        scope="SCENARIO",
                        scope_id=str(rule.scope_id) if rule.scope_id else None,
                        active_scenarios=[str(sid) for sid in active_scenario_ids],
                    )
                    continue
            elif rule.scope == Scope.STEP:
                if rule.scope_id not in active_step_ids:
                    stats["scope_mismatch"] += 1
                    logger.debug(
                        "rule_filtered_scope",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        scope="STEP",
                        scope_id=str(rule.scope_id) if rule.scope_id else None,
                        active_steps=[str(sid) for sid in active_step_ids],
                    )
                    continue

            # Check cooldown
            last_fire = session.rule_last_fire_turn.get(str(rule.id))
            if last_fire is not None and rule.cooldown_turns > 0:
                turns_since_fire = current_turn_number - last_fire
                if turns_since_fire < rule.cooldown_turns:
                    stats["cooldown"] += 1
                    logger.debug(
                        "rule_filtered_cooldown",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        last_fire_turn=last_fire,
                        current_turn=current_turn_number,
                        turns_since_fire=turns_since_fire,
                        cooldown_turns=rule.cooldown_turns,
                    )
                    continue

            # Check max fires
            fire_count = session.rule_fires.get(str(rule.id), 0)
            if rule.max_fires_per_session > 0 and fire_count >= rule.max_fires_per_session:
                stats["max_fires"] += 1
                logger.debug(
                    "rule_filtered_max_fires",
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    fire_count=fire_count,
                    max_fires=rule.max_fires_per_session,
                )
                continue

            # Passed all checks
            stats["passed"] += 1
            filtered.append(candidate)

        logger.info(
            "scope_prefilter_completed",
            total_candidates=len(candidates),
            disabled=stats["disabled"],
            scope_mismatch=stats["scope_mismatch"],
            cooldown=stats["cooldown"],
            max_fires=stats["max_fires"],
            passed=stats["passed"],
        )

        return filtered
