"""Unit tests for MemoryRetriever."""

from datetime import datetime
from uuid import uuid4

import pytest

from soldier.alignment.context.situation_snapshot import SituationSnapshot
from soldier.config.models.selection import SelectionConfig
from soldier.memory.models.episode import Episode
from soldier.memory.retrieval.retriever import MemoryRetriever
from soldier.memory.stores.inmemory import InMemoryMemoryStore
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse


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
async def test_memory_retriever_returns_top_results() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    group_id = f"{tenant_id}:{agent_id}"

    store = InMemoryMemoryStore()
    episode_good = Episode(
        group_id=group_id,
        content="Return policy details",
        source="user",
        occurred_at=datetime.utcnow(),
        embedding=[1.0, 0.0, 0.0],
    )
    episode_other = Episode(
        group_id=group_id,
        content="Shipping information",
        source="user",
        occurred_at=datetime.utcnow(),
        embedding=[0.0, 1.0, 0.0],
    )
    await store.add_episode(episode_good)
    await store.add_episode(episode_other)

    retriever = MemoryRetriever(
        memory_store=store,
        embedding_provider=StaticEmbeddingProvider([1.0, 0.0, 0.0]),
        selection_config=SelectionConfig(strategy="fixed_k", params={"k": 1}),
    )

    snapshot = SituationSnapshot(
        message="returns",
        embedding=[1.0, 0.0, 0.0],
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
    )

    results = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        snapshot=snapshot,
    )

    assert len(results) == 1
    assert results[0].content == "Return policy details"
