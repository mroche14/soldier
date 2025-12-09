"""Reranker for memory episodes."""

from soldier.alignment.retrieval.models import ScoredEpisode
from soldier.observability.logging import get_logger
from soldier.providers.rerank import RerankProvider

logger = get_logger(__name__)


class MemoryReranker:
    """Apply a rerank provider to reorder scored memory episodes.

    Reranking improves memory retrieval precision by using a cross-encoder
    model to score query-episode pairs more accurately than
    embedding-based similarity alone.
    """

    def __init__(self, provider: RerankProvider, top_k: int | None = None) -> None:
        """Initialize the reranker.

        Args:
            provider: RerankProvider implementation
            top_k: Optional limit on results to keep from reranker
        """
        self._provider = provider
        self._top_k = top_k

    async def rerank(
        self,
        query: str,
        scored_episodes: list[ScoredEpisode],
    ) -> list[ScoredEpisode]:
        """Rerank scored episodes using the provider.

        Args:
            query: Query text to rank against
            scored_episodes: Existing scored episodes

        Returns:
            Reranked scored episodes (may be a subset if top_k is set)
        """
        if not scored_episodes:
            return []

        documents = [episode.content for episode in scored_episodes]
        response = await self._provider.rerank(
            query=query,
            documents=documents,
            top_k=self._top_k,
        )

        index_map = dict(enumerate(scored_episodes))
        reranked: list[ScoredEpisode] = []

        for result in response.results:
            candidate = index_map.get(result.index)
            if candidate:
                reranked.append(
                    ScoredEpisode(
                        episode_id=candidate.episode_id,
                        content=candidate.content,
                        score=result.score,
                        metadata=candidate.metadata,
                    )
                )

        if not reranked:
            logger.debug("rerank_no_results", count=len(scored_episodes))
            return scored_episodes

        return reranked
