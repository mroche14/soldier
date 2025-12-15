"""Template models for alignment domain."""

from uuid import UUID, uuid4

from pydantic import Field

from ruche.brains.focal.models.base import AgentScopedModel
from ruche.brains.focal.models.enums import Scope, TemplateResponseMode


class Template(AgentScopedModel):
    """Pre-written response text.

    Templates contain response text with optional {placeholders} that
    are filled at runtime with variable values.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    text: str = Field(..., min_length=1, description="Template with {placeholders}")
    mode: TemplateResponseMode = Field(default=TemplateResponseMode.SUGGEST, description="Usage mode")
    scope: Scope = Field(default=Scope.GLOBAL, description="Scoping level")
    scope_id: UUID | None = Field(default=None, description="scenario_id or step_id")
    conditions: str | None = Field(default=None, description="Expression for when to use")
