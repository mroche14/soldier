"""Response enforcement with two-lane dispatch.

Lane 1: Deterministic - Rules with enforcement_expression use simpleeval
Lane 2: Subjective - Rules without expression use LLM-as-Judge
"""

import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.enforcement.deterministic_enforcer import DeterministicEnforcer
from ruche.brains.focal.phases.enforcement.models import ConstraintViolation, EnforcementResult
from ruche.brains.focal.phases.enforcement.subjective_enforcer import SubjectiveEnforcer
from ruche.brains.focal.phases.enforcement.variable_extractor import VariableExtractor
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.config.models.pipeline import EnforcementConfig
from ruche.conversation.models import Session
from ruche.domain.rules.models import Rule, Scope
from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.brains.focal.stores.agent_config_store import AgentConfigStore
    from ruche.infrastructure.providers.llm import LLMExecutor

logger = get_logger(__name__)


class EnforcementValidator:
    """Validate responses against hard constraint rules using two-lane dispatch.

    Two-lane enforcement:
    - Lane 1 (Deterministic): Rules with enforcement_expression are evaluated
      using simpleeval with variables extracted from the response/session/profile.
    - Lane 2 (Subjective): Rules without enforcement_expression are evaluated
      using LLM-as-Judge to check compliance with action_text.

    CRITICAL: This validator ALWAYS enforces GLOBAL hard constraints,
    even if they weren't matched during retrieval. This prevents
    safety gaps where global guardrails are bypassed.
    """

    def __init__(
        self,
        response_generator: ResponseGenerator,
        agent_config_store: "AgentConfigStore",
        llm_executor: "LLMExecutor",
        config: EnforcementConfig | None = None,
    ) -> None:
        """Initialize the enforcement validator.

        Args:
            response_generator: Generator for response regeneration
            agent_config_store: Store for fetching GLOBAL hard constraints
            llm_executor: LLM executor for subjective enforcement
            config: Enforcement configuration
        """
        self._response_generator = response_generator
        self._agent_config_store = agent_config_store
        self._config = config or EnforcementConfig()

        # Initialize enforcers
        self._deterministic_enforcer = DeterministicEnforcer()
        self._subjective_enforcer = SubjectiveEnforcer(
            llm_executor=llm_executor,
            config=self._config,
        )
        self._variable_extractor = VariableExtractor()

    async def validate(
        self,
        response: str,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        tenant_id: UUID,
        agent_id: UUID,
        session: Session | None = None,
        profile_variables: dict[str, Any] | None = None,
    ) -> EnforcementResult:
        """Validate response against hard constraints using two-lane dispatch.

        CRITICAL: This method ALWAYS enforces GLOBAL hard constraints,
        even if they weren't in matched_rules. This prevents safety gaps.

        Args:
            response: Generated response to validate
            snapshot: Situation snapshot
            matched_rules: Rules that matched this turn
            tenant_id: Tenant ID for fetching GLOBAL constraints
            agent_id: Agent ID for fetching GLOBAL constraints
            session: Optional session for variable extraction
            profile_variables: Optional profile variables for expression evaluation

        Returns:
            EnforcementResult with validation status and final response
        """
        start_time = time.perf_counter()

        # Collect all hard constraints to enforce
        all_hard_rules = await self._get_rules_to_enforce(
            matched_rules=matched_rules,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        if not all_hard_rules:
            logger.debug(
                "enforcement_no_hard_rules",
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
            )
            return EnforcementResult(
                passed=True,
                violations=[],
                final_response=response,
                regeneration_attempted=False,
                regeneration_succeeded=False,
                fallback_used=False,
            )

        # Partition rules into two lanes
        lane1_rules: list[Rule] = []  # Deterministic (has enforcement_expression)
        lane2_rules: list[Rule] = []  # Subjective (no expression)

        for rule in all_hard_rules:
            if rule.enforcement_expression:
                lane1_rules.append(rule)
            else:
                lane2_rules.append(rule)

        logger.info(
            "enforcement_rules_partitioned",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            lane1_count=len(lane1_rules),
            lane2_count=len(lane2_rules),
            total_hard_rules=len(all_hard_rules),
        )

        # Extract variables for deterministic enforcement
        variables = self._extract_variables(
            response=response,
            session=session,
            profile_variables=profile_variables,
        )

        # Run two-lane enforcement
        violations = await self._enforce_two_lanes(
            response=response,
            lane1_rules=lane1_rules,
            lane2_rules=lane2_rules,
            variables=variables,
        )

        if not violations:
            return EnforcementResult(
                passed=True,
                violations=[],
                final_response=response,
                regeneration_attempted=False,
                regeneration_succeeded=False,
                fallback_used=False,
                enforcement_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Attempt regeneration if configured
        regenerated_response = response
        regeneration_succeeded = False
        regeneration_attempted = False

        if self._config.max_retries > 0:
            regeneration_attempted = True
            regenerated_response = await self._regenerate(
                snapshot=snapshot,
                matched_rules=matched_rules,
                response=response,
                violations=violations,
            )
            regeneration_succeeded = bool(regenerated_response)

            if regeneration_succeeded:
                # Re-extract variables from regenerated response
                new_variables = self._extract_variables(
                    response=regenerated_response,
                    session=session,
                    profile_variables=profile_variables,
                )
                # Re-run violations on regenerated output
                violations = await self._enforce_two_lanes(
                    response=regenerated_response,
                    lane1_rules=lane1_rules,
                    lane2_rules=lane2_rules,
                    variables=new_variables,
                )

        return EnforcementResult(
            passed=not violations,
            violations=violations,
            regeneration_attempted=regeneration_attempted,
            regeneration_succeeded=regeneration_succeeded and not violations,
            fallback_used=False,
            final_response=regenerated_response if not violations else response,
            enforcement_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    async def _get_rules_to_enforce(
        self,
        matched_rules: list[MatchedRule],
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Rule]:
        """Get all hard constraints that must be enforced.

        CRITICAL: This method fetches GLOBAL hard constraints even if
        they weren't matched during retrieval. This prevents safety gaps.

        Args:
            matched_rules: Rules that matched this turn
            tenant_id: Tenant ID
            agent_id: Agent ID

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
        if self._config.always_enforce_global:
            try:
                global_rules = await self._agent_config_store.get_rules(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    scope=Scope.GLOBAL,
                    enabled_only=True,
                )

                # Filter to hard constraints only and avoid duplicates
                global_hard_count = 0
                for rule in global_rules:
                    if rule.is_hard_constraint:
                        global_hard_count += 1
                        if rule.id not in matched_ids:
                            rules.append(rule)
                            matched_ids.add(rule.id)

                logger.info(
                    "enforcement_global_constraints_added",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    global_hard_count=global_hard_count,
                    newly_added=len(rules) - sum(
                        1 for m in matched_rules if m.rule.is_hard_constraint
                    ),
                )

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "enforcement_failed_to_fetch_global_constraints",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    error=str(e),
                )

        return rules

    def _extract_variables(
        self,
        response: str,
        session: Session | None,
        profile_variables: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Extract variables from response, session, and profile.

        Args:
            response: Generated response text
            session: Optional session for session variables
            profile_variables: Optional profile variables

        Returns:
            Merged dictionary of all variables
        """
        variables: dict[str, Any] = {}

        # 1. Add profile variables (lowest priority)
        if profile_variables:
            variables.update(profile_variables)

        # 2. Add session variables (medium priority)
        if session and hasattr(session, "variables") and session.variables:
            variables.update(session.variables)

        # 3. Extract from response text (highest priority)
        variables.update(self._variable_extractor._extract_amounts(response))
        variables.update(self._variable_extractor._extract_percentages(response))
        variables.update(self._variable_extractor._extract_boolean_flags(response))

        logger.debug(
            "enforcement_variables_extracted",
            variable_count=len(variables),
            variable_keys=list(variables.keys()),
        )

        return variables

    async def _enforce_two_lanes(
        self,
        response: str,
        lane1_rules: list[Rule],
        lane2_rules: list[Rule],
        variables: dict[str, Any],
    ) -> list[ConstraintViolation]:
        """Execute two-lane enforcement.

        Lane 1: Deterministic enforcement using simpleeval
        Lane 2: Subjective enforcement using LLM-as-Judge

        Args:
            response: Response to validate
            lane1_rules: Rules with enforcement_expression
            lane2_rules: Rules without enforcement_expression
            variables: Variables for expression evaluation

        Returns:
            List of constraint violations
        """
        violations: list[ConstraintViolation] = []

        # Lane 1: Deterministic enforcement
        if self._config.deterministic_enabled and lane1_rules:
            for rule in lane1_rules:
                passed, error_msg = self._deterministic_enforcer.evaluate(
                    expression=rule.enforcement_expression,  # type: ignore
                    variables=variables,
                )
                if not passed:
                    violations.append(
                        ConstraintViolation(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            violation_type="deterministic_expression_failed",
                            details=error_msg or f"Expression '{rule.enforcement_expression}' failed",
                            severity="hard",
                        )
                    )
                    logger.info(
                        "enforcement_lane1_violation",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        expression=rule.enforcement_expression,
                        error=error_msg,
                    )

        # Lane 2: Subjective enforcement (LLM-as-Judge)
        if self._config.llm_judge_enabled and lane2_rules:
            for rule in lane2_rules:
                passed, reason = await self._subjective_enforcer.evaluate(
                    response=response,
                    rule=rule,
                )
                if not passed:
                    violations.append(
                        ConstraintViolation(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            violation_type="llm_judge_failed",
                            details=reason or f"LLM judge found violation of rule '{rule.name}'",
                            severity="hard",
                        )
                    )
                    logger.info(
                        "enforcement_lane2_violation",
                        rule_id=str(rule.id),
                        rule_name=rule.name,
                        reason=reason,
                    )

        return violations

    async def _regenerate(
        self,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        response: str,
        violations: list[ConstraintViolation],
    ) -> str:
        """Regenerate a response with violation context.

        Args:
            snapshot: Situation snapshot
            matched_rules: Matched rules for context
            response: Original response that violated
            violations: Violations that triggered regeneration

        Returns:
            Regenerated response, or empty string on failure
        """
        try:
            # Build violation context for regeneration
            violation_summary = "; ".join(
                f"{v.rule_name}: {v.details}" for v in violations
            )

            regen = await self._response_generator.generate(
                snapshot=snapshot,
                matched_rules=matched_rules,
                history=[],
                tool_results=None,
                memory_context=None,
                templates=None,
                variables={
                    "previous_response": response,
                    "violation_summary": violation_summary,
                },
            )
            return regen.response
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "enforcement_regeneration_failed",
                error=str(exc),
            )
            return ""
