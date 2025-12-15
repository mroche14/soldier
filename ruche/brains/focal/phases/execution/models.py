"""Execution models for alignment pipeline.

Contains models for tool execution results and variable resolution.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Outcome of executing a tool."""

    tool_name: str
    tool_id: UUID | None = None
    rule_id: UUID = Field(..., description="Rule that triggered this tool")

    # Execution details
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None

    # Status
    success: bool
    execution_time_ms: float = Field(ge=0)
    timeout: bool = False

    # Phase 7 enhancements
    when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] | None = Field(
        default=None, description="Timing phase when tool was executed"
    )
    variables_filled: dict[str, Any] = Field(
        default_factory=dict, description="Variables filled by this tool execution"
    )
    tool_binding: Any | None = Field(default=None, description="Reference to ToolBinding")


class VariableResolution(BaseModel):
    """Result of variable resolution."""

    resolved_variables: dict[str, str] = Field(default_factory=dict, description="name -> value")
    unresolved: list[str] = Field(
        default_factory=list, description="Variables that couldn't be resolved"
    )
    sources: dict[str, str] = Field(
        default_factory=dict, description="name -> source (session, profile, tool, etc.)"
    )


class ToolExecutionResult(BaseModel):
    """Result of tool execution phase."""

    engine_variables: dict[str, Any] = Field(
        default_factory=dict, description="Merged variables for response generation"
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list, description="Individual tool execution results"
    )
    missing_variables: set[str] = Field(
        default_factory=set, description="Variables still needed after tool execution"
    )
    queued_tools: list[Any] = Field(
        default_factory=list, description="AFTER_STEP tools queued for future execution"
    )
    phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] = Field(
        ..., description="Execution phase"
    )
