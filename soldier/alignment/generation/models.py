"""Generation models for alignment pipeline.

Contains models for response generation with template support.
"""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateMode(str, Enum):
    """How a template should be used in generation."""

    EXCLUSIVE = "exclusive"  # Use exact template, skip LLM
    SUGGEST = "suggest"  # Include in prompt, LLM can adapt
    FALLBACK = "fallback"  # Use when enforcement fails


class GenerationResult(BaseModel):
    """Result of response generation."""

    response: str = Field(..., min_length=1)

    # Template info
    template_used: UUID | None = None
    template_mode: TemplateMode | None = None

    # LLM details
    model: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    generation_time_ms: float = Field(default=0.0, ge=0)

    # Debug
    prompt_preview: str | None = Field(
        default=None, description="First N chars of prompt for debugging"
    )
