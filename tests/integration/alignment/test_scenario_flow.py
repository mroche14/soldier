"""Integration test for scenario flow in AlignmentEngine."""

import json
from uuid import uuid4

import pytest

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.models import Scope
from soldier.alignment.models.scenario import Scenario, ScenarioStep
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse
from tests.factories.alignment import RuleFactory


class MockLLMProvider(LLMProvider):
    """Mock LLM provider to drive extraction/filter/generation."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(self, messages: list[LLMMessage], **kwargs) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            content = json.dumps(
                {
                    "intent": "start return",
                    "entities": [],
                    "sentiment": "neutral",
                    "urgency": "normal",
                    "scenario_signal": "start",
                }
            )
        elif self.calls == 2:
            content = json.dumps(
                {
                    "evaluations": [
                        {"rule_id": str(self.rule_id), "applies": True, "relevance": 0.9}
                    ]
                }
            )
        else:
            content = "Response with scenario"

        return LLMResponse(content=content, model="mock-model", usage={})

    def generate_stream(self, messages: list[LLMMessage], **kwargs):
        raise NotImplementedError("Streaming not required for test")


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

    store = InMemoryConfigStore()

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

    llm = MockLLMProvider()
    llm.rule_id = rule.id  # type: ignore[attr-defined]

    embeddings = StaticEmbeddingProvider([1.0, 0.0, 0.0])

    engine = AlignmentEngine(
        config_store=store,
        llm_provider=llm,
        embedding_provider=embeddings,
        pipeline_config=PipelineConfig(),
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
