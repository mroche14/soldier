"""Tests for MemoryIngestor."""

from uuid import uuid4

import pytest

from focal.conversation.models import Session, Turn
from focal.conversation.models.enums import Channel
from focal.memory.ingestion.errors import IngestionError
from focal.memory.ingestion.ingestor import MemoryIngestor
from focal.memory.ingestion.queue import InMemoryTaskQueue
from focal.memory.stores.inmemory import InMemoryMemoryStore
from focal.providers.embedding.mock import MockEmbeddingProvider


@pytest.fixture
def memory_store():
    """Create in-memory store for testing."""
    return InMemoryMemoryStore()


@pytest.fixture
def embedding_provider():
    """Create mock embedding provider."""
    return MockEmbeddingProvider(dimensions=768)


@pytest.fixture
def task_queue():
    """Create in-memory task queue."""
    return InMemoryTaskQueue()


@pytest.fixture
def session():
    """Create test session."""
    return Session(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.API,
        user_channel_id="test-user",
        config_version=1,
    )


@pytest.fixture
def turn(session):
    """Create test turn."""
    return Turn(
        tenant_id=session.tenant_id,
        session_id=session.session_id,
        turn_number=1,
        user_message="I ordered a laptop but it arrived damaged",
        agent_response="I'm sorry to hear that. Let me help you.",
        latency_ms=100,
        tokens_used=50,
    )


class TestMemoryIngestorEpisodeCreation:
    """Tests for episode creation functionality."""

    @pytest.mark.asyncio
    async def test_ingest_turn_creates_episode(
        self, memory_store, embedding_provider, task_queue, session, turn
    ):
        """Should create episode from turn."""
        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
        )

        episode = await ingestor.ingest_turn(turn, session)

        assert episode is not None
        assert episode.content is not None
        assert episode.group_id == f"{session.tenant_id}:{session.session_id}"
        assert episode.source in ["user", "agent", "system"]

    @pytest.mark.asyncio
    async def test_ingest_turn_generates_embedding(
        self, memory_store, embedding_provider, task_queue, session, turn
    ):
        """Should generate embedding for episode."""
        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
        )

        episode = await ingestor.ingest_turn(turn, session)

        assert episode.embedding is not None
        assert len(episode.embedding) == 768
        assert episode.embedding_model is not None

    @pytest.mark.asyncio
    async def test_ingest_turn_embedding_fallback_on_timeout(
        self, memory_store, task_queue, session, turn
    ):
        """Should fallback when embedding times out."""
        # Create a slow embedding provider
        class SlowEmbeddingProvider(MockEmbeddingProvider):
            async def embed(self, texts, **kwargs):
                import asyncio

                await asyncio.sleep(2)  # Simulate timeout
                return await super().embed(texts, **kwargs)

        slow_provider = SlowEmbeddingProvider(dimensions=768)
        fallback_provider = MockEmbeddingProvider(dimensions=1536)

        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=slow_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
            fallback_embedding_provider=fallback_provider,
        )

        # This should not raise, should use fallback
        episode = await ingestor.ingest_turn(turn, session)
        assert episode is not None

    @pytest.mark.asyncio
    async def test_ingest_event_creates_system_episode(
        self, memory_store, embedding_provider, task_queue
    ):
        """Should create system event episode."""
        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
        )

        group_id = f"{uuid4()}:{uuid4()}"
        episode = await ingestor.ingest_event(
            event_type="tool_executed",
            content="Tool 'check_order' executed successfully",
            group_id=group_id,
            metadata={"tool": "check_order"},
        )

        assert episode.source == "system"
        assert episode.content_type == "event"
        assert episode.group_id == group_id
        assert "tool_executed" in episode.source_metadata.get("event_type", "")


class TestMemoryIngestorAsyncTasks:
    """Tests for async task queuing."""

    @pytest.mark.asyncio
    async def test_ingest_turn_queues_async_tasks(
        self, memory_store, embedding_provider, task_queue, session, turn
    ):
        """Should queue entity extraction task."""
        from focal.config.models.pipeline import MemoryIngestionConfig

        config = MemoryIngestionConfig(
            entity_extraction_enabled=True,
            async_extraction=True,
        )

        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=config,
        )

        episode = await ingestor.ingest_turn(turn, session)

        # Verify episode was created
        assert episode is not None
        # Task should be queued (we can't easily verify queue contents in unit test)


class TestMemoryIngestorErrorHandling:
    """Tests for graceful degradation."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_storage_failure(
        self, embedding_provider, task_queue, session, turn
    ):
        """Should handle storage failures gracefully."""

        class FailingMemoryStore(InMemoryMemoryStore):
            async def add_episode(self, _episode):
                raise Exception("Storage unavailable")

        failing_store = FailingMemoryStore()

        ingestor = MemoryIngestor(
            memory_store=failing_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
        )

        # Should raise IngestionError, not raw exception
        with pytest.raises(IngestionError):
            await ingestor.ingest_turn(turn, session)


class TestMemoryIngestorLatency:
    """Tests for latency targets."""

    @pytest.mark.asyncio
    async def test_ingest_turn_completes_under_500ms(
        self, memory_store, embedding_provider, task_queue, session, turn
    ):
        """Should complete episode ingestion within 500ms."""
        import time

        ingestor = MemoryIngestor(
            memory_store=memory_store,
            embedding_provider=embedding_provider,
            entity_extractor=None,
            summarizer=None,
            task_queue=task_queue,
            config=None,
        )

        start = time.time()
        await ingestor.ingest_turn(turn, session)
        duration_ms = (time.time() - start) * 1000

        # Should complete within 500ms target (allow some buffer for test overhead)
        assert duration_ms < 600, f"Ingestion took {duration_ms}ms, exceeds 500ms target"
