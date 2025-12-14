"""Structured output models for entity extraction."""

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """Pydantic model for LLM structured output during entity extraction."""

    name: str = Field(description="Entity name as mentioned in text")
    type: str = Field(description="Entity type classification")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Extracted key-value attributes"
    )
    confidence: str = Field(
        description="Extraction confidence: high, medium, or low"
    )


class ExtractedRelationship(BaseModel):
    """Pydantic model for LLM structured output during relationship extraction."""

    from_name: str = Field(description="Source entity name")
    to_name: str = Field(description="Target entity name")
    relation_type: str = Field(
        description="Relationship type (e.g., ordered, contains)"
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Optional relationship metadata"
    )
    confidence: str = Field(
        description="Extraction confidence: high, medium, or low"
    )


class EntityExtractionResult(BaseModel):
    """Complete extraction result from LLM containing all entities and relationships."""

    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="All extracted entities"
    )
    relationships: list[ExtractedRelationship] = Field(
        default_factory=list, description="All extracted relationships"
    )
