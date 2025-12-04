"""VectorStore factory for creating backend instances.

This module provides a factory function to create the appropriate
VectorStore implementation based on configuration.

API keys and connection strings are read from environment variables:
- QDRANT_URL: Qdrant server URL (defaults to http://localhost:6333)
- QDRANT_API_KEY: Qdrant API key (optional for local, required for cloud)
- DATABASE_URL or SOLDIER_DATABASE_URL: PostgreSQL connection string for pgvector
"""

import os

from soldier.config.models.storage import VectorStoreConfig
from soldier.observability.logging import get_logger
from soldier.vector.stores.base import VectorStore
from soldier.vector.stores.inmemory import InMemoryVectorStore
from soldier.vector.stores.pgvector import PgVectorStore
from soldier.vector.stores.qdrant import QdrantVectorStore

logger = get_logger(__name__)


def create_vector_store(config: VectorStoreConfig) -> VectorStore:
    """Create a VectorStore instance based on configuration.

    Configuration comes from TOML files (backend, dimensions, etc.).
    Secrets come from environment variables (QDRANT_API_KEY, QDRANT_URL).

    Args:
        config: Vector store configuration from settings

    Returns:
        Configured VectorStore instance

    Raises:
        ValueError: If backend type is not supported
    """
    backend = config.backend

    if backend == "inmemory":
        logger.info(
            "creating_vector_store",
            backend="inmemory",
            dimensions=config.dimensions,
        )
        return InMemoryVectorStore(dimensions=config.dimensions)

    elif backend == "qdrant":
        # Read connection details from environment
        url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        api_key = os.environ.get("QDRANT_API_KEY")

        logger.info(
            "creating_vector_store",
            backend="qdrant",
            url=url,
            has_api_key=bool(api_key),
            prefix=config.collection_prefix,
            dimensions=config.dimensions,
        )

        return QdrantVectorStore(
            url=url,
            api_key=api_key,
            collection_prefix=config.collection_prefix,
            timeout=config.timeout,
        )

    elif backend == "pgvector":
        from soldier.db.pool import PostgresPool

        # PostgresPool reads from DATABASE_URL or SOLDIER_DATABASE_URL env vars
        pool = PostgresPool()

        logger.info(
            "creating_vector_store",
            backend="pgvector",
            prefix=config.collection_prefix,
            dimensions=config.dimensions,
        )

        return PgVectorStore(
            pool=pool,
            table_prefix=config.collection_prefix,
        )

    else:
        raise ValueError(f"Unsupported vector store backend: {backend}")


async def ensure_vector_collections(
    store: VectorStore,
    *,
    dimensions: int = 1024,
    collections: list[str] | None = None,
) -> None:
    """Ensure required vector collections exist.

    Args:
        store: VectorStore instance
        dimensions: Vector dimensions
        collections: List of collection names to create (defaults to standard set)
    """
    if collections is None:
        collections = ["default", "rules", "scenarios", "episodes", "entities"]

    for collection in collections:
        await store.ensure_collection(
            collection=collection,
            dimensions=dimensions,
            distance_metric="cosine",
        )

    logger.info(
        "vector_collections_ensured",
        collections=collections,
        dimensions=dimensions,
    )
