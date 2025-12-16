"""Memory API request and response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ruche.memory.models import Entity, Episode


class EpisodeCreate(BaseModel):
    """Request model for creating an episode."""

    content: str = Field(..., description="Episode content")
    content_type: str = Field(
        default="message",
        description="Content type: message, event, document, summary",
    )
    source: str = Field(..., description="Source: user, agent, system, external")
    source_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional source metadata"
    )
    occurred_at: datetime = Field(..., description="When the event occurred")
    entity_ids: list[UUID] = Field(default_factory=list, description="Linked entity IDs")


class EpisodeResponse(BaseModel):
    """Response model for episode."""

    id: UUID
    group_id: str
    content: str
    content_type: str
    source: str
    source_metadata: dict[str, Any]
    occurred_at: datetime
    recorded_at: datetime
    embedding_model: str | None
    entity_ids: list[UUID]

    @classmethod
    def from_episode(cls, episode: Episode) -> "EpisodeResponse":
        """Create response from Episode model.

        Args:
            episode: Episode domain model

        Returns:
            EpisodeResponse for API
        """
        return cls(
            id=episode.id,
            group_id=episode.group_id,
            content=episode.content,
            content_type=episode.content_type,
            source=episode.source,
            source_metadata=episode.source_metadata,
            occurred_at=episode.occurred_at,
            recorded_at=episode.recorded_at,
            embedding_model=episode.embedding_model,
            entity_ids=episode.entity_ids,
        )


class EpisodeSearchResult(BaseModel):
    """Search result with episode and score."""

    episode: EpisodeResponse
    score: float = Field(..., description="Similarity/relevance score")


class MemorySearchResponse(BaseModel):
    """Response for memory search endpoint."""

    results: list[EpisodeSearchResult]
    query: str
    limit: int
    search_type: str = Field(..., description="vector or text")


class EntityResponse(BaseModel):
    """Response model for entity."""

    id: UUID
    group_id: str
    name: str
    entity_type: str
    attributes: dict[str, Any]
    valid_from: datetime
    valid_to: datetime | None
    recorded_at: datetime

    @classmethod
    def from_entity(cls, entity: Entity) -> "EntityResponse":
        """Create response from Entity model.

        Args:
            entity: Entity domain model

        Returns:
            EntityResponse for API
        """
        return cls(
            id=entity.id,
            group_id=entity.group_id,
            name=entity.name,
            entity_type=entity.entity_type,
            attributes=entity.attributes,
            valid_from=entity.valid_from,
            valid_to=entity.valid_to,
            recorded_at=entity.recorded_at,
        )
