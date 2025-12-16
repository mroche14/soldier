"""Template domain models (stub).

Will contain Template models for response generation.
Currently a placeholder - main implementation is in ruche.brains.focal.models.template
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from jinja2 import Environment, TemplateSyntaxError, UndefinedError, meta
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Scope(str, Enum):
    """Template scoping levels."""

    GLOBAL = "GLOBAL"
    TENANT = "TENANT"
    AGENT = "AGENT"
    SCENARIO = "SCENARIO"


class TemplateResponseMode(str, Enum):
    """How templates are used in response generation.

    - SUGGEST: LLM can adapt the text as a suggestion
    - EXCLUSIVE: Use exactly, bypass LLM entirely
    - FALLBACK: Use if LLM fails or violates rules
    """

    SUGGEST = "SUGGEST"
    EXCLUSIVE = "EXCLUSIVE"
    FALLBACK = "FALLBACK"


class Template(BaseModel):
    """Response template (stub).

    Will define canned responses or response frameworks
    that can be used in generation.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")
    name: str = Field(..., description="Template name")
    content: str = Field(..., description="Template content")
    response_mode: TemplateResponseMode = Field(
        default=TemplateResponseMode.SUGGEST,
        description="How to use this template"
    )
    scope: Scope = Field(
        default=Scope.AGENT,
        description="Visibility scope of the template",
    )
    scope_id: UUID | None = Field(
        default=None,
        description="ID of the scoping entity (tenant_id, agent_id, or scenario_id)",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions under which this template applies",
    )
    enabled: bool = Field(default=True, description="Is active")
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")

    def render(self, variables: dict) -> str:
        """Render the template content with provided variables.

        Args:
            variables: Dictionary of variable names to values

        Returns:
            Rendered template string

        Raises:
            TemplateSyntaxError: If template content has invalid Jinja2 syntax
            UndefinedError: If required variables are missing
        """
        env = Environment(
            trim_blocks=True,
            lstrip_blocks=True,
        )
        try:
            template = env.from_string(self.content)
            return template.render(**variables)
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"Invalid template syntax in template '{self.name}': {e.message}",
                e.lineno,
            ) from e
        except UndefinedError as e:
            raise UndefinedError(
                f"Missing variable in template '{self.name}': {str(e)}"
            ) from e

    @property
    def variables_used(self) -> list[str]:
        """Extract and return list of variable names used in the template.

        Returns:
            List of variable names referenced in the template content

        Raises:
            TemplateSyntaxError: If template content has invalid Jinja2 syntax
        """
        env = Environment()
        try:
            ast = env.parse(self.content)
            return sorted(meta.find_undeclared_variables(ast))
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"Invalid template syntax in template '{self.name}': {e.message}",
                e.lineno,
            ) from e
