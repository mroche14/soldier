"""Unit tests for RuleRetriever."""

from uuid import UUID, uuid4

import pytest

from focal.alignment.context.situation_snapshot import SituationSnapshot
from focal.alignment.models import Scope
from focal.alignment.retrieval.models import RuleSource
from focal.alignment.retrieval.reranker import RuleReranker
from focal.alignment.retrieval.rule_retriever import RuleRetriever
from focal.alignment.stores import InMemoryAgentConfigStore
from focal.config.models.selection import SelectionConfig
from focal.providers.embedding import EmbeddingProvider, EmbeddingResponse
from focal.providers.rerank.mock import MockRerankProvider
from tests.factories.alignment import RuleFactory


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
def config_store() -> InMemoryAgentConfigStore:
    return InMemoryAgentConfigStore()


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
    config_store: InMemoryAgentConfigStore,
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

    snapshot = SituationSnapshot(
        message="test",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        embedding=[1.0, 0.0, 0.0],
    )

    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        snapshot=snapshot,
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
    config_store: InMemoryAgentConfigStore,
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

    snapshot = SituationSnapshot(
        message="test",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        embedding=[1.0, 0.0, 0.0],
        turn_count=3,
    )

    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        snapshot=snapshot,
        fired_rule_counts={over_fired.id: 1},
        last_fired_turns={in_cooldown.id: 2},
    )

    names = {rule.rule.name for rule in result.rules}
    assert names == {"Allowed"}


@pytest.mark.asyncio
async def test_reranker_reorders_results(
    config_store: InMemoryAgentConfigStore,
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

    snapshot = SituationSnapshot(
        message="How do returns work?",
        intent_changed=False,
        topic_changed=False,
        tone="neutral",
        embedding=[0.5, 0.5, 0.0],
    )
    result = await retriever.retrieve(
        tenant_id=tenant_id,
        agent_id=agent_id,
        snapshot=snapshot,
    )

    assert result.rules[0].rule.name == "Return Policy"
    assert rerank_provider.call_history  # Reranker was invoked
