"""Rule filtering for alignment pipeline.

Uses LLM-based judgment to determine which candidate rules apply
to the current user message and context.
"""

import json
import time
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape

from focal.alignment.context.situation_snapshot import SituationSnapshot
from focal.alignment.filtering.models import (
    MatchedRule,
    RuleApplicability,
    RuleEvaluation,
    RuleFilterResult,
)
from focal.alignment.models import Rule
from focal.observability.logging import get_logger
from focal.providers.llm import LLMExecutor, LLMMessage

logger = get_logger(__name__)


class RuleFilter:
    """LLM-based rule relevance filtering.

    Evaluates candidate rules against the current context to determine
    which rules should apply to this turn.
    """

    def __init__(
        self,
        llm_executor: LLMExecutor,
        confidence_threshold: float = 0.7,
        unsure_policy: str = "exclude",
    ) -> None:
        """Initialize the rule filter.

        Args:
            llm_executor: Executor for LLM-based filtering
            confidence_threshold: Minimum confidence for APPLIES
            unsure_policy: How to handle UNSURE rules ("include", "exclude", "log_only")
        """
        self._llm_executor = llm_executor
        self._confidence_threshold = confidence_threshold
        self._unsure_policy = unsure_policy

        template_dir = Path(__file__).parent / "prompts"
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._template = self._env.get_template("filter_rules.jinja2")

    async def filter(
        self,
        snapshot: SituationSnapshot,
        candidates: list[Rule],
        batch_size: int = 5,
    ) -> RuleFilterResult:
        """Filter rules by relevance to the current context.

        Args:
            snapshot: Situation snapshot from user message
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
        unsure_rule_ids: list[UUID] = []

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            evaluations = await self._evaluate_batch(snapshot, batch)

            for rule, evaluation in zip(batch, evaluations):
                applicability = evaluation.applicability
                confidence = evaluation.confidence

                if applicability == RuleApplicability.APPLIES and confidence >= self._confidence_threshold:
                    matched_rules.append(
                        MatchedRule(
                            rule=rule,
                            match_score=1.0,
                            relevance_score=evaluation.relevance,
                            reasoning=evaluation.reasoning,
                        )
                    )
                elif applicability == RuleApplicability.NOT_RELATED:
                    rejected_rule_ids.append(rule.id)
                elif applicability == RuleApplicability.UNSURE:
                    unsure_rule_ids.append(rule.id)
                    if self._unsure_policy == "include":
                        matched_rules.append(
                            MatchedRule(
                                rule=rule,
                                match_score=1.0,
                                relevance_score=evaluation.relevance,
                                reasoning=f"UNSURE (included by policy): {evaluation.reasoning}",
                            )
                        )
                    logger.info(
                        "unsure_rule",
                        rule_id=str(rule.id),
                        policy=self._unsure_policy,
                        confidence=confidence,
                        reasoning=evaluation.reasoning,
                    )

        # Sort matched rules by relevance
        matched_rules.sort(key=lambda m: m.relevance_score, reverse=True)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "rules_filtered",
            matched=len(matched_rules),
            rejected=len(rejected_rule_ids),
            unsure=len(unsure_rule_ids),
            unsure_policy=self._unsure_policy,
            elapsed_ms=elapsed_ms,
        )

        return RuleFilterResult(
            matched_rules=matched_rules,
            rejected_rule_ids=rejected_rule_ids,
            filter_time_ms=elapsed_ms,
        )

    async def _evaluate_batch(
        self,
        snapshot: SituationSnapshot,
        rules: list[Rule],
    ) -> list[RuleEvaluation]:
        """Evaluate a batch of rules against the snapshot."""
        prompt = self._template.render(
            snapshot=snapshot,
            rules=rules,
        )

        response = await self._llm_executor.generate(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,
            max_tokens=1000,
        )

        evaluations = self._parse_evaluations(response.content, rules)
        return evaluations

    def _parse_evaluations(
        self,
        content: str,
        rules: list[Rule],
    ) -> list[RuleEvaluation]:
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
            eval_data = data.get("evaluations", [])

            # Map by rule_id
            eval_map = {str(e.get("rule_id", "")): e for e in eval_data}

            # Return in same order as rules
            result = []
            for rule in rules:
                if str(rule.id) in eval_map:
                    e = eval_map[str(rule.id)]
                    applicability_str = e.get("applicability", "UNSURE")

                    # Validate applicability value
                    try:
                        applicability = RuleApplicability(applicability_str)
                    except ValueError:
                        logger.warning(
                            "invalid_applicability",
                            rule_id=str(rule.id),
                            value=applicability_str,
                        )
                        applicability = RuleApplicability.UNSURE

                    result.append(
                        RuleEvaluation(
                            rule_id=rule.id,
                            applicability=applicability,
                            confidence=e.get("confidence", 0.5),
                            relevance=e.get("relevance", 0.5),
                            reasoning=e.get("reasoning", ""),
                        )
                    )
                else:
                    # Default to UNSURE if not in response
                    result.append(
                        RuleEvaluation(
                            rule_id=rule.id,
                            applicability=RuleApplicability.UNSURE,
                            confidence=0.0,
                            relevance=0.0,
                            reasoning="Not evaluated by LLM",
                        )
                    )

            return result

        except json.JSONDecodeError:
            logger.warning("failed_to_parse_filter_response", content_preview=content[:100])
            # Default to UNSURE on parse error
            return [
                RuleEvaluation(
                    rule_id=rule.id,
                    applicability=RuleApplicability.UNSURE,
                    confidence=0.0,
                    relevance=0.5,
                    reasoning="Parse error in LLM response",
                )
                for rule in rules
            ]
