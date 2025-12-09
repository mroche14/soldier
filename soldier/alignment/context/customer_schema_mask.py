"""Customer schema mask model.

Privacy-safe view of customer data schema for LLM.
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
