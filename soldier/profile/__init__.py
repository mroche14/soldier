"""Customer profiles: tenant and agent configuration.

Manages customer-specific configuration including agent definitions,
feature flags, and tenant-level settings.
"""

from soldier.profile.enums import ProfileFieldSource, VerificationLevel
from soldier.profile.models import (
    ChannelIdentity,
    Consent,
    CustomerProfile,
    ProfileAsset,
    ProfileField,
)

__all__ = [
    # Enums
    "ProfileFieldSource",
    "VerificationLevel",
    # Models
    "CustomerProfile",
    "ChannelIdentity",
    "ProfileField",
    "ProfileAsset",
    "Consent",
]
