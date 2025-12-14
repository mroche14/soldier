"""Generation models for alignment pipeline.

Contains models for response generation with template support.
"""

from uuid import UUID

from pydantic import BaseModel, Field

from ruche.alignment.models.enums import TemplateResponseMode
from ruche.alignment.models.outcome import OutcomeCategory


class GenerationResult(BaseModel):
    """Result of response generation."""

    response: str = Field(..., min_length=1)

    # Template info
    template_used: UUID | None = None
    template_mode: TemplateResponseMode | None = None

    # LLM details
    model: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    generation_time_ms: float = Field(default=0.0, ge=0)

    # Debug
    prompt_preview: str | None = Field(
        default=None, description="First N chars of prompt for debugging"
    )

    # Phase 9 additions
    llm_categories: list[OutcomeCategory] = Field(
        default_factory=list,
        description="Semantic categories output by LLM",
    )
    channel_formatted: bool = Field(
        default=False,
        description="Whether response was formatted for specific channel",
    )
    channel: str | None = Field(
        default=None,
        description="Target channel if formatted (whatsapp, email, etc.)",
    )
