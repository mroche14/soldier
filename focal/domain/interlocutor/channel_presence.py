"""Channel presence models for interlocutor data domain.

Contains models for tracking interlocutor presence and identity
across multiple communication channels.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class Channel(str, Enum):
    """Communication channels.

    Represents the medium through which the conversation
    is taking place.
    """

    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBCHAT = "webchat"
    EMAIL = "email"
    VOICE = "voice"
    SMS = "sms"
    API = "api"


class ChannelIdentity(BaseModel):
    """Interlocutor identity on a channel."""

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


class InterlocutorChannelPresence(BaseModel):
    """Cross-channel awareness: where this interlocutor can be reached / has interacted.

    Provides agents with awareness that interactions happen across multiple channels
    without merging sessions. Sessions stay separate per channel, but agents can
    reference prior interactions on other channels.

    Example: "I see you also reached out via WhatsApp earlier today..."
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    channel: str = Field(..., description="Channel identifier: whatsapp, webchat, phone, etc.")
    channel_user_id: str = Field(..., description="Channel-specific identifier")
    last_active_at: datetime = Field(..., description="Most recent interaction on this channel")
    session_status: Literal["active", "idle", "closed"] = Field(
        ..., description="Current session state"
    )
    message_count: int = Field(..., description="Total messages exchanged on this channel")
    first_interaction_at: datetime = Field(
        ..., description="When interlocutor first used this channel"
    )


class Consent(BaseModel):
    """Interlocutor consent record."""

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
    source_session_id: str | None = Field(
        default=None, description="Source session"
    )
    ip_address: str | None = Field(default=None, description="IP for audit")


class VerificationLevel(str, Enum):
    """Interlocutor identity verification status.

    Progressive verification levels, can skip levels.
    """

    UNVERIFIED = "unverified"
    EMAIL_VERIFIED = "email_verified"
    PHONE_VERIFIED = "phone_verified"
    DOCUMENT_VERIFIED = "document_verified"
    KYC_COMPLETE = "kyc_complete"
