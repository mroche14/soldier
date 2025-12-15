"""LLM-as-Judge enforcement for subjective rules."""

from ruche.brains.focal.models import Rule
from ruche.config.models.pipeline import EnforcementConfig
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.llm import LLMExecutor

logger = get_logger(__name__)


class SubjectiveEnforcer:
    """Evaluate subjective rules using LLM-as-Judge.

    For rules without formal expressions, use an LLM to judge whether
    the response complies with the rule's intent.
    """

    JUDGE_PROMPT_TEMPLATE = """You are a compliance judge. Evaluate if this response follows the rule.

Rule: {rule_action}

Response to evaluate:
"{response}"

Does the response comply with the rule? Answer with:
- "PASS" if it complies
- "FAIL: <reason>" if it violates

Be strict but fair. Only one line."""

    def __init__(
        self,
        llm_executor: LLMExecutor,
        config: EnforcementConfig,
    ) -> None:
        """Initialize subjective enforcer.

        Args:
            llm_executor: LLM executor for judgment calls
            config: Enforcement configuration (for model selection)
        """
        self._llm = llm_executor
        self._config = config

    async def evaluate(
        self,
        response: str,
        rule: Rule,
    ) -> tuple[bool, str]:
        """Evaluate response against a subjective rule using LLM.

        Args:
            response: Generated response to evaluate
            rule: Rule to check compliance against

        Returns:
            Tuple of (passed, explanation)
            - (True, "") if complies
            - (False, reason) if violates
        """
        # Build judge prompt
        prompt = self.JUDGE_PROMPT_TEMPLATE.format(
            rule_action=rule.action_text,
            response=response,
        )

        try:
            # Call LLM with temperature=0 for deterministic judgment
            models = self._config.llm_judge_models
            if not models:
                logger.warning(
                    "enforcement_llm_judge_no_models_configured",
                    rule_id=str(rule.id),
                )
                return (True, "")  # Pass by default if no models configured

            result = await self._llm.generate(
                prompt=prompt,
                model=models[0],
                temperature=0.0,
                max_tokens=100,
            )

            judgment = result.text.strip()

            # Parse judgment
            if judgment.upper().startswith("PASS"):
                logger.debug(
                    "enforcement_llm_judge_pass",
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    judgment=judgment,
                )
                return (True, "")

            elif judgment.upper().startswith("FAIL"):
                # Extract reason after "FAIL:"
                reason = judgment[5:].strip() if len(judgment) > 5 else "Rule violation detected"
                logger.info(
                    "enforcement_llm_judge_fail",
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    reason=reason,
                )
                return (False, reason)

            else:
                # Unexpected format - log and treat as pass to be safe
                logger.warning(
                    "enforcement_llm_judge_unexpected_format",
                    rule_id=str(rule.id),
                    judgment=judgment,
                )
                return (True, "")

        except Exception as e:  # noqa: BLE001
            logger.error(
                "enforcement_llm_judge_error",
                rule_id=str(rule.id),
                error=str(e),
            )
            # On error, pass by default (fail-open for reliability)
            return (True, "")
