"""Memory retrieval with selection strategies."""

from uuid import UUID

from soldier.alignment.context.models import Context
from soldier.alignment.retrieval.models import ScoredEpisode
from soldier.alignment.retrieval.selection import ScoredItem, create_selection_strategy
from soldier.config.models.selection import SelectionConfig
from soldier.memory.store import MemoryStore
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider

logger = get_logger(__name__)


class MemoryRetriever:
    """Retrieve relevant memory episodes using embeddings and selection."""

    def __init__(
        self,
        memory_store: MemoryStore,
        embedding_provider: EmbeddingProvider,
        selection_config: SelectionConfig | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._embedding_provider = embedding_provider
        self._selection_config = selection_config or SelectionConfig()
        self._selection_strategy = create_selection_strategy(
            self._selection_config.strategy,
            **self._selection_config.params,
        )

    @property
    def selection_strategy_name(self) -> str:
        return self._selection_strategy.name

    async def retrieve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        context: Context,
    ) -> list[ScoredEpisode]:
        """Retrieve episodes for the tenant/agent."""
        query_embedding = context.embedding or await self._embedding_provider.embed_single(
            context.message
        )

        group_id = f"{tenant_id}:{agent_id}"
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
        scored.sort(key=lambda s: s.score, reverse=True)

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
