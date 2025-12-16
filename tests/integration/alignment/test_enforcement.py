"""Integration test for two-lane response enforcement."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.brains.focal.phases.enforcement import EnforcementValidator, FallbackHandler
from ruche.brains.focal.pipeline import FocalCognitivePipeline as AlignmentEngine
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.models import Rule, Scope
from ruche.brains.focal.stores import InMemoryAgentConfigStore
from ruche.config.models.pipeline import EnforcementConfig, PipelineConfig
from ruche.infrastructure.providers.embedding import EmbeddingProvider, EmbeddingResponse
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class SequenceLLMExecutor(LLMExecutor):
    """LLM executor that returns responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses
        self._call_count = 0
        self.generate_calls: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        self.generate_calls.append(messages)
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=content, model="seq-model", usage={})


class StaticEmbeddingProvider(EmbeddingProvider):
    """Return fixed embeddings."""

    def __init__(self, embedding: list[float]) -> None:
        self._embedding = embedding

    @property
    def provider_name(self) -> str:
        return "static"

    @property
    def dimensions(self) -> int:
        return len(self._embedding)

    async def embed(self, texts: list[str], **kwargs) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[self._embedding for _ in texts],
            model="static",
            dimensions=self.dimensions,
        )


@pytest.mark.asyncio
async def test_enforcement_lane1_deterministic_blocks_violation() -> None:
    """Lane 1 deterministic enforcement blocks response that violates expression."""
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    # Rule with deterministic expression - amount must be <= 50
    hard_rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Refund limit",
        condition_text="When processing refunds",
        action_text="Limit refunds to $50",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 50",  # Lane 1
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryAgentConfigStore()
    await store.save_rule(hard_rule)

    # Create executors for each step
    extraction_resp = json.dumps({"intent": "refund", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    filter_resp = json.dumps({"evaluations": [{"rule_id": str(hard_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    # First response violates ($75 > $50), second response complies ($40 <= $50)
    gen_executor = SequenceLLMExecutor(["Your refund of $75 has been processed", "Your refund of $40 has been processed"])
    judge_executor = SequenceLLMExecutor(["PASS"])  # Not used for Lane 1

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_executor=gen_executor)
    enforcement_validator = EnforcementValidator(
        response_generator=response_generator,
        agent_config_store=store,
        llm_executor=judge_executor,
        config=EnforcementConfig(max_retries=1),
    )

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        enforcement_validator=enforcement_validator,
        fallback_handler=FallbackHandler(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="I want a refund",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    # First response ($75) should have been blocked, regeneration ($40) should pass
    assert result.enforcement is not None
    assert result.enforcement.passed is True
    assert result.enforcement.regeneration_attempted is True
    assert result.enforcement.regeneration_attempts == 1
    assert result.enforcement.regeneration_succeeded is True
    assert "$40" in result.response


@pytest.mark.asyncio
async def test_enforcement_lane2_subjective_blocks_violation() -> None:
    """Lane 2 LLM-as-Judge enforcement blocks response that LLM deems non-compliant."""
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    # Rule without expression - goes to LLM judge
    hard_rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Professional tone",
        condition_text="Always",
        action_text="Maintain professional and respectful tone",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        # No enforcement_expression - Lane 2
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryAgentConfigStore()
    await store.save_rule(hard_rule)

    extraction_resp = json.dumps({"intent": "greeting", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    filter_resp = json.dumps({"evaluations": [{"rule_id": str(hard_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    # First response is casual, second is professional
    gen_executor = SequenceLLMExecutor([
        "yo what's up, how can i help ya",
        "Hello! How may I assist you today?"
    ])
    # Judge: FAIL first (casual), then PASS (professional)
    judge_executor = SequenceLLMExecutor([
        "FAIL: Response tone is too casual and unprofessional",
        "PASS"
    ])

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_executor=gen_executor)
    enforcement_validator = EnforcementValidator(
        response_generator=response_generator,
        agent_config_store=store,
        llm_executor=judge_executor,
        config=EnforcementConfig(max_retries=1),
    )

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        enforcement_validator=enforcement_validator,
        fallback_handler=FallbackHandler(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="Hello",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    # First response (casual) should have been blocked, regeneration (professional) should pass
    assert result.enforcement is not None
    assert result.enforcement.passed is True
    assert result.enforcement.regeneration_attempted is True
    assert result.enforcement.regeneration_attempts == 1
    assert result.enforcement.regeneration_succeeded is True
    assert "assist" in result.response.lower()


@pytest.mark.asyncio
async def test_enforcement_always_enforces_global_constraints() -> None:
    """GLOBAL hard constraints are always enforced even if not matched."""
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    # GLOBAL hard constraint that will not be in matched_rules
    global_rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="No financial advice",
        condition_text="Always applies",
        action_text="Never provide financial investment advice",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        # No enforcement_expression - Lane 2
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryAgentConfigStore()
    await store.save_rule(global_rule)

    extraction_resp = json.dumps({"intent": "advice", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    # Empty filter response - rule not matched during retrieval
    filter_resp = json.dumps({"evaluations": []})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    gen_executor = SequenceLLMExecutor([
        "You should invest all your savings in crypto",
        "I cannot provide financial advice. Please consult a qualified financial advisor."
    ])
    # Judge: FAIL first (financial advice), PASS second (refusal)
    judge_executor = SequenceLLMExecutor([
        "FAIL: Response provides financial investment advice",
        "PASS"
    ])

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_executor=gen_executor)
    enforcement_validator = EnforcementValidator(
        response_generator=response_generator,
        agent_config_store=store,
        llm_executor=judge_executor,
        config=EnforcementConfig(always_enforce_global=True, max_retries=1),
    )

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        enforcement_validator=enforcement_validator,
        fallback_handler=FallbackHandler(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="What stocks should I buy?",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    # Global rule should have been enforced despite not being in matched_rules
    assert result.enforcement is not None
    assert result.enforcement.passed is True
    assert result.enforcement.regeneration_attempted is True
    assert result.enforcement.regeneration_attempts == 1
    assert result.enforcement.regeneration_succeeded is True
    assert "cannot" in result.response.lower() or "advisor" in result.response.lower()


@pytest.mark.asyncio
async def test_enforcement_max_retries_exceeded() -> None:
    """Test that regeneration stops after max_retries and tracks attempts correctly."""
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    # Rule with deterministic expression - amount must be <= 50
    hard_rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Refund limit",
        condition_text="When processing refunds",
        action_text="Limit refunds to $50",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        enforcement_expression="amount <= 50",  # Lane 1
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryAgentConfigStore()
    await store.save_rule(hard_rule)

    extraction_resp = json.dumps({"intent": "refund", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    filter_resp = json.dumps({"evaluations": [{"rule_id": str(hard_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    # All responses violate the constraint ($75 > $50)
    gen_executor = SequenceLLMExecutor([
        "Your refund of $75 has been processed",  # Initial (violates)
        "Your refund of $80 has been processed",  # Attempt 1 (still violates)
        "Your refund of $90 has been processed",  # Attempt 2 (still violates)
        "Your refund of $85 has been processed",  # Attempt 3 (still violates)
    ])
    judge_executor = SequenceLLMExecutor(["PASS"])  # Not used for Lane 1

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_executor=gen_executor)
    enforcement_validator = EnforcementValidator(
        response_generator=response_generator,
        agent_config_store=store,
        llm_executor=judge_executor,
        config=EnforcementConfig(max_retries=3),  # Allow 3 retries
    )

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        enforcement_validator=enforcement_validator,
        fallback_handler=FallbackHandler(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="I want a refund",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    # All attempts should fail, enforcement should still fail after max_retries
    assert result.enforcement is not None
    assert result.enforcement.passed is False
    assert result.enforcement.regeneration_attempted is True
    assert result.enforcement.regeneration_attempts == 3  # Should have tried 3 times
    assert result.enforcement.regeneration_succeeded is False
    assert len(result.enforcement.violations) > 0
