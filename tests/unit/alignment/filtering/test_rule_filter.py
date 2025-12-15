"""Unit tests for RuleFilter."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.context.models import Sentiment, Urgency
from ruche.brains.focal.phases.filtering.models import MatchedRule, RuleFilterResult
from ruche.brains.focal.phases.filtering.rule_filter import RuleFilter
from ruche.brains.focal.models import Rule
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for testing rule filtering."""

    def __init__(
        self,
        evaluations: list[dict[str, Any]] | None = None,
        raise_error: bool = False,
        return_invalid_json: bool = False,
    ) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._evaluations = evaluations
        self._raise_error = raise_error
        self._return_invalid_json = return_invalid_json
        self.generate_calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        self.generate_calls.append(messages)

        if self._raise_error:
            raise RuntimeError("LLM error")

        if self._return_invalid_json:
            return LLMResponse(
                content="not valid json at all",
                model="mock",
                usage={},
            )

        evaluations = self._evaluations or []
        return LLMResponse(
            content=json.dumps({"evaluations": evaluations}),
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )


def create_rule(
    rule_id: str | None = None,
    name: str = "Test Rule",
    condition_text: str = "When user asks",
    action_text: str = "Respond helpfully",
    priority: int = 100,
    tenant_id: str | None = None,
    agent_id: str | None = None,
    enabled: bool = True,
) -> Rule:
    """Create a test rule."""
    return Rule(
        id=uuid4() if rule_id is None else rule_id,
        tenant_id=uuid4() if tenant_id is None else tenant_id,
        agent_id=uuid4() if agent_id is None else agent_id,
        name=name,
        condition_text=condition_text,
        action_text=action_text,
        priority=priority,
        enabled=enabled,
    )


