"""Enforcement models for alignment pipeline.

Contains models for constraint validation and enforcement results.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ConstraintViolation(BaseModel):
    """A detected constraint violation."""

    rule_id: UUID
    rule_name: str
    violation_type: str = Field(..., description="e.g., contains_prohibited, missing_required")
    details: str
    severity: str = Field(default="hard", description="hard or soft")


class EnforcementResult(BaseModel):
    """Result of enforcement validation."""

    passed: bool
    violations: list[ConstraintViolation] = Field(default_factory=list)

    # Remediation
    regeneration_attempted: bool = False
    regeneration_succeeded: bool = False
    regeneration_attempts: int = Field(
        default=0,
        ge=0,
        description="Number of regeneration attempts made (0 if no regeneration)"
    )
    fallback_used: bool = False
    fallback_template_id: UUID | None = None

    # Final response (may differ from generation)
    final_response: str
    enforcement_time_ms: float = Field(default=0.0, ge=0)
