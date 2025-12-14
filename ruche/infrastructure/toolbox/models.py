"""Toolbox data models.

Defines tools, activations, results, and policies for the agent toolbox.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SideEffectPolicy(str, Enum):
    """Policy for how to handle tool side effects."""

    NONE = "none"  # Pure function, no side effects
    IDEMPOTENT = "idempotent"  # Can be retried safely
    MUTATING = "mutating"  # Has side effects, requires confirmation


class ToolDefinition(BaseModel):
    """Definition of a tool available to agents.

    Tools are external capabilities the agent can invoke (HTTP APIs, Composio actions, etc).
    """

    id: str = Field(..., description="Unique tool identifier (e.g., 'github.create_issue')")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="What the tool does")

    # Provider routing
    provider: str = Field(..., description="Provider type (composio, http, internal)")
    provider_tool_id: str = Field(..., description="Tool ID in provider's namespace")

    # Schema
    input_schema: dict[str, Any] = Field(..., description="JSON schema for tool inputs")
    output_schema: dict[str, Any] | None = Field(None, description="Expected output schema")

    # Metadata
    side_effect_policy: SideEffectPolicy = Field(
        default=SideEffectPolicy.NONE,
        description="How to handle side effects",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether to ask user before executing",
    )
    timeout_seconds: int = Field(default=30, description="Execution timeout")

    # Configuration
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration",
    )


class ToolActivation(BaseModel):
    """Agent-specific tool activation.

    Links a tool to an agent with custom configuration.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Tenant owning this activation")
    agent_id: UUID = Field(..., description="Agent this activation applies to")
    tool_id: str = Field(..., description="Tool being activated")

    # Activation settings
    enabled: bool = Field(default=True, description="Whether tool is active")
    override_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific configuration overrides",
    )

    # Constraints
    max_calls_per_turn: int | None = Field(
        None,
        description="Max invocations per turn",
    )
    allowed_scenarios: list[UUID] | None = Field(
        None,
        description="Restrict to specific scenarios (None = all)",
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolResult(BaseModel):
    """Result of a tool execution."""

    tool_id: str = Field(..., description="Tool that was executed")
    success: bool = Field(..., description="Whether execution succeeded")

    # Output
    output: Any = Field(None, description="Tool output data")
    error: str | None = Field(None, description="Error message if failed")

    # Metadata
    execution_time_ms: int = Field(..., description="Execution duration in milliseconds")
    provider: str = Field(..., description="Provider that executed the tool")

    # Context
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional execution metadata",
    )


class ToolMetadata(BaseModel):
    """Metadata about a tool for display/selection."""

    id: str
    name: str
    description: str
    side_effect_policy: SideEffectPolicy
    requires_confirmation: bool

    # Categorization
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
