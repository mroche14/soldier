"""Customer profiles: tenant and agent configuration.

Manages customer-specific configuration including agent definitions,
feature flags, and tenant-level settings.

Enhanced with:
- Lineage tracking via source_item_id
- Explicit status management (active/superseded/expired/orphaned)
- Schema-driven validation via CustomerDataField
- Scenario requirements via ScenarioFieldRequirement
"""

from soldier.customer_data.enums import (
    FallbackAction,
    ItemStatus,
    VariableSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
    VerificationLevel,
)
from soldier.customer_data.models import (
    ChannelIdentity,
    Consent,
    CustomerDataStore,
    ProfileAsset,
    VariableEntry,
    CustomerDataField,
    ScenarioFieldRequirement,
)

__all__ = [
    # Enums
    "FallbackAction",
    "ItemStatus",
    "VariableSource",
    "RequiredLevel",
    "SourceType",
    "ValidationMode",
    "VerificationLevel",
    # Models
    "CustomerDataStore",
    "ChannelIdentity",
    "VariableEntry",
    "ProfileAsset",
    "Consent",
    "CustomerDataField",
    "ScenarioFieldRequirement",
]
