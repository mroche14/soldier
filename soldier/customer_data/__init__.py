"""Customer profiles: tenant and agent configuration.

Manages customer-specific configuration including agent definitions,
feature flags, and tenant-level settings.

Enhanced with:
- Lineage tracking via source_item_id
- Explicit status management (active/superseded/expired/orphaned)
- Schema-driven validation via ProfileFieldDefinition
- Scenario requirements via ScenarioFieldRequirement
"""

from soldier.profile.enums import (
    FallbackAction,
    ItemStatus,
    ProfileFieldSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
    VerificationLevel,
)
from soldier.profile.models import (
    ChannelIdentity,
    Consent,
    CustomerProfile,
    ProfileAsset,
    ProfileField,
    ProfileFieldDefinition,
    ScenarioFieldRequirement,
)

__all__ = [
    # Enums
    "FallbackAction",
    "ItemStatus",
    "ProfileFieldSource",
    "RequiredLevel",
    "SourceType",
    "ValidationMode",
    "VerificationLevel",
    # Models
    "CustomerProfile",
    "ChannelIdentity",
    "ProfileField",
    "ProfileAsset",
    "Consent",
    "ProfileFieldDefinition",
    "ScenarioFieldRequirement",
]
