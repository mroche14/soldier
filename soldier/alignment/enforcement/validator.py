"""Response enforcement for hard constraints."""

import time

from soldier.alignment.context.models import Context
from soldier.alignment.enforcement.models import ConstraintViolation, EnforcementResult
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.models import Rule
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


class EnforcementValidator:
    """Validate responses against hard constraint rules.

    Hard constraints are rules that must be satisfied for every response.
    When violations are detected, the validator can:
    1. Attempt to regenerate the response with stronger instructions
    2. Pass to FallbackHandler for template-based recovery
    """

    def __init__(
        self,
        response_generator: ResponseGenerator,
        max_retries: int = 1,
    ) -> None:
        """Initialize the enforcement validator.

        Args:
            response_generator: Generator for response regeneration
            max_retries: Maximum regeneration attempts on violation
        """
        self._response_generator = response_generator
        self._max_retries = max_retries

    async def validate(
        self,
        response: str,
        context: Context,
        matched_rules: list[MatchedRule],
        hard_rules: list[Rule],
    ) -> EnforcementResult:
        """Validate response against hard constraints.

        Args:
            response: Generated response to validate
            context: User message context
            matched_rules: Rules that matched this turn
            hard_rules: Subset of rules that are hard constraints

        Returns:
            EnforcementResult with validation status and final response
        """
        start_time = time.perf_counter()
        violations = self._detect_violations(response, hard_rules)

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
                context=context,
                matched_rules=matched_rules,
                response=response,
            )
            regeneration_succeeded = bool(regenerated_response)
            if regeneration_succeeded:
                # Re-run violations on regenerated output
                violations = self._detect_violations(regenerated_response, hard_rules)

        return EnforcementResult(
            passed=not violations,
            violations=violations,
            regeneration_attempted=regeneration_attempted,
            regeneration_succeeded=regeneration_succeeded,
            fallback_used=False,
            final_response=regenerated_response if not violations else response,
            enforcement_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    async def _regenerate(
        self,
        context: Context,
        matched_rules: list[MatchedRule],
        response: str,
    ) -> str:
        """Regenerate a response with a stronger instruction prompt."""
        try:
            regen = await self._response_generator.generate(
                context=context,
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
