"""Profile domain models.

Contains all Pydantic models for customer profiles.
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ruche.conversation.models.enums import Channel
from ruche.customer_data.enums import (
    FallbackAction,
    ItemStatus,
    VariableSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
    VerificationLevel,
)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class ChannelIdentity(BaseModel):
    """Customer identity on a channel."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    channel: Channel = Field(..., description="Communication channel")
    channel_user_id: str = Field(..., description="User ID on channel")
    verified: bool = Field(default=False, description="Is verified")
    verified_at: datetime | None = Field(
        default=None, description="Verification time"
    )
    primary: bool = Field(
        default=False, description="Primary for channel type"
    )


class VariableEntry(BaseModel):
    """Single customer fact with lineage and status tracking.

    Represents a single piece of customer data with full
    provenance, verification, and lineage tracking.

    Enhanced to support:
    - Derivation lineage via source_item_id
    - Explicit status management
    - Schema reference for validation
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique field instance ID")
    name: str = Field(..., description="Field name")
    value: Any = Field(..., description="Field value")
    value_type: str = Field(..., description="Type: string, date, number, etc.")

    # Provenance (original)
    source: VariableSource = Field(..., description="How obtained")
    source_session_id: UUID | None = Field(
        default=None, description="Source session"
    )
    source_scenario_id: UUID | None = Field(
        default=None, description="Source scenario"
    )
    source_step_id: UUID | None = Field(
        default=None, description="Source step"
    )

    # Lineage (NEW - from CCV)
    source_item_id: UUID | None = Field(
        default=None,
        description="ID of VariableEntry or ProfileAsset this was derived from",
    )
    source_item_type: SourceType | None = Field(
        default=None,
        description="Type of source item for derivation chain traversal",
    )
    source_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context about derivation (e.g., tool name)",
    )

    # Status (NEW - from CCV)
    status: ItemStatus = Field(
        default=ItemStatus.ACTIVE,
        description="Lifecycle status: active, superseded, expired, or orphaned",
    )
    superseded_by_id: UUID | None = Field(
        default=None,
        description="ID of the field that replaced this one",
    )
    superseded_at: datetime | None = Field(
        default=None,
        description="When this field was superseded",
    )

    # Verification (original)
    verified: bool = Field(default=False, description="Is verified")
    verification_method: str | None = Field(
        default=None, description="How verified"
    )
    verified_at: datetime | None = Field(
        default=None, description="Verification time"
    )
    verified_by: str | None = Field(default=None, description="Who verified")

    # Confidence (original)
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )
    requires_confirmation: bool = Field(
        default=False, description="Needs user confirm"
    )

    # Timestamps
    collected_at: datetime = Field(
        default_factory=utc_now, description="Collection time"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration time"
    )

    # Schema reference (NEW)
    field_definition_id: UUID | None = Field(
        default=None,
        description="Reference to CustomerDataField for validation",
    )

    # History tracking (from Focal Turn Pipeline)
    history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Value history: [{value, timestamp, source, confidence}, ...]",
    )

    @property
    def is_orphaned(self) -> bool:
        """True if this field's source was deleted.

        Note: This is computed by checking if status is ORPHANED.
        The actual orphan detection is done by background job.
        """
        return self.status == ItemStatus.ORPHANED


class ProfileAsset(BaseModel):
    """Document/media attached to profile with lineage and status tracking.

    Enhanced to support:
    - Derivation lineage (asset-to-asset, e.g., thumbnail from original)
    - Explicit status management
    - Analysis results linkage
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(..., description="Type: image, pdf, document")

    # Storage
    storage_provider: str = Field(..., description="Storage backend")
    storage_path: str = Field(..., description="Storage location")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size")
    checksum: str = Field(..., description="SHA256 hash")

    # Provenance (original)
    uploaded_at: datetime = Field(
        default_factory=utc_now, description="Upload time"
    )
    uploaded_in_session_id: UUID | None = Field(
        default=None, description="Upload session"
    )
    uploaded_in_scenario_id: UUID | None = Field(
        default=None, description="Upload scenario"
    )

    # Lineage (NEW - from CCV)
    source_item_id: UUID | None = Field(
        default=None,
        description="ID of ProfileAsset this was derived from (e.g., thumbnail)",
    )
    source_item_type: SourceType | None = Field(
        default=None,
        description="Type of source item",
    )
    derived_from_tool: str | None = Field(
        default=None,
        description="Tool that created this derived asset (e.g., 'image_resize')",
    )

    # Status (NEW - from CCV)
    status: ItemStatus = Field(
        default=ItemStatus.ACTIVE,
        description="Lifecycle status: active, superseded, expired, or orphaned",
    )
    superseded_by_id: UUID | None = Field(
        default=None,
        description="ID of the asset that replaced this one",
    )
    superseded_at: datetime | None = Field(
        default=None,
        description="When this asset was superseded",
    )

    # Verification (original)
    verified: bool = Field(default=False, description="Is verified")
    verification_result: dict[str, Any] | None = Field(
        default=None, description="Verification data"
    )

    # Retention (original)
    retention_policy: str = Field(
        default="permanent", description="Retention rule"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration time"
    )

    # Analysis linkage (NEW)
    analysis_field_ids: list[UUID] = Field(
        default_factory=list,
        description="VariableEntry IDs derived from this asset (e.g., OCR)",
    )

    @property
    def is_orphaned(self) -> bool:
        """True if this asset's source was deleted.

        Note: This is computed by checking if status is ORPHANED.
        The actual orphan detection is done by background job.
        """
        return self.status == ItemStatus.ORPHANED


class Consent(BaseModel):
    """Customer consent record."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    consent_type: str = Field(
        ..., description="Type: marketing, data_processing, etc."
    )
    granted: bool = Field(..., description="Is consent granted")
    granted_at: datetime | None = Field(
        default=None, description="Grant time"
    )
    revoked_at: datetime | None = Field(
        default=None, description="Revocation time"
    )
    source_session_id: UUID | None = Field(
        default=None, description="Source session"
    )
    ip_address: str | None = Field(default=None, description="IP for audit")


class CustomerDataStore(BaseModel):
    """Persistent customer data.

    Contains all persistent information about a customer
    spanning across sessions.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    customer_id: UUID = Field(
        default_factory=uuid4, description="Customer identifier"
    )
    channel_identities: list[ChannelIdentity] = Field(
        default_factory=list, description="Channel mappings"
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


class CustomerDataField(BaseModel):
    """Definition of a profile field that can be collected.

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
        description="Prompt to ask customer for this field",
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
    """Binding between a scenario/step and required profile fields.

    Defines what customer data is needed for a scenario to execute.
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
        description="CustomerDataField.name that is required",
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
