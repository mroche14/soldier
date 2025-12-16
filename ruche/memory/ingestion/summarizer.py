"""Conversation summarization for long conversations."""

from typing import Any

from ruche.config.models.pipeline import SummarizationConfig
from ruche.memory.ingestion.errors import SummarizationError
from ruche.memory.models.episode import Episode
from ruche.infrastructure.stores.memory.interface import MemoryStore
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.llm import LLMMessage

logger = get_logger(__name__)


class ConversationSummarizer:
    """Generate hierarchical conversation summaries."""

    def __init__(
        self,
        llm_executor: Any,
        memory_store: MemoryStore,
        config: SummarizationConfig,
    ):
        """Initialize conversation summarizer.

        Args:
            llm_executor: LLM executor (or any object with compatible generate method)
            memory_store: Memory store
            config: Summarization configuration
        """
        self._llm_executor = llm_executor
        self._memory_store = memory_store
        self._config = config

    async def summarize_window(
        self,
        episodes: list[Episode],
        group_id: str,
    ) -> Episode:
        """Create summary of conversation window.

        Uses LLM to generate concise summary of N turns.
        Summary is returned as Episode with content_type="summary".

        Args:
            episodes: Window of episodes to summarize (typically 10-50)
            group_id: Tenant:session for the summary

        Returns:
            Episode: Summary episode (NOT persisted, caller stores it)

        Raises:
            SummarizationError: If LLM call fails
        """
        try:
            # Format episodes for summarization
            context = self._format_episodes_for_summary(episodes)

            # Generate summary using LLM
            messages = [
                LLMMessage(
                    role="system",
                    content="""You are a concise summarizer of customer conversations.
Extract the key information: what the customer wanted, what happened,
and what was resolved. Be brief (1-2 paragraphs max).""",
                ),
                LLMMessage(
                    role="user",
                    content=f"Summarize this conversation:\n\n{context}",
                ),
            ]

            response = await self._llm_executor.generate(
                messages,
                max_tokens=self._config.window.max_tokens,
                temperature=self._config.window.temperature,
            )

            # Create summary episode
            summary_episode = Episode(
                group_id=group_id,
                content=response.content,
                source="system",
                content_type="summary",
                occurred_at=episodes[-1].occurred_at,  # Use last turn time
                source_metadata={
                    "summary_type": "window",
                    "episodes_covered": len(episodes),
                    "episode_ids": [str(e.id) for e in episodes],
                },
            )

            logger.info(
                "window_summary_created",
                group_id=group_id,
                episodes_covered=len(episodes),
            )

            return summary_episode

        except Exception as e:
            logger.error(
                "window_summarization_failed",
                group_id=group_id,
                error=str(e),
            )
            raise SummarizationError(
                message=f"Window summarization failed: {str(e)}",
                group_id=group_id,
                summary_type="window",
                cause=e,
            ) from e

    async def create_meta_summary(
        self,
        summaries: list[Episode],
        group_id: str,
    ) -> Episode:
        """Create meta-summary (summary of summaries).

        For very long conversations, combines multiple window
        summaries into higher-level overview.

        Args:
            summaries: Window summaries to combine (typically 5-10)
            group_id: Tenant:session for the meta-summary

        Returns:
            Episode: Meta-summary episode (NOT persisted)

        Raises:
            SummarizationError: If LLM call fails
        """
        try:
            # Format summaries for meta-summarization
            context = self._format_episodes_for_summary(summaries)

            # Generate meta-summary
            messages = [
                LLMMessage(
                    role="system",
                    content="""You are summarizing previously generated conversation
summaries into a high-level overview. Focus on major themes and outcomes.""",
                ),
                LLMMessage(
                    role="user",
                    content=f"Create a meta-summary from these summaries:\n\n{context}",
                ),
            ]

            response = await self._llm_executor.generate(
                messages,
                max_tokens=self._config.meta.max_tokens,
                temperature=self._config.meta.temperature,
            )

            # Create meta-summary episode
            meta_episode = Episode(
                group_id=group_id,
                content=response.content,
                source="system",
                content_type="meta_summary",
                occurred_at=summaries[-1].occurred_at,
                source_metadata={
                    "summary_type": "meta",
                    "summaries_covered": len(summaries),
                    "summary_ids": [str(s.id) for s in summaries],
                },
            )

            logger.info(
                "meta_summary_created",
                group_id=group_id,
                summaries_covered=len(summaries),
            )

            return meta_episode

        except Exception as e:
            logger.error(
                "meta_summarization_failed",
                group_id=group_id,
                error=str(e),
            )
            raise SummarizationError(
                message=f"Meta-summarization failed: {str(e)}",
                group_id=group_id,
                summary_type="meta",
                cause=e,
            ) from e

    async def check_and_summarize_if_needed(
        self,
        group_id: str,
    ) -> Episode | None:
        """Check if summarization threshold reached and summarize if needed.

        Queries MemoryStore to count episodes, compares against thresholds,
        and triggers window or meta-summary generation.

        Args:
            group_id: Tenant:session to check

        Returns:
            Episode: Created summary if threshold was reached, None otherwise
            (Summary is automatically persisted by this method)

        Raises:
            SummarizationError: If summary generation or storage fails
        """
        try:
            # Get all episodes
            all_episodes = await self._memory_store.get_episodes(group_id)

            # Count message episodes (exclude summaries)
            message_episodes = [
                e for e in all_episodes if e.content_type in ("message", "event")
            ]
            turn_count = len(message_episodes)

            # Check window summarization threshold
            window_threshold = self._config.window.turns_per_summary

            if turn_count % window_threshold != 0 or turn_count == 0:
                return None

            # Get unsummarized episodes for this window
            start_idx = max(0, turn_count - window_threshold)
            window_episodes = message_episodes[start_idx:turn_count]

            if len(window_episodes) < window_threshold:
                return None

            # Generate window summary
            summary = await self.summarize_window(window_episodes, group_id)

            # Store summary
            await self._memory_store.add_episode(summary)

            # Check if meta-summarization needed
            if turn_count >= self._config.meta.enabled_at_turn_count:
                # Get all window summaries
                summaries = [
                    e for e in all_episodes if e.content_type == "summary"
                ]

                if len(summaries) % self._config.meta.summaries_per_meta == 0:
                    # Generate meta-summary
                    meta_summaries_start = max(
                        0, len(summaries) - self._config.meta.summaries_per_meta
                    )
                    meta_summaries = summaries[meta_summaries_start:]

                    if len(meta_summaries) >= self._config.meta.summaries_per_meta:
                        meta = await self.create_meta_summary(meta_summaries, group_id)
                        await self._memory_store.add_episode(meta)
                        return meta

            return summary

        except Exception as e:
            logger.error(
                "summarization_check_failed",
                group_id=group_id,
                error=str(e),
            )
            raise SummarizationError(
                message=f"Summarization check failed: {str(e)}",
                group_id=group_id,
                cause=e,
            ) from e

    def _format_episodes_for_summary(self, episodes: list[Episode]) -> str:
        """Format episodes for LLM consumption.

        Args:
            episodes: Episodes to format

        Returns:
            Formatted context string
        """
        lines = []
        for episode in episodes:
            if episode.source == "user":
                lines.append(f"Customer: {episode.content}")
            elif episode.source == "agent":
                lines.append(f"Agent: {episode.content}")
            elif episode.source == "system":
                lines.append(f"[System: {episode.content}]")
        return "\n".join(lines)
