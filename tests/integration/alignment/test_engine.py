"""Integration test for AlignmentEngine pipeline."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.brains.focal.pipeline import FocalCognitivePipeline as AlignmentEngine
from ruche.brains.focal.stores import InMemoryAgentConfigStore
from ruche.config.models.pipeline import PipelineConfig
from ruche.infrastructure.providers.embedding import EmbeddingProvider, EmbeddingResponse
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage, LLMResponse
from tests.factories.alignment import RuleFactory


class MockSequencedLLMExecutor(LLMExecutor):
    """Mock LLM executor that returns different responses based on call sequence."""

    def __init__(
        self,
        responses: list[str],
    ) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses
        self._call_count = 0
        self.generate_calls: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        self.generate_calls.append(messages)
        response_index = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return LLMResponse(
            content=self._responses[response_index],
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider returning constant embeddings."""

    def __init__(self, dims: int = 3) -> None:
        self._dims = dims

    @property
    def provider_name(self) -> str:
        return "mock-embedding"

    @property
    def dimensions(self) -> int:
        return self._dims

    async def embed(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[[0.1] * self._dims for _ in texts],
            model="mock-embedding",
            dimensions=self._dims,
        )


@pytest.mark.asyncio
async def test_alignment_engine_full_pipeline() -> None:
    """Process a turn end-to-end with retrieval, filtering, and generation."""
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    config_store = InMemoryAgentConfigStore()
    rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        condition_text="When user mentions return",
        action_text="Explain return policy",
        embedding=[0.1, 0.1, 0.1],
    )
    await config_store.save_rule(rule)

    extraction_response = json.dumps({
        "intent": "return_request",
        "entities": [],
        "sentiment": "neutral",
        "urgency": "normal",
    })
    filter_response = json.dumps({
        "evaluations": [
            {"rule_id": str(rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9, "reasoning": "Matches return intent"}
        ]
    })
    generation_response = "Here is the return policy."

    # Create executors for each step
    context_executor = MockSequencedLLMExecutor(responses=[extraction_response])
    filter_executor = MockSequencedLLMExecutor(responses=[filter_response])
    gen_executor = MockSequencedLLMExecutor(responses=[generation_response])

    embedding_provider = MockEmbeddingProvider()

    engine = AlignmentEngine(
        config_store=config_store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="I need to return my order",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.response == "Here is the return policy."
    assert result.retrieval is not None
    assert len(result.retrieval.rules) == 1
    assert result.matched_rules[0].rule.id == rule.id
