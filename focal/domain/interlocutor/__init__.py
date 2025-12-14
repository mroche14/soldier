"""Interlocutor data domain models.

This module contains all models related to interlocutor (customer) data:
- InterlocutorDataStore: Runtime state of interlocutor data
- InterlocutorDataField: Schema definition for collectable fields
- VariableEntry: Individual facts with provenance tracking
- ChannelIdentity/Presence: Multi-channel awareness
- Schema masks: Privacy-safe field exposure for LLM context
"""

from focal.domain.interlocutor.channel_presence import (
    Channel,
    ChannelIdentity,
    Consent,
    InterlocutorChannelPresence,
    VerificationLevel,
)
from focal.domain.interlocutor.models import (
    FallbackAction,
    InterlocutorDataField,
    InterlocutorDataStore,
    RequiredLevel,
    ScenarioFieldRequirement,
    ValidationMode,
)
from focal.domain.interlocutor.schema_mask import (
    InterlocutorSchemaMask,
    InterlocutorSchemaMaskEntry,
)
from focal.domain.interlocutor.variable_entry import (
    ItemStatus,
    ProfileAsset,
    SourceType,
    VariableEntry,
    VariableSource,
)

__all__ = [
    # Core models
    "InterlocutorDataStore",
    "InterlocutorDataField",
    "VariableEntry",
    "ProfileAsset",
    # Channel models
    "Channel",
    "ChannelIdentity",
    "InterlocutorChannelPresence",
    "Consent",
    "VerificationLevel",
    # Schema models
    "InterlocutorSchemaMask",
    "InterlocutorSchemaMaskEntry",
    # Requirements
    "ScenarioFieldRequirement",
    # Enums
    "VariableSource",
    "ItemStatus",
    "SourceType",
    "RequiredLevel",
    "FallbackAction",
    "ValidationMode",
]
