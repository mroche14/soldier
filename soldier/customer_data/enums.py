"""Enums for profile domain."""

from enum import Enum


class ItemStatus(str, Enum):
    """Explicit lifecycle status for profile data.

    Used for ProfileField and ProfileAsset to track lifecycle state.
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


class RequiredLevel(str, Enum):
    """How strictly a field is required for a scenario."""

    HARD = "hard"  # Must have to proceed
    SOFT = "soft"  # Nice to have, can proceed without


class FallbackAction(str, Enum):
    """What to do when a required field is missing."""

    ASK = "ask"  # Ask the customer
    SKIP = "skip"  # Proceed without (soft requirements only)
    BLOCK = "block"  # Block scenario entry
    EXTRACT = "extract"  # Try LLM extraction from conversation


class ValidationMode(str, Enum):
    """Schema validation behavior mode."""

    STRICT = "strict"  # Reject invalid values
    WARN = "warn"  # Log warning, accept value
    DISABLED = "disabled"  # Skip validation entirely


class ProfileFieldSource(str, Enum):
    """How a profile field was populated.

    Tracks the provenance of profile data.
    """

    USER_PROVIDED = "user_provided"
    LLM_EXTRACTED = "llm_extracted"
    TOOL_RESULT = "tool_result"
    DOCUMENT_EXTRACTED = "document_extracted"
    HUMAN_ENTERED = "human_entered"
    SYSTEM_INFERRED = "system_inferred"
    EXTRACTED = "extracted"  # Generic extraction (used by MissingFieldResolver)


class VerificationLevel(str, Enum):
    """Customer identity verification status.

    Progressive verification levels, can skip levels.
    """

    UNVERIFIED = "unverified"
    EMAIL_VERIFIED = "email_verified"
    PHONE_VERIFIED = "phone_verified"
    DOCUMENT_VERIFIED = "document_verified"
    KYC_COMPLETE = "kyc_complete"
