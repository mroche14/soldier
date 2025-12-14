"""Audit domain models.

Contains all Pydantic models for audit records:
- TurnRecords for immutable turn audit
- AuditEvents for generic audit events
"""

from ruche.audit.models.event import AuditEvent
from ruche.audit.models.turn_record import TurnRecord

# Rebuild TurnRecord to resolve forward reference to TurnOutcome
# This is needed because TurnOutcome is imported under TYPE_CHECKING
# to avoid circular imports with focal.alignment
from ruche.alignment.models.outcome import TurnOutcome

TurnRecord.model_rebuild()

__all__ = [
    "TurnRecord",
    "AuditEvent",
]