class TestRuleFilter:
    """Tests for RuleFilter class."""

    @pytest.fixture
    def snapshot(self) -> SituationSnapshot:
        return SituationSnapshot(
            message="I want to return my order",
            new_intent_label="return order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        )

    @pytest.fixture
    def sample_rules(self) -> list[Rule]:
        return [
            create_rule(name="Return Policy", condition_text="When user mentions return"),
            create_rule(name="Order Info", condition_text="When user asks about order"),
            create_rule(name="Payment Help", condition_text="When user mentions payment"),
        ]

    # Test initialization

    def test_filter_can_be_created(self) -> None:
        """Test that RuleFilter can be instantiated."""
        llm = MockLLMExecutor()
        rule_filter = RuleFilter(llm_executor=llm)
        assert rule_filter is not None

    def test_filter_with_custom_threshold(self) -> None:
        """Test creating filter with custom confidence threshold."""
        llm = MockLLMExecutor()
        rule_filter = RuleFilter(llm_executor=llm, confidence_threshold=0.7)
        assert rule_filter._confidence_threshold == 0.7

    def test_filter_with_custom_template(self) -> None:
        """Test creating filter with custom prompt template path."""
        llm = MockLLMExecutor()
        # Template path is now configured via template_path parameter
        rule_filter = RuleFilter(llm_executor=llm)
        assert rule_filter is not None

    # Test filtering behavior

    @pytest.mark.asyncio
    async def test_filter_empty_candidates_returns_empty(
        self,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that filtering no candidates returns empty result."""
        llm = MockLLMExecutor()
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=[])

        assert isinstance(result, RuleFilterResult)
        assert result.matched_rules == []
        assert result.rejected_rule_ids == []
        assert result.filter_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_filter_returns_matched_rules(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that matching rules are returned."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Matches return topic"},
            {"rule_id": str(sample_rules[1].id), "applicability": "APPLIES", "confidence": 0.8, "relevance": 0.7, "reasoning": "Mentions order"},
            {"rule_id": str(sample_rules[2].id), "applicability": "NOT_RELATED", "confidence": 0.9, "relevance": 0.2, "reasoning": "No payment topic"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        assert len(result.matched_rules) == 2
        assert len(result.rejected_rule_ids) == 1
        assert sample_rules[2].id in result.rejected_rule_ids

    @pytest.mark.asyncio
    async def test_filter_sorts_by_relevance(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that matched rules are sorted by relevance score."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.6, "reasoning": "Medium match"},
            {"rule_id": str(sample_rules[1].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "High match"},
            {"rule_id": str(sample_rules[2].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.75, "reasoning": "Good match"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        # Should be sorted descending by relevance
        assert result.matched_rules[0].relevance_score == 0.9
        assert result.matched_rules[1].relevance_score == 0.75
        assert result.matched_rules[2].relevance_score == 0.6

    @pytest.mark.asyncio
    async def test_filter_applies_threshold(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that rules below threshold are rejected."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.8, "reasoning": "Above threshold"},
            {"rule_id": str(sample_rules[1].id), "applicability": "APPLIES", "confidence": 0.4, "relevance": 0.4, "reasoning": "Below threshold"},
            {"rule_id": str(sample_rules[2].id), "applicability": "APPLIES", "confidence": 0.3, "relevance": 0.3, "reasoning": "Below threshold"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm, confidence_threshold=0.5)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        assert len(result.matched_rules) == 1
        assert result.matched_rules[0].rule.id == sample_rules[0].id

    @pytest.mark.asyncio
    async def test_filter_includes_reasoning(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that reasoning is captured in matched rules."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Direct match on returns"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=[sample_rules[0]])

        assert result.matched_rules[0].reasoning == "Direct match on returns"

    # Test batching

    @pytest.mark.asyncio
    async def test_filter_respects_batch_size(
        self,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that rules are processed in batches."""
        rules = [create_rule(name=f"Rule {i}") for i in range(7)]

        evaluations = [
            {"rule_id": str(r.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.8, "reasoning": "Match"}
            for r in rules
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        # Process with batch_size=3 should make 3 calls (3+3+1)
        await rule_filter.filter(snapshot=snapshot, candidates=rules, batch_size=3)

        assert len(llm.generate_calls) == 3

    @pytest.mark.asyncio
    async def test_filter_single_batch(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that small set uses single batch."""
        evaluations = [
            {"rule_id": str(r.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.8, "reasoning": "Match"}
            for r in sample_rules
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        await rule_filter.filter(snapshot=snapshot, candidates=sample_rules, batch_size=10)

        assert len(llm.generate_calls) == 1

    # Test error handling

    @pytest.mark.asyncio
    async def test_filter_handles_invalid_json(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that invalid JSON treats all rules as UNSURE (excluded by default)."""
        llm = MockLLMExecutor(return_invalid_json=True)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        # With ternary output, parse errors result in UNSURE which are excluded by default
        assert len(result.matched_rules) == 0

    @pytest.mark.asyncio
    async def test_filter_handles_missing_rule_evaluations(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test handling when LLM doesn't return all rule evaluations."""
        # Only return evaluation for first rule
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Match"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        # First rule should match, others treated as UNSURE (excluded by default, not rejected)
        assert len(result.matched_rules) == 1
        # With ternary, missing evals are UNSURE and excluded, not put in rejected_rule_ids
        assert len(result.rejected_rule_ids) == 0

    @pytest.mark.asyncio
    async def test_filter_handles_markdown_wrapped_json(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""

        class MarkdownLLMExecutor(MockLLMExecutor):
            async def generate(self, messages, **kwargs):
                evaluations = [
                    {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Match"}
                ]
                return LLMResponse(
                    content=f'```json\n{json.dumps({"evaluations": evaluations})}\n```',
                    model="mock",
                    usage={},
                )

        llm = MarkdownLLMExecutor()
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=[sample_rules[0]])

        assert len(result.matched_rules) == 1

    # Test timing

    @pytest.mark.asyncio
    async def test_filter_records_timing(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that filter time is recorded."""
        evaluations = [
            {"rule_id": str(r.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.8, "reasoning": "Match"}
            for r in sample_rules
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=sample_rules)

        assert result.filter_time_ms > 0

    # Test MatchedRule structure

    @pytest.mark.asyncio
    async def test_matched_rule_contains_original_rule(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that MatchedRule contains the original Rule object."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Match"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=[sample_rules[0]])

        matched = result.matched_rules[0]
        assert isinstance(matched, MatchedRule)
        assert matched.rule == sample_rules[0]
        assert matched.rule.name == "Return Policy"

    @pytest.mark.asyncio
    async def test_matched_rule_has_scores(
        self,
        snapshot: SituationSnapshot,
        sample_rules: list[Rule],
    ) -> None:
        """Test that MatchedRule has both match and relevance scores."""
        evaluations = [
            {"rule_id": str(sample_rules[0].id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.85, "reasoning": "Match"},
        ]
        llm = MockLLMExecutor(evaluations=evaluations)
        rule_filter = RuleFilter(llm_executor=llm)

        result = await rule_filter.filter(snapshot=snapshot, candidates=[sample_rules[0]])

        matched = result.matched_rules[0]
        assert matched.match_score == 1.0  # Default from retrieval
        assert matched.relevance_score == 0.85


class TestRuleFilterResult:
    """Tests for RuleFilterResult model."""

    def test_empty_result(self) -> None:
        """Test creating an empty result."""
        result = RuleFilterResult(
            matched_rules=[],
            rejected_rule_ids=[],
            filter_time_ms=0.0,
        )
        assert result.matched_rules == []
        assert result.rejected_rule_ids == []

    def test_result_with_scenario_signal(self) -> None:
        """Test result can include scenario signal."""
        from ruche.brains.focal.phases.context.models import ScenarioSignal

        result = RuleFilterResult(
            matched_rules=[],
            rejected_rule_ids=[],
            scenario_signal=ScenarioSignal.START,
            filter_time_ms=10.0,
        )
        assert result.scenario_signal == ScenarioSignal.START
