"""Vector storage and similarity search."""

from soldier.vector.embedding_manager import EmbeddingManager
from soldier.vector.factory import create_vector_store, ensure_vector_collections
from soldier.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)
from soldier.vector.stores.inmemory import InMemoryVectorStore
from soldier.vector.stores.pgvector import PgVectorStore
from soldier.vector.stores.qdrant import QdrantVectorStore

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
