"""Integration test for response enforcement."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.brains.focal.phases.enforcement import EnforcementValidator, FallbackHandler
from ruche.brains.focal.engine import AlignmentEngine
from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.models import Rule, Scope
from ruche.brains.focal.stores import InMemoryAgentConfigStore
from ruche.config.models.pipeline import PipelineConfig
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
async def test_enforcement_regenerates_and_cleans_response() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    hard_rule = Rule(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="No secrets",
        condition_text="Always",
        action_text="secret",
        scope=Scope.GLOBAL,
        is_hard_constraint=True,
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryAgentConfigStore()
    await store.save_rule(hard_rule)

    # Create executors for each step
    extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    filter_resp = json.dumps({"evaluations": [{"rule_id": str(hard_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    # Generation returns violation first, then clean response
    gen_executor = SequenceLLMExecutor(["This contains secret info", "Safe response with no issues"])

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_executor=gen_executor)
    enforcement_validator = EnforcementValidator(
        response_generator=response_generator,
        agent_config_store=store,
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
        message="Tell me something secret",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.enforcement is not None
    assert result.enforcement.passed is True
    assert "secret" not in result.response.lower()
