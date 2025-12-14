"""Memory ingestion orchestrator."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ruche.config.models.pipeline import MemoryIngestionConfig
from ruche.conversation.models.session import Session
from ruche.conversation.models.turn import Turn
from ruche.memory.ingestion.errors import IngestionError
from ruche.memory.ingestion.queue import TaskQueue
from ruche.memory.models.episode import Episode
from ruche.memory.store import MemoryStore
from ruche.observability.logging import get_logger
from ruche.providers.embedding.base import EmbeddingProvider

logger = get_logger(__name__)


class MemoryIngestor:
    """Main orchestrator for episode creation and async task dispatching."""

    def __init__(
        self,
        memory_store: MemoryStore,
        embedding_provider: EmbeddingProvider,
        entity_extractor: Any | None,
        summarizer: Any | None,
        task_queue: TaskQueue,
        config: MemoryIngestionConfig | None = None,
        fallback_embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize memory ingestor.

        Args:
            memory_store: Store for episodes and entities
            embedding_provider: Primary provider for embeddings
            entity_extractor: Service for entity extraction (optional)
            summarizer: Service for summarization (optional)
            task_queue: Queue for async tasks
            config: Configuration for ingestion
            fallback_embedding_provider: Fallback provider for embeddings
        """
        self._memory_store = memory_store
        self._embedding_provider = embedding_provider
        self._fallback_embedding_provider = fallback_embedding_provider
        self._entity_extractor = entity_extractor
        self._summarizer = summarizer
        self._task_queue = task_queue
        self._config = config or MemoryIngestionConfig()

    async def ingest_turn(
        self,
        turn: Turn,
        session: Session,
    ) -> Episode:
        """Ingest a conversation turn into memory.

        Synchronous operations (<500ms):
        - Create Episode model from turn
        - Generate embedding via EmbeddingProvider
        - Store episode in MemoryStore
        - Queue async extraction tasks

        Asynchronous operations (queued):
        - Extract entities and relationships
        - Check if summarization threshold reached

        Args:
            turn: Conversation turn with user message and agent response
            session: Current session context (for group_id)

        Returns:
            Episode: Stored episode with generated embedding

        Raises:
            IngestionError: If episode creation or storage fails
        """
        start_time = datetime.now(UTC)

        try:
            # Build group_id from session context
            group_id = f"{session.tenant_id}:{session.session_id}"

            # Create combined content from turn
            content = self._format_turn_content(turn)

            # Create episode model
            episode = Episode(
                group_id=group_id,
                content=content,
                source="user",  # Mark as user-initiated turn
                content_type="message",
                occurred_at=turn.timestamp,
                source_metadata={
                    "turn_id": str(turn.turn_id),
                    "turn_number": turn.turn_number,
                    "user_message": turn.user_message,
                    "agent_response": turn.agent_response,
                },
            )

            # Generate embedding if enabled
            if self._config.embedding_enabled:
                try:
                    embedding, model_name = await self._generate_embedding_with_fallback(
                        episode.content
                    )
                    episode.embedding = embedding
                    episode.embedding_model = model_name
                except Exception as e:
                    logger.warning(
                        "embedding_generation_failed",
                        episode_id=episode.id,
                        error=str(e),
                    )
                    # Continue without embedding (graceful degradation)

            # Store episode
            await self._memory_store.add_episode(episode)

            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            # Log success
            logger.info(
                "episode_created",
                episode_id=episode.id,
                group_id=episode.group_id,
                content_type=episode.content_type,
                embedding_model=episode.embedding_model,
                latency_ms=latency_ms,
            )

            # Queue async tasks
            if self._config.entity_extraction_enabled and self._config.async_extraction:
                await self._queue_entity_extraction(episode.id, group_id)

            if self._config.summarization_enabled and self._config.async_summarization:
                await self._queue_summarization_check(group_id)

            return episode

        except Exception as e:
            logger.error(
                "ingestion_failed",
                group_id=f"{session.tenant_id}:{session.session_id}",
                error=str(e),
                cause=type(e).__name__,
            )
            raise IngestionError(
                message=f"Failed to ingest turn: {str(e)}",
                group_id=f"{session.tenant_id}:{session.session_id}",
                cause=e,
            ) from e

    async def ingest_event(
        self,
        event_type: str,
        content: str,
        group_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Episode:
        """Ingest a system event into memory.

        Similar to ingest_turn but for non-conversation events
        (e.g., tool execution, scenario transitions, errors).

        Args:
            event_type: Type of event (for source_metadata)
            content: Event description
            group_id: Tenant:session identifier
            metadata: Optional additional context

        Returns:
            Episode: Stored episode

        Raises:
            IngestionError: If episode creation or storage fails
        """
        start_time = datetime.now(UTC)

        try:
            # Create system event episode
            episode = Episode(
                group_id=group_id,
                content=content,
                source="system",
                content_type="event",
                occurred_at=datetime.now(UTC),
                source_metadata={
                    "event_type": event_type,
                    **(metadata or {}),
                },
            )

            # Generate embedding if enabled
            if self._config.embedding_enabled:
                try:
                    embedding, model_name = await self._generate_embedding_with_fallback(
                        episode.content
                    )
                    episode.embedding = embedding
                    episode.embedding_model = model_name
                except Exception:
                    # Continue without embedding for events
                    pass

            # Store episode
            await self._memory_store.add_episode(episode)

            # Calculate latency
            latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                "event_ingested",
                episode_id=episode.id,
                event_type=event_type,
                group_id=group_id,
                latency_ms=latency_ms,
            )

            return episode

        except Exception as e:
            logger.error(
                "event_ingestion_failed",
                event_type=event_type,
                group_id=group_id,
                error=str(e),
            )
            raise IngestionError(
                message=f"Failed to ingest event: {str(e)}",
                group_id=group_id,
                cause=e,
            ) from e

    async def _generate_embedding_with_fallback(
        self, text: str, timeout_ms: int = 500
    ) -> tuple[list[float], str]:
        """Generate embedding with fallback on timeout.

        Args:
            text: Text to embed
            timeout_ms: Timeout for primary provider

        Returns:
            Tuple of (embedding vector, model name)
        """
        try:
            # Try primary provider with timeout
            embedding = await asyncio.wait_for(
                self._embedding_provider.embed_single(text),
                timeout=timeout_ms / 1000,
            )
            return embedding, self._embedding_provider.provider_name

        except TimeoutError:
            # Fallback to secondary provider if available
            if self._fallback_embedding_provider:
                logger.warning(
                    "embedding_timeout_using_fallback",
                    provider=self._embedding_provider.provider_name,
                    fallback=self._fallback_embedding_provider.provider_name,
                )
                embedding = await self._fallback_embedding_provider.embed_single(text)
                return embedding, self._fallback_embedding_provider.provider_name
            else:
                # No fallback, re-raise timeout
                raise

    async def _queue_entity_extraction(self, episode_id: UUID, group_id: str) -> None:
        """Queue async entity extraction task.

        Args:
            episode_id: Episode to process
            group_id: Tenant:session identifier
        """
        try:
            await self._task_queue.enqueue(
                "extract_entities",
                episode_id=episode_id,
                group_id=group_id,
            )
        except Exception as e:
            logger.error(
                "failed_to_queue_extraction",
                episode_id=episode_id,
                error=str(e),
            )

    async def _queue_summarization_check(self, group_id: str) -> None:
        """Queue async summarization threshold check.

        Args:
            group_id: Tenant:session identifier
        """
        try:
            await self._task_queue.enqueue(
                "check_summarization",
                group_id=group_id,
            )
        except Exception as e:
            logger.error(
                "failed_to_queue_summarization",
                group_id=group_id,
                error=str(e),
            )

    def _format_turn_content(self, turn: Turn) -> str:
        """Format turn into combined content string.

        Args:
            turn: Turn to format

        Returns:
            Combined content string
        """
        return f"User: {turn.user_message}\nAgent: {turn.agent_response}"
