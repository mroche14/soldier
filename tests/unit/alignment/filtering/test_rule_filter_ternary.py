"""Unit tests for RuleFilter ternary output (APPLIES/NOT_RELATED/UNSURE)."""

import json
from typing import Any
from uuid import uuid4

import pytest

from focal.alignment.context.situation_snapshot import SituationSnapshot
from focal.alignment.filtering.models import RuleApplicability, RuleFilterResult
from focal.alignment.filtering.rule_filter import RuleFilter
from focal.alignment.models import Rule, Scope
from focal.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for testing."""

    def __init__(self, evaluations: list[dict[str, Any]] | None = None):
        super().__init__(model="mock/test", step_name="test")
        self._evaluations = evaluations or []

    async def generate(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(
            content=json.dumps({"evaluations": self._evaluations}),
            model="mock",
            usage={},
        )


@pytest.fixture
def snapshot():
    """Create a test snapshot."""
    return SituationSnapshot(
        message="I want to check my balance",
        new_intent_label="check_balance",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        turn_count=1,
    )


@pytest.fixture
def sample_rules():
    """Create sample rules."""
    tenant_id = uuid4()
    agent_id = uuid4()

    return [
        Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            id=uuid4(),
            name="Check Balance Rule",
            condition_text="User wants to check balance",
            action_text="Provide balance information",
            scope=Scope.GLOBAL,
        ),
        Rule(
            tenant_id=tenant_id,
            agent_id=agent_id,
            id=uuid4(),
            name="Transfer Money Rule",
            condition_text="User wants to transfer money",
            action_text="Initiate transfer",
            scope=Scope.GLOBAL,
        ),
    ]


class TestTernaryOutput:
    """Test ternary output (APPLIES/NOT_RELATED/UNSURE)."""

    @pytest.mark.asyncio
    async def test_applies_with_high_confidence(self, snapshot, sample_rules):
        """Test APPLIES classification with high confidence."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "APPLIES",
                    "confidence": 0.9,
                    "relevance": 0.85,
                    "reasoning": "User explicitly asked to check balance",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7)
        result = await filter.filter(snapshot, [rule])

        assert len(result.matched_rules) == 1
        assert result.matched_rules[0].rule.id == rule.id
        assert result.matched_rules[0].relevance_score == 0.85

    @pytest.mark.asyncio
    async def test_not_related_excluded(self, snapshot, sample_rules):
        """Test NOT_RELATED rules are excluded."""
        rule = sample_rules[1]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "NOT_RELATED",
                    "confidence": 0.95,
                    "relevance": 0.1,
                    "reasoning": "User wants balance info, not transfer",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7)
        result = await filter.filter(snapshot, [rule])

        assert len(result.matched_rules) == 0
        assert rule.id in result.rejected_rule_ids

    @pytest.mark.asyncio
    async def test_unsure_excluded_by_default(self, snapshot, sample_rules):
        """Test UNSURE rules are excluded by default."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "UNSURE",
                    "confidence": 0.5,
                    "relevance": 0.6,
                    "reasoning": "Ambiguous whether this applies",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7, unsure_policy="exclude")
        result = await filter.filter(snapshot, [rule])

        assert len(result.matched_rules) == 0
        assert rule.id not in result.rejected_rule_ids

    @pytest.mark.asyncio
    async def test_unsure_included_by_policy(self, snapshot, sample_rules):
        """Test UNSURE rules can be included with policy."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "UNSURE",
                    "confidence": 0.5,
                    "relevance": 0.6,
                    "reasoning": "Ambiguous whether this applies",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7, unsure_policy="include")
        result = await filter.filter(snapshot, [rule])

        assert len(result.matched_rules) == 1
        assert "UNSURE" in result.matched_rules[0].reasoning

    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(self, snapshot, sample_rules):
        """Test confidence threshold filters low-confidence APPLIES."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "APPLIES",
                    "confidence": 0.5,
                    "relevance": 0.8,
                    "reasoning": "Low confidence match",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7, unsure_policy="exclude")
        result = await filter.filter(snapshot, [rule])

        # Low confidence APPLIES should not be included
        assert len(result.matched_rules) == 0

    @pytest.mark.asyncio
    async def test_invalid_applicability_defaults_to_unsure(self, snapshot, sample_rules):
        """Test invalid applicability values default to UNSURE."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "applicability": "MAYBE",
                    "confidence": 0.8,
                    "relevance": 0.7,
                    "reasoning": "Invalid applicability value",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7, unsure_policy="exclude")
        result = await filter.filter(snapshot, [rule])

        # Should be treated as UNSURE and excluded
        assert len(result.matched_rules) == 0

    @pytest.mark.asyncio
    async def test_mixed_applicability_results(self, snapshot, sample_rules):
        """Test handling multiple rules with mixed applicability."""
        rule1, rule2 = sample_rules

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule1.id),
                    "applicability": "APPLIES",
                    "confidence": 0.9,
                    "relevance": 0.85,
                    "reasoning": "Clear match",
                },
                {
                    "rule_id": str(rule2.id),
                    "applicability": "NOT_RELATED",
                    "confidence": 0.95,
                    "relevance": 0.1,
                    "reasoning": "Not applicable",
                },
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7)
        result = await filter.filter(snapshot, sample_rules)

        assert len(result.matched_rules) == 1
        assert result.matched_rules[0].rule.id == rule1.id
        assert rule2.id in result.rejected_rule_ids

    @pytest.mark.asyncio
    async def test_missing_applicability_defaults_to_unsure(self, snapshot, sample_rules):
        """Test missing applicability field defaults to UNSURE."""
        rule = sample_rules[0]

        llm = MockLLMExecutor(
            evaluations=[
                {
                    "rule_id": str(rule.id),
                    "confidence": 0.8,
                    "relevance": 0.7,
                    "reasoning": "No applicability field",
                }
            ]
        )

        filter = RuleFilter(llm, confidence_threshold=0.7, unsure_policy="exclude")
        result = await filter.filter(snapshot, [rule])

        # Should default to UNSURE and be excluded
        assert len(result.matched_rules) == 0
