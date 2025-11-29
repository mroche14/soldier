"""Chat request and response models."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScenarioState(BaseModel):
    """Current scenario and step state."""

    id: str | None = None
    """Scenario ID if in a scenario."""

    step: str | None = None
    """Current step ID within the scenario."""


class ChatRequest(BaseModel):
    """Request body for POST /v1/chat and POST /v1/chat/stream.

    Contains all information needed to process a user message through
    the alignment engine.
    """

    tenant_id: UUID
    """Tenant identifier (resolved upstream by gateway)."""

    agent_id: UUID
    """Agent to process the message."""

    channel: str = Field(min_length=1)
    """Channel source: whatsapp, slack, webchat, etc."""

    user_channel_id: str = Field(min_length=1)
    """User identifier on the channel (e.g., phone number, Slack user ID)."""

    message: str = Field(min_length=1, max_length=10000)
    """The user's message text."""

    session_id: str | None = None
    """Optional existing session ID. Auto-created if omitted."""

    metadata: dict[str, Any] | None = None
    """Optional additional context (locale, device info, etc.)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "channel": "whatsapp",
                "user_channel_id": "+1234567890",
                "message": "I want to return my order",
                "session_id": "sess_abc123",
                "metadata": {"locale": "en-US"},
            }
        }
    )


class ChatResponse(BaseModel):
    """Response body for POST /v1/chat.

    Contains the agent's response along with metadata about the turn.
    """

    response: str
    """The agent's response text."""

    session_id: str
    """Session identifier (existing or newly created)."""

    turn_id: str
    """Unique identifier for this turn."""

    scenario: ScenarioState | None = None
    """Current scenario state if in a scenario."""

    matched_rules: list[str] = Field(default_factory=list)
    """IDs of rules that matched this turn."""

    tools_called: list[str] = Field(default_factory=list)
    """IDs of tools that were executed."""

    tokens_used: int = 0
    """Total tokens consumed (prompt + completion)."""

    latency_ms: int = 0
    """Total processing time in milliseconds."""


class TokenEvent(BaseModel):
    """Incremental token during streaming."""

    type: Literal["token"] = "token"
    content: str


class DoneEvent(BaseModel):
    """Final event when streaming completes."""

    type: Literal["done"] = "done"
    turn_id: str
    session_id: str
    matched_rules: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    latency_ms: int = 0


class ErrorEvent(BaseModel):
    """Error event during streaming."""

    type: Literal["error"] = "error"
    code: str
    message: str


# Union type for stream events
StreamEvent = TokenEvent | DoneEvent | ErrorEvent
