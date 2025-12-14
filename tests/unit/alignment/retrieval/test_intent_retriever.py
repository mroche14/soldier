"""Tests for intent retrieval."""

import pytest
from uuid import uuid4
from datetime import datetime, UTC

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.models.intent import Intent
from ruche.alignment.retrieval.intent_retriever import IntentRetriever
from ruche.alignment.stores.inmemory import InMemoryAgentConfigStore
from ruche.config.models.selection import SelectionConfig
from ruche.providers.embedding import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def dimensions(self) -> int:
        return 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch of texts."""
        return [
            [float(ord(c)) / 1000.0 for c in text[:384]] + [0.0] * (384 - len(text))
            for text in texts
        ]

    async def embed_single(self, text: str) -> list[float]:
        """Generate simple embedding based on text."""
        return [float(ord(c)) / 1000.0 for c in text[:384]] + [0.0] * (384 - len(text))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate batch embeddings."""
        return await self.embed(texts)


@pytest.fixture
def config_store():
    """In-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def embedding_provider():
    """Mock embedding provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
async def sample_intents(config_store, tenant_id, agent_id, embedding_provider):
    """Create sample intents with embeddings."""
    intents = [
        Intent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="order_cancellation",
            description="User wants to cancel their order",
            example_phrases=[
                "cancel my order",
                "I want to cancel",
                "cancel order please",
            ],
            embedding=await embedding_provider.embed_single(
                "cancel my order I want to cancel cancel order please"
            ),
            embedding_model="mock",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enabled=True,
        ),
        Intent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="refund_request",
            description="User wants a refund",
            example_phrases=[
                "I want a refund",
                "give me my money back",
                "refund please",
            ],
            embedding=await embedding_provider.embed_single(
                "I want a refund give me my money back refund please"
            ),
            embedding_model="mock",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enabled=True,
        ),
        Intent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="order_status",
            description="User wants to check order status",
            example_phrases=[
                "where is my order",
                "track my order",
                "order status",
            ],
            embedding=await embedding_provider.embed_single(
                "where is my order track my order order status"
            ),
            embedding_model="mock",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enabled=True,
        ),
    ]

    for intent in intents:
        await config_store.save_intent(intent)

    return intents


class TestIntentRetriever:
    """Test intent retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_with_matching_intent(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_intents
    ):
        """Test retrieving intents with matching query."""
        retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=5, min_k=1, min_score=0.0),
        )

        snapshot = SituationSnapshot(
            message="I want to cancel my order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("I want to cancel my order"),
        )

        candidates = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(candidates) > 0
        # First candidate should be order_cancellation
        assert candidates[0].intent_name == "order_cancellation"
        assert candidates[0].source == "hybrid"
        assert 0.0 <= candidates[0].score <= 1.0

    @pytest.mark.asyncio
    async def test_retrieve_no_intents(
        self, config_store, embedding_provider, tenant_id, agent_id
    ):
        """Test retrieval when no intents exist."""
        retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=5, min_k=1, min_score=0.0),
        )

        snapshot = SituationSnapshot(
            message="test query",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("test query"),
        )

        candidates = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_retrieve_respects_selection_strategy(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_intents
    ):
        """Test that selection strategy limits results."""
        retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=2, min_k=1, min_score=0.0),
        )

        snapshot = SituationSnapshot(
            message="I want to cancel my order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("I want to cancel my order"),
        )

        candidates = await retriever.retrieve(tenant_id, agent_id, snapshot)

        # Should return at most max_k=2 candidates
        assert len(candidates) <= 2

    @pytest.mark.asyncio
    async def test_retrieve_disabled_intents_excluded(
        self, config_store, embedding_provider, tenant_id, agent_id
    ):
        """Test that disabled intents are excluded."""
        # Create enabled and disabled intents
        enabled_intent = Intent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="enabled_intent",
            example_phrases=["test query"],
            embedding=await embedding_provider.embed_single("test query"),
            embedding_model="mock",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enabled=True,
        )

        disabled_intent = Intent(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="disabled_intent",
            example_phrases=["test query"],
            embedding=await embedding_provider.embed_single("test query"),
            embedding_model="mock",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            enabled=False,
        )

        await config_store.save_intent(enabled_intent)
        await config_store.save_intent(disabled_intent)

        retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
        )

        snapshot = SituationSnapshot(
            message="test query",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("test query"),
        )

        candidates = await retriever.retrieve(tenant_id, agent_id, snapshot)

        # Should only return enabled intent
        assert len(candidates) == 1
        assert candidates[0].intent_name == "enabled_intent"

    @pytest.mark.asyncio
    async def test_retrieve_uses_cached_embedding(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_intents
    ):
        """Test that cached context embedding is used."""
        retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=5, min_k=1, min_score=0.0),
        )

        cached_embedding = await embedding_provider.embed_single("cancel order")
        snapshot = SituationSnapshot(
            message="cancel order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=cached_embedding,
        )

        candidates = await retriever.retrieve(tenant_id, agent_id, snapshot)

        # Should successfully retrieve using cached embedding
        assert len(candidates) > 0
