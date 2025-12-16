"""Turn context model.

Aggregated context for processing a turn.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# Import types directly since Pydantic needs them at runtime
from ruche.conversation.models.session import Session
from ruche.domain.interlocutor.models import InterlocutorDataStore, InterlocutorDataField
from ruche.config.models.pipeline import PipelineConfig
from ruche.brains.focal.models.glossary import GlossaryItem
from ruche.brains.focal.migration.models import ReconciliationResult


class TurnContext(BaseModel):
    """Aggregated context for processing a turn.

    Loaded in Phase 1, used throughout pipeline.
    Contains all necessary data for processing a turn:
    - Session state (active scenarios, variables, rule fires)
    - Customer data snapshot (runtime view of profile fields)
    - Static configuration (pipeline config, glossary, customer data schema)
    - Scenario reconciliation (handle version changes)
    """

    # Routing
    tenant_id: UUID = Field(..., description="Tenant ID")
    agent_id: UUID = Field(..., description="Agent ID")
    interlocutor_id: UUID = Field(..., description="Customer ID")
    session_id: UUID = Field(..., description="Session ID")
    turn_number: int = Field(..., description="Turn number in session")

    # Session state - proper typed model
    session: Session = Field(..., description="Session state")

    # Customer data - properly typed InterlocutorDataStore
    customer_data: InterlocutorDataStore = Field(..., description="Customer data snapshot")

    # Static config - properly typed PipelineConfig
    pipeline_config: PipelineConfig = Field(..., description="Pipeline configuration")
    customer_data_fields: dict[str, InterlocutorDataField] = Field(
        default_factory=dict,
        description="Field name -> InterlocutorDataField definition",
    )
    glossary: dict[str, GlossaryItem] = Field(
        default_factory=dict, description="Term -> GlossaryItem"
    )

    # Reconciliation (if happened)
    reconciliation_result: ReconciliationResult | None = Field(
        default=None, description="Scenario reconciliation result if migration occurred"
    )

    # Timestamps
    turn_started_at: datetime = Field(..., description="When turn processing started")
