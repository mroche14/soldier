"""Unit tests for ScenarioRetriever."""

from uuid import UUID, uuid4

import pytest

from soldier.alignment.context.models import Context
from soldier.alignment.models.scenario import Scenario, ScenarioStep
from soldier.alignment.retrieval.scenario_retriever import ScenarioRetriever
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.selection import SelectionConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse


class StaticEmbeddingProvider(EmbeddingProvider):
    """Embedding provider returning a fixed vector."""

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


def _make_scenario(
    tenant_id: UUID,
    agent_id: UUID,
    *,
    name: str,
    entry_embedding: list[float],
) -> Scenario:
    step_id = uuid4()
    return Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name=name,
        entry_step_id=step_id,
        steps=[
            ScenarioStep(
                id=step_id,
                scenario_id=step_id,
                name="entry",
                transitions=[],
            )
        ],
        entry_condition_embedding=entry_embedding,
    )


@pytest.mark.asyncio
async def test_scenario_retriever_returns_top_match() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    store = InMemoryConfigStore()

    best = _make_scenario(tenant_id, agent_id, name="Best", entry_embedding=[1.0, 0.0, 0.0])
    other = _make_scenario(tenant_id, agent_id, name="Other", entry_embedding=[0.0, 1.0, 0.0])
    await store.save_scenario(best)
    await store.save_scenario(other)

    retriever = ScenarioRetriever(
        config_store=store,
        embedding_provider=StaticEmbeddingProvider([1.0, 0.0, 0.0]),
        selection_config=SelectionConfig(strategy="fixed_k", params={"k": 1}),
    )

    context = Context(message="start return", embedding=[1.0, 0.0, 0.0])
    result = await retriever.retrieve(tenant_id, agent_id, context)

    assert len(result) == 1
    assert result[0].scenario_name == "Best"


@pytest.mark.asyncio
async def test_scenario_retriever_embeds_entry_text_when_missing_embedding() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    store = InMemoryConfigStore()

    step_id = uuid4()
    scenario = Scenario(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="NeedsEmbedding",
        entry_step_id=step_id,
        steps=[ScenarioStep(id=step_id, scenario_id=step_id, name="entry", transitions=[])],
        entry_condition_text="start",
        entry_condition_embedding=None,
    )
    await store.save_scenario(scenario)

    retriever = ScenarioRetriever(
        config_store=store,
        embedding_provider=StaticEmbeddingProvider([0.5, 0.5]),
        selection_config=SelectionConfig(strategy="fixed_k", params={"k": 1}),
    )

    context = Context(message="hello", embedding=[0.5, 0.5])
    result = await retriever.retrieve(tenant_id, agent_id, context)

    assert len(result) == 1
    assert result[0].scenario_name == "NeedsEmbedding"
