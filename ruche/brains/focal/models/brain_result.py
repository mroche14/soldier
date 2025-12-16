"""BrainResult model for Brain.think() return value.

This is the standardized result format that all Brain implementations
(FOCAL, LangGraph, Agno) must return.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HandoffRequest(BaseModel):
    """Request to transfer session to another agent."""

    target_agent_id: UUID
    context_summary: dict[str, Any]
    reason: str | None = None


class ResponseSegment(BaseModel):
    """A segment of the response with optional metadata.

    Responses may be broken into segments for streaming or
    to attach different metadata to parts of the response.
    """

    content: str
    segment_type: str = "text"  # text, code, image_url, etc.
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrainResult(BaseModel):
    """Result from Brain.think().

    This is the standardized output that all Brain implementations return.
    ACF consumes this to commit state and send responses.
    """

    # Response to send to user
    response_segments: list[ResponseSegment] = Field(default_factory=list)
    """Response segments to send to the user (streaming-friendly)."""

    # Convenience property for simple text response
    @property
    def response(self) -> str:
        """Combined text response from all segments."""
        return "".join(seg.content for seg in self.response_segments)

    # State mutations to commit atomically
    staged_mutations: dict[str, Any] = Field(default_factory=dict)
    """State changes to commit atomically (session updates, profile changes, etc.)."""

    # Artifacts for potential reuse
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    """Artifacts produced during processing (for debugging, reuse, etc.)."""

    # Signals
    expects_more_input: bool = False
    """True if Brain expects the user to provide more input (e.g., waiting for answer)."""

    # Handoff request (optional)
    handoff: HandoffRequest | None = None
    """Optional request to transfer session to another agent."""
