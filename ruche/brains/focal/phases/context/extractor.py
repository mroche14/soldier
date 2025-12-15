"""Context extraction for alignment pipeline.

Extracts structured context from user messages including intent,
entities, sentiment, and scenario navigation signals.
"""

import json
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID

from ruche.brains.focal.phases.context.models import (
    Context,
    ExtractedEntity,
    ScenarioSignal,
    Sentiment,
    Turn,
    Urgency,
)
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.embedding import EmbeddingProvider
from ruche.infrastructure.providers.llm import LLMExecutor, LLMMessage

logger = get_logger(__name__)

# Load prompt template
_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "extract_intent.txt"


class ContextExtractor:
    """Extract structured context from user messages.

    Supports three extraction modes:
    - llm: Full LLM-based extraction (highest quality, slowest)
    - embedding_only: Vector embedding only (fast, no semantic analysis)
    - disabled: Pass-through (fastest, message only)
    """

    def __init__(
        self,
        llm_executor: LLMExecutor,
        embedding_provider: EmbeddingProvider,
        prompt_template: str | None = None,
    ) -> None:
        """Initialize the context extractor.

        Args:
            llm_executor: Executor for LLM-based extraction
            embedding_provider: Provider for generating embeddings
            prompt_template: Optional custom prompt template
        """
        self._llm_executor = llm_executor
        self._embedding_provider = embedding_provider

        if prompt_template:
            self._prompt_template = prompt_template
        elif _PROMPT_TEMPLATE_PATH.exists():
            self._prompt_template = _PROMPT_TEMPLATE_PATH.read_text()
        else:
            # Fallback minimal template
            self._prompt_template = self._default_prompt_template()

    def _default_prompt_template(self) -> str:
        """Return a minimal default prompt template."""
        return """Extract the user's intent, entities, sentiment, and topic from this message.

Message: {message}
History: {history}

Respond with JSON: {"intent": "...", "entities": [], "sentiment": "neutral", "topic": "...", "urgency": "normal", "scenario_signal": "continue"}"""

    async def extract(
        self,
        message: str,
        history: list[Turn],
        mode: Literal["llm", "embedding_only", "disabled"] = "llm",
        session_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> Context:
        """Extract structured context from a user message.

        Args:
            message: The user's message to analyze
            history: Previous conversation turns for context
            mode: Extraction mode determining analysis depth
            session_id: Optional session ID for logging/tracing
            tenant_id: Optional tenant ID for logging/tracing

        Returns:
            Context object with extracted information

        Raises:
            ValueError: If message is empty or whitespace-only
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty or whitespace-only")

        logger.debug(
            "extracting_context",
            mode=mode,
            message_length=len(message),
            history_length=len(history),
            session_id=str(session_id) if session_id else None,
            tenant_id=str(tenant_id) if tenant_id else None,
        )

        if mode == "disabled":
            return Context(message=message, turn_count=len(history))

        # Get embedding for all modes except disabled
        embedding = await self._get_embedding(message)

        if mode == "embedding_only":
            return Context(
                message=message,
                embedding=embedding,
                turn_count=len(history),
            )

        # LLM mode - full extraction
        extracted = await self._extract_with_llm(message, history)

        return Context(
            message=message,
            embedding=embedding,
            intent=extracted.get("intent"),
            entities=self._parse_entities(extracted.get("entities", [])),
            sentiment=self._parse_sentiment(extracted.get("sentiment")),
            topic=extracted.get("topic"),
            urgency=self._parse_urgency(extracted.get("urgency")),
            scenario_signal=self._parse_scenario_signal(extracted.get("scenario_signal")),
            turn_count=len(history),
            recent_topics=self._extract_recent_topics(history),
        )

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text."""
        return await self._embedding_provider.embed_single(text)

    async def _extract_with_llm(
        self,
        message: str,
        history: list[Turn],
    ) -> dict[str, Any]:
        """Use LLM to extract structured information."""
        history_text = self._format_history(history)

        prompt = self._prompt_template.format(
            message=message,
            history=history_text,
        )

        response = await self._llm_executor.generate(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,  # Deterministic for extraction
            max_tokens=500,
        )

        return self._parse_llm_response(response.content)

    def _format_history(self, history: list[Turn]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "(No prior conversation)"

        lines = []
        for turn in history[-5:]:  # Last 5 turns
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.content}")

        return "\n".join(lines)

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response JSON."""
        # Try to extract JSON from the response
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        try:
            return cast(dict[str, Any], json.loads(content))
        except json.JSONDecodeError:
            logger.warning("failed_to_parse_llm_response", content_preview=content[:100])
            return {}

    def _parse_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> list[ExtractedEntity]:
        """Parse entity list from LLM output."""
        result = []
        for entity in entities:
            if isinstance(entity, dict) and "type" in entity and "value" in entity:
                try:
                    result.append(
                        ExtractedEntity(
                            type=str(entity["type"]),
                            value=str(entity["value"]),
                            confidence=float(entity.get("confidence", 1.0)),
                        )
                    )
                except (ValueError, TypeError):
                    continue
        return result

    def _parse_sentiment(self, sentiment: str | None) -> Sentiment | None:
        """Parse sentiment string to enum."""
        if not sentiment:
            return None
        try:
            return Sentiment(sentiment.lower())
        except ValueError:
            return None

    def _parse_urgency(self, urgency: str | None) -> Urgency:
        """Parse urgency string to enum."""
        if not urgency:
            return Urgency.NORMAL
        try:
            return Urgency(urgency.lower())
        except ValueError:
            return Urgency.NORMAL

    def _parse_scenario_signal(
        self,
        signal: str | None,
    ) -> ScenarioSignal | None:
        """Parse scenario signal string to enum."""
        if not signal:
            return None
        try:
            return ScenarioSignal(signal.lower())
        except ValueError:
            return ScenarioSignal.UNKNOWN

    def _extract_recent_topics(self, history: list[Turn]) -> list[str]:
        """Extract topics from recent history (simplified heuristic)."""
        # This is a placeholder - in production, could use NLP or another LLM call
        topics = []
        keywords = ["order", "return", "refund", "shipping", "payment", "account"]

        for turn in history[-5:]:
            content_lower = turn.content.lower()
            for keyword in keywords:
                if keyword in content_lower and keyword not in topics:
                    topics.append(keyword)

        return topics[:3]  # Return max 3 recent topics
