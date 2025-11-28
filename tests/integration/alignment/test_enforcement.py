"""Integration test for response enforcement."""

import json
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.enforcement import EnforcementValidator, FallbackHandler
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.models import Rule, Scope
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse


class SequenceLLMProvider(LLMProvider):
    """LLM provider that returns responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.generate_calls: list[list[LLMMessage]] = []

    @property
    def provider_name(self) -> str:
        return "sequence"

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.generate_calls.append(messages)
        content = self._responses[len(self.generate_calls) - 1]
        return LLMResponse(content=content, model="seq-model", usage={})

    def generate_stream(self, messages: list[LLMMessage], **kwargs):
        raise NotImplementedError


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

    store = InMemoryConfigStore()
    await store.save_rule(hard_rule)

    # Sequence: extraction JSON, filter JSON, generation violates, regeneration cleans
    llm = SequenceLLMProvider(
        responses=[
            json.dumps({"intent": "test", "entities": [], "sentiment": "neutral", "urgency": "normal"}),
            json.dumps({"evaluations": [{"rule_id": str(hard_rule.id), "applies": True, "relevance": 0.9}]}),
            "This contains secret info",
            "Safe response with no issues",
        ]
    )

    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])
    response_generator = ResponseGenerator(llm_provider=llm)
    enforcement_validator = EnforcementValidator(response_generator=response_generator)

    engine = AlignmentEngine(
        config_store=store,
        llm_provider=llm,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        enforcement_validator=enforcement_validator,
        fallback_handler=FallbackHandler(),
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
