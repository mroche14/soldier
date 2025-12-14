"""Vector storage and similarity search."""

from focal.vector.embedding_manager import EmbeddingManager
from focal.vector.factory import create_vector_store, ensure_vector_collections
from focal.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)
from focal.vector.stores.inmemory import InMemoryVectorStore
from focal.vector.stores.pgvector import PgVectorStore
from focal.vector.stores.qdrant import QdrantVectorStore

__all__ = [
    "EmbeddingManager",
    "EntityType",
    "InMemoryVectorStore",
    "PgVectorStore",
    "QdrantVectorStore",
    "VectorDocument",
    "VectorMetadata",
    "VectorSearchResult",
    "VectorStore",
    "create_vector_store",
    "ensure_vector_collections",
]
