"""In-memory implementation of MemoryStore."""

from collections import deque
from uuid import UUID

from ruche.memory.models import Entity, Episode, Relationship
from ruche.memory.store import MemoryStore
from ruche.utils.vector import cosine_similarity


class InMemoryMemoryStore(MemoryStore):
    """In-memory implementation of MemoryStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Implements BFS for graph traversal.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._episodes: dict[UUID, Episode] = {}
        self._entities: dict[UUID, Entity] = {}
        self._relationships: dict[UUID, Relationship] = {}

    # Episode operations
    async def add_episode(self, episode: Episode) -> UUID:
        """Add an episode to the store."""
        self._episodes[episode.id] = episode
        return episode.id

    async def get_episode(self, group_id: str, episode_id: UUID) -> Episode | None:
        """Get an episode by ID."""
        episode = self._episodes.get(episode_id)
        if episode and episode.group_id == group_id:
            return episode
        return None

    async def get_episodes(self, group_id: str, *, limit: int = 100) -> list[Episode]:
        """Get episodes for a group."""
        results = [ep for ep in self._episodes.values() if ep.group_id == group_id]
        # Sort by occurred_at descending
        results.sort(key=lambda x: x.occurred_at, reverse=True)
        return results[:limit]

    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        group_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Episode, float]]:
        """Search episodes by vector similarity."""
        results: list[tuple[Episode, float]] = []

        for episode in self._episodes.values():
            if episode.group_id != group_id:
                continue
            if episode.embedding is None:
                continue

            score = cosine_similarity(query_embedding, episode.embedding)
            if score >= min_score:
                results.append((episode, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def text_search_episodes(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 10,
    ) -> list[Episode]:
        """Search episodes by text content (substring match)."""
        query_lower = query.lower()
        results = [
            ep
            for ep in self._episodes.values()
            if ep.group_id == group_id and query_lower in ep.content.lower()
        ]
        # Sort by occurred_at descending
        results.sort(key=lambda x: x.occurred_at, reverse=True)
        return results[:limit]

    async def delete_episode(self, group_id: str, episode_id: UUID) -> bool:
        """Delete an episode."""
        episode = self._episodes.get(episode_id)
        if episode and episode.group_id == group_id:
            del self._episodes[episode_id]
            return True
        return False

    # Entity operations
    async def add_entity(self, entity: Entity) -> UUID:
        """Add an entity to the store."""
        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, group_id: str, entity_id: UUID) -> Entity | None:
        """Get an entity by ID."""
        entity = self._entities.get(entity_id)
        if entity and entity.group_id == group_id:
            return entity
        return None

    async def get_entities(
        self,
        group_id: str,
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Get entities for a group with optional type filter."""
        results = []
        for entity in self._entities.values():
            if entity.group_id != group_id:
                continue
            if entity_type is not None and entity.entity_type != entity_type:
                continue
            results.append(entity)
        return results[:limit]

    async def update_entity(self, entity: Entity) -> bool:
        """Update an existing entity."""
        if entity.id in self._entities:
            self._entities[entity.id] = entity
            return True
        return False

    async def delete_entity(self, group_id: str, entity_id: UUID) -> bool:
        """Delete an entity."""
        entity = self._entities.get(entity_id)
        if entity and entity.group_id == group_id:
            del self._entities[entity_id]
            return True
        return False

    # Relationship operations
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Add a relationship to the store."""
        self._relationships[relationship.id] = relationship
        return relationship.id

    async def get_relationship(
        self, group_id: str, relationship_id: UUID
    ) -> Relationship | None:
        """Get a single relationship by ID."""
        rel = self._relationships.get(relationship_id)
        if rel and rel.group_id == group_id:
            return rel
        return None

    async def get_relationships(
        self,
        group_id: str,
        *,
        from_entity_id: UUID | None = None,
        to_entity_id: UUID | None = None,
        relation_type: str | None = None,
    ) -> list[Relationship]:
        """Get relationships with optional filters."""
        results = []
        for rel in self._relationships.values():
            if rel.group_id != group_id:
                continue
            if from_entity_id is not None and rel.from_entity_id != from_entity_id:
                continue
            if to_entity_id is not None and rel.to_entity_id != to_entity_id:
                continue
            if relation_type is not None and rel.relation_type != relation_type:
                continue
            results.append(rel)
        return results

    async def update_relationship(self, relationship: Relationship) -> bool:
        """Update an existing relationship."""
        if relationship.id in self._relationships:
            self._relationships[relationship.id] = relationship
            return True
        return False

    async def delete_relationship(self, group_id: str, relationship_id: UUID) -> bool:
        """Delete a relationship."""
        rel = self._relationships.get(relationship_id)
        if rel and rel.group_id == group_id:
            del self._relationships[relationship_id]
            return True
        return False

    # Graph traversal
    async def traverse_from_entities(
        self,
        entity_ids: list[UUID],
        group_id: str,
        *,
        depth: int = 2,
        relation_types: list[str] | None = None,
    ) -> list[Entity]:
        """Traverse graph from given entities using BFS."""
        if depth < 1 or not entity_ids:
            return []

        visited: set[UUID] = set()
        result_entities: list[Entity] = []

        # BFS queue: (entity_id, current_depth)
        queue: deque[tuple[UUID, int]] = deque()

        # Initialize with starting entities
        for eid in entity_ids:
            if eid not in visited:
                visited.add(eid)
                entity = await self.get_entity(group_id, eid)
                if entity:
                    result_entities.append(entity)
                    queue.append((eid, 0))

        while queue:
            current_id, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Find outgoing relationships
            rels = await self.get_relationships(group_id, from_entity_id=current_id)

            for rel in rels:
                if relation_types and rel.relation_type not in relation_types:
                    continue
                if rel.to_entity_id not in visited:
                    visited.add(rel.to_entity_id)
                    entity = await self.get_entity(group_id, rel.to_entity_id)
                    if entity:
                        result_entities.append(entity)
                        queue.append((rel.to_entity_id, current_depth + 1))

            # Find incoming relationships
            rels = await self.get_relationships(group_id, to_entity_id=current_id)

            for rel in rels:
                if relation_types and rel.relation_type not in relation_types:
                    continue
                if rel.from_entity_id not in visited:
                    visited.add(rel.from_entity_id)
                    entity = await self.get_entity(group_id, rel.from_entity_id)
                    if entity:
                        result_entities.append(entity)
                        queue.append((rel.from_entity_id, current_depth + 1))

        return result_entities

    # Bulk operations
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all items for a group."""
        count = 0

        # Delete episodes
        episode_ids = [eid for eid, ep in self._episodes.items() if ep.group_id == group_id]
        for eid in episode_ids:
            del self._episodes[eid]
            count += 1

        # Delete entities
        entity_ids = [eid for eid, en in self._entities.items() if en.group_id == group_id]
        for eid in entity_ids:
            del self._entities[eid]
            count += 1

        # Delete relationships
        rel_ids = [rid for rid, rel in self._relationships.items() if rel.group_id == group_id]
        for rid in rel_ids:
            del self._relationships[rid]
            count += 1

        return count
