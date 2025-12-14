"""Integration test for scenario flow in AlignmentEngine."""

import json
from typing import Any
from uuid import uuid4

import pytest

from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.models import Scope
from ruche.alignment.models.scenario import Scenario, ScenarioStep
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

    async def generate(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        content = self._responses[min(self._call_count, len(self._responses) - 1)]
        self._call_count += 1
        return LLMResponse(content=content, model="mock-model", usage={})


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
async def test_scenario_start_flow() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()

    store = InMemoryAgentConfigStore()

    step_id = uuid4()
    scenario = Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Return Flow",
        entry_step_id=step_id,
        steps=[ScenarioStep(id=step_id, scenario_id=step_id, name="entry", transitions=[])],
        entry_condition_embedding=[1.0, 0.0, 0.0],
    )
    await store.save_scenario(scenario)

    rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=Scope.SCENARIO,
        scope_id=scenario.id,
        condition_text="Return related",
        action_text="Handle returns",
        embedding=[1.0, 0.0, 0.0],
    )
    await store.save_rule(rule)

    # Create executors for each step
    extraction_resp = json.dumps({
        "intent": "start return",
        "entities": [],
        "sentiment": "neutral",
        "urgency": "normal",
        "scenario_signal": "start",
    })
    filter_resp = json.dumps({
        "evaluations": [{"rule_id": str(rule.id), "applicability": "APPLIES", "confidence": 0.9, "relevance": 0.9}]
    })

    context_executor = SequenceLLMExecutor([extraction_resp])
    filter_executor = SequenceLLMExecutor([filter_resp])
    gen_executor = SequenceLLMExecutor(["Response with scenario"])

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
        message="I want to start a return",
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
    )

    assert result.scenario_result is not None
    assert result.scenario_result.action.value == "start"
    assert result.scenario_result.scenario_id == scenario.id
    assert result.scenario_result.target_step_id == scenario.entry_step_id
