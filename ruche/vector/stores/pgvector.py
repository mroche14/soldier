"""PostgreSQL with pgvector extension for vector storage.

This module provides a VectorStore implementation using PostgreSQL
with the pgvector extension for similarity search.

pgvector supports:
- Exact and approximate nearest neighbor search
- Multiple distance metrics (cosine, L2, inner product)
- HNSW and IVFFlat indexes for fast search
- Native PostgreSQL filtering with vector operations
"""

import json
from typing import Any
from uuid import UUID

from ruche.infrastructure.db.pool import PostgresPool
from ruche.observability.logging import get_logger
from ruche.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)

logger = get_logger(__name__)

# Distance operators in pgvector
DISTANCE_OPERATORS = {
    "cosine": "<=>",  # Cosine distance
    "euclidean": "<->",  # L2 distance
    "dot": "<#>",  # Negative inner product
}


class PgVectorStore(VectorStore):
    """Vector store implementation using PostgreSQL with pgvector.

    Uses the pgvector extension for efficient vector similarity search.
    Stores vectors in a table with tenant/agent isolation via row-level filtering.
    """

    def __init__(
        self,
        pool: PostgresPool,
        table_prefix: str = "focal",
    ) -> None:
        """Initialize pgvector store.

        Args:
            pool: PostgreSQL connection pool
            table_prefix: Prefix for table names
        """
        self._pool = pool
        self._table_prefix = table_prefix

        logger.info(
            "pgvector_store_initialized",
            prefix=table_prefix,
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "pgvector"

    def _table_name(self, collection: str) -> str:
        """Get full table name with prefix."""
        return f"{self._table_prefix}_{collection}_vectors"

    def _metadata_to_json(self, metadata: VectorMetadata) -> dict[str, Any]:
        """Convert VectorMetadata to JSON-serializable dict."""
        return {
            "tenant_id": str(metadata.tenant_id),
            "agent_id": str(metadata.agent_id),
            "entity_type": metadata.entity_type.value,
            "entity_id": str(metadata.entity_id),
            "scope": metadata.scope,
            "scope_id": str(metadata.scope_id) if metadata.scope_id else None,
            "enabled": metadata.enabled,
            "embedding_model": metadata.embedding_model,
            "extra": metadata.extra,
        }

    def _json_to_metadata(self, data: dict[str, Any]) -> VectorMetadata:
        """Convert JSON dict to VectorMetadata."""
        return VectorMetadata(
            tenant_id=UUID(data["tenant_id"]),
            agent_id=UUID(data["agent_id"]),
            entity_type=EntityType(data["entity_type"]),
            entity_id=UUID(data["entity_id"]),
            scope=data.get("scope"),
            scope_id=UUID(data["scope_id"]) if data.get("scope_id") else None,
            enabled=data.get("enabled", True),
            embedding_model=data.get("embedding_model"),
            extra=data.get("extra", {}),
        )

    async def upsert(
        self,
        documents: list[VectorDocument],
        *,
        collection: str = "default",
    ) -> int:
        """Insert or update vectors in PostgreSQL."""
        if not documents:
            return 0

        table = self._table_name(collection)

        async with self._pool.acquire() as conn:
            # Use ON CONFLICT for upsert
            for doc in documents:
                await conn.execute(
                    f"""
                    INSERT INTO {table} (id, vector, metadata, text, tenant_id, agent_id, entity_type, enabled)
                    VALUES ($1, $2::vector, $3::jsonb, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        vector = EXCLUDED.vector,
                        metadata = EXCLUDED.metadata,
                        text = EXCLUDED.text,
                        tenant_id = EXCLUDED.tenant_id,
                        agent_id = EXCLUDED.agent_id,
                        entity_type = EXCLUDED.entity_type,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    doc.id,
                    str(doc.vector),  # pgvector accepts string format
                    json.dumps(self._metadata_to_json(doc.metadata)),
                    doc.text,
                    str(doc.metadata.tenant_id),
                    str(doc.metadata.agent_id),
                    doc.metadata.entity_type.value,
                    doc.metadata.enabled,
                )

            logger.debug(
                "pgvector_upsert_success",
                table=table,
                count=len(documents),
            )

            return len(documents)

    async def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_types: list[EntityType] | None = None,
        collection: str = "default",
        limit: int = 10,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
        include_vectors: bool = False,
        distance_metric: str = "cosine",
    ) -> list[VectorSearchResult]:
        """Search for similar vectors using pgvector."""
        table = self._table_name(collection)
        operator = DISTANCE_OPERATORS.get(distance_metric, "<=>")

        # Build WHERE clause
        conditions = ["tenant_id = $2", "enabled = true"]
        params: list[Any] = [str(query_vector), str(tenant_id)]
        param_idx = 3

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(str(agent_id))
            param_idx += 1

        if entity_types:
            placeholders = ", ".join(f"${param_idx + i}" for i in range(len(entity_types)))
            conditions.append(f"entity_type IN ({placeholders})")
            params.extend(et.value for et in entity_types)
            param_idx += len(entity_types)

        if filter_metadata:
            for key, value in filter_metadata.items():
                conditions.append(f"metadata->>'{key}' = ${param_idx}")
                params.append(str(value) if isinstance(value, UUID) else value)
                param_idx += 1

        where_clause = " AND ".join(conditions)

        # For cosine, convert distance to similarity score (1 - distance)
        # pgvector cosine distance is 0 for identical, 2 for opposite
        if distance_metric == "cosine":
            score_expr = f"1 - (vector {operator} $1::vector)"
            score_filter = f"(1 - (vector {operator} $1::vector)) >= ${param_idx}" if min_score > 0 else None
        else:
            # For euclidean/dot, lower distance = more similar
            score_expr = f"1 / (1 + (vector {operator} $1::vector))"
            score_filter = None  # More complex for these metrics

        if score_filter:
            conditions.append(score_filter)
            params.append(min_score)
            where_clause = " AND ".join(conditions)

        vector_col = ", vector" if include_vectors else ""

        query = f"""
            SELECT id, metadata, text{vector_col}, {score_expr} as score
            FROM {table}
            WHERE {where_clause}
            ORDER BY vector {operator} $1::vector
            LIMIT {limit}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            results = []
            for row in rows:
                metadata = self._json_to_metadata(json.loads(row["metadata"]))
                results.append(
                    VectorSearchResult(
                        id=row["id"],
                        score=float(row["score"]),
                        metadata=metadata,
                        vector=list(row["vector"]) if include_vectors and row.get("vector") else None,
                    )
                )

            logger.debug(
                "pgvector_search_success",
                table=table,
                results=len(results),
                min_score=min_score,
            )

            return results

    async def delete(
        self,
        ids: list[str],
        *,
        collection: str = "default",
    ) -> int:
        """Delete vectors by ID from PostgreSQL."""
        if not ids:
            return 0

        table = self._table_name(collection)

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {table} WHERE id = ANY($1)",
                ids,
            )

            # Parse "DELETE N" result
            deleted = int(result.split()[-1]) if result else 0

            logger.debug(
                "pgvector_delete_success",
                table=table,
                count=deleted,
            )

            return deleted

    async def delete_by_filter(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        entity_ids: list[UUID] | None = None,
        collection: str = "default",
    ) -> int:
        """Delete vectors matching filter criteria."""
        table = self._table_name(collection)

        conditions = ["tenant_id = $1"]
        params: list[Any] = [str(tenant_id)]
        param_idx = 2

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(str(agent_id))
            param_idx += 1

        if entity_type:
            conditions.append(f"entity_type = ${param_idx}")
            params.append(entity_type.value)
            param_idx += 1

        if entity_ids:
            conditions.append(f"metadata->>'entity_id' = ANY(${param_idx})")
            params.append([str(eid) for eid in entity_ids])
            param_idx += 1

        where_clause = " AND ".join(conditions)

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {table} WHERE {where_clause}",
                *params,
            )

            deleted = int(result.split()[-1]) if result else 0

            logger.debug(
                "pgvector_delete_by_filter_success",
                table=table,
                deleted=deleted,
            )

            return deleted

    async def get(
        self,
        ids: list[str],
        *,
        collection: str = "default",
        include_vectors: bool = True,
    ) -> list[VectorDocument]:
        """Get vectors by ID from PostgreSQL."""
        if not ids:
            return []

        table = self._table_name(collection)
        vector_col = ", vector" if include_vectors else ""

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, metadata, text{vector_col} FROM {table} WHERE id = ANY($1)",
                ids,
            )

            documents = []
            for row in rows:
                metadata = self._json_to_metadata(json.loads(row["metadata"]))
                documents.append(
                    VectorDocument(
                        id=row["id"],
                        vector=list(row["vector"]) if include_vectors and row.get("vector") else [],
                        metadata=metadata,
                        text=row["text"],
                    )
                )

            return documents

    async def count(
        self,
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        collection: str = "default",
    ) -> int:
        """Count vectors matching criteria."""
        table = self._table_name(collection)

        conditions = []
        params: list[Any] = []
        param_idx = 1

        if tenant_id:
            conditions.append(f"tenant_id = ${param_idx}")
            params.append(str(tenant_id))
            param_idx += 1

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(str(agent_id))
            param_idx += 1

        if entity_type:
            conditions.append(f"entity_type = ${param_idx}")
            params.append(entity_type.value)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {table} WHERE {where_clause}",
                    *params,
                )
                return result or 0
            except Exception:
                # Table might not exist
                return 0

    async def ensure_collection(
        self,
        collection: str,
        *,
        dimensions: int,
        distance_metric: str = "cosine",
    ) -> None:
        """Ensure a collection table exists with the specified configuration."""
        table = self._table_name(collection)

        async with self._pool.acquire() as conn:
            # Enable pgvector extension if not exists
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Create table with vector column
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    vector vector({dimensions}),
                    metadata JSONB NOT NULL,
                    text TEXT,
                    tenant_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )

            # Create indexes for filtering
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_tenant_idx ON {table}(tenant_id)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_agent_idx ON {table}(agent_id)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_type_idx ON {table}(entity_type)"
            )
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {table}_enabled_idx ON {table}(enabled)"
            )

            # Create HNSW index for fast approximate search
            # Using cosine distance by default
            index_ops = {
                "cosine": "vector_cosine_ops",
                "euclidean": "vector_l2_ops",
                "dot": "vector_ip_ops",
            }
            ops = index_ops.get(distance_metric, "vector_cosine_ops")

            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {table}_vector_idx
                ON {table}
                USING hnsw (vector {ops})
                """
            )

            logger.info(
                "pgvector_collection_created",
                table=table,
                dimensions=dimensions,
                distance=distance_metric,
            )

    async def delete_collection(self, collection: str) -> bool:
        """Delete an entire collection table."""
        table = self._table_name(collection)

        async with self._pool.acquire() as conn:
            try:
                await conn.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info("pgvector_collection_deleted", table=table)
                return True
            except Exception as e:
                logger.error(
                    "pgvector_delete_collection_error",
                    table=table,
                    error=str(e),
                )
                return False

    async def close(self) -> None:
        """Close is handled by the pool, not the store."""
        pass
