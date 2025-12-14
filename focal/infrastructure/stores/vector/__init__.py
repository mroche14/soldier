"""VectorStore for managing embedding vectors and similarity search.

Stores embedding vectors with metadata and performs similarity search
with tenant/agent isolation.
"""

from focal.infrastructure.stores.vector.inmemory import InMemoryVectorStore
from focal.infrastructure.stores.vector.interface import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)
from focal.infrastructure.stores.vector.pgvector import PgVectorStore
from focal.infrastructure.stores.vector.qdrant import QdrantVectorStore

__all__ = [
    # Interface
    "VectorStore",
    "VectorDocument",
    "VectorMetadata",
    "VectorSearchResult",
    "EntityType",
    # Implementations
    "InMemoryVectorStore",
    "PgVectorStore",
    "QdrantVectorStore",
]
