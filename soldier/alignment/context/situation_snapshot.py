"""Situational snapshot models.

Output of Phase 2 Situational Sensor.
The primary context object used throughout the pipeline.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from soldier.alignment.context.models import ScenarioSignal, Sentiment, Urgency


class CandidateVariableInfo(BaseModel):
    """Extracted variable candidate from user message.

    Represents a potential customer data field value extracted
    by the situation sensor with scoping metadata.
    """

    value: Any = Field(..., description="Extracted value")
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"] = Field(
        ..., description="Persistence scope"
    )
    is_update: bool = Field(
        default=False, description="True if updating existing value"
    )


class SituationSnapshot(BaseModel):
    """Complete situation understanding of a user message.

    This is the primary context object used throughout the pipeline.
    Created by SituationSensor, enriched during retrieval.
    """

    # Core message data
    message: str = Field(..., description="Original user message")
    embedding: list[float] | None = Field(default=None, description="Vector representation")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Language detection
    language: str = Field(default="en", description="ISO 639-1 code (e.g., 'en', 'es')")

    # Intent evolution
    previous_intent_label: str | None = Field(
        default=None, description="Previous canonical intent"
    )
    intent_changed: bool = Field(..., description="Has intent changed this turn")
    new_intent_label: str | None = Field(
        default=None, description="New intent label if changed"
    )
    new_intent_text: str | None = Field(
        default=None, description="New intent text for retrieval"
    )

    # Conversation state
    topic: str | None = Field(default=None, description="Current topic classification")
    topic_changed: bool = Field(..., description="Has topic changed")
    tone: str = Field(..., description="neutral, frustrated, excited, etc.")
    sentiment: Sentiment = Field(default=Sentiment.NEUTRAL, description="Detected sentiment")
    frustration_level: Literal["low", "medium", "high"] | None = Field(
        default=None, description="Frustration level if detected"
    )
    urgency: Urgency = Field(default=Urgency.NORMAL, description="Urgency level")

    # Scenario navigation
    scenario_signal: ScenarioSignal = Field(
        default=ScenarioSignal.CONTINUE, description="Signal about scenario intent"
    )

    # Situational understanding
    situation_facts: list[str] = Field(
        default_factory=list, description="Mini rule-like statements"
    )

    # Customer data extraction (CRITICAL FOR PHASE 3)
    candidate_variables: dict[str, CandidateVariableInfo] = Field(
        default_factory=dict,
        description="Field name -> extracted variable info",
    )

    # Canonical intent (set after retrieval phase)
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
