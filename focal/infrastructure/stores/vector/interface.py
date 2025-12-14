"""VectorStore abstract interface.

This module defines the abstract interface for vector storage backends.
Implementations can use Qdrant, pgvector, Pinecone, or other vector databases.

The VectorStore is responsible for:
- Storing embedding vectors with associated metadata
- Performing similarity search with tenant/agent isolation
- Managing vector lifecycle (upsert, delete)

Vectors are associated with entities (rules, scenarios, episodes) but stored
separately to allow swapping vector backends without changing entity storage.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities that can have embeddings."""

    RULE = "rule"
    SCENARIO = "scenario"
    EPISODE = "episode"
    ENTITY = "entity"  # Knowledge graph entity
    TEMPLATE = "template"


class VectorMetadata(BaseModel):
    """Metadata stored alongside vectors for filtering.

    All vectors must have tenant_id and agent_id for isolation.
    Additional fields enable rich filtering during search.
    """

    tenant_id: UUID = Field(..., description="Tenant ID for isolation")
    agent_id: UUID = Field(..., description="Agent ID for scoping")
    entity_type: EntityType = Field(..., description="Type of entity")
    entity_id: UUID = Field(..., description="ID of the associated entity")

    # Optional filtering metadata
    scope: str | None = Field(default=None, description="Scope level (global, scenario, step)")
    scope_id: UUID | None = Field(default=None, description="Scope identifier")
    enabled: bool = Field(default=True, description="Whether entity is active")
    embedding_model: str | None = Field(default=None, description="Model that generated embedding")

    # Extensible metadata
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class VectorDocument(BaseModel):
    """A document with its embedding vector and metadata."""

    id: str = Field(..., description="Unique vector ID (typically entity_type:entity_id)")
    vector: list[float] = Field(..., description="Embedding vector")
    metadata: VectorMetadata = Field(..., description="Associated metadata")
    text: str | None = Field(default=None, description="Original text (for debugging)")

    @classmethod
    def create_id(cls, entity_type: EntityType, entity_id: UUID) -> str:
        """Create a consistent vector ID from entity type and ID."""
        return f"{entity_type.value}:{entity_id}"


class VectorSearchResult(BaseModel):
    """A single search result with score."""

    id: str = Field(..., description="Vector ID")
    score: float = Field(..., description="Similarity score (0-1, higher is better)")
    metadata: VectorMetadata = Field(..., description="Associated metadata")
    vector: list[float] | None = Field(default=None, description="Vector if requested")


class VectorStore(ABC):
    """Abstract interface for vector storage and similarity search.

    Implementations must ensure:
    - Tenant isolation: vectors from tenant A never visible to tenant B
    - Agent scoping: searches can be filtered by agent_id
    - Consistent IDs: same entity always gets same vector ID
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'qdrant', 'pgvector')."""
        pass

    @abstractmethod
    async def upsert(
        self,
        documents: list[VectorDocument],
        *,
        collection: str = "default",
    ) -> int:
        """Insert or update vectors.

        Args:
            documents: List of documents with vectors and metadata
            collection: Collection/namespace to store in

        Returns:
            Number of vectors upserted
        """
        pass

    @abstractmethod
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
        """Search for similar vectors.

        Args:
            query_vector: Query embedding vector
            tenant_id: Required tenant ID for isolation
            agent_id: Optional agent ID filter
            entity_types: Optional filter by entity types
            collection: Collection to search in
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)
            filter_metadata: Additional metadata filters
            include_vectors: Whether to return vectors in results

        Returns:
            List of search results sorted by score descending
        """
        pass

    @abstractmethod
    async def delete(
        self,
        ids: list[str],
        *,
        collection: str = "default",
    ) -> int:
        """Delete vectors by ID.

        Args:
            ids: Vector IDs to delete
            collection: Collection to delete from

        Returns:
            Number of vectors deleted
        """
        pass

    @abstractmethod
    async def delete_by_filter(
        self,
        *,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        entity_ids: list[UUID] | None = None,
        collection: str = "default",
    ) -> int:
        """Delete vectors matching filter criteria.

        Args:
            tenant_id: Required tenant ID
            agent_id: Optional agent ID filter
            entity_type: Optional entity type filter
            entity_ids: Optional specific entity IDs
            collection: Collection to delete from

        Returns:
            Number of vectors deleted
        """
        pass

    @abstractmethod
    async def get(
        self,
        ids: list[str],
        *,
        collection: str = "default",
        include_vectors: bool = True,
    ) -> list[VectorDocument]:
        """Get vectors by ID.

        Args:
            ids: Vector IDs to retrieve
            collection: Collection to get from
            include_vectors: Whether to include vector data

        Returns:
            List of found documents
        """
        pass

    @abstractmethod
    async def count(
        self,
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        entity_type: EntityType | None = None,
        collection: str = "default",
    ) -> int:
        """Count vectors matching criteria.

        Args:
            tenant_id: Optional tenant filter
            agent_id: Optional agent filter
            entity_type: Optional entity type filter
            collection: Collection to count in

        Returns:
            Number of matching vectors
        """
        pass

    @abstractmethod
    async def ensure_collection(
        self,
        collection: str,
        *,
        dimensions: int,
        distance_metric: str = "cosine",
    ) -> None:
        """Ensure a collection exists with the specified configuration.

        Args:
            collection: Collection name
            dimensions: Vector dimensions
            distance_metric: Distance metric ('cosine', 'euclidean', 'dot')
        """
        pass

    @abstractmethod
    async def delete_collection(self, collection: str) -> bool:
        """Delete an entire collection.

        Args:
            collection: Collection to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        pass

    async def __aenter__(self) -> "VectorStore":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()
