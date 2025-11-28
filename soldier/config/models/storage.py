"""Storage backend configuration models."""

from typing import Literal

from pydantic import BaseModel, Field

BackendType = Literal["inmemory", "postgres", "redis", "mongodb", "neo4j", "dynamodb"]


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


class StorageConfig(BaseModel):
    """Configuration for all storage backends."""

    config: StoreBackendConfig = Field(
        default_factory=lambda: StoreBackendConfig(backend="postgres"),
        description="ConfigStore backend",
    )
    memory: StoreBackendConfig = Field(
        default_factory=lambda: StoreBackendConfig(backend="postgres"),
        description="MemoryStore backend",
    )
    session: StoreBackendConfig = Field(
        default_factory=lambda: StoreBackendConfig(backend="redis"),
        description="SessionStore backend",
    )
    audit: StoreBackendConfig = Field(
        default_factory=lambda: StoreBackendConfig(backend="postgres"),
        description="AuditStore backend",
    )
