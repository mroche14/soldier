"""Tests for hybrid rule retrieval."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.models import Rule, Scope
from ruche.brains.focal.retrieval.rule_retriever import RuleRetriever
from ruche.brains.focal.stores.inmemory import InMemoryAgentConfigStore
from ruche.config.models.pipeline import HybridRetrievalConfig
from ruche.config.models.selection import SelectionConfig
from ruche.infrastructure.providers.embedding import EmbeddingProvider


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
        return [[float(len(text)) / 100.0] * 384 for text in texts]

    async def embed_single(self, text: str) -> list[float]:
        """Generate simple embedding based on text length."""
        return [float(len(text)) / 100.0] * 384

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
async def sample_rules(config_store, tenant_id, agent_id, embedding_provider):
    """Create sample rules with embeddings."""
    rules = [
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Cancel Order Rule",
            scope=Scope.GLOBAL,
            scope_id=None,
            priority=100,
            condition_text="user wants to cancel their order",
            condition_embedding=await embedding_provider.embed_single(
                "user wants to cancel their order"
            ),
            action_text="offer cancellation",
            enabled=True,
        ),
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Return Product Rule",
            scope=Scope.GLOBAL,
            scope_id=None,
            priority=90,
            condition_text="user wants to return a product",
            condition_embedding=await embedding_provider.embed_single(
                "user wants to return a product"
            ),
            action_text="provide return instructions",
            enabled=True,
        ),
        Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Refund Info Rule",
            scope=Scope.GLOBAL,
            scope_id=None,
            priority=80,
            condition_text="user wants refund information",
            condition_embedding=await embedding_provider.embed_single(
                "user wants refund information"
            ),
            action_text="explain refund policy",
            enabled=True,
        ),
    ]

    for rule in rules:
        await config_store.save_rule(rule)

    return rules


class TestHybridRuleRetrieval:
    """Test hybrid rule retrieval with BM25 + vector."""

    @pytest.mark.asyncio
    async def test_vector_only_retrieval(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_rules
    ):
        """Test vector-only retrieval (hybrid disabled)."""
        retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
            hybrid_config=None,  # No hybrid
        )

        snapshot = SituationSnapshot(
            message="I want to cancel my order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("I want to cancel my order"),
        )

        result = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(result.rules) > 0
        # First rule should match best with "cancel order"
        assert "cancel" in result.rules[0].rule.condition_text.lower()

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_enabled(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_rules
    ):
        """Test hybrid retrieval with BM25 enabled."""
        hybrid_config = HybridRetrievalConfig(
            enabled=True,
            vector_weight=0.5,
            bm25_weight=0.5,
            normalization="min_max",
        )

        retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
            hybrid_config=hybrid_config,
        )

        snapshot = SituationSnapshot(
            message="cancel order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("cancel order"),
        )

        result = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(result.rules) > 0
        # Lexical match should boost "cancel" rule
        assert "cancel" in result.rules[0].rule.condition_text.lower()

    @pytest.mark.asyncio
    async def test_hybrid_improves_lexical_matches(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_rules
    ):
        """Test that hybrid retrieval improves lexical keyword matches."""
        hybrid_config = HybridRetrievalConfig(
            enabled=True,
            vector_weight=0.3,
            bm25_weight=0.7,  # Favor lexical matching
            normalization="min_max",
        )

        retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
            hybrid_config=hybrid_config,
        )

        # Query with exact keyword match
        snapshot = SituationSnapshot(
            message="refund",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("refund"),
        )

        result = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(result.rules) > 0
        # Rule with "refund" keyword should rank highly due to BM25
        assert "refund" in result.rules[0].rule.condition_text.lower()

    @pytest.mark.asyncio
    async def test_hybrid_different_normalizations(
        self, config_store, embedding_provider, tenant_id, agent_id, sample_rules
    ):
        """Test hybrid retrieval with different normalization methods."""
        for normalization in ["min_max", "z_score", "softmax"]:
            hybrid_config = HybridRetrievalConfig(
                enabled=True,
                vector_weight=0.5,
                bm25_weight=0.5,
                normalization=normalization,
            )

            retriever = RuleRetriever(
                config_store=config_store,
                embedding_provider=embedding_provider,
                selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
                hybrid_config=hybrid_config,
            )

            snapshot = SituationSnapshot(
                message="cancel order",
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
                embedding=await embedding_provider.embed_single("cancel order"),
            )

            result = await retriever.retrieve(tenant_id, agent_id, snapshot)

            # All normalizations should return results
            assert len(result.rules) > 0

    @pytest.mark.asyncio
    async def test_hybrid_with_business_filters(
        self, config_store, embedding_provider, tenant_id, agent_id
    ):
        """Test that hybrid retrieval respects business filters."""
        # Create rule with max_fires limit
        rule = Rule(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Special Offer Rule",
            scope=Scope.GLOBAL,
            scope_id=None,
            priority=100,
            condition_text="special offer",
            condition_embedding=await embedding_provider.embed_single("special offer"),
            action_text="show offer",
            enabled=True,
            max_fires_per_session=1,
        )
        await config_store.save_rule(rule)

        hybrid_config = HybridRetrievalConfig(enabled=True)

        retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
            hybrid_config=hybrid_config,
        )

        snapshot = SituationSnapshot(
            message="special offer",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("special offer"),
        )

        # First retrieval should return the rule
        result1 = await retriever.retrieve(
            tenant_id,
            agent_id,
            snapshot,
            fired_rule_counts={rule.id: 0},
        )
        assert len(result1.rules) == 1

        # Second retrieval with rule already fired should exclude it
        result2 = await retriever.retrieve(
            tenant_id,
            agent_id,
            snapshot,
            fired_rule_counts={rule.id: 1},
        )
        assert len(result2.rules) == 0

    @pytest.mark.asyncio
    async def test_hybrid_empty_rules(
        self, config_store, embedding_provider, tenant_id, agent_id
    ):
        """Test hybrid retrieval with no matching rules."""
        hybrid_config = HybridRetrievalConfig(enabled=True)

        retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=SelectionConfig(max_k=10, min_k=1, min_score=0.0),
            hybrid_config=hybrid_config,
        )

        snapshot = SituationSnapshot(
            message="test query",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            embedding=await embedding_provider.embed_single("test query"),
        )

        result = await retriever.retrieve(tenant_id, agent_id, snapshot)

        assert len(result.rules) == 0
        assert result.retrieval_time_ms >= 0
