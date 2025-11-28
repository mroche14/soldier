"""Enums for profile domain."""

from enum import Enum


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


class VerificationLevel(str, Enum):
    """Customer identity verification status.

    Progressive verification levels, can skip levels.
    """

    UNVERIFIED = "unverified"
    EMAIL_VERIFIED = "email_verified"
    PHONE_VERIFIED = "phone_verified"
    DOCUMENT_VERIFIED = "document_verified"
    KYC_COMPLETE = "kyc_complete"
