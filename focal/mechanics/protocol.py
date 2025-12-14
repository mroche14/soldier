"""Cognitive Pipeline Protocol for Focal.

This module defines the abstract interface that all cognitive pipeline
implementations must adhere to. It represents the contract for processing
conversational turns from input to output.

The CognitivePipeline protocol defines a single method `process_turn` that
takes a user message and context, and returns a PipelineResult containing
the generated response and metadata about the processing.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, Field


class ResponseSegment(BaseModel):
    """A segment of the response with metadata.

    Responses can be composed of multiple segments, each with different
    characteristics (e.g., text vs tool output, different confidence levels).
    """

    content: str = Field(..., description="The text content of this segment")
    type: str = Field(default="text", description="Segment type: text, tool_output, etc")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0, description="Confidence score if available")
    metadata: dict = Field(default_factory=dict, description="Additional segment metadata")


class PipelineResult(BaseModel):
    """Result of processing a turn through the cognitive pipeline.

    This is the standardized output format that all pipeline implementations
    must return. It contains the response, metadata, and timing information.
    """

    # Identifiers
    turn_id: UUID = Field(..., description="Unique identifier for this turn")
    session_id: UUID = Field(..., description="Session this turn belongs to")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    agent_id: UUID = Field(..., description="Agent identifier")

    # Input
    user_message: str = Field(..., description="The original user message")

    # Output
    response: str = Field(..., description="The final response text to return to user")
    segments: list[ResponseSegment] = Field(
        default_factory=list, description="Response broken into segments with metadata"
    )

    # Metadata
    pipeline_name: str = Field(..., description="Name of the pipeline that processed this turn")
    total_time_ms: float = Field(ge=0, description="Total processing time in milliseconds")
    step_timings: dict[str, float] = Field(
        default_factory=dict, description="Timing for each pipeline step in milliseconds"
    )

    # Additional context
    metadata: dict = Field(default_factory=dict, description="Pipeline-specific metadata")

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)


@runtime_checkable
class CognitivePipeline(Protocol):
    """Abstract interface for cognitive pipelines.

    A cognitive pipeline processes conversational turns from user input
    to agent response. Different implementations (FOCAL, LangGraph, ReAct)
    provide different strategies for this transformation.

    All implementations must provide a `process_turn` method that accepts
    standardized inputs and returns a PipelineResult.
    """

    async def process_turn(
        self,
        message: str,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        channel: str | None = None,
        channel_user_id: str | None = None,
        metadata: dict | None = None,
    ) -> PipelineResult:
        """Process a single conversational turn.

        Args:
            message: The user's message text
            tenant_id: Unique identifier for the tenant
            agent_id: Unique identifier for the agent
            session_id: Unique identifier for the session
            channel: Optional channel identifier (e.g., "whatsapp", "web")
            channel_user_id: Optional channel-specific user identifier
            metadata: Optional additional context metadata

        Returns:
            PipelineResult containing the response and processing metadata

        Raises:
            PipelineError: If processing fails in a recoverable way
            ValidationError: If input validation fails
        """
        ...
