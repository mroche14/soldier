"""Storage interfaces and implementations.

Four domain-aligned stores:
- ConfigStore: How should it behave? (rules, scenarios, templates, variables)
- MemoryStore: What does it remember? (episodes, entities, relationships)
- SessionStore: What's happening now? (session state, active step, variables)
- AuditStore: What happened? (turn records, events - immutable)

Plus supporting stores:
- InterlocutorDataStore: Customer/user data and profiles
- VectorStore: Embedding vectors for similarity search
"""

# Config Store
from focal.infrastructure.stores.config import (
    ConfigStore,
    InMemoryConfigStore,
    PostgresConfigStore,
)

# Session Store
from focal.infrastructure.stores.session import (
    InMemorySessionStore,
    RedisSessionStore,
    SessionStore,
)

# Interlocutor Data Store
from focal.infrastructure.stores.interlocutor import (
    CachedInterlocutorDataStore,
    InMemoryInterlocutorDataStore,
    InterlocutorDataStore,
    PostgresInterlocutorDataStore,
)

# Memory Store
from focal.infrastructure.stores.memory import (
    InMemoryMemoryStore,
    MemoryStore,
    PostgresMemoryStore,
)

# Audit Store
from focal.infrastructure.stores.audit import (
    AuditStore,
    InMemoryAuditStore,
    PostgresAuditStore,
)

# Vector Store
from focal.infrastructure.stores.vector import (
    EntityType,
    InMemoryVectorStore,
    PgVectorStore,
    QdrantVectorStore,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)

__all__ = [
    # Config Store
    "ConfigStore",
    "InMemoryConfigStore",
    "PostgresConfigStore",
    # Session Store
    "SessionStore",
    "InMemorySessionStore",
    "RedisSessionStore",
    # Interlocutor Data Store
    "InterlocutorDataStore",
    "InMemoryInterlocutorDataStore",
    "PostgresInterlocutorDataStore",
    "CachedInterlocutorDataStore",
    # Memory Store
    "MemoryStore",
    "InMemoryMemoryStore",
    "PostgresMemoryStore",
    # Audit Store
    "AuditStore",
    "InMemoryAuditStore",
    "PostgresAuditStore",
    # Vector Store
    "VectorStore",
    "VectorDocument",
    "VectorMetadata",
    "VectorSearchResult",
    "EntityType",
    "InMemoryVectorStore",
    "PgVectorStore",
    "QdrantVectorStore",
]
