"""Request and response models for CRUD operations."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from soldier.alignment.models import AgentSettings, Scope, TemplateResponseMode, VariableUpdatePolicy


# Agent models
class AgentCreate(BaseModel):
    """Request model for creating an agent."""

    name: str = Field(..., min_length=1, max_length=100, description="Agent display name")
    description: str | None = Field(default=None, description="Human-readable description")
    settings: AgentSettings | None = Field(default=None, description="LLM configuration")


class AgentUpdate(BaseModel):
    """Request model for updating an agent."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)
    enabled: bool | None = Field(default=None)
    settings: AgentSettings | None = Field(default=None)


class AgentStats(BaseModel):
    """Agent usage statistics."""

    total_sessions: int = 0
    total_turns: int = 0
    avg_turns_per_session: float = 0.0


class AgentResponse(BaseModel):
    """Response model for agent operations."""

    id: UUID
    name: str
    description: str | None
    enabled: bool
    current_version: int
    settings: AgentSettings
    stats: AgentStats | None = None
    created_at: datetime
    updated_at: datetime


# Rule models
class RuleCreate(BaseModel):
    """Request model for creating a rule."""

    name: str = Field(..., min_length=1, max_length=100)
    condition_text: str = Field(..., min_length=1)
    action_text: str = Field(..., min_length=1)
    scope: Scope = Field(default=Scope.GLOBAL)
    scope_id: UUID | None = Field(default=None)
    priority: int = Field(default=0, ge=-100, le=100)
    enabled: bool = Field(default=True)
    max_fires_per_session: int = Field(default=0, ge=0)
    cooldown_turns: int = Field(default=0, ge=0)
    is_hard_constraint: bool = Field(default=False)
    attached_tool_ids: list[str] = Field(default_factory=list)
    attached_template_ids: list[UUID] = Field(default_factory=list)


class RuleUpdate(BaseModel):
    """Request model for updating a rule."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    condition_text: str | None = Field(default=None, min_length=1)
    action_text: str | None = Field(default=None, min_length=1)
    scope: Scope | None = Field(default=None)
    scope_id: UUID | None = Field(default=None)
    priority: int | None = Field(default=None, ge=-100, le=100)
    enabled: bool | None = Field(default=None)
    max_fires_per_session: int | None = Field(default=None, ge=0)
    cooldown_turns: int | None = Field(default=None, ge=0)
    is_hard_constraint: bool | None = Field(default=None)
    attached_tool_ids: list[str] | None = Field(default=None)
    attached_template_ids: list[UUID] | None = Field(default=None)


class RuleResponse(BaseModel):
    """Response model for rule operations."""

    id: UUID
    name: str
    condition_text: str
    action_text: str
    scope: Scope
    scope_id: UUID | None
    priority: int
    enabled: bool
    max_fires_per_session: int
    cooldown_turns: int
    is_hard_constraint: bool
    attached_tool_ids: list[str]
    attached_template_ids: list[UUID]
    has_embedding: bool
    created_at: datetime
    updated_at: datetime

    @property
    def condition(self) -> str:
        """Alias for condition_text."""
        return self.condition_text

    @property
    def action(self) -> str:
        """Alias for action_text."""
        return self.action_text


# Scenario models
class StepTransitionCreate(BaseModel):
    """Request model for step transition."""

    condition: str = Field(..., description="Transition condition")
    to_step_id: UUID = Field(..., description="Target step ID")


class StepCreate(BaseModel):
    """Request model for creating a scenario step."""

    id: UUID | None = Field(default=None, description="Optional step ID, auto-generated if not provided")
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None)
    is_terminal: bool = Field(default=False)
    transitions: list[StepTransitionCreate] = Field(default_factory=list)


class StepUpdate(BaseModel):
    """Request model for updating a scenario step."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)
    is_terminal: bool | None = Field(default=None)
    transitions: list[StepTransitionCreate] | None = Field(default=None)


class ScenarioCreate(BaseModel):
    """Request model for creating a scenario."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None)
    entry_condition_text: str | None = Field(default=None)
    steps: list[StepCreate] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)


class ScenarioUpdate(BaseModel):
    """Request model for updating a scenario."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)
    entry_condition_text: str | None = Field(default=None)
    entry_step_id: UUID | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    enabled: bool | None = Field(default=None)


class StepTransitionResponse(BaseModel):
    """Response model for step transition."""

    condition: str
    to_step_id: UUID


