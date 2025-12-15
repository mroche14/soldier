"""Variable models for alignment domain."""

from uuid import UUID, uuid4

from pydantic import Field

from ruche.brains.focal.models.base import AgentScopedModel
from ruche.brains.focal.models.enums import VariableUpdatePolicy


class Variable(AgentScopedModel):
    """Dynamic context value resolved at runtime.

    Variables are resolved by calling tools and can be cached
    based on the update policy.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(
        ...,
        max_length=50,
        pattern=r"^[a-z_][a-z0-9_]*$",
        description="Variable name (lowercase with underscores)",
    )
    description: str | None = Field(default=None, description="Human description")
    resolver_tool_id: str = Field(..., description="Tool that computes value")
    update_policy: VariableUpdatePolicy = Field(
        default=VariableUpdatePolicy.ON_DEMAND, description="Refresh policy"
    )
    cache_ttl_seconds: int = Field(default=0, ge=0, description="0 = no cache")
