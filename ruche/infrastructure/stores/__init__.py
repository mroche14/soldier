"""Storage interfaces and implementations.

Four domain-aligned stores:
- ConfigStore: How should it behave? (rules, scenarios, templates, variables)
- MemoryStore: What does it remember? (episodes, entities, relationships)
- SessionStore: What's happening now? (session state, active step, variables)
- AuditStore: What happened? (turn records, events - immutable)

Plus supporting stores:
- InterlocutorDataStore: Customer/user data and profiles
- VectorStore: Embedding vectors for similarity search

Note: Some stores have canonical locations in top-level modules:
- ruche/audit/ - AuditStore
- ruche/conversation/ - SessionStore
- ruche/vector/ - VectorStore
"""

# Config Store (canonical: infrastructure/stores/config/)
from ruche.infrastructure.stores.config import (
    ConfigStore,
    InMemoryConfigStore,
    PostgresConfigStore,
)

# Session Store (canonical: ruche/conversation/)
from ruche.conversation.stores import (
    InMemorySessionStore,
    RedisSessionStore,
    SessionStore,
)

# Interlocutor Data Store (canonical: infrastructure/stores/interlocutor/)
from ruche.infrastructure.stores.interlocutor import (
    InterlocutorDataStoreCacheLayer,
    InMemoryInterlocutorDataStore,
    InterlocutorDataStore,
    PostgresInterlocutorDataStore,
)

# Memory Store (canonical: infrastructure/stores/memory/)
from ruche.infrastructure.stores.memory import (
    InMemoryMemoryStore,
    MemoryStore,
    PostgresMemoryStore,
)

# Audit Store (canonical: ruche/audit/)
from ruche.audit.stores import (
    AuditStore,
    InMemoryAuditStore,
    PostgresAuditStore,
)

# Vector Store (canonical: ruche/vector/)
from ruche.vector import (
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
    "InterlocutorDataStoreCacheLayer",
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
