"""Profile domain models.

Contains all Pydantic models for customer profiles.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from soldier.conversation.models.enums import Channel
from soldier.profile.enums import ProfileFieldSource, VerificationLevel


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


class ProfileField(BaseModel):
    """Single customer fact.

    Represents a single piece of customer data with full
    provenance and verification tracking.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    name: str = Field(..., description="Field name")
    value: Any = Field(..., description="Field value")
    value_type: str = Field(..., description="Type: string, date, number, etc.")
    source: ProfileFieldSource = Field(..., description="How obtained")
    source_session_id: UUID | None = Field(
        default=None, description="Source session"
    )
    source_scenario_id: UUID | None = Field(
        default=None, description="Source scenario"
    )
    source_step_id: UUID | None = Field(
        default=None, description="Source step"
    )
    verified: bool = Field(default=False, description="Is verified")
    verification_method: str | None = Field(
        default=None, description="How verified"
    )
    verified_at: datetime | None = Field(
        default=None, description="Verification time"
    )
    verified_by: str | None = Field(default=None, description="Who verified")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence"
    )
    requires_confirmation: bool = Field(
        default=False, description="Needs user confirm"
    )
    collected_at: datetime = Field(
        default_factory=utc_now, description="Collection time"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration time"
    )


class ProfileAsset(BaseModel):
    """Document attached to profile."""

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., description="Asset name")
    asset_type: str = Field(..., description="Type: image, pdf, document")
    storage_provider: str = Field(..., description="Storage backend")
    storage_path: str = Field(..., description="Storage location")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size")
    checksum: str = Field(..., description="SHA256 hash")
    uploaded_at: datetime = Field(
        default_factory=utc_now, description="Upload time"
    )
    uploaded_in_session_id: UUID | None = Field(
        default=None, description="Upload session"
    )
    uploaded_in_scenario_id: UUID | None = Field(
        default=None, description="Upload scenario"
    )
    verified: bool = Field(default=False, description="Is verified")
    verification_result: dict[str, Any] | None = Field(
        default=None, description="Verification data"
    )
    retention_policy: str = Field(
        default="permanent", description="Retention rule"
    )
    expires_at: datetime | None = Field(
        default=None, description="Expiration time"
    )


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


class CustomerProfile(BaseModel):
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
    fields: dict[str, ProfileField] = Field(
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
