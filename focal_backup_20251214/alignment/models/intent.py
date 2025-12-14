"""Intent models for intent catalog and retrieval."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Intent(BaseModel):
    """Canonical intent definition in the intent catalog.

    Intents represent distinct user goals that can be matched through
    hybrid retrieval (embeddings + lexical). They enable intent-based
    routing and analytics.
    """

    id: UUID
    tenant_id: UUID
    agent_id: UUID

    # Intent identification
    name: str = Field(description="Intent identifier (e.g., 'refund_request')")
    description: str | None = Field(
        default=None,
        description="Human-readable description of the intent",
    )

    # Retrieval - semantic matching
    example_phrases: list[str] = Field(
        default_factory=list,
        description="Example phrases that represent this intent",
    )
    embedding: list[float] | None = Field(
        default=None,
        description="Precomputed embedding from example phrases",
    )
    embedding_model: str | None = Field(
        default=None,
        description="Model used to generate the embedding",
    )

    # Metadata
    created_at: datetime
    updated_at: datetime
    enabled: bool = Field(
        default=True,
        description="Whether this intent is active",
    )


class IntentCandidate(BaseModel):
    """Scored intent candidate from retrieval.

    Represents a potential intent match with a confidence score
    and source information.
    """

    intent_id: UUID
    intent_name: str
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Relevance score (0-1)",
    )
    source: Literal["hybrid", "llm_sensor"] = Field(
        description="How this intent was identified",
    )


class ScoredIntent(BaseModel):
    """Intent with similarity score from retrieval.

    Used during the retrieval process before selection.
    """

    intent_id: UUID
    intent_name: str
    score: float
