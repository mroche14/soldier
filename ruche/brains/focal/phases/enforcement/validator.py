"""Response enforcement for hard constraints."""

import time
from typing import TYPE_CHECKING
from uuid import UUID

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.enforcement.models import ConstraintViolation, EnforcementResult
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.models import Rule, Scope
from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.brains.focal.stores.agent_config_store import AgentConfigStore

logger = get_logger(__name__)


class EnforcementValidator:
    """Validate responses against hard constraint rules.

    Hard constraints are rules that must be satisfied for every response.
    When violations are detected, the validator can:
    1. Attempt to regenerate the response with stronger instructions
    2. Pass to FallbackHandler for template-based recovery

    CRITICAL: This validator ALWAYS enforces GLOBAL hard constraints,
    even if they weren't matched during retrieval. This prevents
    safety gaps where global guardrails are bypassed.
    """

    def __init__(
        self,
        response_generator: ResponseGenerator,
        agent_config_store: "AgentConfigStore",
        max_retries: int = 1,
        always_enforce_global: bool = True,
    ) -> None:
        """Initialize the enforcement validator.

        Args:
            response_generator: Generator for response regeneration
            agent_config_store: Store for fetching GLOBAL hard constraints
            max_retries: Maximum regeneration attempts on violation
            always_enforce_global: If True, always fetch and enforce GLOBAL hard constraints
        """
        self._response_generator = response_generator
        self._agent_config_store = agent_config_store
        self._max_retries = max_retries
        self._always_enforce_global = always_enforce_global

    async def validate(
        self,
        response: str,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        tenant_id: UUID,
        agent_id: UUID,
        hard_rules: list[Rule] | None = None,
    ) -> EnforcementResult:
        """Validate response against hard constraints.

        CRITICAL: This method ALWAYS enforces GLOBAL hard constraints,
        even if they weren't in matched_rules. This prevents safety gaps.

        Args:
            response: Generated response to validate
            snapshot: Situation snapshot
            matched_rules: Rules that matched this turn
            tenant_id: Tenant ID for fetching GLOBAL constraints
            agent_id: Agent ID for fetching GLOBAL constraints
            hard_rules: Deprecated - now fetches GLOBAL constraints automatically

        Returns:
            EnforcementResult with validation status and final response
        """
        start_time = time.perf_counter()

        # Collect all hard constraints to enforce
        all_hard_rules = await self._get_rules_to_enforce(
            matched_rules=matched_rules,
            tenant_id=tenant_id,
            agent_id=agent_id,
            hard_rules=hard_rules,
        )

        logger.debug(
            "enforcement_rules_collected",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            matched_hard_rules=sum(1 for m in matched_rules if m.rule.is_hard_constraint),
            total_hard_rules=len(all_hard_rules),
        )

        violations = self._detect_violations(response, all_hard_rules)

        if not violations:
            return EnforcementResult(
                passed=True,
                violations=[],
                final_response=response,
                regeneration_attempted=False,
                regeneration_succeeded=False,
                fallback_used=False,
            )

        regenerated_response = response
        regeneration_succeeded = False
        regeneration_attempted = False

        if self._max_retries > 0:
            regeneration_attempted = True
            regenerated_response = await self._regenerate(
                snapshot=snapshot,
                matched_rules=matched_rules,
                response=response,
            )
            regeneration_succeeded = bool(regenerated_response)
            if regeneration_succeeded:
                # Re-run violations on regenerated output
                violations = self._detect_violations(regenerated_response, all_hard_rules)

        return EnforcementResult(
            passed=not violations,
            violations=violations,
            regeneration_attempted=regeneration_attempted,
            regeneration_succeeded=regeneration_succeeded,
            fallback_used=False,
            final_response=regenerated_response if not violations else response,
            enforcement_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    async def _get_rules_to_enforce(
        self,
        matched_rules: list[MatchedRule],
        tenant_id: UUID,
        agent_id: UUID,
        hard_rules: list[Rule] | None = None,
    ) -> list[Rule]:
        """Get all hard constraints that must be enforced.

        CRITICAL: This method fetches GLOBAL hard constraints even if
        they weren't matched during retrieval. This prevents safety gaps.

        Args:
            matched_rules: Rules that matched this turn
            tenant_id: Tenant ID
            agent_id: Agent ID
            hard_rules: Deprecated - for backward compatibility

        Returns:
            List of all hard constraint rules to enforce
        """
        rules: list[Rule] = []
        matched_ids: set[UUID] = set()

        # 1. Add hard constraints from matched rules
        for matched in matched_rules:
            if matched.rule.is_hard_constraint:
                rules.append(matched.rule)
                matched_ids.add(matched.rule.id)

        # 2. CRITICAL: Add ALL GLOBAL hard constraints (always enforce)
        if self._always_enforce_global:
            try:
                global_rules = await self._agent_config_store.get_rules(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    scope=Scope.GLOBAL,
                    enabled_only=True,
                )

                # Filter to hard constraints only and avoid duplicates
                for rule in global_rules:
                    if rule.is_hard_constraint and rule.id not in matched_ids:
                        rules.append(rule)
                        matched_ids.add(rule.id)

                logger.info(
                    "enforcement_global_constraints_added",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    global_hard_count=sum(1 for r in global_rules if r.is_hard_constraint),
                    already_matched=len(
                        [r for r in rules if r.id in {m.rule.id for m in matched_rules}]
                    ),
                    newly_added=len(rules)
                    - sum(1 for m in matched_rules if m.rule.is_hard_constraint),
                )

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "enforcement_failed_to_fetch_global_constraints",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    error=str(e),
                )

        # 3. Backward compatibility: add any hard_rules passed in
        if hard_rules:
            for rule in hard_rules:
                if rule.id not in matched_ids:
                    rules.append(rule)
                    matched_ids.add(rule.id)

        return rules

    async def _regenerate(
        self,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        response: str,
    ) -> str:
        """Regenerate a response with a stronger instruction prompt."""
        try:
            regen = await self._response_generator.generate(
                snapshot=snapshot,
                matched_rules=matched_rules,
                history=[],
                tool_results=None,
                memory_context=None,
                templates=None,
                variables={"previous_response": response},
            )
            return regen.response
        except Exception as exc:  # noqa: BLE001
            logger.warning("enforcement_regeneration_failed", error=str(exc))
            return ""

    def _detect_violations(
        self,
        response: str,
        hard_rules: list[Rule],
    ) -> list[ConstraintViolation]:
        """Simple text-based violation detection against hard rules."""
        violations: list[ConstraintViolation] = []
        lower_response = response.lower()
        for rule in hard_rules:
            if rule.is_hard_constraint and any(
                phrase in lower_response for phrase in self._extract_phrases(rule)
            ):
                violations.append(
                    ConstraintViolation(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        violation_type="contains_prohibited",
                        details=f"Response triggered hard constraint: {rule.name}",
                    )
                )
        return violations

    def _extract_phrases(self, rule: Rule) -> list[str]:
        """Extract simple prohibited phrases from a rule's action text."""
        if not rule.action_text:
            return []
        return [rule.action_text.lower()]
