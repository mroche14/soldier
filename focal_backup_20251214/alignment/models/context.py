"""Context models for alignment domain."""

from pydantic import BaseModel, ConfigDict, Field


class UserIntent(BaseModel):
    """Classified user intent."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    primary: str = Field(..., description="Primary intent label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    secondary: list[str] = Field(default_factory=list, description="Secondary intents")


class ExtractedEntities(BaseModel):
    """Named entities from message."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    entities: dict[str, list[str]] = Field(
        default_factory=dict, description="Type -> values mapping"
    )


class Context(BaseModel):
    """Extracted understanding of user message.

    Contains the processed understanding of a user's message
    including intent, entities, and metadata.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    user_intent: UserIntent = Field(..., description="Classified intent")
    entities: ExtractedEntities = Field(..., description="Named entities")
    sentiment: str | None = Field(default=None, description="Detected sentiment")
    language: str | None = Field(default=None, description="Detected language")
    raw_message: str = Field(..., description="Original message")
