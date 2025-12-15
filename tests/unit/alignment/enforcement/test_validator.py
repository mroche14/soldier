"""Unit tests for EnforcementValidator with two-lane dispatch."""

from typing import Any
from uuid import uuid4

import pytest

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.enforcement.validator import EnforcementValidator
from ruche.brains.focal.phases.filtering.models import MatchedRule
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.models import Rule, Scope
from ruche.config.models.pipeline import EnforcementConfig
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class MockConfigStore:
    """Mock config store for testing."""

    def __init__(self, global_rules: list[Rule] | None = None):
        self._global_rules = global_rules or []

    async def get_rules(self, **kwargs) -> list[Rule]:
        """Return configured rules filtered by scope."""
        scope = kwargs.get("scope")
        if scope == Scope.GLOBAL:
            return self._global_rules
        return []


class MockGenerator(ResponseGenerator):
    """Stub generator that returns a fixed response."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def generate(self, *args, **kwargs):
        class DummyResult:
            def __init__(self, content: str):
                self.response = content

        return DummyResult(self._response)


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for subjective enforcement."""

    def __init__(self, responses: list[str] | None = None):
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses or ["PASS"]
        self._call_count = 0

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=content, model="mock-model", usage={})


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def snapshot():
    return SituationSnapshot(
        message="test message",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
    )


@pytest.mark.asyncio
async def test_validator_passes_when_no_constraints(tenant_id, agent_id, snapshot) -> None:
    """Validator passes when there are no hard constraint rules."""
    validator = EnforcementValidator(
        response_generator=MockGenerator("ok"),
        agent_config_store=MockConfigStore(),
        llm_executor=MockLLMExecutor(),
    )
    result = await validator.validate(
        response="hello",
        snapshot=snapshot,
        matched_rules=[],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )
    assert result.passed is True
    assert result.final_response == "hello"


@pytest.mark.asyncio
async def test_validator_enforces_deterministic_expression(tenant_id, agent_id, snapshot) -> None:
    """Validator enforces rules with enforcement_expression (Lane 1)."""
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Amount limit",
        condition_text="When processing refunds",
        action_text="Limit refunds to $50",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 50",
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[hard_rule]),
        llm_executor=MockLLMExecutor(),
        config=EnforcementConfig(max_retries=0),  # Don't retry for this test
    )

    # Response that extracts to amount=75, violating amount <= 50
    result = await validator.validate(
        response="I can offer you a refund of $75",
        snapshot=snapshot,
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].violation_type == "deterministic_expression_failed"
    assert "amount <= 50" in result.violations[0].details


@pytest.mark.asyncio
async def test_validator_passes_deterministic_when_expression_satisfied(
    tenant_id, agent_id, snapshot
) -> None:
    """Validator passes when deterministic expression is satisfied."""
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Amount limit",
        condition_text="When processing refunds",
        action_text="Limit refunds to $50",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 50",
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[hard_rule]),
        llm_executor=MockLLMExecutor(),
    )

    # Response that extracts to amount=30, satisfying amount <= 50
    result = await validator.validate(
        response="I can offer you a refund of $30",
        snapshot=snapshot,
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is True
    assert len(result.violations) == 0


@pytest.mark.asyncio
async def test_validator_enforces_subjective_rule_via_llm(tenant_id, agent_id, snapshot) -> None:
    """Validator enforces rules without expression using LLM-as-Judge (Lane 2)."""
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Professional tone",
        condition_text="Always",
        action_text="Maintain professional tone",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        # No enforcement_expression - goes to Lane 2
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    # LLM returns FAIL indicating violation
    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[hard_rule]),
        llm_executor=MockLLMExecutor(responses=["FAIL: Response is too casual"]),
        config=EnforcementConfig(max_retries=0),
    )

    result = await validator.validate(
        response="yo wassup dude",
        snapshot=snapshot,
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].violation_type == "llm_judge_failed"


@pytest.mark.asyncio
async def test_validator_passes_subjective_when_llm_approves(tenant_id, agent_id, snapshot) -> None:
    """Validator passes subjective rule when LLM returns PASS."""
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Professional tone",
        condition_text="Always",
        action_text="Maintain professional tone",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[hard_rule]),
        llm_executor=MockLLMExecutor(responses=["PASS"]),
    )

    result = await validator.validate(
        response="Thank you for your inquiry. I'd be happy to assist.",
        snapshot=snapshot,
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is True
    assert len(result.violations) == 0


@pytest.mark.asyncio
async def test_validator_always_enforces_global_constraints(tenant_id, agent_id, snapshot) -> None:
    """Validator fetches and enforces GLOBAL hard constraints even if not matched."""
    global_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Global: No financial advice",
        condition_text="Always",
        action_text="Never give financial advice",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        # No expression - goes to LLM judge
    )

    # GLOBAL rule not in matched_rules, but should still be enforced
    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[global_rule]),
        llm_executor=MockLLMExecutor(responses=["FAIL: Contains financial advice"]),
        config=EnforcementConfig(always_enforce_global=True, max_retries=0),
    )

    result = await validator.validate(
        response="You should invest in this stock",
        snapshot=snapshot,
        matched_rules=[],  # No matched rules
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is False
    assert len(result.violations) == 1


@pytest.mark.asyncio
async def test_validator_attempts_regeneration_on_violation(tenant_id, agent_id, snapshot) -> None:
    """Validator attempts to regenerate response when violations detected."""
    hard_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Amount limit",
        condition_text="When processing refunds",
        action_text="Limit refunds to $50",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 50",
    )
    matched = MatchedRule(rule=hard_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    # Generator returns compliant response on regeneration
    validator = EnforcementValidator(
        response_generator=MockGenerator("Your refund of $40 has been processed"),
        agent_config_store=MockConfigStore(global_rules=[hard_rule]),
        llm_executor=MockLLMExecutor(),
        config=EnforcementConfig(max_retries=1),
    )

    result = await validator.validate(
        response="I can offer you a refund of $75",  # Violates amount <= 50
        snapshot=snapshot,
        matched_rules=[matched],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.regeneration_attempted is True
    assert result.regeneration_succeeded is True
    assert "$40" in result.final_response


@pytest.mark.asyncio
async def test_validator_handles_two_lane_partition(tenant_id, agent_id, snapshot) -> None:
    """Validator correctly partitions rules into Lane 1 (deterministic) and Lane 2 (subjective)."""
    deterministic_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Deterministic rule",
        condition_text="Always",
        action_text="Keep amounts under 100",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 100",  # Lane 1
    )
    subjective_rule = Rule(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Subjective rule",
        condition_text="Always",
        action_text="Be polite",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        # No expression - Lane 2
    )
    matched_det = MatchedRule(rule=deterministic_rule, match_score=1.0, relevance_score=1.0, reasoning="")
    matched_sub = MatchedRule(rule=subjective_rule, match_score=1.0, relevance_score=1.0, reasoning="")

    validator = EnforcementValidator(
        response_generator=MockGenerator("clean response"),
        agent_config_store=MockConfigStore(global_rules=[deterministic_rule, subjective_rule]),
        llm_executor=MockLLMExecutor(responses=["PASS"]),  # Subjective passes
    )

    # Response passes both: amount=50 (passes amount <= 100), LLM says PASS
    result = await validator.validate(
        response="Your order total is $50. Thank you!",
        snapshot=snapshot,
        matched_rules=[matched_det, matched_sub],
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.passed is True
    assert len(result.violations) == 0
