"""Rule filtering for alignment pipeline.

Uses LLM-based judgment to determine which candidate rules apply
to the current user message and context.
"""

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from soldier.alignment.context.models import Context, ScenarioSignal
from soldier.alignment.filtering.models import MatchedRule, RuleFilterResult
from soldier.alignment.models import Rule
from soldier.observability.logging import get_logger
from soldier.providers.llm import LLMExecutor, LLMMessage

logger = get_logger(__name__)

_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "filter_rules.txt"


class RuleFilter:
    """LLM-based rule relevance filtering.

    Evaluates candidate rules against the current context to determine
    which rules should apply to this turn.
    """

    def __init__(
        self,
        llm_executor: LLMExecutor,
        prompt_template: str | None = None,
        relevance_threshold: float = 0.5,
    ) -> None:
        """Initialize the rule filter.

        Args:
            llm_executor: Executor for LLM-based filtering
            prompt_template: Optional custom prompt template
            relevance_threshold: Minimum relevance score to consider a match
        """
        self._llm_executor = llm_executor
        self._relevance_threshold = relevance_threshold

        if prompt_template:
            self._prompt_template = prompt_template
        elif _PROMPT_TEMPLATE_PATH.exists():
            self._prompt_template = _PROMPT_TEMPLATE_PATH.read_text()
        else:
            self._prompt_template = self._default_prompt_template()

    def _default_prompt_template(self) -> str:
        """Return a minimal default prompt template."""
        return """Evaluate if these rules apply to the message: {message}

Rules: {rules}

Respond with JSON: {"evaluations": [{"rule_id": "...", "applies": true, "relevance": 0.8, "reasoning": "..."}]}"""

    async def filter(
        self,
        context: Context,
        candidates: list[Rule],
        batch_size: int = 5,
    ) -> RuleFilterResult:
        """Filter rules by relevance to the current context.

        Args:
            context: Extracted context from user message
            candidates: Candidate rules to evaluate
            batch_size: Number of rules to evaluate per LLM call

        Returns:
            RuleFilterResult with matched rules and metadata
        """
        start_time = time.perf_counter()

        if not candidates:
            return RuleFilterResult(
                matched_rules=[],
                rejected_rule_ids=[],
                filter_time_ms=0.0,
            )

        logger.debug(
            "filtering_rules",
            num_candidates=len(candidates),
            batch_size=batch_size,
        )

        # Process in batches
        matched_rules: list[MatchedRule] = []
        rejected_rule_ids: list[UUID] = []
        scenario_signal: ScenarioSignal | None = None

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            evaluations = await self._evaluate_batch(context, batch)

            for rule, evaluation in zip(batch, evaluations):
                if (
                    evaluation.get("applies", False)
                    and evaluation.get("relevance", 0) >= self._relevance_threshold
                ):
                    matched_rules.append(
                        MatchedRule(
                            rule=rule,
                            match_score=1.0,  # From retrieval
                            relevance_score=evaluation.get("relevance", 0.5),
                            reasoning=evaluation.get("reasoning", ""),
                        )
                    )
                else:
                    rejected_rule_ids.append(rule.id)

        # Sort matched rules by relevance
        matched_rules.sort(key=lambda m: m.relevance_score, reverse=True)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "rules_filtered",
            matched=len(matched_rules),
            rejected=len(rejected_rule_ids),
            elapsed_ms=elapsed_ms,
        )

        return RuleFilterResult(
            matched_rules=matched_rules,
            rejected_rule_ids=rejected_rule_ids,
            scenario_signal=scenario_signal,
            filter_time_ms=elapsed_ms,
        )

    async def _evaluate_batch(
        self,
        context: Context,
        rules: list[Rule],
    ) -> list[dict[str, Any]]:
        """Evaluate a batch of rules against the context."""
        rules_text = self._format_rules(rules)

        prompt = self._prompt_template.format(
            message=context.message,
            intent=context.intent or "unknown",
            rules=rules_text,
        )

        response = await self._llm_executor.generate(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,
            max_tokens=1000,
        )

        evaluations = self._parse_evaluations(response.content, rules)
        return evaluations

    def _format_rules(self, rules: list[Rule]) -> str:
        """Format rules for the prompt."""
        lines = []
        for rule in rules:
            lines.append(f"- Rule ID: {rule.id}")
            lines.append(f"  Name: {rule.name}")
            lines.append(f"  Condition: {rule.condition_text}")
            lines.append(f"  Action: {rule.action_text}")
            lines.append("")
        return "\n".join(lines)

    def _parse_evaluations(
        self,
        content: str,
        rules: list[Rule],
    ) -> list[dict[str, Any]]:
        """Parse LLM response into evaluations."""
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        try:
            data = json.loads(content)
            evaluations = data.get("evaluations", [])

            # Map by rule_id
            eval_map = {str(e.get("rule_id", "")): e for e in evaluations}

            # Return in same order as rules
            result = []
            for rule in rules:
                if str(rule.id) in eval_map:
                    result.append(eval_map[str(rule.id)])
                else:
                    # Default to not applying if not in response
                    result.append(
                        {"applies": False, "relevance": 0.0, "reasoning": "Not evaluated"}
                    )

            return result

        except json.JSONDecodeError:
            logger.warning("failed_to_parse_filter_response", content_preview=content[:100])
            # Default to all rules applying with medium relevance
            return [
                {"applies": True, "relevance": 0.6, "reasoning": "Parse error, defaulting to apply"}
                for _ in rules
            ]
