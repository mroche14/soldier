"""Turn context model.

Aggregated context for processing a turn.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# Note: These imports will work after we rename the profile models
# For now, we'll use forward references


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
    customer_id: UUID = Field(..., description="Customer ID")
    session_id: UUID = Field(..., description="Session ID")
    turn_number: int = Field(..., description="Turn number in session")

    # Session state - forward reference until we have a proper SessionState model
    session: dict = Field(..., description="Session state")

    # Customer data - will be CustomerDataStore after rename
    customer_data: dict = Field(..., description="Customer data snapshot")

    # Static config
    pipeline_config: dict = Field(..., description="Pipeline configuration")
    customer_data_fields: dict[str, dict] = Field(
        default_factory=dict,
        description="Field name -> CustomerDataField definition",
    )
    glossary: dict[str, dict] = Field(
        default_factory=dict, description="Term -> GlossaryItem"
    )

    # Reconciliation (if happened)
    reconciliation_result: dict | None = Field(
        default=None, description="Scenario reconciliation result if migration occurred"
    )

    # Timestamps
    turn_started_at: datetime = Field(..., description="When turn processing started")
