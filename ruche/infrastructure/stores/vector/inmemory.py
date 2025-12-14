"""In-memory vector store implementation for testing.

This module provides a VectorStore implementation that stores vectors
in memory using Python data structures. It uses numpy for efficient
similarity calculations.

Use this implementation for:
- Unit tests
- Development without external dependencies
- Quick prototyping
"""

from typing import Any
from uuid import UUID

import numpy as np

from ruche.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)


class InMemoryVectorStore(VectorStore):
    """In-memory vector store for testing and development.

    Stores vectors in dictionaries and uses numpy for similarity search.
    Thread-safe operations are not guaranteed.
    """

    def __init__(self, dimensions: int = 1024):
        """Initialize in-memory store.

        Args:
            dimensions: Expected vector dimensions (for validation)
        """
        self._dimensions = dimensions
        # collection -> id -> VectorDocument
        self._collections: dict[str, dict[str, VectorDocument]] = {}

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "inmemory"

    def _get_collection(self, collection: str) -> dict[str, VectorDocument]:
        """Get or create a collection."""
        if collection not in self._collections:
            self._collections[collection] = {}
        return self._collections[collection]

    def _cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _matches_filter(
        self,
        metadata: VectorMetadata,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_types: list[EntityType] | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Check if metadata matches filter criteria."""
        # Must match tenant
        if metadata.tenant_id != tenant_id:
            return False

        # Must be enabled
        if not metadata.enabled:
            return False

        # Optional agent filter
        if agent_id and metadata.agent_id != agent_id:
            return False

        # Optional entity type filter
        if entity_types and metadata.entity_type not in entity_types:
            return False

        # Optional additional filters
        if filter_metadata:
            for key, value in filter_metadata.items():
                meta_value = getattr(metadata, key, None)
                if meta_value is None:
                    meta_value = metadata.extra.get(key)
                if meta_value != value:
                    return False

        return True

    async def upsert(
        self,
        documents: list[VectorDocument],
        *,
        collection: str = "default",
    ) -> int:
        """Insert or update vectors."""
        coll = self._get_collection(collection)

        for doc in documents:
            coll[doc.id] = doc

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
    ) -> list[VectorSearchResult]:
        """Search for similar vectors."""
        coll = self._get_collection(collection)

        # Score all matching documents
        scored: list[tuple[VectorDocument, float]] = []

        for doc in coll.values():
            if not self._matches_filter(
                doc.metadata,
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_types=entity_types,
                filter_metadata=filter_metadata,
            ):
                continue

            score = self._cosine_similarity(query_vector, doc.vector)
            if score >= min_score:
                scored.append((doc, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        scored = scored[:limit]

        # Convert to results
        return [
            VectorSearchResult(
                id=doc.id,
                score=score,
                metadata=doc.metadata,
                vector=doc.vector if include_vectors else None,
            )
            for doc, score in scored
        ]

    async def delete(
        self,
        ids: list[str],
        *,
        collection: str = "default",
    ) -> int:
        """Delete vectors by ID."""
        coll = self._get_collection(collection)

        deleted = 0
        for id_ in ids:
            if id_ in coll:
                del coll[id_]
                deleted += 1

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
        coll = self._get_collection(collection)

        to_delete = []
        for id_, doc in coll.items():
            if doc.metadata.tenant_id != tenant_id:
                continue

            if agent_id and doc.metadata.agent_id != agent_id:
                continue

            if entity_type and doc.metadata.entity_type != entity_type:
                continue

            if entity_ids and doc.metadata.entity_id not in entity_ids:
                continue

            to_delete.append(id_)

        for id_ in to_delete:
            del coll[id_]

        return len(to_delete)

    async def get(
        self,
        ids: list[str],
        *,
        collection: str = "default",
        include_vectors: bool = True,
    ) -> list[VectorDocument]:
        """Get vectors by ID."""
        coll = self._get_collection(collection)

        results = []
        for id_ in ids:
            if id_ in coll:
                doc = coll[id_]
                if include_vectors:
                    results.append(doc)
                else:
                    results.append(
                        VectorDocument(
                            id=doc.id,
                            vector=[],
                            metadata=doc.metadata,
                            text=doc.text,
                        )
                    )

        return results

    async def count(
        self,
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        collection: str = "default",
    ) -> int:
        """Count vectors matching criteria."""
        coll = self._get_collection(collection)

        count = 0
        for doc in coll.values():
            if tenant_id and doc.metadata.tenant_id != tenant_id:
                continue
            if agent_id and doc.metadata.agent_id != agent_id:
                continue
            if entity_type and doc.metadata.entity_type != entity_type:
                continue
            count += 1

        return count

    async def ensure_collection(
        self,
        collection: str,
        *,
        dimensions: int,
        distance_metric: str = "cosine",
    ) -> None:
        """Ensure a collection exists (no-op for in-memory)."""
        self._get_collection(collection)
        self._dimensions = dimensions

    async def delete_collection(self, collection: str) -> bool:
        """Delete an entire collection."""
        if collection in self._collections:
            del self._collections[collection]
            return True
        return False

    def clear(self) -> None:
        """Clear all collections (for testing)."""
        self._collections.clear()
