"""Customer data update models.

Models for Phase 3 customer data updates.
"""

from typing import Any

from pydantic import BaseModel, Field

from focal.customer_data.models import CustomerDataField


class CustomerDataUpdate(BaseModel):
    """Represents a single update to apply to CustomerDataStore."""

    field_name: str = Field(..., description="Field name to update")
    field_definition: CustomerDataField = Field(..., description="Schema definition")
    raw_value: Any = Field(..., description="Raw extracted value")
    is_update: bool = Field(..., description="True if updating existing value")
    validated_value: Any | None = Field(default=None, description="Coerced value")
    validation_error: str | None = Field(default=None, description="Validation error if any")
