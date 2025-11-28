"""Integration tests for template modes."""

import json
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.models import Scope
from soldier.alignment.models.enums import TemplateMode
from soldier.alignment.models.template import Template
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse
from tests.factories.alignment import RuleFactory


class SequenceLLMProvider(LLMProvider):
    """LLM provider returning responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.generate_calls: list[list[LLMMessage]] = []

    @property
    def provider_name(self) -> str:
        return "seq-llm"

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.generate_calls.append(messages)
        content = self._responses[len(self.generate_calls) - 1]
        return LLMResponse(content=content, model="seq-llm", usage={})

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
async def test_exclusive_template_skips_generation() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    store = InMemoryConfigStore()
    template_id = uuid4()
    template = Template(
        id=template_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Exclusive template",
        text="Exact response.",
        mode=TemplateMode.EXCLUSIVE,
        scope=Scope.GLOBAL,
    )
    await store.save_template(template)

    aligned_rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=Scope.GLOBAL,
        condition_text="always",
        action_text="respond",
        attached_template_ids=[template_id],
        embedding=[1.0, 0.0, 0.0],
    )
    await store.save_rule(aligned_rule)

    llm = SequenceLLMProvider(
        responses=[
            json.dumps({"intent": "test", "entities": [], "sentiment": "neutral", "urgency": "normal"}),
            json.dumps({"evaluations": [{"rule_id": str(aligned_rule.id), "applies": True, "relevance": 0.9}]}),
            "LLM generation output",
        ]
    )
    embeddings = StaticEmbeddingProvider([1.0, 0.0, 0.0])

    engine = AlignmentEngine(
        config_store=store,
        llm_provider=llm,
        embedding_provider=embeddings,
        pipeline_config=PipelineConfig(),
    )

    result = await engine.process_turn(
        message="Test",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.response == "Exact response."
    # LLM should have been used for extraction + filtering only (no third generation call)
    assert len(llm.generate_calls) == 2
