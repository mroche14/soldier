"""Integration test for AlignmentEngine pipeline."""

import json
from typing import Any
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse
from tests.factories.alignment import RuleFactory


class MockLLMProvider(LLMProvider):
    """Mock LLM provider driving extraction, filtering, and generation."""

    def __init__(
        self,
        extraction_response: dict[str, Any],
        filter_response: dict[str, Any],
        generation_response: str,
    ) -> None:
        self._extraction_response = extraction_response
        self._filter_response = filter_response
        self._generation_response = generation_response
        self.generate_calls: list[list[LLMMessage]] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        self.generate_calls.append(messages)
        call_index = len(self.generate_calls)

        if call_index == 1:
            content = json.dumps(self._extraction_response)
        elif call_index == 2:
            content = json.dumps(self._filter_response)
        else:
            content = self._generation_response

        return LLMResponse(
            content=content,
            model="mock-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

    def generate_stream(self, messages: list[LLMMessage], **kwargs: Any):
        raise NotImplementedError("Streaming not required for this test")


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

    config_store = InMemoryConfigStore()
    rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        condition_text="When user mentions return",
        action_text="Explain return policy",
        embedding=[0.1, 0.1, 0.1],
    )
    await config_store.save_rule(rule)

    llm_provider = MockLLMProvider(
        extraction_response={
            "intent": "return_request",
            "entities": [],
            "sentiment": "neutral",
            "urgency": "normal",
        },
        filter_response={
            "evaluations": [
                {"rule_id": str(rule.id), "applies": True, "relevance": 0.9, "reasoning": "Matches return intent"}
            ]
        },
        generation_response="Here is the return policy.",
    )

    embedding_provider = MockEmbeddingProvider()

    engine = AlignmentEngine(
        config_store=config_store,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
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
