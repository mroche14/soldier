"""Scenario retrieval using embeddings and selection strategies."""

from uuid import UUID

from soldier.alignment.context.models import Context
from soldier.alignment.retrieval.models import ScoredScenario
from soldier.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from soldier.alignment.stores import AgentConfigStore
from soldier.config.models.selection import SelectionConfig
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider
from soldier.utils.vector import cosine_similarity

logger = get_logger(__name__)


class ScenarioRetriever:
    """Retrieve candidate scenarios using similarity against entry conditions.

    Scenarios are retrieved by comparing the user message embedding against
    each scenario's entry condition embedding. Selection strategies filter
    to the most relevant candidates.
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
    ) -> None:
        """Initialize the scenario retriever.

        Args:
            config_store: Store for scenario definitions
            embedding_provider: Provider for query embeddings
            selection_config: Configuration for selection strategy
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )

    @property
    def selection_strategy_name(self) -> str:
        """Return the selection strategy name."""
        return self._selection_strategy.name

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        context: Context,
    ) -> list[ScoredScenario]:
        """Retrieve scenarios for an agent and apply selection.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            context: Extracted context with embedding

        Returns:
            List of scored scenarios sorted by relevance
        """
        scenarios = await self._config_store.get_scenarios(
            tenant_id,
            agent_id,
            enabled_only=True,
        )

        if not scenarios:
            return []

        context_embedding = context.embedding or await self._embedding_provider.embed_single(
            context.message
        )

        scored: list[ScoredScenario] = []
        for scenario in scenarios:
            entry_embedding = scenario.entry_condition_embedding
            if entry_embedding is None and scenario.entry_condition_text:
                try:
                    entry_embedding = await self._embedding_provider.embed_single(
                        scenario.entry_condition_text
                    )
                except Exception:
                    entry_embedding = None

            score = self._score_scenario(entry_embedding, context_embedding)
            scored.append(
                ScoredScenario(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    score=score,
                )
            )

        scored.sort(key=lambda s: s.score, reverse=True)

        # Filter by min_score but ensure min_k is honored
        above_min = [s for s in scored if s.score >= self._selection_config.min_score]
        pool = above_min if len(above_min) >= self._selection_config.min_k else scored

        items = [ScoredItem(item=s, score=s.score) for s in pool]
        selection = self._selection_strategy.select(
            items,
            max_k=self._selection_config.max_k,
            min_k=self._selection_config.min_k,
        )

        return [item.item for item in selection.selected]

    def _score_scenario(
        self,
        entry_embedding: list[float] | None,
        query_embedding: list[float],
    ) -> float:
        """Compute similarity score for a scenario entry condition."""
        if entry_embedding is None:
            return 0.0
        try:
            return cosine_similarity(query_embedding, entry_embedding)
        except ValueError:
            return 0.0
