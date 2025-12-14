"""Core interlocutor data models.

Contains InterlocutorDataStore (runtime state) and InterlocutorDataField (schema definition).
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ruche.domain.interlocutor.channel_presence import (
    ChannelIdentity,
    Consent,
    InterlocutorChannelPresence,
    VerificationLevel,
)
from ruche.domain.interlocutor.variable_entry import ProfileAsset, VariableEntry


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class InterlocutorDataStore(BaseModel):
    """Persistent interlocutor data.

    Contains all persistent information about an interlocutor
    spanning across sessions.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    interlocutor_id: UUID = Field(
        default_factory=uuid4, description="Interlocutor identifier"
    )
    channel_identities: list[ChannelIdentity] = Field(
        default_factory=list, description="Channel mappings"
    )
    channel_presence: list[InterlocutorChannelPresence] = Field(
        default_factory=list, description="Cross-channel awareness"
    )
    fields: dict[str, VariableEntry] = Field(
        default_factory=dict, description="Profile data"
    )
    assets: list[ProfileAsset] = Field(
        default_factory=list, description="Attached documents"
    )
    verification_level: VerificationLevel = Field(
        default=VerificationLevel.UNVERIFIED, description="Identity status"
    )
    consents: list[Consent] = Field(
        default_factory=list, description="Consent records"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update"
    )
    last_interaction_at: datetime | None = Field(
        default=None, description="Last activity"
    )

    # Status summary (computed)
    @property
    def active_field_count(self) -> int:
        """Count of active fields."""
        return len(self.fields)

    def get_derived_fields(self, source_item_id: UUID) -> list[VariableEntry]:
        """Get all fields derived from a specific source."""
        return [
            f for f in self.fields.values()
            if f.source_item_id == source_item_id
        ]


class RequiredLevel(str, Enum):
    """How strictly a field is required for a scenario."""

    HARD = "hard"  # Must have to proceed
    SOFT = "soft"  # Nice to have, can proceed without


class FallbackAction(str, Enum):
    """What to do when a required field is missing."""

    ASK = "ask"  # Ask the interlocutor
    SKIP = "skip"  # Proceed without (soft requirements only)
    BLOCK = "block"  # Block scenario entry
    EXTRACT = "extract"  # Try LLM extraction from conversation


class ValidationMode(str, Enum):
    """Schema validation behavior mode."""

    STRICT = "strict"  # Reject invalid values
    WARN = "warn"  # Log warning, accept value
    DISABLED = "disabled"  # Skip validation entirely


class InterlocutorDataField(BaseModel):
    """Definition of an interlocutor field that can be collected.

    Agent-scoped schema that defines:
    - What data can be collected
    - How to validate it
    - How to collect it (prompts)
    - Privacy classification
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")

    # Definition
    name: str = Field(
        ...,
        pattern=r"^[a-z_][a-z0-9_]*$",
        max_length=50,
        description="Field key (must match VariableEntry.name)",
    )
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Field purpose")

    # Type and Validation
    value_type: str = Field(
        ...,
        description="Type: string, email, phone, date, number, boolean, json",
    )
    validation_regex: str | None = Field(
        default=None,
        description="Regex for value validation",
    )
    validation_tool_id: str | None = Field(
        default=None,
        description="Tool ID for complex validation",
    )
    allowed_values: list[str] | None = Field(
        default=None,
        description="Enum-like allowed values",
    )
    validation_mode: ValidationMode = Field(
        default=ValidationMode.STRICT,
        description="Validation behavior: strict, warn, or disabled",
    )

    # Collection Settings
    required_verification: bool = Field(
        default=False,
        description="Must be verified to be considered complete",
    )
    verification_methods: list[str] = Field(
        default_factory=list,
        description="Allowed verification methods: otp, document, human_review",
    )

    # Collection Prompts (for MissingFieldResolver)
    collection_prompt: str | None = Field(
        default=None,
        description="Prompt to ask interlocutor for this field",
    )
    extraction_examples: list[str] = Field(
        default_factory=list,
        description="Example values for LLM extraction",
    )
    extraction_prompt_hint: str | None = Field(
        default=None,
        description="Hint for LLM extraction from conversation",
    )

    # Privacy Classification
    is_pii: bool = Field(default=False, description="Personally Identifiable Information")
    encryption_required: bool = Field(
        default=False, description="Requires encryption at rest"
    )
    retention_days: int | None = Field(
        default=None,
        description="Auto-expire after N days (None = permanent)",
    )

    # Freshness (from CCV)
    freshness_seconds: int | None = Field(
        default=None,
        description="Max age before considered stale (None = never stale)",
    )

    # Persistence and Scope (from Focal Turn Pipeline)
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"] = Field(
        default="IDENTITY",
        description="Persistence scope: IDENTITY/BUSINESS persist always, CASE per-conversation, SESSION ephemeral",
    )
    persist: bool = Field(
        default=True,
        description="If False, field is runtime-only (never saved to database)",
    )

    # Metadata
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")
    enabled: bool = Field(default=True, description="Is this definition active")


class ScenarioFieldRequirement(BaseModel):
    """Binding between a scenario/step and required interlocutor fields.

    Defines what interlocutor data is needed for a scenario to execute.
    Used by MissingFieldResolver and ScenarioFilter.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")

    # Binding
    scenario_id: UUID = Field(..., description="Scenario requiring this field")
    step_id: UUID | None = Field(
        default=None,
        description="Specific step (None = scenario-wide requirement)",
    )
    rule_id: UUID | None = Field(
        default=None,
        description="Specific rule (for rule-scoped requirements)",
    )

    # Requirement
    field_name: str = Field(
        ...,
        description="InterlocutorDataField.name that is required",
    )
    required_level: RequiredLevel = Field(
        default=RequiredLevel.HARD,
        description="How strictly required",
    )
    fallback_action: FallbackAction = Field(
        default=FallbackAction.ASK,
        description="What to do if missing",
    )

    # Conditional Requirements
    when_condition: str | None = Field(
        default=None,
        description="Expression for conditional requirement",
    )
    depends_on_fields: list[str] = Field(
        default_factory=list,
        description="Other fields that must be present for this to apply",
    )

    # Priority
    collection_order: int = Field(
        default=0,
        description="Order in which to collect if multiple fields missing",
    )

    # Extraction metadata
    needs_human_review: bool = Field(
        default=False,
        description="Low confidence extraction, needs review",
    )
    extraction_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence of automatic extraction",
    )

    # Metadata
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")
