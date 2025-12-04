"""Dependency injection for API routes.

Provides FastAPI dependencies for stores and providers used by API endpoints.
Dependencies are configured based on settings and can be overridden for testing.
"""

import os
from functools import lru_cache
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.stores import AgentConfigStore
from soldier.alignment.stores.inmemory import InMemoryAgentConfigStore
from soldier.alignment.stores.postgres import PostgresAgentConfigStore
from soldier.audit.store import AuditStore
from soldier.audit.stores.inmemory import InMemoryAuditStore
from soldier.audit.stores.postgres import PostgresAuditStore
from soldier.config.loader import load_config
from soldier.config.settings import Settings, set_toml_config
from soldier.conversation.store import SessionStore
from soldier.conversation.stores.inmemory import InMemorySessionStore
from soldier.conversation.stores.redis import RedisSessionStore
from soldier.db.pool import PostgresPool
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider
from soldier.vector import VectorStore, EmbeddingManager, create_vector_store

logger = get_logger(__name__)

# Connection pool and client instances - shared across stores
_postgres_pool: PostgresPool | None = None
_redis_client: redis.Redis | None = None

# Store instances - created once and reused
_config_store: AgentConfigStore | None = None
_session_store: SessionStore | None = None
_audit_store: AuditStore | None = None
_vector_store: VectorStore | None = None
_embedding_provider: EmbeddingProvider | None = None
_embedding_manager: EmbeddingManager | None = None
_alignment_engine: AlignmentEngine | None = None


async def get_postgres_pool() -> PostgresPool:
    """Get the shared PostgreSQL connection pool.

    Creates and connects the pool on first access.
    Uses DATABASE_URL from environment.

    Returns:
        Connected PostgresPool instance
    """
    global _postgres_pool
    if _postgres_pool is None:
        _postgres_pool = PostgresPool()
        await _postgres_pool.connect()
        logger.info("postgres_pool_connected")
    return _postgres_pool


async def get_redis_client() -> redis.Redis:
    """Get the shared Redis client.

    Creates the client on first access.
    Uses REDIS_URL from environment.

    Returns:
        Redis client instance
    """
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info("redis_client_connected", url=redis_url.split("@")[-1])  # Log without credentials
    return _redis_client


@lru_cache
def get_settings() -> Settings:
    """Get application settings.

    Loads configuration from TOML files and environment variables.
    Cached to avoid reloading on every request.

    Returns:
        Settings object with all configuration
    """
    try:
        toml_config = load_config()
        set_toml_config(toml_config)
    except FileNotFoundError:
        # Use defaults if no config file
        logger.warning("config_file_not_found", msg="Using default configuration")
        set_toml_config({})

    return Settings()


async def get_config_store() -> AgentConfigStore:
    """Get the AgentConfigStore instance.

    Uses PostgresAgentConfigStore with shared connection pool.
    Falls back to InMemoryAgentConfigStore if database unavailable.

    Returns:
        AgentConfigStore for rules, scenarios, templates, variables
    """
    global _config_store
    if _config_store is None:
        try:
            pool = await get_postgres_pool()
            _config_store = PostgresAgentConfigStore(pool)
            logger.info("config_store_initialized", store_type="postgres")
        except Exception as e:
            logger.warning(
                "config_store_postgres_failed_using_inmemory",
                error=str(e),
            )
            _config_store = InMemoryAgentConfigStore()
            logger.info("config_store_initialized", store_type="inmemory")
    return _config_store


async def get_session_store() -> SessionStore:
    """Get the SessionStore instance.

    Uses RedisSessionStore with two-tier caching.
    Falls back to InMemorySessionStore if Redis unavailable.

    Returns:
        SessionStore for session state
    """
    global _session_store
    if _session_store is None:
        try:
            client = await get_redis_client()
            _session_store = RedisSessionStore(client)
            logger.info("session_store_initialized", store_type="redis")
        except Exception as e:
            logger.warning(
                "session_store_redis_failed_using_inmemory",
                error=str(e),
            )
            _session_store = InMemorySessionStore()
            logger.info("session_store_initialized", store_type="inmemory")
    return _session_store


