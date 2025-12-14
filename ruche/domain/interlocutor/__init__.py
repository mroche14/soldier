"""Interlocutor data domain models.

This module contains all models related to interlocutor (customer) data:
- InterlocutorDataStore: Runtime state of interlocutor data
- InterlocutorDataField: Schema definition for collectable fields
- VariableEntry: Individual facts with provenance tracking
- ChannelIdentity/Presence: Multi-channel awareness
- Schema masks: Privacy-safe field exposure for LLM context
"""

from ruche.domain.interlocutor.channel_presence import (
    Channel,
    ChannelIdentity,
    Consent,
    InterlocutorChannelPresence,
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
from ruche.domain.interlocutor.schema_mask import (
    InterlocutorSchemaMask,
    InterlocutorSchemaMaskEntry,
)
from ruche.domain.interlocutor.variable_entry import (
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
