"""Integration test for tool execution flow."""

import json
from typing import Any
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.execution import ToolExecutor
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.models import Scope
from soldier.alignment.stores import InMemoryAgentConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMExecutor, LLMMessage, LLMResponse
from tests.factories.alignment import RuleFactory


class SequenceLLMExecutor(LLMExecutor):
    """LLM executor returning responses in sequence."""

    def __init__(self, responses: list[str]) -> None:
        super().__init__(model="mock/test", step_name="test")
        self._responses = responses
        self._call_count = 0

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=content, model="mock-model", usage={})


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

    store = InMemoryAgentConfigStore()
    await store.save_rule(rule)

    async def lookup_order_tool(context, matched_rule: MatchedRule):
        return {"status": "shipped", "rule": matched_rule.rule.name, "message": context.message}

    # Create executors for each step
    extraction_resp = json.dumps(
        {"intent": "order_status", "entities": [], "sentiment": "neutral", "urgency": "normal"}
    )
    filter_resp = json.dumps(
        {"evaluations": [{"rule_id": str(rule.id), "applies": True, "relevance": 0.9}]}
    )

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    gen_executor = SequenceLLMExecutor(["Here is the result with tool output."])

    tool_executor = ToolExecutor({"lookup_order": lookup_order_tool})
    embedding_provider = StaticEmbeddingProvider([1.0, 0.0, 0.0])

    engine = AlignmentEngine(
        config_store=store,
        embedding_provider=embedding_provider,
        pipeline_config=PipelineConfig(),
        tool_executor=tool_executor,
        executors={
            "context_extraction": context_executor,
            "rule_filtering": filter_executor,
            "generation": gen_executor,
        },
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
