"""Context models for alignment pipeline.

Contains enriched context models for understanding user messages,
including intent, entities, sentiment, and scenario navigation hints.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

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
    PAUSE = "pause"  # User wants to temporarily pause
    CANCEL = "cancel"  # User wants to abort/cancel
    UNKNOWN = "unknown"  # Unclear intent


class ExtractedEntity(BaseModel):
    """An entity extracted from the message."""

    type: str = Field(..., description="Entity type (e.g., order_id, product_name)")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Turn(BaseModel):
    """A single turn in the conversation history."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime | None = None


class Context(BaseModel):
    """Extracted context from a user message.

    This is the enriched understanding of what the user said,
    including semantic analysis, entity extraction, and
    navigation hints.
    """

    # Core fields
    message: str = Field(..., description="Original user message")
    embedding: list[float] | None = Field(default=None, description="Vector representation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Extracted fields (from LLM extraction)
    intent: str | None = Field(default=None, description="Synthesized user intent")
    entities: list[ExtractedEntity] = Field(default_factory=list, description="Extracted entities")
    sentiment: Sentiment | None = Field(default=None, description="Detected sentiment")
    topic: str | None = Field(default=None, description="Topic classification")
    urgency: Urgency = Field(default=Urgency.NORMAL, description="Urgency level")

    # Scenario navigation hints
    scenario_signal: ScenarioSignal | None = Field(
        default=None, description="Signal about scenario intent"
    )

    # Conversation context
    turn_count: int = Field(default=0, ge=0, description="Number of turns in conversation")
    recent_topics: list[str] = Field(default_factory=list, description="Recent conversation topics")

    # Canonical intent (P4.3 - decided from hybrid retrieval + LLM sensor)
    canonical_intent_label: str | None = Field(
        default=None,
        description="Final canonical intent label after merging LLM sensor and hybrid retrieval",
    )
    canonical_intent_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for canonical intent",
    )
