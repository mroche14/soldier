"""Integration tests for template modes."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.models import Scope
from ruche.alignment.models.enums import TemplateResponseMode
from ruche.alignment.models.template import Template
from ruche.alignment.stores import InMemoryAgentConfigStore
from ruche.config.models.pipeline import PipelineConfig
from ruche.providers.embedding import EmbeddingProvider, EmbeddingResponse
from ruche.providers.llm import LLMExecutor, LLMMessage, LLMResponse
from tests.factories.alignment import RuleFactory


class SequenceLLMExecutor(LLMExecutor):
    """LLM executor returning responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses
        self._call_count = 0
        self.generate_calls: list[list[LLMMessage]] = []

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        self.generate_calls.append(messages)
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=content, model="seq-llm", usage={})


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

    store = InMemoryAgentConfigStore()
    template_id = uuid4()
    template = Template(
        id=template_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Exclusive template",
        text="Exact response.",
        mode=TemplateResponseMode.EXCLUSIVE,
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

    extraction_resp = json.dumps({"intent": "test", "entities": [], "sentiment": "neutral", "urgency": "normal"})
    filter_resp = json.dumps({"evaluations": [{"rule_id": str(aligned_rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]})

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    gen_executor = SequenceLLMExecutor(["LLM generation output"])

    embeddings = StaticEmbeddingProvider([1.0, 0.0, 0.0])

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embeddings,
        pipeline_config=PipelineConfig(),
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
    )

    result = await engine.process_turn(
        message="Test",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.response == "Exact response."
    # Generation executor should not have been called (exclusive template)
    assert len(gen_executor.generate_calls) == 0
