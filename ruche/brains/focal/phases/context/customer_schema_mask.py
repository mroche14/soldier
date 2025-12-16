"""Customer schema mask model.

Privacy-safe view of customer data schema for LLM.

NOTE: This is intentionally separate from ruche.domain.interlocutor.schema_mask.InterlocutorSchemaMask.
While InterlocutorSchemaMask is the general-purpose domain model with full feature set
(6 fields: name, scope, value_type, exists, verified, requires_confirmation),
CustomerSchemaMask is a FOCAL-specific variant optimized for Phase 2 (Situational Sensor)
LLM prompts with a minimal field set (4 fields: scope, type, exists, display_name).

The simpler structure reduces token usage in LLM prompts while providing exactly
the information needed for situation sensing. If you need the full schema mask,
use InterlocutorSchemaMask from ruche.domain.interlocutor instead.
"""

from typing import Literal

from pydantic import BaseModel, Field


class CustomerSchemaMaskEntry(BaseModel):
    """Single field in the schema mask."""

    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"] = Field(
        ..., description="Persistence scope"
    )
    type: str = Field(..., description="Field type")
    exists: bool = Field(..., description="True if value currently stored")
    display_name: str | None = Field(
        default=None, description="Human-readable name"
    )


class CustomerSchemaMask(BaseModel):
    """Privacy-safe view of customer data schema for LLM.

    Shows field existence and type, NOT values.
    Used in Phase 2 (Situational Sensor).
    """

    variables: dict[str, CustomerSchemaMaskEntry] = Field(
        ..., description="Field name -> schema entry"
    )