class StepResponse(BaseModel):
    """Response model for scenario step."""

    id: UUID
    name: str
    description: str | None
    is_entry: bool
    is_terminal: bool
    transitions: list[StepTransitionResponse]


class ScenarioResponse(BaseModel):
    """Response model for scenario operations."""

    id: UUID
    name: str
    description: str | None
    entry_step_id: UUID | None
    steps: list[StepResponse]
    tags: list[str]
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime


# Template models
class TemplateCreate(BaseModel):
    """Request model for creating a template."""

    name: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1)
    mode: TemplateResponseMode = Field(default=TemplateResponseMode.SUGGEST)
    scope: Scope = Field(default=Scope.GLOBAL)
    scope_id: UUID | None = Field(default=None)
    conditions: str | None = Field(default=None)


class TemplateUpdate(BaseModel):
    """Request model for updating a template."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    text: str | None = Field(default=None, min_length=1)
    mode: TemplateResponseMode | None = Field(default=None)
    scope: Scope | None = Field(default=None)
    scope_id: UUID | None = Field(default=None)
    conditions: str | None = Field(default=None)


class TemplateResponse(BaseModel):
    """Response model for template operations."""

    id: UUID
    name: str
    text: str
    mode: TemplateResponseMode
    scope: Scope
    scope_id: UUID | None
    conditions: str | None
    variables_used: list[str]
    created_at: datetime
    updated_at: datetime


class TemplatePreviewRequest(BaseModel):
    """Request model for template preview."""

    variables: dict[str, str] = Field(..., description="Variable values for substitution")


class TemplatePreviewResponse(BaseModel):
    """Response model for template preview."""

    rendered: str = Field(..., description="Rendered template text")


# Variable models
class VariableCreate(BaseModel):
    """Request model for creating a variable."""

    name: str = Field(..., pattern=r"^[a-z_][a-z0-9_]*$", max_length=100)
    description: str | None = Field(default=None)
    resolver_tool_id: str | None = Field(default=None)
    update_policy: VariableUpdatePolicy = Field(default=VariableUpdatePolicy.ON_DEMAND)
    cache_ttl_seconds: int = Field(default=0, ge=0)


class VariableUpdate(BaseModel):
    """Request model for updating a variable."""

    description: str | None = Field(default=None)
    resolver_tool_id: str | None = Field(default=None)
    update_policy: VariableUpdatePolicy | None = Field(default=None)
    cache_ttl_seconds: int | None = Field(default=None, ge=0)


class VariableResponse(BaseModel):
    """Response model for variable operations."""

    id: UUID
    name: str
    description: str | None
    resolver_tool_id: str | None
    update_policy: VariableUpdatePolicy
    cache_ttl_seconds: int
    created_at: datetime
    updated_at: datetime


# Tool activation models
class ToolActivationCreate(BaseModel):
    """Request model for enabling a tool."""

    tool_id: str = Field(..., description="External tool identifier")
    policy_override: dict[str, Any] | None = Field(default=None)


class ToolActivationUpdate(BaseModel):
    """Request model for updating tool activation."""

    policy_override: dict[str, Any] | None = Field(default=None)


class ToolActivationResponse(BaseModel):
    """Response model for tool activation."""

    id: UUID
    tool_id: str
    status: Literal["enabled", "disabled"]
    policy_override: dict[str, Any] | None
    enabled_at: datetime | None
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


# Publish models
class PublishStatusResponse(BaseModel):
    """Response model for publish status."""

    current_version: int
    draft_version: int
    has_unpublished_changes: bool
    last_published_at: str | None
    last_published_by: str | None
    changes_since_publish: dict[str, int]


class PublishRequest(BaseModel):
    """Request model for initiating publish."""

    description: str | None = Field(default=None)


class PublishStageResponse(BaseModel):
    """Response model for publish stage."""

    name: str
    status: Literal["pending", "running", "completed", "failed"]
    duration_ms: int | None
    error: str | None


class PublishJobResponse(BaseModel):
    """Response model for publish job."""

    publish_id: UUID
    version: int
    status: Literal["pending", "running", "completed", "failed"]
    stages: list[PublishStageResponse]
    started_at: datetime
    completed_at: datetime | None


class RollbackRequest(BaseModel):
    """Request model for rollback."""

    target_version: int = Field(..., ge=1)
    reason: str | None = Field(default=None)
