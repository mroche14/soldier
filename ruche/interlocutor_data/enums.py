"""Enums for profile domain.

DEPRECATED: This module is deprecated. Use ruche.domain.interlocutor instead.

All enums have been moved to ruche.domain.interlocutor:
- VariableSource → ruche.domain.interlocutor.variable_entry
- ItemStatus → ruche.domain.interlocutor.variable_entry
- SourceType → ruche.domain.interlocutor.variable_entry
- RequiredLevel → ruche.domain.interlocutor.models
- FallbackAction → ruche.domain.interlocutor.models
- ValidationMode → ruche.domain.interlocutor.models
- VerificationLevel → ruche.domain.interlocutor.channel_presence

This file maintains backwards compatibility by re-exporting from the canonical location.
"""

# Re-export from canonical locations for backwards compatibility
from ruche.domain.interlocutor.channel_presence import VerificationLevel
from ruche.domain.interlocutor.models import (
    FallbackAction,
    RequiredLevel,
    ValidationMode,
)
from ruche.domain.interlocutor.variable_entry import (
    ItemStatus,
    SourceType,
    VariableSource,
)

__all__ = [
    "ItemStatus",
    "SourceType",
    "RequiredLevel",
    "FallbackAction",
    "ValidationMode",
    "VariableSource",
    "VerificationLevel",
]
