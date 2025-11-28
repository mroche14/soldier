"""Execution models for alignment pipeline.

Contains models for tool execution results and variable resolution.
"""

from typing import Any
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


class VariableResolution(BaseModel):
    """Result of variable resolution."""

    resolved_variables: dict[str, str] = Field(default_factory=dict, description="name -> value")
    unresolved: list[str] = Field(
        default_factory=list, description="Variables that couldn't be resolved"
    )
    sources: dict[str, str] = Field(
        default_factory=dict, description="name -> source (session, profile, tool, etc.)"
    )
