"""Customer profiles: tenant and agent configuration.

Manages customer-specific configuration including agent definitions,
feature flags, and tenant-level settings.

Enhanced with:
- Lineage tracking via source_item_id
- Explicit status management (active/superseded/expired/orphaned)
- Schema-driven validation via InterlocutorDataField
- Scenario requirements via ScenarioFieldRequirement
"""

from ruche.interlocutor_data.enums import (
    FallbackAction,
    ItemStatus,
    VariableSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
    VerificationLevel,
)
from ruche.interlocutor_data.models import (
    ChannelIdentity,
    Consent,
    InterlocutorDataStore,
    ProfileAsset,
    VariableEntry,
    InterlocutorDataField,
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
    "InterlocutorDataStore",
    "ChannelIdentity",
    "VariableEntry",
    "ProfileAsset",
    "Consent",
    "InterlocutorDataField",
    "ScenarioFieldRequirement",
]
