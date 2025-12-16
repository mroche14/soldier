"""Customer profiles: tenant and agent configuration.

DEPRECATED: This package is deprecated. Use ruche.domain.interlocutor for models
and ruche.infrastructure.stores.interlocutor for store implementations.

Manages customer-specific configuration including agent definitions,
feature flags, and tenant-level settings.

Enhanced with:
- Lineage tracking via source_item_id
- Explicit status management (active/superseded/expired/orphaned)
- Schema-driven validation via InterlocutorDataField
- Scenario requirements via ScenarioFieldRequirement
"""

# Re-export from canonical locations for backwards compatibility
from ruche.domain.interlocutor.channel_presence import (
    Channel,
    ChannelIdentity,
    Consent,
    VerificationLevel,
)
from ruche.domain.interlocutor.models import (
    FallbackAction,
    InterlocutorDataField,
    InterlocutorDataStore,
    RequiredLevel,
    ScenarioFieldRequirement,
    ValidationMode,
)
from ruche.domain.interlocutor.variable_entry import (
    ItemStatus,
    ProfileAsset,
    SourceType,
    VariableEntry,
    VariableSource,
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
    "Channel",
    # Models
    "InterlocutorDataStore",
    "ChannelIdentity",
    "VariableEntry",
    "ProfileAsset",
    "Consent",
    "InterlocutorDataField",
    "ScenarioFieldRequirement",
]
