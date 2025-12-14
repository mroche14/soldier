"""Variable entry models for interlocutor data domain.

Contains VariableEntry and related enums for tracking individual facts
about interlocutors with full provenance and lifecycle management.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class ItemStatus(str, Enum):
    """Explicit lifecycle status for interlocutor data.

    Used for VariableEntry and ProfileAsset to track lifecycle state.
    """

    ACTIVE = "active"  # Current, valid value
    SUPERSEDED = "superseded"  # Replaced by newer value
    EXPIRED = "expired"  # Past expires_at timestamp
    ORPHANED = "orphaned"  # Source item was deleted


class SourceType(str, Enum):
    """Type of source for derived data.

    Tracks the origin type for lineage traversal.
    """

    PROFILE_FIELD = "profile_field"  # Derived from another field
    PROFILE_ASSET = "profile_asset"  # Derived from an asset (e.g., OCR)
    SESSION = "session"  # Extracted from conversation
    TOOL = "tool"  # From tool execution
    EXTERNAL = "external"  # From external system


class VariableSource(str, Enum):
    """How an interlocutor data field was populated.

    Tracks the provenance of interlocutor data.
    """

    USER_PROVIDED = "user_provided"
    LLM_EXTRACTED = "llm_extracted"
    TOOL_RESULT = "tool_result"
    DOCUMENT_EXTRACTED = "document_extracted"
    HUMAN_ENTERED = "human_entered"
    SYSTEM_INFERRED = "system_inferred"
    EXTRACTED = "extracted"  # Generic extraction (used by MissingFieldResolver)


class VariableEntry(BaseModel):
    """Single interlocutor fact with lineage and status tracking.

    Represents a single piece of interlocutor data with full
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
        description="Reference to InterlocutorDataField for validation",
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
    """Document/media attached to interlocutor profile with lineage and status tracking.

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
