"""Context Extractor Contract - Interface specification for Phase 7."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    """Detected sentiment of the user message."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"


class Urgency(str, Enum):
    """Urgency level detected from the message."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioSignal(str, Enum):
    """Signal about scenario navigation intent."""

    START = "start"  # User wants to begin a process
    CONTINUE = "continue"  # Normal flow continuation
    EXIT = "exit"  # User wants to leave/cancel
    UNKNOWN = "unknown"  # Unclear intent


class ExtractedEntity(BaseModel):
    """An entity extracted from the message."""

    type: str = Field(..., description="Entity type (e.g., order_id, product_name)")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Context(BaseModel):
    """Extracted context from a user message.

    This is the enriched understanding of what the user said,
    including semantic analysis, entity extraction, and
    navigation hints.
    """

    # Core fields
    message: str = Field(..., description="Original user message")
    embedding: list[float] | None = Field(
        default=None, description="Vector representation"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extracted fields (from LLM extraction)
    intent: str | None = Field(
        default=None, description="Synthesized user intent"
    )
    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="Extracted entities"
    )
    sentiment: Sentiment | None = Field(
        default=None, description="Detected sentiment"
    )
    topic: str | None = Field(
        default=None, description="Topic classification"
    )
    urgency: Urgency = Field(
        default=Urgency.NORMAL, description="Urgency level"
    )

    # Scenario navigation hints
    scenario_signal: ScenarioSignal | None = Field(
        default=None, description="Signal about scenario intent"
    )

    # Conversation context
    turn_count: int = Field(
        default=0, ge=0, description="Number of turns in conversation"
    )
    recent_topics: list[str] = Field(
        default_factory=list, description="Recent conversation topics"
    )


class Turn(BaseModel):
    """A single turn in the conversation history."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime | None = None


class ContextExtractor(ABC):
    """Interface for extracting structured context from user messages.

    The context extractor analyzes user messages to produce a rich
    Context object that informs downstream pipeline steps (retrieval,
    filtering, generation).

    Supports three extraction modes:
        - llm: Full LLM-based extraction (highest quality, slowest)
        - embedding_only: Vector embedding only (fast, no semantic analysis)
        - disabled: Pass-through (fastest, message only)

    Example:
        ```python
        extractor = ContextExtractor(llm_provider, embedding_provider)
        context = await extractor.extract(
            message="I want to return my order #12345",
            history=[Turn(role="assistant", content="How can I help?")],
            mode="llm"
        )
        # context.intent = "return order"
        # context.entities = [ExtractedEntity(type="order_id", value="12345")]
        ```

    Contract guarantees:
        - Always returns a valid Context with message field set
        - In "llm" mode: intent, entities, sentiment populated if extractable
        - In "embedding_only" mode: embedding populated, others may be None
        - In "disabled" mode: only message field populated
        - Never raises on empty history
    """

    @abstractmethod
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
        pass
