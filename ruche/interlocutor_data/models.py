"""Profile domain models.

DEPRECATED: This module is deprecated. Use ruche.domain.interlocutor instead.

All models have been moved to ruche.domain.interlocutor:
- InterlocutorDataStore → ruche.domain.interlocutor.models
- InterlocutorDataField → ruche.domain.interlocutor.models
- ScenarioFieldRequirement → ruche.domain.interlocutor.models
- VariableEntry → ruche.domain.interlocutor.variable_entry
- ProfileAsset → ruche.domain.interlocutor.variable_entry
- ChannelIdentity → ruche.domain.interlocutor.channel_presence
- Consent → ruche.domain.interlocutor.channel_presence

This file maintains backwards compatibility by re-exporting from the canonical location.
"""

# Re-export from canonical locations for backwards compatibility
from ruche.domain.interlocutor.channel_presence import (
    ChannelIdentity,
    Consent,
)
from ruche.domain.interlocutor.models import (
    InterlocutorDataField,
    InterlocutorDataStore,
    ScenarioFieldRequirement,
)
from ruche.domain.interlocutor.variable_entry import (
    ProfileAsset,
    VariableEntry,
)

__all__ = [
    "InterlocutorDataStore",
    "ChannelIdentity",
    "VariableEntry",
    "ProfileAsset",
    "Consent",
    "InterlocutorDataField",
    "ScenarioFieldRequirement",
]
