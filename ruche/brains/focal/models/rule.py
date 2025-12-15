"""Rule models for alignment domain."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, ValidationInfo, field_validator

from ruche.brains.focal.models.base import AgentScopedModel
from ruche.brains.focal.models.enums import Scope
from ruche.brains.focal.models.tool_binding import ToolBinding


class Rule(AgentScopedModel):
    """Behavioral policy: when X, then Y.

    Rules define agent behavior through natural language conditions
    and actions. They can be scoped to global, scenario, or step level.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    description: str | None = Field(default=None, description="Human description")
    condition_text: str = Field(
        ..., min_length=1, description="When this is true (natural language)"
    )
    action_text: str = Field(..., min_length=1, description="Do this action (natural language)")
    scope: Scope = Field(default=Scope.GLOBAL, description="Scoping level")
    scope_id: UUID | None = Field(default=None, description="scenario_id or step_id when scoped")
    priority: int = Field(
        default=0,
        ge=-100,
        le=100,
        description="Higher wins in conflicts (-100 to 100)",
    )
    enabled: bool = Field(default=True, description="Is rule active")
    max_fires_per_session: int = Field(default=0, ge=0, description="0 = unlimited")
    cooldown_turns: int = Field(default=0, ge=0, description="Min turns between re-fire")
    is_hard_constraint: bool = Field(default=False, description="Must be satisfied or fallback")
    enforcement_expression: str | None = Field(
        default=None,
        description="Formal expression for deterministic enforcement (e.g., 'amount <= 50')"
    )
    attached_tool_ids: list[str] = Field(
        default_factory=list, description="DEPRECATED: Tool IDs from ToolHub (use tool_bindings)"
    )
    tool_bindings: list[ToolBinding] = Field(
        default_factory=list, description="Tool bindings with timing and dependencies"
    )
    attached_template_ids: list[UUID] = Field(
        default_factory=list, description="Template references"
    )
    embedding: list[float] | None = Field(default=None, description="Precomputed vector")
    embedding_model: str | None = Field(default=None, description="Model that generated embedding")

    @field_validator("scope_id")
    @classmethod
    def validate_scope_id(cls, v: UUID | None, info: ValidationInfo) -> UUID | None:
        """Validate scope_id is set when scope requires it."""
        scope = info.data.get("scope")
        if scope in (Scope.SCENARIO, Scope.STEP) and v is None:
            raise ValueError(f"scope_id is required when scope is {scope}")
        return v


class MatchedRule(AgentScopedModel):
    """Rule that matched with scoring details."""

    rule: Rule = Field(..., description="The matched rule")
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Vector similarity")
    bm25_score: float = Field(default=0.0, ge=0.0, description="Keyword match score")
    final_score: float = Field(default=0.0, ge=0.0, description="Combined weighted score")
    newly_fired: bool = Field(..., description="First time this session")
    tools_to_execute: list[str] = Field(default_factory=list, description="Resolved tool IDs")
    # Note: Using Any for templates to avoid circular import issues
    # In practice, this would be list[Template] after model_rebuild()
    templates_to_consider: list[Any] = Field(default_factory=list, description="Resolved templates")
