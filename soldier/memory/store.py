"""MemoryStore abstract interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from soldier.memory.models import Entity, Episode, Relationship


class MemoryStore(ABC):
    """Abstract interface for memory storage.

    Manages episodes, entities, and relationships with support
    for vector search, text search, and graph traversal.
    """

    # Episode operations
    @abstractmethod
    async def add_episode(self, episode: Episode) -> UUID:
        """Add an episode to the store."""
        pass

    @abstractmethod
    async def get_episode(self, group_id: str, episode_id: UUID) -> Episode | None:
        """Get an episode by ID."""
        pass

    @abstractmethod
    async def get_episodes(
        self, group_id: str, *, limit: int = 100
    ) -> list[Episode]:
        """Get episodes for a group."""
        pass

    @abstractmethod
    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        group_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Episode, float]]:
        """Search episodes by vector similarity."""
        pass

    @abstractmethod
    async def text_search_episodes(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 10,
    ) -> list[Episode]:
        """Search episodes by text content."""
        pass

    @abstractmethod
    async def delete_episode(self, group_id: str, episode_id: UUID) -> bool:
        """Delete an episode."""
        pass

    # Entity operations
    @abstractmethod
    async def add_entity(self, entity: Entity) -> UUID:
        """Add an entity to the store."""
        pass

    @abstractmethod
    async def get_entity(self, group_id: str, entity_id: UUID) -> Entity | None:
        """Get an entity by ID."""
        pass

    @abstractmethod
    async def get_entities(
        self,
        group_id: str,
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Get entities for a group with optional type filter."""
        pass

    @abstractmethod
    async def update_entity(self, entity: Entity) -> bool:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete_entity(self, group_id: str, entity_id: UUID) -> bool:
        """Delete an entity."""
        pass

    # Relationship operations
    @abstractmethod
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Add a relationship to the store."""
        pass

    @abstractmethod
    async def get_relationships(
        self,
        group_id: str,
        *,
        from_entity_id: UUID | None = None,
        to_entity_id: UUID | None = None,
        relation_type: str | None = None,
    ) -> list[Relationship]:
        """Get relationships with optional filters."""
        pass

    @abstractmethod
    async def delete_relationship(
        self, group_id: str, relationship_id: UUID
    ) -> bool:
        """Delete a relationship."""
        pass

    # Graph traversal
    @abstractmethod
    async def traverse_from_entities(
        self,
        entity_ids: list[UUID],
        group_id: str,
        *,
        depth: int = 2,
        relation_types: list[str] | None = None,
    ) -> list[Entity]:
        """Traverse graph from given entities up to specified depth."""
        pass

    # Bulk operations
    @abstractmethod
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all episodes, entities, and relationships for a group.

        Returns count of deleted items.
        """
        pass
