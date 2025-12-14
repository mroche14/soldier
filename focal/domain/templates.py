"""Template domain models (stub).

Will contain Template models for response generation.
Currently a placeholder.
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


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
    enabled: bool = Field(default=True, description="Is active")
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")
