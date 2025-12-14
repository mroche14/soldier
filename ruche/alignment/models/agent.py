"""Agent model for conversational AI configuration."""

from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from ruche.alignment.models.base import TenantScopedModel


class AgentSettings(BaseModel):
    """Embedded settings for an agent's LLM configuration.

    Controls the LLM model and generation parameters for
    the agent's responses.
    """

    model: str | None = Field(
        default=None,
        description="Full model identifier (e.g., 'openrouter/anthropic/claude-3-5-sonnet-20241022')",
    )

    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Generation temperature"
    )

    max_tokens: int = Field(
        default=1024, ge=1, description="Maximum tokens in response"
    )


class Agent(TenantScopedModel):
    """Top-level container for conversational AI configuration.

    An agent represents a complete conversational AI configuration,
    including its rules, scenarios, templates, and variables.
    All other configuration entities are scoped to an agent.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique agent identifier")

    name: str = Field(
        ..., min_length=1, max_length=100, description="Agent display name"
    )

    description: str | None = Field(default=None, description="Human-readable description")

    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt for the agent's persona and base instructions. "
        "This is injected into the response generation prompt.",
    )

    enabled: bool = Field(default=True, description="Whether agent is active")

    current_version: int = Field(
        default=1, ge=1, description="Current published version number"
    )

    settings: AgentSettings = Field(
        default_factory=AgentSettings, description="LLM configuration settings"
    )

    @classmethod
    def create(
        cls,
        tenant_id: UUID,
        name: str,
        description: str | None = None,
        settings: AgentSettings | None = None,
    ) -> Self:
        """Create a new agent with defaults.

        Args:
            tenant_id: Owning tenant identifier
            name: Agent display name
            description: Optional description
            settings: Optional LLM settings

        Returns:
            New Agent instance
        """
        return cls(
            tenant_id=tenant_id,
            name=name,
            description=description,
            settings=settings or AgentSettings(),
        )
