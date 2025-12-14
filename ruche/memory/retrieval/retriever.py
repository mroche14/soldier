"""Memory retrieval with selection strategies."""

from uuid import UUID

from rank_bm25 import BM25Okapi

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.retrieval.models import ScoredEpisode
from ruche.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from ruche.config.models.pipeline import HybridRetrievalConfig
from ruche.config.models.selection import SelectionConfig
from ruche.memory.retrieval.reranker import MemoryReranker
from ruche.memory.store import MemoryStore
from ruche.observability.logging import get_logger
from ruche.providers.embedding import EmbeddingProvider
from ruche.utils.hybrid import HybridScorer
from ruche.utils.vector import cosine_similarity

logger = get_logger(__name__)


class MemoryRetriever:
    """Retrieve relevant memory episodes using embeddings and selection."""

    def __init__(
        self,
        memory_store: MemoryStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
        reranker: MemoryReranker | None = None,
        hybrid_config: HybridRetrievalConfig | None = None,
    ) -> None:
        self._memory_store = memory_store
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
        return self._selection_strategy.name

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        snapshot: SituationSnapshot,
    ) -> list[ScoredEpisode]:
        """Retrieve episodes for the tenant/agent."""
        query_embedding = snapshot.embedding or await self._embedding_provider.embed_single(
            snapshot.message
        )

        group_id = f"{tenant_id}:{agent_id}"

        # Use hybrid scoring if configured
        if self._hybrid_scorer:
            scored = await self._hybrid_retrieval(
                query_embedding, snapshot.message, group_id
            )
        else:
            scored = await self._vector_only_retrieval(query_embedding, group_id)

        scored.sort(key=lambda s: s.score, reverse=True)

        # Optional reranking
        if self._reranker and scored:
            scored = await self._reranker.rerank(snapshot.message, scored)

        # Selection
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
        query_embedding: list[float],
        group_id: str,
    ) -> list[ScoredEpisode]:
        """Vector-only retrieval using cosine similarity."""
        raw_results = await self._memory_store.vector_search_episodes(
            query_embedding,
            group_id=group_id,
            limit=self._selection_config.max_k,
            min_score=self._selection_config.min_score,
        )

        scored = [
            ScoredEpisode(
                episode_id=episode.id,
                content=episode.content,
                score=score,
                metadata={"occurred_at": str(episode.occurred_at)},
            )
            for episode, score in raw_results
        ]
        return scored

    async def _hybrid_retrieval(
        self,
        query_embedding: list[float],
        query_text: str,
        group_id: str,
    ) -> list[ScoredEpisode]:
        """Hybrid retrieval combining vector and BM25 scores."""
        # Get all episodes for the group (no limit for hybrid scoring)
        raw_results = await self._memory_store.vector_search_episodes(
            query_embedding,
            group_id=group_id,
            limit=self._selection_config.max_k * 2,  # Get more for BM25 reranking
            min_score=0.0,  # No threshold for hybrid
        )

        if not raw_results:
            return []

        episodes = [episode for episode, _ in raw_results]
        vector_scores = [score for _, score in raw_results]

        # Compute BM25 scores
        corpus = [episode.content.split() for episode in episodes]
        bm25 = BM25Okapi(corpus)
        bm25_scores = bm25.get_scores(query_text.split())

        # Combine scores
        combined_scores = self._hybrid_scorer.combine_scores(vector_scores, list(bm25_scores))

        # Build scored episodes
        scored = [
            ScoredEpisode(
                episode_id=episode.id,
                content=episode.content,
                score=score,
                metadata={"occurred_at": str(episode.occurred_at)},
            )
            for episode, score in zip(episodes, combined_scores)
        ]

        return scored
