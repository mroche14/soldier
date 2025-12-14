"""Infrastructure layer for Focal.

Consolidates all infrastructure concerns in one place:
- Stores: ConfigStore, SessionStore, InterlocutorDataStore, MemoryStore, AuditStore, VectorStore
- Providers: LLM, Embedding, Rerank
- Toolbox: Tool execution and routing
- Channels: Message routing to external platforms

This layer provides the foundation for the alignment engine and API layer.
"""

# Stores
from ruche.infrastructure.stores import (
    AuditStore,
    CachedInterlocutorDataStore,
    ConfigStore,
    EntityType,
    InMemoryAuditStore,
    InMemoryConfigStore,
    InMemoryInterlocutorDataStore,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryVectorStore,
    InterlocutorDataStore,
    MemoryStore,
    PgVectorStore,
    PostgresAuditStore,
    PostgresConfigStore,
    PostgresInterlocutorDataStore,
    PostgresMemoryStore,
    QdrantVectorStore,
    RedisSessionStore,
    SessionStore,
    VectorDocument,
    VectorMetadata,
    VectorSearchResult,
    VectorStore,
)

# Providers
from ruche.infrastructure.providers import (
    EmbeddingProvider,
    JinaEmbeddingProvider,
    JinaRerankProvider,
    LLMExecutor,
    LLMProvider,
    MockEmbeddingProvider,
    MockLLMProvider,
    MockRerankProvider,
    RerankProvider,
    SentenceTransformerEmbeddingProvider,
)

# Toolbox
from ruche.infrastructure.toolbox import (
    ComposioProvider,
    HTTPProvider,
    InternalProvider,
    SideEffectPolicy,
    ToolActivation,
    ToolDefinition,
    ToolGateway,
    ToolMetadata,
    ToolResult,
    Toolbox,
)

# Channels
from ruche.infrastructure.channels import (
    AGUIWebchatAdapter,
    ChannelBinding,
    ChannelGateway,
    ChannelPolicy,
    ChannelType,
    InboundMessage,
    OutboundMessage,
    SimpleWebchatAdapter,
    SMTPEmailAdapter,
    TwilioWhatsAppAdapter,
)

__all__ = [
    # Stores - Config
    "ConfigStore",
    "InMemoryConfigStore",
    "PostgresConfigStore",
    # Stores - Session
    "SessionStore",
    "InMemorySessionStore",
    "RedisSessionStore",
    # Stores - Interlocutor
    "InterlocutorDataStore",
    "InMemoryInterlocutorDataStore",
    "PostgresInterlocutorDataStore",
    "CachedInterlocutorDataStore",
    # Stores - Memory
    "MemoryStore",
    "InMemoryMemoryStore",
    "PostgresMemoryStore",
    # Stores - Audit
    "AuditStore",
    "InMemoryAuditStore",
    "PostgresAuditStore",
    # Stores - Vector
    "VectorStore",
    "VectorDocument",
    "VectorMetadata",
    "VectorSearchResult",
    "EntityType",
    "InMemoryVectorStore",
    "PgVectorStore",
    "QdrantVectorStore",
    # Providers - LLM
    "LLMProvider",
    "LLMExecutor",
    "MockLLMProvider",
    # Providers - Embedding
    "EmbeddingProvider",
    "JinaEmbeddingProvider",
    "MockEmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    # Providers - Rerank
    "RerankProvider",
    "JinaRerankProvider",
    "MockRerankProvider",
    # Toolbox
    "Toolbox",
    "ToolGateway",
    "ToolDefinition",
    "ToolActivation",
    "ToolResult",
    "ToolMetadata",
    "SideEffectPolicy",
    "ComposioProvider",
    "HTTPProvider",
    "InternalProvider",
    # Channels
    "ChannelGateway",
    "ChannelType",
    "ChannelPolicy",
    "ChannelBinding",
    "InboundMessage",
    "OutboundMessage",
    "AGUIWebchatAdapter",
    "SimpleWebchatAdapter",
    "TwilioWhatsAppAdapter",
    "SMTPEmailAdapter",
]
