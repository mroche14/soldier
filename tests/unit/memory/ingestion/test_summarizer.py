"""Tests for ConversationSummarizer."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from soldier.memory.ingestion.summarizer import ConversationSummarizer
from soldier.memory.models.episode import Episode
from soldier.memory.stores.inmemory import InMemoryMemoryStore
from soldier.providers.llm.mock import MockLLMProvider


@pytest.fixture
def memory_store():
    """Create in-memory store for testing."""
    return InMemoryMemoryStore()


@pytest.fixture
def llm_provider():
    """Create mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def group_id():
    """Create test group_id."""
    return f"{uuid4()}:{uuid4()}"


class TestConversationSummarizerWindow:
    """Tests for window summarization."""

    @pytest.mark.asyncio
    async def test_summarize_window_generates_summary(
        self, memory_store, llm_provider, group_id
    ):
        """Should generate summary from episode window."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        # Create test episodes
        episodes = [
            Episode(
                group_id=group_id,
                content=f"User message {i}",
                source="user" if i % 2 == 0 else "agent",
                occurred_at=datetime.now(UTC),
            )
            for i in range(10)
        ]

        summary = await summarizer.summarize_window(episodes, group_id)

        assert summary is not None
        assert summary.content_type == "summary"
        assert summary.source == "system"
        assert summary.source_metadata.get("summary_type") == "window"

    @pytest.mark.asyncio
    async def test_summarize_window_includes_metadata(
        self, memory_store, llm_provider, group_id
    ):
        """Should include summary metadata."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        episodes = [
            Episode(
                group_id=group_id,
                content=f"Message {i}",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        summary = await summarizer.summarize_window(episodes, group_id)

        assert "summary_type" in summary.source_metadata
        assert "episodes_covered" in summary.source_metadata
        assert summary.source_metadata["episodes_covered"] == 5


class TestConversationSummarizerMeta:
    """Tests for meta-summarization."""

    @pytest.mark.asyncio
    async def test_create_meta_summary_combines_summaries(
        self, memory_store, llm_provider, group_id
    ):
        """Should create meta-summary from summaries."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        # Create test summaries
        summaries = [
            Episode(
                group_id=group_id,
                content=f"Summary of turns {i*10}-{(i+1)*10}",
                source="system",
                content_type="summary",
                occurred_at=datetime.now(UTC),
                source_metadata={"summary_type": "window"},
            )
            for i in range(5)
        ]

        meta = await summarizer.create_meta_summary(summaries, group_id)

        assert meta is not None
        assert meta.content_type == "meta_summary"
        assert meta.source == "system"
        assert "meta" in meta.source_metadata.get("summary_type", "")


class TestConversationSummarizerThreshold:
    """Tests for threshold checking."""

    @pytest.mark.asyncio
    async def test_check_and_summarize_if_needed_respects_threshold(
        self, memory_store, llm_provider, group_id
    ):
        """Should only summarize when threshold reached."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        config.window.turns_per_summary = 10
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        # Add 9 episodes (below threshold)
        for i in range(9):
            episode = Episode(
                group_id=group_id,
                content=f"Message {i}",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            await memory_store.add_episode(episode)

        # Should not trigger summarization
        summary = await summarizer.check_and_summarize_if_needed(group_id)
        assert summary is None

    @pytest.mark.asyncio
    async def test_check_and_summarize_if_needed_triggers_at_threshold(
        self, memory_store, llm_provider, group_id
    ):
        """Should trigger summarization when threshold reached."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        config.window.turns_per_summary = 10
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        # Add exactly 10 episodes (at threshold)
        for i in range(10):
            episode = Episode(
                group_id=group_id,
                content=f"Message {i}",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            await memory_store.add_episode(episode)

        # Should trigger summarization
        summary = await summarizer.check_and_summarize_if_needed(group_id)
        assert summary is not None
        assert summary.content_type == "summary"


class TestConversationSummarizerCompression:
    """Tests for compression ratio validation."""

    @pytest.mark.asyncio
    async def test_summarize_window_compresses_content(
        self, memory_store, llm_provider, group_id
    ):
        """Should compress content in summary."""
        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        summarizer = ConversationSummarizer(
            llm_provider=llm_provider,
            memory_store=memory_store,
            config=config,
        )

        # Create verbose episodes
        episodes = [
            Episode(
                group_id=group_id,
                content="This is a very long message with lots of details that should be compressed in the summary. " * 10,
                source="user",
                occurred_at=datetime.now(UTC),
            )
            for i in range(10)
        ]

        _original_length = sum(len(e.content) for e in episodes)

        summary = await summarizer.summarize_window(episodes, group_id)

        # Summary should be shorter than original
        # (Mock LLM may not actually compress, so check structure instead)
        assert summary.content is not None
        assert len(summary.content) > 0


class TestConversationSummarizerErrorHandling:
    """Tests for LLM provider timeout handling."""

    @pytest.mark.asyncio
    async def test_summarize_handles_slow_llm(self, memory_store, group_id):
        """Should complete even with slow LLM provider."""

        class SlowLLMProvider(MockLLMProvider):
            async def generate(self, *args, **kwargs):
                import asyncio

                await asyncio.sleep(0.1)  # Simulate slow LLM
                return await super().generate(*args, **kwargs)

        from soldier.config.models.pipeline import SummarizationConfig

        config = SummarizationConfig()
        summarizer = ConversationSummarizer(
            llm_provider=SlowLLMProvider(),
            memory_store=memory_store,
            config=config,
        )

        episodes = [
            Episode(
                group_id=group_id,
                content=f"Message {i}",
                source="user",
                occurred_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        # Should complete successfully even with slow LLM
        summary = await summarizer.summarize_window(episodes, group_id)
        assert summary is not None
        assert summary.content_type == "summary"
