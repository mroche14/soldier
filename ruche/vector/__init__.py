"""Vector storage and similarity search."""

from ruche.vector.embedding_manager import EmbeddingManager
from ruche.vector.factory import create_vector_store, ensure_vector_collections
from ruche.vector.stores.base import (
    EntityType,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)
from ruche.vector.stores.inmemory import InMemoryVectorStore
from ruche.vector.stores.pgvector import PgVectorStore
from ruche.vector.stores.qdrant import QdrantVectorStore

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
