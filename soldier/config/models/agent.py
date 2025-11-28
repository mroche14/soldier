"""Agent-level configuration models."""

from typing import Any

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Per-agent configuration overrides.

    Agent configuration allows overriding default settings at the agent level.
    These settings take precedence over global configuration when processing
    requests for a specific agent.
    """

    name: str = Field(description="Agent display name")
    description: str | None = Field(default=None, description="Agent description")
    llm_provider: str | None = Field(
        default=None,
        description="Override default LLM provider",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Override generation temperature",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Override max tokens",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt for this agent",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent metadata",
    )
