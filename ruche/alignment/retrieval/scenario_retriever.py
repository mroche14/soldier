"""Scenario retrieval using embeddings and selection strategies."""

from uuid import UUID

from rank_bm25 import BM25Okapi

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.retrieval.models import ScoredScenario
from ruche.alignment.retrieval.reranker import ScenarioReranker
from ruche.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from ruche.alignment.stores import AgentConfigStore
from ruche.config.models.pipeline import HybridRetrievalConfig
from ruche.config.models.selection import SelectionConfig
from ruche.observability.logging import get_logger
from ruche.providers.embedding import EmbeddingProvider
from ruche.utils.hybrid import HybridScorer
from ruche.utils.vector import cosine_similarity

logger = get_logger(__name__)


class ScenarioRetriever:
    """Retrieve candidate scenarios using similarity against entry conditions.

    Scenarios are retrieved by comparing the user message embedding against
    each scenario's entry condition embedding. Selection strategies filter
    to the most relevant candidates. Optional reranking improves precision.
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
        reranker: ScenarioReranker | None = None,
        hybrid_config: HybridRetrievalConfig | None = None,
    ) -> None:
        """Initialize the scenario retriever.

        Args:
            config_store: Store for scenario definitions
            embedding_provider: Provider for query embeddings
            selection_config: Configuration for selection strategy
            reranker: Optional reranker for result refinement
            hybrid_config: Optional hybrid retrieval configuration
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )
        self._reranker = reranker
        self._hybrid_config = hybrid_config
        self._hybrid_scorer = (
            HybridScorer(
                vector_weight=hybrid_config.vector_weight,
                bm25_weight=hybrid_config.bm25_weight,
                normalization=hybrid_config.normalization,
            )
            if hybrid_config and hybrid_config.enabled
            else None
        )

    @property
    def selection_strategy_name(self) -> str:
        """Return the selection strategy name."""
        return self._selection_strategy.name

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        snapshot: SituationSnapshot,
    ) -> list[ScoredScenario]:
        """Retrieve scenarios for an agent and apply selection.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            snapshot: Situational snapshot with message and embedding

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

        query_embedding = snapshot.embedding or await self._embedding_provider.embed_single(
            snapshot.message
        )

        # Use hybrid scoring if configured, else vector-only
        if self._hybrid_scorer:
            scored = await self._hybrid_retrieval(scenarios, query_embedding, snapshot.message)
        else:
            scored = await self._vector_only_retrieval(scenarios, query_embedding)

        scored.sort(key=lambda s: s.score, reverse=True)

        # Optional reranking
        if self._reranker and scored:
            scored = await self._reranker.rerank(snapshot.message, scored)

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

    async def _vector_only_retrieval(
        self,
        scenarios,
        context_embedding: list[float],
    ) -> list[ScoredScenario]:
        """Vector-only retrieval using cosine similarity."""
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
        return scored

    async def _hybrid_retrieval(
        self,
        scenarios,
        context_embedding: list[float],
        query_text: str,
    ) -> list[ScoredScenario]:
        """Hybrid retrieval combining vector and BM25 scores."""
        # Ensure all scenarios have embeddings
        entry_embeddings = []
        for scenario in scenarios:
            entry_embedding = scenario.entry_condition_embedding
            if entry_embedding is None and scenario.entry_condition_text:
                try:
                    entry_embedding = await self._embedding_provider.embed_single(
                        scenario.entry_condition_text
                    )
                except Exception:
                    entry_embedding = None
            entry_embeddings.append(entry_embedding)

        # Compute vector scores
        vector_scores = [
            cosine_similarity(context_embedding, emb) if emb else 0.0
            for emb in entry_embeddings
        ]

        # Compute BM25 scores
        corpus = [
            scenario.entry_condition_text.split() if scenario.entry_condition_text else []
            for scenario in scenarios
        ]
        bm25 = BM25Okapi(corpus)
        bm25_scores = bm25.get_scores(query_text.split())

        # Combine scores
        combined_scores = self._hybrid_scorer.combine_scores(vector_scores, list(bm25_scores))

        # Build scored scenarios
        scored = [
            ScoredScenario(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                score=score,
            )
            for scenario, score in zip(scenarios, combined_scores)
        ]

        return scored

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
