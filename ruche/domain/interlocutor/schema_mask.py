"""Schema mask models for privacy-safe interlocutor data exposure.

Provides schema-only views of interlocutor data without revealing actual values,
safe for including in LLM prompts.
"""

from typing import Literal

from pydantic import BaseModel, Field


class InterlocutorSchemaMaskEntry(BaseModel):
    """Privacy-safe schema information for a single field.

    Shows what fields exist without revealing their values.
    """

    name: str = Field(..., description="Field name")
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"] = Field(
        ..., description="Field scope"
    )
    value_type: str = Field(..., description="Type: string, email, phone, etc.")
    exists: bool = Field(..., description="Whether field has a value")
    verified: bool = Field(default=False, description="Whether value is verified")
    requires_confirmation: bool = Field(
        default=False, description="Whether value needs confirmation"
    )


class InterlocutorSchemaMask(BaseModel):
    """Privacy-safe schema view of interlocutor data.

    Container for schema mask entries, safe to include in LLM prompts.
    """

    fields: dict[str, InterlocutorSchemaMaskEntry] = Field(
        default_factory=dict, description="Field name -> schema metadata"
    )

    def add_field(
        self,
        name: str,
        scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"],
        value_type: str,
        exists: bool,
        verified: bool = False,
        requires_confirmation: bool = False,
    ) -> None:
        """Add a field to the schema mask."""
        self.fields[name] = InterlocutorSchemaMaskEntry(
            name=name,
            scope=scope,
            value_type=value_type,
            exists=exists,
            verified=verified,
            requires_confirmation=requires_confirmation,
        )

    def to_dict(self) -> dict[str, dict]:
        """Convert to dict for template rendering."""
        return {name: entry.model_dump() for name, entry in self.fields.items()}
