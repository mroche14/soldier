"""PostgreSQL implementation of MemoryStore.

Uses asyncpg for async database access and pgvector for
vector similarity search.
"""

import json
from uuid import UUID

from focal.db.errors import ConnectionError
from focal.db.pool import PostgresPool
from focal.memory.models import Entity, Episode, Relationship
from focal.memory.store import MemoryStore
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class PostgresMemoryStore(MemoryStore):
    """PostgreSQL implementation of MemoryStore.

    Uses asyncpg connection pool for efficient database access
    and pgvector for vector similarity search.
    """

    def __init__(self, pool: PostgresPool) -> None:
        """Initialize with connection pool.

        Args:
            pool: PostgreSQL connection pool
        """
        self._pool = pool

    # Episode operations
    async def add_episode(self, episode: Episode) -> UUID:
        """Add an episode to the store."""
        try:
            async with self._pool.acquire() as conn:
                embedding_str = self._embedding_to_pgvector(episode.embedding)
                await conn.execute(
                    """
                    INSERT INTO episodes (
                        id, group_id, content, content_type, source,
                        source_metadata, occurred_at, recorded_at,
                        embedding, embedding_model, entity_ids
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    episode.id,
                    episode.group_id,
                    episode.content,
                    episode.content_type,
                    episode.source,
                    json.dumps(episode.source_metadata),
                    episode.occurred_at,
                    episode.recorded_at,
                    embedding_str,
                    episode.embedding_model,
                    [str(eid) for eid in episode.entity_ids],
                )
                logger.debug("episode_added", episode_id=str(episode.id))
                return episode.id
        except Exception as e:
            logger.error(
                "postgres_add_episode_error", episode_id=str(episode.id), error=str(e)
            )
            raise ConnectionError(f"Failed to add episode: {e}", cause=e) from e

    async def get_episode(self, group_id: str, episode_id: UUID) -> Episode | None:
        """Get an episode by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, group_id, content, content_type, source,
                           source_metadata, occurred_at, recorded_at,
                           embedding, embedding_model, entity_ids
                    FROM episodes
                    WHERE id = $1 AND group_id = $2
                    """,
                    episode_id,
                    group_id,
                )
                if row:
                    return self._row_to_episode(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_episode_error", episode_id=str(episode_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get episode: {e}", cause=e) from e

    async def get_episodes(self, group_id: str, *, limit: int = 100) -> list[Episode]:
        """Get episodes for a group."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, group_id, content, content_type, source,
                           source_metadata, occurred_at, recorded_at,
                           embedding, embedding_model, entity_ids
                    FROM episodes
                    WHERE group_id = $1
                    ORDER BY occurred_at DESC
                    LIMIT $2
                    """,
                    group_id,
                    limit,
                )
                return [self._row_to_episode(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_episodes_error", group_id=group_id, error=str(e)
            )
            raise ConnectionError(f"Failed to get episodes: {e}", cause=e) from e

    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        group_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[Episode, float]]:
        """Search episodes by vector similarity using pgvector."""
        try:
            async with self._pool.acquire() as conn:
                embedding_str = f"[{','.join(map(str, query_embedding))}]"

                rows = await conn.fetch(
                    """
                    SELECT id, group_id, content, content_type, source,
                           source_metadata, occurred_at, recorded_at,
                           embedding, embedding_model, entity_ids,
                           1 - (embedding <=> $1::vector) AS score
                    FROM episodes
                    WHERE group_id = $2
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> $1::vector) >= $3
                    ORDER BY score DESC
                    LIMIT $4
                    """,
                    embedding_str,
                    group_id,
                    min_score,
                    limit,
                )
                return [(self._row_to_episode(row), row["score"]) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_vector_search_episodes_error",
                group_id=group_id,
                error=str(e),
            )
            raise ConnectionError(f"Failed to search episodes: {e}", cause=e) from e

    async def text_search_episodes(
        self,
        query: str,
        group_id: str,
        *,
        limit: int = 10,
    ) -> list[Episode]:
        """Search episodes by text content using ILIKE."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, group_id, content, content_type, source,
                           source_metadata, occurred_at, recorded_at,
                           embedding, embedding_model, entity_ids
                    FROM episodes
                    WHERE group_id = $1 AND content ILIKE $2
                    ORDER BY occurred_at DESC
                    LIMIT $3
                    """,
                    group_id,
                    f"%{query}%",
                    limit,
                )
                return [self._row_to_episode(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_text_search_episodes_error",
                group_id=group_id,
                error=str(e),
            )
            raise ConnectionError(f"Failed to search episodes: {e}", cause=e) from e

    async def delete_episode(self, group_id: str, episode_id: UUID) -> bool:
        """Delete an episode."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM episodes
                    WHERE id = $1 AND group_id = $2
                    """,
                    episode_id,
                    group_id,
                )
                deleted = result == "DELETE 1"
                if deleted:
                    logger.info("episode_deleted", episode_id=str(episode_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_episode_error",
                episode_id=str(episode_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete episode: {e}", cause=e) from e

    # Entity operations
    async def add_entity(self, entity: Entity) -> UUID:
        """Add an entity to the store."""
        try:
            async with self._pool.acquire() as conn:
                embedding_str = self._embedding_to_pgvector(entity.embedding)
                await conn.execute(
                    """
                    INSERT INTO entities (
                        id, group_id, name, entity_type, attributes,
                        valid_from, valid_to, recorded_at, embedding
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    entity.id,
                    entity.group_id,
                    entity.name,
                    entity.entity_type,
                    json.dumps(entity.attributes),
                    entity.valid_from,
                    entity.valid_to,
                    entity.recorded_at,
                    embedding_str,
                )
                logger.debug("entity_added", entity_id=str(entity.id))
                return entity.id
        except Exception as e:
            logger.error(
                "postgres_add_entity_error", entity_id=str(entity.id), error=str(e)
            )
            raise ConnectionError(f"Failed to add entity: {e}", cause=e) from e

    async def get_entity(self, group_id: str, entity_id: UUID) -> Entity | None:
        """Get an entity by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, group_id, name, entity_type, attributes,
                           valid_from, valid_to, recorded_at, embedding
                    FROM entities
                    WHERE id = $1 AND group_id = $2
                    """,
                    entity_id,
                    group_id,
                )
                if row:
                    return self._row_to_entity(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_entity_error", entity_id=str(entity_id), error=str(e)
            )
            raise ConnectionError(f"Failed to get entity: {e}", cause=e) from e

    async def get_entities(
        self,
        group_id: str,
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Get entities for a group with optional type filter."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, group_id, name, entity_type, attributes,
                           valid_from, valid_to, recorded_at, embedding
                    FROM entities
                    WHERE group_id = $1
                """
                params: list = [group_id]

                if entity_type is not None:
                    params.append(entity_type)
                    query += f" AND entity_type = ${len(params)}"

                params.append(limit)
                query += f" ORDER BY recorded_at DESC LIMIT ${len(params)}"

                rows = await conn.fetch(query, *params)
                return [self._row_to_entity(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_entities_error", group_id=group_id, error=str(e)
            )
            raise ConnectionError(f"Failed to get entities: {e}", cause=e) from e

    async def update_entity(self, entity: Entity) -> bool:
        """Update an existing entity."""
        try:
            async with self._pool.acquire() as conn:
                embedding_str = self._embedding_to_pgvector(entity.embedding)
                result = await conn.execute(
                    """
                    UPDATE entities
                    SET name = $1, entity_type = $2, attributes = $3,
                        valid_from = $4, valid_to = $5, embedding = $6
                    WHERE id = $7 AND group_id = $8
                    """,
                    entity.name,
                    entity.entity_type,
                    json.dumps(entity.attributes),
                    entity.valid_from,
                    entity.valid_to,
                    embedding_str,
                    entity.id,
                    entity.group_id,
                )
                updated = result == "UPDATE 1"
                if updated:
                    logger.debug("entity_updated", entity_id=str(entity.id))
                return updated
        except Exception as e:
            logger.error(
                "postgres_update_entity_error", entity_id=str(entity.id), error=str(e)
            )
            raise ConnectionError(f"Failed to update entity: {e}", cause=e) from e

    async def delete_entity(self, group_id: str, entity_id: UUID) -> bool:
        """Delete an entity."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM entities
                    WHERE id = $1 AND group_id = $2
                    """,
                    entity_id,
                    group_id,
                )
                deleted = result == "DELETE 1"
                if deleted:
                    logger.info("entity_deleted", entity_id=str(entity_id))
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_entity_error", entity_id=str(entity_id), error=str(e)
            )
            raise ConnectionError(f"Failed to delete entity: {e}", cause=e) from e

    # Relationship operations
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Add a relationship to the store."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO relationships (
                        id, group_id, from_entity_id, to_entity_id,
                        relation_type, attributes, valid_from, valid_to, recorded_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    relationship.id,
                    relationship.group_id,
                    relationship.from_entity_id,
                    relationship.to_entity_id,
                    relationship.relation_type,
                    json.dumps(relationship.attributes),
                    relationship.valid_from,
                    relationship.valid_to,
                    relationship.recorded_at,
                )
                logger.debug("relationship_added", relationship_id=str(relationship.id))
                return relationship.id
        except Exception as e:
            logger.error(
                "postgres_add_relationship_error",
                relationship_id=str(relationship.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to add relationship: {e}", cause=e) from e

    async def get_relationship(
        self, group_id: str, relationship_id: UUID
    ) -> Relationship | None:
        """Get a single relationship by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, group_id, from_entity_id, to_entity_id,
                           relation_type, attributes, valid_from, valid_to, recorded_at
                    FROM relationships
                    WHERE id = $1 AND group_id = $2
                    """,
                    relationship_id,
                    group_id,
                )
                if row:
                    return self._row_to_relationship(row)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_relationship_error",
                relationship_id=str(relationship_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get relationship: {e}", cause=e) from e

    async def get_relationships(
        self,
        group_id: str,
        *,
        from_entity_id: UUID | None = None,
        to_entity_id: UUID | None = None,
        relation_type: str | None = None,
    ) -> list[Relationship]:
        """Get relationships with optional filters."""
        try:
            async with self._pool.acquire() as conn:
                query = """
                    SELECT id, group_id, from_entity_id, to_entity_id,
                           relation_type, attributes, valid_from, valid_to, recorded_at
                    FROM relationships
                    WHERE group_id = $1
                """
                params: list = [group_id]

                if from_entity_id is not None:
                    params.append(from_entity_id)
                    query += f" AND from_entity_id = ${len(params)}"

                if to_entity_id is not None:
                    params.append(to_entity_id)
                    query += f" AND to_entity_id = ${len(params)}"

                if relation_type is not None:
                    params.append(relation_type)
                    query += f" AND relation_type = ${len(params)}"

                query += " ORDER BY valid_from DESC"

                rows = await conn.fetch(query, *params)
                return [self._row_to_relationship(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_get_relationships_error", group_id=group_id, error=str(e)
            )
            raise ConnectionError(f"Failed to get relationships: {e}", cause=e) from e

    async def update_relationship(self, relationship: Relationship) -> bool:
        """Update an existing relationship."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE relationships
                    SET relation_type = $1, attributes = $2,
                        valid_from = $3, valid_to = $4
                    WHERE id = $5 AND group_id = $6
                    """,
                    relationship.relation_type,
                    json.dumps(relationship.attributes),
                    relationship.valid_from,
                    relationship.valid_to,
                    relationship.id,
                    relationship.group_id,
                )
                updated = result == "UPDATE 1"
                if updated:
                    logger.debug(
                        "relationship_updated", relationship_id=str(relationship.id)
                    )
                return updated
        except Exception as e:
            logger.error(
                "postgres_update_relationship_error",
                relationship_id=str(relationship.id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to update relationship: {e}", cause=e) from e

    async def delete_relationship(self, group_id: str, relationship_id: UUID) -> bool:
        """Delete a relationship."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM relationships
                    WHERE id = $1 AND group_id = $2
                    """,
                    relationship_id,
                    group_id,
                )
                deleted = result == "DELETE 1"
                if deleted:
                    logger.info(
                        "relationship_deleted", relationship_id=str(relationship_id)
                    )
                return deleted
        except Exception as e:
            logger.error(
                "postgres_delete_relationship_error",
                relationship_id=str(relationship_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to delete relationship: {e}", cause=e) from e

    # Graph traversal
    async def traverse_from_entities(
        self,
        entity_ids: list[UUID],
        group_id: str,
        *,
        depth: int = 2,
        relation_types: list[str] | None = None,
    ) -> list[Entity]:
        """Traverse graph from given entities up to specified depth."""
        try:
            async with self._pool.acquire() as conn:
                visited: set[UUID] = set(entity_ids)
                current_level = set(entity_ids)

                for _ in range(depth):
                    if not current_level:
                        break

                    # Build query for related entities
                    query = """
                        SELECT DISTINCT e.id, e.group_id, e.name, e.entity_type,
                               e.attributes, e.valid_from, e.valid_to,
                               e.recorded_at, e.embedding
                        FROM entities e
                        JOIN relationships r ON (
                            e.id = r.to_entity_id OR e.id = r.from_entity_id
                        )
                        WHERE r.group_id = $1
                          AND (r.from_entity_id = ANY($2) OR r.to_entity_id = ANY($2))
                          AND e.id != ALL($2)
                    """
                    params: list = [group_id, list(current_level)]

                    if relation_types:
                        params.append(relation_types)
                        query += f" AND r.relation_type = ANY(${len(params)})"

                    rows = await conn.fetch(query, *params)

                    next_level: set[UUID] = set()
                    for row in rows:
                        entity_id = row["id"]
                        if entity_id not in visited:
                            visited.add(entity_id)
                            next_level.add(entity_id)

                    current_level = next_level

                # Fetch all visited entities
                if not visited:
                    return []

                rows = await conn.fetch(
                    """
                    SELECT id, group_id, name, entity_type, attributes,
                           valid_from, valid_to, recorded_at, embedding
                    FROM entities
                    WHERE id = ANY($1)
                    """,
                    list(visited),
                )
                return [self._row_to_entity(row) for row in rows]
        except Exception as e:
            logger.error(
                "postgres_traverse_error", group_id=group_id, error=str(e)
            )
            raise ConnectionError(f"Failed to traverse entities: {e}", cause=e) from e

    # Bulk operations
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all episodes, entities, and relationships for a group."""
        try:
            async with self._pool.acquire() as conn:
                total = 0

                # Delete relationships first (FK constraint)
                result = await conn.execute(
                    "DELETE FROM relationships WHERE group_id = $1",
                    group_id,
                )
                total += int(result.split()[-1])

                # Delete entities
                result = await conn.execute(
                    "DELETE FROM entities WHERE group_id = $1",
                    group_id,
                )
                total += int(result.split()[-1])

                # Delete episodes
                result = await conn.execute(
                    "DELETE FROM episodes WHERE group_id = $1",
                    group_id,
                )
                total += int(result.split()[-1])

                logger.info("group_deleted", group_id=group_id, total_deleted=total)
                return total
        except Exception as e:
            logger.error(
                "postgres_delete_by_group_error", group_id=group_id, error=str(e)
            )
            raise ConnectionError(f"Failed to delete by group: {e}", cause=e) from e

    # Helper methods
    def _row_to_episode(self, row) -> Episode:
        """Convert database row to Episode model."""
        entity_ids = []
        if row["entity_ids"]:
            entity_ids = [UUID(eid) for eid in row["entity_ids"]]

        return Episode(
            id=row["id"],
            group_id=row["group_id"],
            content=row["content"],
            content_type=row["content_type"],
            source=row["source"],
            source_metadata=json.loads(row["source_metadata"]) if row["source_metadata"] else {},
            occurred_at=row["occurred_at"],
            recorded_at=row["recorded_at"],
            embedding=self._pgvector_to_embedding(row["embedding"]),
            embedding_model=row["embedding_model"],
            entity_ids=entity_ids,
        )

    def _row_to_entity(self, row) -> Entity:
        """Convert database row to Entity model."""
        return Entity(
            id=row["id"],
            group_id=row["group_id"],
            name=row["name"],
            entity_type=row["entity_type"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            recorded_at=row["recorded_at"],
            embedding=self._pgvector_to_embedding(row["embedding"]),
        )

    def _row_to_relationship(self, row) -> Relationship:
        """Convert database row to Relationship model."""
        return Relationship(
            id=row["id"],
            group_id=row["group_id"],
            from_entity_id=row["from_entity_id"],
            to_entity_id=row["to_entity_id"],
            relation_type=row["relation_type"],
            attributes=json.loads(row["attributes"]) if row["attributes"] else {},
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            recorded_at=row["recorded_at"],
        )

    def _embedding_to_pgvector(self, embedding: list[float] | None) -> str | None:
        """Convert embedding list to pgvector string format."""
        if embedding is None:
            return None
        return f"[{','.join(map(str, embedding))}]"

    def _pgvector_to_embedding(self, data: str | None) -> list[float] | None:
        """Convert pgvector string to embedding list."""
        if data is None:
            return None
        clean = data.strip("[]")
        if not clean:
            return None
        return [float(x) for x in clean.split(",")]
