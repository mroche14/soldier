"""Dependency injection for API routes.

Provides FastAPI dependencies for stores and providers used by API endpoints.
Dependencies are configured based on settings and can be overridden for testing.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from soldier.alignment.engine import AlignmentEngine
from soldier.alignment.stores import ConfigStore
from soldier.alignment.stores.inmemory import InMemoryConfigStore
from soldier.audit.store import AuditStore
from soldier.audit.stores.inmemory import InMemoryAuditStore
from soldier.config.loader import load_config
from soldier.config.settings import Settings, set_toml_config
from soldier.conversation.store import SessionStore
from soldier.conversation.stores.inmemory import InMemorySessionStore
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider
from soldier.providers.llm import LLMProvider

logger = get_logger(__name__)

# Store instances - created once and reused
_config_store: ConfigStore | None = None
_session_store: SessionStore | None = None
_audit_store: AuditStore | None = None
_alignment_engine: AlignmentEngine | None = None


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


def get_config_store() -> ConfigStore:
    """Get the ConfigStore instance.

    Returns:
        ConfigStore for rules, scenarios, templates, variables
    """
    global _config_store
    if _config_store is None:
        # TODO: Use production store based on settings
        _config_store = InMemoryConfigStore()
        logger.info("config_store_initialized", store_type="inmemory")
    return _config_store


def get_session_store() -> SessionStore:
    """Get the SessionStore instance.

    Returns:
        SessionStore for session state
    """
    global _session_store
    if _session_store is None:
        # TODO: Use production store based on settings
        _session_store = InMemorySessionStore()
        logger.info("session_store_initialized", store_type="inmemory")
    return _session_store


def get_audit_store() -> AuditStore:
    """Get the AuditStore instance.

    Returns:
        AuditStore for turn records and audit events
    """
    global _audit_store
    if _audit_store is None:
        # TODO: Use production store based on settings
        _audit_store = InMemoryAuditStore()
        logger.info("audit_store_initialized", store_type="inmemory")
    return _audit_store


def get_llm_provider(
    _settings: Annotated[Settings, Depends(get_settings)],
) -> LLMProvider:
    """Get the LLMProvider instance.

    Args:
        _settings: Application settings (unused, for future provider selection)

    Returns:
        LLMProvider for text generation
    """
    # Import here to avoid circular imports and defer provider loading
    from soldier.providers.llm.mock import MockLLMProvider

    # TODO: Create provider based on settings.providers.llm configuration
    # For now, use mock provider
    return MockLLMProvider(default_response="Mock response")


def get_embedding_provider(
    _settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProvider:
    """Get the EmbeddingProvider instance.

    Args:
        settings: Application settings

    Returns:
        EmbeddingProvider for vector embeddings
    """
    # Import here to avoid circular imports
    from soldier.providers.embedding.mock import MockEmbeddingProvider

    # TODO: Create provider based on settings.providers.embedding configuration
    return MockEmbeddingProvider(dimensions=1536)


def get_alignment_engine(
    config_store: Annotated[ConfigStore, Depends(get_config_store)],
    session_store: Annotated[SessionStore, Depends(get_session_store)],
    audit_store: Annotated[AuditStore, Depends(get_audit_store)],
    llm_provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AlignmentEngine:
    """Get the AlignmentEngine instance.

    Creates the alignment engine with all required dependencies.

    Args:
        config_store: Store for configuration
        session_store: Store for sessions
        audit_store: Store for audit records
        llm_provider: LLM provider
        embedding_provider: Embedding provider
        settings: Application settings

    Returns:
        AlignmentEngine for processing turns
    """
    global _alignment_engine
    if _alignment_engine is None:
        _alignment_engine = AlignmentEngine(
            config_store=config_store,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            session_store=session_store,
            audit_store=audit_store,
            pipeline_config=settings.pipeline,
        )
        logger.info("alignment_engine_initialized")
    return _alignment_engine


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
ConfigStoreDep = Annotated[ConfigStore, Depends(get_config_store)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
AuditStoreDep = Annotated[AuditStore, Depends(get_audit_store)]
AlignmentEngineDep = Annotated[AlignmentEngine, Depends(get_alignment_engine)]


def reset_dependencies() -> None:
    """Reset all cached dependencies.

    Used for testing to ensure fresh instances.
    """
    global _config_store, _session_store, _audit_store, _alignment_engine
    _config_store = None
    _session_store = None
    _audit_store = None
    _alignment_engine = None
    get_settings.cache_clear()
