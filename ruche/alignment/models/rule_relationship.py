"""Rule relationship models for dependency and exclusion management."""

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from ruche.alignment.models.base import AgentScopedModel


class RuleRelationshipKind(str, Enum):
    """Types of rule-to-rule relationships."""

    DEPENDS_ON = "depends_on"
    IMPLIES = "implies"
    EXCLUDES = "excludes"
    SPECIALIZES = "specializes"
    RELATED = "related"


class RuleRelationship(AgentScopedModel):
    """Relationship between two rules.

    Defines semantic dependencies and constraints between rules.
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    source_rule_id: UUID = Field(..., description="Source rule ID")
    target_rule_id: UUID = Field(..., description="Target rule ID")
    kind: RuleRelationshipKind = Field(..., description="Type of relationship")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Relationship strength")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional data")
