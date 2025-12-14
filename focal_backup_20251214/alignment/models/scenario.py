"""Scenario models for alignment domain."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from focal.alignment.models.base import AgentScopedModel
from focal.alignment.models.tool_binding import ToolBinding


class StepTransition(BaseModel):
    """Possible transition between steps."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    to_step_id: UUID = Field(..., description="Target step")
    condition_text: str = Field(..., description="Natural language condition")
    condition_embedding: list[float] | None = Field(default=None, description="Vector for matching")
    priority: int = Field(default=0, description="Higher evaluated first")
    condition_fields: list[str] = Field(
        default_factory=list, description="Profile fields in condition"
    )


class ScenarioStep(BaseModel):
    """Single step within a Scenario."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    scenario_id: UUID = Field(..., description="Parent scenario")
    name: str = Field(..., description="Step name")
    description: str | None = Field(default=None, description="Human description")
    transitions: list[StepTransition] = Field(
        default_factory=list, description="Possible next steps"
    )
    template_ids: list[UUID] = Field(default_factory=list, description="Step-scoped templates")
    rule_ids: list[UUID] = Field(default_factory=list, description="Step-scoped rules")
    tool_ids: list[str] = Field(
        default_factory=list, description="DEPRECATED: Available tools (use tool_bindings)"
    )
    tool_bindings: list[ToolBinding] = Field(
        default_factory=list, description="Tool bindings with timing and dependencies"
    )
    is_entry: bool = Field(default=False, description="Is entry point")
    is_terminal: bool = Field(default=False, description="Is exit point")
    can_skip: bool = Field(default=False, description="Allow jumping past")
    reachable_from_anywhere: bool = Field(default=False, description="Recovery step")
    collects_profile_fields: list[str] = Field(default_factory=list, description="Fields collected")
    performs_action: bool = Field(default=False, description="Has side effects")
    is_required_action: bool = Field(default=False, description="Must execute")
    is_checkpoint: bool = Field(default=False, description="Irreversible action")
    checkpoint_description: str | None = Field(
        default=None, description="Description if checkpoint"
    )


class Scenario(AgentScopedModel):
    """Multi-step conversational flow."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Scenario name")
    description: str | None = Field(default=None, description="Human description")
    entry_step_id: UUID = Field(..., description="First step to enter")
    steps: list[ScenarioStep] = Field(default_factory=list, description="All steps in scenario")
    entry_condition_text: str | None = Field(
        default=None, description="Condition for auto-activation"
    )
    entry_condition_embedding: list[float] | None = Field(
        default=None, description="Vector for entry matching"
    )
    version: int = Field(default=1, description="Incremented on edit")
    content_hash: str | None = Field(default=None, description="SHA256 of serialized content")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    enabled: bool = Field(default=True, description="Is scenario active")