async def get_audit_store() -> AuditStore:
    """Get the AuditStore instance.

    Uses PostgresAuditStore with shared connection pool.
    Falls back to InMemoryAuditStore if database unavailable.

    Returns:
        AuditStore for turn records and audit events
    """
    global _audit_store
    if _audit_store is None:
        try:
            pool = await get_postgres_pool()
            _audit_store = PostgresAuditStore(pool)
            logger.info("audit_store_initialized", store_type="postgres")
        except Exception as e:
            logger.warning(
                "audit_store_postgres_failed_using_inmemory",
                error=str(e),
            )
            _audit_store = InMemoryAuditStore()
            logger.info("audit_store_initialized", store_type="inmemory")
    return _audit_store


def get_vector_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorStore:
    """Get the VectorStore instance.

    Configuration comes from settings.storage.vector (TOML).
    API keys come from environment variables (QDRANT_API_KEY, QDRANT_URL).

    Args:
        settings: Application settings

    Returns:
        VectorStore for similarity search
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = create_vector_store(settings.storage.vector)
        logger.info(
            "vector_store_initialized",
            backend=settings.storage.vector.backend,
            dimensions=settings.storage.vector.dimensions,
        )
    return _vector_store


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProvider:
    """Get the EmbeddingProvider instance.

    Uses Jina AI by default. API key from JINA_API_KEY env var.

    Args:
        settings: Application settings

    Returns:
        EmbeddingProvider for vector embeddings
    """
    global _embedding_provider
    if _embedding_provider is None:
        provider_config = settings.providers.embedding.get("default")

        if provider_config and provider_config.provider == "jina":
            from soldier.providers.embedding.jina import JinaEmbeddingProvider

            _embedding_provider = JinaEmbeddingProvider(
                dimensions=provider_config.dimensions,
                model=provider_config.model,
            )
            logger.info(
                "embedding_provider_initialized",
                provider="jina",
                model=provider_config.model,
                dimensions=provider_config.dimensions,
            )
        else:
            # Fallback to mock for testing
            from soldier.providers.embedding.mock import MockEmbeddingProvider

            _embedding_provider = MockEmbeddingProvider(
                dimensions=settings.storage.vector.dimensions
            )
            logger.info("embedding_provider_initialized", provider="mock")

    return _embedding_provider


def get_embedding_manager(
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> EmbeddingManager:
    """Get the EmbeddingManager instance.

    Provides synchronization between entities and vectors.

    Args:
        vector_store: Vector storage backend
        embedding_provider: Embedding generation provider

    Returns:
        EmbeddingManager for entity-vector sync
    """
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager(
            vector_store=vector_store,
            embedding_provider=embedding_provider,
        )
        logger.info("embedding_manager_initialized")
    return _embedding_manager


def get_alignment_engine(
    config_store: Annotated[AgentConfigStore, Depends(get_config_store)],
    session_store: Annotated[SessionStore, Depends(get_session_store)],
    audit_store: Annotated[AuditStore, Depends(get_audit_store)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AlignmentEngine:
    """Get the AlignmentEngine instance.

    Creates the alignment engine with all required dependencies.
    LLM executors are created internally from pipeline_config.

    Args:
        config_store: Store for configuration
        session_store: Store for sessions
        audit_store: Store for audit records
        embedding_provider: Embedding provider
        settings: Application settings

    Returns:
        AlignmentEngine for processing turns
    """
    global _alignment_engine
    if _alignment_engine is None:
        _alignment_engine = AlignmentEngine(
            config_store=config_store,
            embedding_provider=embedding_provider,
            session_store=session_store,
            audit_store=audit_store,
            pipeline_config=settings.pipeline,
        )
        logger.info("alignment_engine_initialized")
    return _alignment_engine


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
AgentConfigStoreDep = Annotated[AgentConfigStore, Depends(get_config_store)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
AuditStoreDep = Annotated[AuditStore, Depends(get_audit_store)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
EmbeddingManagerDep = Annotated[EmbeddingManager, Depends(get_embedding_manager)]
AlignmentEngineDep = Annotated[AlignmentEngine, Depends(get_alignment_engine)]


async def reset_dependencies() -> None:
    """Reset all cached dependencies.

    Used for testing to ensure fresh instances.
    Closes connections before resetting.
    """
    global _config_store, _session_store, _audit_store, _alignment_engine
    global _vector_store, _embedding_provider, _embedding_manager
    global _postgres_pool, _redis_client

    # Close connections
    if _postgres_pool is not None:
        await _postgres_pool.close()
        _postgres_pool = None

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None

    _config_store = None
    _session_store = None
    _audit_store = None
    _vector_store = None
    _embedding_provider = None
    _embedding_manager = None
    _alignment_engine = None
    get_settings.cache_clear()
