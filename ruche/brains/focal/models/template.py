"""Template models for alignment domain."""

import re
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, computed_field

from ruche.brains.focal.models.base import AgentScopedModel
from ruche.brains.focal.models.enums import Scope, TemplateResponseMode


class Template(AgentScopedModel):
    """Pre-written response text.

    Templates contain response text with optional {placeholders} that
    are filled at runtime with variable values.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    content: str = Field(..., min_length=1, description="Template with {{placeholders}}")
    mode: TemplateResponseMode = Field(default=TemplateResponseMode.SUGGEST, description="Usage mode")
    scope: Scope = Field(default=Scope.AGENT, description="Scoping level")
    scope_id: UUID | None = Field(default=None, description="scenario_id or step_id")
    conditions: list[str] = Field(default_factory=list, description="Conditions under which this template applies")

    def render(self, variables: dict[str, Any]) -> str:
        """Render template with provided variables.

        Uses Jinja2-style {{ variable }} syntax.

        Args:
            variables: Dict of variable name to value

        Returns:
            Rendered template string
        """
        result = self.content
        for name, value in variables.items():
            result = result.replace(f"{{{{{name}}}}}", str(value))
        return result

    @computed_field
    @property
    def variables_used(self) -> list[str]:
        """Extract variable names used in template.

        Returns:
            List of variable names found in {{ }} placeholders
        """
        pattern = r'\{\{(\w+)\}\}'
        return list(set(re.findall(pattern, self.content)))
