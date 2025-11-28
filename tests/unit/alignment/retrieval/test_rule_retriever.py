"""Unit tests for RuleRetriever."""

from uuid import UUID, uuid4

import pytest

from soldier.alignment.context.models import Context
from soldier.alignment.models import Scope
from soldier.alignment.retrieval.models import RuleSource
from soldier.alignment.retrieval.rule_retriever import RuleRetriever
from soldier.alignment.retrieval.reranker import RuleReranker
from soldier.alignment.stores import InMemoryConfigStore
from soldier.config.models.selection import SelectionConfig
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.rerank.mock import MockRerankProvider
from tests.factories.alignment import ContextFactory, RuleFactory


class StaticEmbeddingProvider(EmbeddingProvider):
    """Embedding provider returning a static embedding for tests."""

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


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture
def agent_id() -> UUID:
    return uuid4()


@pytest.fixture
def config_store() -> InMemoryConfigStore:
    return InMemoryConfigStore()


@pytest.fixture
def selection_config() -> SelectionConfig:
    return SelectionConfig(
        strategy="fixed_k",
        max_k=5,
        min_k=1,
        min_score=0.0,
        params={"k": 5, "min_score": 0.0},
    )


@pytest.fixture
def embedding_provider() -> StaticEmbeddingProvider:
    return StaticEmbeddingProvider([1.0, 0.0, 0.0])


@pytest.mark.asyncio
async def test_retrieve_returns_rules_across_scopes(
    config_store: InMemoryConfigStore,
    embedding_provider: StaticEmbeddingProvider,
    selection_config: SelectionConfig,
    tenant_id: UUID,
    agent_id: UUID,
) -> None:
    """Global, scenario, and step scoped rules are returned when available."""
    scenario_id = uuid4()
    step_id = uuid4()

    global_rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Global",
        embedding=[1.0, 0.0, 0.0],
    )
    scenario_rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Scenario",
        scope=Scope.SCENARIO,
        scope_id=scenario_id,
        embedding=[0.9, 0.0, 0.0],
    )
    step_rule = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Step",
        scope=Scope.STEP,
        scope_id=step_id,
        embedding=[0.8, 0.0, 0.0],
    )

    for rule in (global_rule, scenario_rule, step_rule):
        await config_store.save_rule(rule)

    retriever = RuleRetriever(
        config_store=config_store,
        embedding_provider=embedding_provider,
        selection_config=selection_config,
    )

    context = ContextFactory.create(embedding=[1.0, 0.0, 0.0])

    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        context=context,
        active_scenario_id=scenario_id,
        active_step_id=step_id,
    )

    assert {rule.source for rule in result.rules} == {
        RuleSource.GLOBAL,
        RuleSource.SCENARIO,
        RuleSource.STEP,
    }


@pytest.mark.asyncio
async def test_business_filters_exclude_fired_rules(
    config_store: InMemoryConfigStore,
    embedding_provider: StaticEmbeddingProvider,
    selection_config: SelectionConfig,
    tenant_id: UUID,
    agent_id: UUID,
) -> None:
    """Rules exceeding max fires or within cooldown are excluded."""
    over_fired = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Over fired",
        max_fires_per_session=1,
        embedding=[1.0, 0.0, 0.0],
    )
    in_cooldown = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Cooling",
        cooldown_turns=2,
        embedding=[1.0, 0.0, 0.0],
    )
    allowed = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Allowed",
        embedding=[1.0, 0.0, 0.0],
    )

    for rule in (over_fired, in_cooldown, allowed):
        await config_store.save_rule(rule)

    retriever = RuleRetriever(
        config_store=config_store,
        embedding_provider=embedding_provider,
        selection_config=selection_config,
    )

    context = Context(message="test", embedding=[1.0, 0.0, 0.0], turn_count=3)

    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        context=context,
        fired_rule_counts={over_fired.id: 1},
        last_fired_turns={in_cooldown.id: 2},
    )

    names = {rule.rule.name for rule in result.rules}
    assert names == {"Allowed"}


@pytest.mark.asyncio
async def test_reranker_reorders_results(
    config_store: InMemoryConfigStore,
    embedding_provider: StaticEmbeddingProvider,
    selection_config: SelectionConfig,
    tenant_id: UUID,
    agent_id: UUID,
) -> None:
    """Reranker output dictates final ordering."""
    less_relevant = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Shipping",
        condition_text="Ask about shipping",
        action_text="Explain shipping",
        embedding=[0.5, 0.5, 0.0],
    )
    more_relevant = RuleFactory.create(
        tenant_id=tenant_id,
        agent_id=agent_id,
        name="Return Policy",
        condition_text="Ask about returns",
        action_text="Explain returns",
        embedding=[0.5, 0.5, 0.0],
    )

    for rule in (less_relevant, more_relevant):
        await config_store.save_rule(rule)

    rerank_provider = MockRerankProvider()
    retriever = RuleRetriever(
        config_store=config_store,
        embedding_provider=embedding_provider,
        selection_config=selection_config,
        reranker=RuleReranker(rerank_provider, top_k=2),
    )

    context = Context(message="How do returns work?", embedding=[0.5, 0.5, 0.0])
    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        context=context,
    )

    assert result.rules[0].rule.name == "Return Policy"
    assert rerank_provider.call_history  # Reranker was invoked
