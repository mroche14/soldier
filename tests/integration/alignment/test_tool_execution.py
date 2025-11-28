"""Integration test for tool execution flow."""

import json
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.execution import ToolExecutor
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.models import Scope
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse
from tests.factories.alignment import RuleFactory


class MockLLMProvider(LLMProvider):
    """Drive extraction, filtering, and generation for tool flow."""

    def __init__(self, rule_id):
        self.rule_id = rule_id
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            content = json.dumps(
                {"intent": "order_status", "entities": [], "sentiment": "neutral", "urgency": "normal"}
            )
        elif self.calls == 2:
            content = json.dumps(
                {"evaluations": [{"rule_id": str(self.rule_id), "applies": True, "relevance": 0.9}]}
            )
        else:
            content = "Here is the result with tool output."
        return LLMResponse(content=content, model="mock-model", usage={})

    def generate_stream(self, messages: list[LLMMessage], **kwargs):
        raise NotImplementedError


class StaticEmbeddingProvider(EmbeddingProvider):
    """Return fixed embeddings for tests."""

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
async def test_tool_execution_flow_integration() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=Scope.GLOBAL,
        attached_tool_ids=["lookup_order"],
        embedding=[1.0, 0.0, 0.0],
    )

    store = InMemoryConfigStore()
    await store.save_rule(rule)

    async def lookup_order_tool(context, matched_rule: MatchedRule):
        return {"status": "shipped", "rule": matched_rule.rule.name, "message": context.message}

    tool_executor = ToolExecutor({"lookup_order": lookup_order_tool})
    llm_provider = MockLLMProvider(rule_id=rule.id)
    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])

    engine = AlignmentEngine(
        config_store=store,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        tool_executor=tool_executor,
    )

    result = await engine.process_turn(
        message="Where is my order?",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.tool_results
    tool_result = result.tool_results[0]
    assert tool_result.success is True
    assert tool_result.outputs["status"] == "shipped"
