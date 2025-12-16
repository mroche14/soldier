"""Toolbox data models.

Defines tool-related models for the runtime layer.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SideEffectPolicy(str, Enum):
    """Classification of tool side effects.

    Determines supersede behavior and execution safety.
    """

    PURE = "pure"
    """Read-only. No external state modified. Safe to cancel/retry."""

    IDEMPOTENT = "idempotent"
    """Can be safely retried with same result."""

    COMPENSATABLE = "compensatable"
    """Modifies state but can be undone via compensation action."""

    IRREVERSIBLE = "irreversible"
    """Point of no return. Cannot be undone."""


class ToolDefinition(BaseModel):
    """Tool definition stored in ConfigStore.

    Tenant-wide definition of a tool's capabilities and semantics.
    """

    id: UUID
    tenant_id: UUID
    name: str
    description: str

    # Execution configuration
    gateway: str = Field(..., description="Provider type: composio, http, internal")
    gateway_config: dict[str, Any] = Field(default_factory=dict)

    # Side effect classification (Toolbox uses this for supersede decisions)
    side_effect_policy: SideEffectPolicy = Field(default=SideEffectPolicy.PURE)

    # For COMPENSATABLE tools
    compensation_tool_id: UUID | None = None

    # User confirmation
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None

    # Parameter schema (JSON Schema)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    categories: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolActivation(BaseModel):
    """Per-agent tool activation.

    Controls which tools an agent can use and any policy overrides.
    """

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    tool_id: UUID

    # Enablement
    enabled: bool = True

    # Policy overrides (agent-specific)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"requires_confirmation": True} even if tool definition says False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlannedToolExecution(BaseModel):
    """Brain's proposal to execute a tool.

    Created by Brain during planning, executed by Toolbox.
    """

    tool_name: str
    args: dict[str, Any]
    idempotency_key: str | None = None  # Optional override
    when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] = "DURING_STEP"
    bound_rule_id: UUID | None = None
    bound_step_id: str | None = None
    critical: bool = True  # Stop batch on failure?


class ToolResult(BaseModel):
    """Result of tool execution."""

    status: str = Field(..., description="success, error, skipped, cached")
    data: dict[str, Any] | None = None
    error: str | None = None
    cached: bool = False
    execution_time_ms: int | None = None

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == "success"


class ToolMetadata(BaseModel):
    """Tool metadata for Brain decisions.

    Used by Brain to decide:
    - Should I check supersede before this tool?
    - Does this tool require user confirmation?
    """

    name: str
    side_effect_policy: SideEffectPolicy
    requires_confirmation: bool = False
    compensation_tool: UUID | None = None
    categories: list[str] = Field(default_factory=list)

    @property
    def is_irreversible(self) -> bool:
        """Check if tool has irreversible side effects."""
        return self.side_effect_policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def is_safe_to_retry(self) -> bool:
        """Check if tool can be safely retried."""
        return self.side_effect_policy in [
            SideEffectPolicy.PURE,
            SideEffectPolicy.IDEMPOTENT,
        ]


class SideEffectRecord(BaseModel):
    """Record of an executed side effect.

    Emitted via ACFEvent; ACF stores in LogicalTurn.side_effects.
    """

    id: UUID = Field(default_factory=uuid4)
    tool_name: str
    policy: SideEffectPolicy
    executed_at: datetime
    args: dict[str, Any]
    result: dict[str, Any] | None = None
    status: str = Field(..., description="executed, failed, compensated")
    idempotency_key: str | None = None

    # For compensation tracking
    compensation_id: UUID | None = None
    compensation_executed: bool = False
    compensation_result: dict[str, Any] | None = None

    @property
    def irreversible(self) -> bool:
        """Check if this is an irreversible side effect."""
        return self.policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def needs_compensation(self) -> bool:
        """Check if compensation is needed and not yet executed."""
        return (
            self.policy == SideEffectPolicy.COMPENSATABLE
            and not self.compensation_executed
        )


@dataclass
class ResolvedTool:
    """Tool with resolved definition and activation."""

    definition: ToolDefinition
    activation: ToolActivation | None
