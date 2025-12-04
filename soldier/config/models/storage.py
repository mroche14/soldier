"""Storage backend configuration models."""

from typing import Literal

from pydantic import BaseModel, Field

BackendType = Literal["inmemory", "postgres", "redis", "mongodb", "neo4j", "dynamodb"]
VectorBackendType = Literal["inmemory", "qdrant", "pgvector"]


class StoreBackendConfig(BaseModel):
    """Configuration for a single store backend."""

    backend: BackendType = Field(
        default="inmemory",
        description="Backend type",
    )
    connection_url: str | None = Field(
        default=None,
        description="Connection URL (from env var)",
    )
    pool_size: int = Field(
        default=10,
        gt=0,
        description="Connection pool size",
    )
    pool_timeout: int = Field(
        default=30,
        gt=0,
        description="Pool timeout in seconds",
    )


class PostgresConfig(StoreBackendConfig):
    """PostgreSQL-specific configuration."""

    backend: Literal["postgres"] = "postgres"
    min_pool_size: int = Field(
        default=5,
        gt=0,
        description="Minimum connections to keep open",
    )
    max_pool_size: int = Field(
        default=20,
        gt=0,
        description="Maximum connections in pool",
    )
    max_inactive_connection_lifetime: float = Field(
        default=300.0,
        gt=0,
        description="Close connections idle longer than this (seconds)",
    )
    command_timeout: float = Field(
        default=60.0,
        gt=0,
        description="Default timeout for queries (seconds)",
    )


class RedisSessionConfig(StoreBackendConfig):
    """Redis session store configuration with two-tier caching."""

    backend: Literal["redis"] = "redis"
    hot_ttl_seconds: int = Field(
        default=1800,  # 30 minutes
        gt=0,
        description="TTL for hot cache tier (seconds)",
    )
    persist_ttl_seconds: int = Field(
        default=604800,  # 7 days
        gt=0,
        description="TTL for persistent tier (seconds)",
    )
    max_session_age_seconds: int = Field(
        default=604800,  # 7 days
        gt=0,
        description="Maximum session age before permanent expiration",
    )
    key_prefix: str = Field(
        default="session",
        description="Redis key prefix for session keys",
    )


class RedisProfileCacheConfig(StoreBackendConfig):
    """Redis profile cache configuration.

    Wraps PostgresProfileStore with Redis caching for read-heavy workloads.
    Uses write-through invalidation strategy.
    """

    backend: Literal["redis"] = "redis"
    ttl_seconds: int = Field(
        default=1800,  # 30 minutes
        gt=0,
        description="Cache TTL in seconds",
    )
    key_prefix: str = Field(
        default="profile",
        description="Redis key prefix for profile cache",
    )
    enabled: bool = Field(
        default=True,
        description="Enable/disable caching (useful for debugging)",
    )
    fallback_on_error: bool = Field(
        default=True,
        description="Fall back to backend on Redis errors",
    )


class VectorStoreConfig(BaseModel):
    """Configuration for vector storage backend.

    Note: API keys should come from environment variables (QDRANT_API_KEY),
    NOT from config files. This ensures secrets are never committed.
    """

    backend: VectorBackendType = Field(
        default="qdrant",
        description="Vector store backend type (inmemory, qdrant, pgvector)",
    )
    collection_prefix: str = Field(
        default="soldier",
        description="Prefix for collection names",
    )
    dimensions: int = Field(
        default=1024,
        gt=0,
        description="Vector dimensions (must match embedding provider)",
    )
    distance_metric: Literal["cosine", "euclidean", "dot"] = Field(
        default="cosine",
        description="Distance metric for similarity",
    )
    timeout: float = Field(
        default=60.0,
        gt=0,
        description="Request timeout in seconds",
    )
    # Embedding storage strategy
    store_on_entity: bool = Field(
        default=True,
        description="Store embedding on entity record (e.g., rule.embedding)",
    )
    sync_to_vector_store: bool = Field(
        default=True,
        description="Sync embedding to vector store for similarity search",
    )


class StorageConfig(BaseModel):
    """Configuration for all storage backends."""

    config: StoreBackendConfig = Field(
        default_factory=lambda: PostgresConfig(),
        description="AgentConfigStore backend",
    )
    memory: StoreBackendConfig = Field(
        default_factory=lambda: PostgresConfig(),
        description="MemoryStore backend",
    )
    session: RedisSessionConfig = Field(
        default_factory=lambda: RedisSessionConfig(),
        description="SessionStore backend",
    )
    audit: StoreBackendConfig = Field(
        default_factory=lambda: PostgresConfig(),
        description="AuditStore backend",
    )
    profile_cache: RedisProfileCacheConfig = Field(
        default_factory=lambda: RedisProfileCacheConfig(),
        description="Profile cache configuration (Redis)",
    )
    vector: VectorStoreConfig = Field(
        default_factory=VectorStoreConfig,
        description="VectorStore backend for embeddings",
    )
