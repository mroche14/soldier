# ADR-001: Storage and Provider Architecture

**Status**: Proposed
**Date**: 2025-01-15
**Deciders**: [Team]

## Context

Soldier needs:
1. **Storage** for data persistence (config, sessions, memory, audit)
2. **Providers** for AI capabilities (LLMs, embeddings, reranking)

Both must be pluggable to support different backends and services.

## Decision

### Storage: 4 Domain-Aligned Stores

Each store corresponds to a clear conceptual domain:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STORAGE INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ConfigStore                                                        │    │
│  │  "How should the agent behave?"                                     │    │
│  │                                                                      │    │
│  │  Contents: Rules, Scenarios, Templates, Variables, Agent settings   │    │
│  │  Pattern: Read-heavy, write-rarely, versioned                       │    │
│  │  Backends: PostgreSQL, MongoDB, MySQL                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  MemoryStore                                                        │    │
│  │  "What does the agent remember?"                                    │    │
│  │                                                                      │    │
│  │  Contents: Episodes, Entities, Relationships (knowledge graph)      │    │
│  │  Pattern: Append-heavy, semantic search, graph traversal            │    │
│  │  Backends: Neo4j, PostgreSQL+pgvector, MongoDB+Atlas, FalkorDB     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SessionStore                                                       │    │
│  │  "What's happening right now?"                                      │    │
│  │                                                                      │    │
│  │  Contents: Sessions (active step, variables, rule fires)            │    │
│  │  Pattern: Two-tier (cache + persistent), per-session isolation      │    │
│  │  Cache: Redis (TTL=1h)  |  Persistent: PostgreSQL, MongoDB          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  AuditStore                                                         │    │
│  │  "What happened?"                                                   │    │
│  │                                                                      │    │
│  │  Contents: Turn records, tool calls, enforcement events             │    │
│  │  Pattern: Append-only, time-series queries, compliance              │    │
│  │  Backends: PostgreSQL, TimescaleDB, MongoDB, ClickHouse             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Providers: 3 AI Capability Interfaces

Each provider corresponds to a type of AI capability:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROVIDER INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LLMProvider                                                        │    │
│  │  "Generate text responses"                                          │    │
│  │                                                                      │    │
│  │  Used by: Context extraction, LLM filtering, Response generation,   │    │
│  │           Enforcement (self-critique)                               │    │
│  │  Backends: Anthropic, OpenAI, Bedrock, Vertex, Ollama               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  EmbeddingProvider                                                  │    │
│  │  "Convert text to vectors"                                          │    │
│  │                                                                      │    │
│  │  Used by: Rule retrieval, Scenario matching, Memory search          │    │
│  │  Backends: OpenAI, Cohere, Voyage, SentenceTransformers             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  RerankProvider                                                     │    │
│  │  "Re-order search results by relevance"                             │    │
│  │                                                                      │    │
│  │  Used by: Reranking step (optional)                                 │    │
│  │  Backends: Cohere, Voyage, CrossEncoder (local)                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Store Interfaces

### ConfigStore

```python
class ConfigStore(ABC):
    """
    Storage for agent configuration: rules, scenarios, templates, variables.

    This is the source of truth for "how the agent should behave".
    """

    # ─── Rules ───────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_rules(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        scope: str | None = None,
        scope_id: UUID | None = None,
        enabled_only: bool = True,
    ) -> list[Rule]:
        """Get rules for an agent, optionally filtered by scope."""
        pass

    @abstractmethod
    async def get_rule(self, rule_id: UUID) -> Rule | None:
        """Get a single rule by ID."""
        pass

    @abstractmethod
    async def save_rule(self, rule: Rule) -> UUID:
        """Create or update a rule. Returns rule ID."""
        pass

    @abstractmethod
    async def delete_rule(self, rule_id: UUID) -> bool:
        """Delete a rule. Returns True if existed."""
        pass

    @abstractmethod
    async def vector_search_rules(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        scope: str | None = None,
        scope_id: UUID | None = None,
        limit: int = 10,
    ) -> list[Rule]:
        """Find rules by vector similarity."""
        pass

    # ─── Scenarios ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_scenarios(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        enabled_only: bool = True,
    ) -> list[Scenario]:
        """Get all scenarios for an agent."""
        pass

    @abstractmethod
    async def get_scenario(self, scenario_id: UUID) -> Scenario | None:
        """Get a scenario with its states."""
        pass

    @abstractmethod
    async def save_scenario(self, scenario: Scenario) -> UUID:
        """Create or update a scenario."""
        pass

    @abstractmethod
    async def delete_scenario(self, scenario_id: UUID) -> bool:
        """Delete a scenario."""
        pass

    # ─── Templates ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_templates(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        scope: str | None = None,
        scope_id: UUID | None = None,
    ) -> list[Template]:
        """Get templates for an agent."""
        pass

    @abstractmethod
    async def save_template(self, template: Template) -> UUID:
        """Create or update a template."""
        pass

    # ─── Variables ───────────────────────────────────────────────────────────

    @abstractmethod
    async def get_variables(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[Variable]:
        """Get variable definitions for an agent."""
        pass

    # ─── Agent Config ────────────────────────────────────────────────────────

    @abstractmethod
    async def get_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentConfig | None:
        """Get agent configuration including pipeline settings."""
        pass

    @abstractmethod
    async def save_agent(self, agent: AgentConfig) -> UUID:
        """Create or update agent configuration."""
        pass
```

**Implementations**:

| Backend | Vector Support | Best For |
|---------|----------------|----------|
| `PostgresConfigStore` | pgvector | ACID, mature tooling |
| `MongoDBConfigStore` | Atlas Vector Search | Flexible schema |
| `MySQLConfigStore` | External (Milvus) | Existing MySQL |
| `InMemoryConfigStore` | Linear scan | Testing |

---

### MemoryStore

```python
class MemoryStore(ABC):
    """
    Storage for long-term memory: episodes, entities, relationships.

    This is the agent's "knowledge graph" - what it remembers from conversations.
    """

    # ─── Episodes ────────────────────────────────────────────────────────────

    @abstractmethod
    async def add_episode(self, episode: Episode) -> UUID:
        """Store an episode. Embedding computed if not provided."""
        pass

    @abstractmethod
    async def get_episode(self, episode_id: UUID) -> Episode | None:
        """Get an episode by ID."""
        pass

    @abstractmethod
    async def vector_search_episodes(
        self,
        query_embedding: list[float],
        group_id: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Find episodes by vector similarity within a group."""
        pass

    @abstractmethod
    async def text_search_episodes(
        self,
        query: str,
        group_id: str,
        limit: int = 10,
    ) -> list[Episode]:
        """Find episodes by full-text search (BM25)."""
        pass

    # ─── Entities ────────────────────────────────────────────────────────────

    @abstractmethod
    async def add_entity(self, entity: Entity) -> UUID:
        """Store an entity node."""
        pass

    @abstractmethod
    async def get_entities(
        self,
        group_id: str,
        entity_type: str | None = None,
    ) -> list[Entity]:
        """Get entities in a group, optionally filtered by type."""
        pass

    # ─── Relationships ───────────────────────────────────────────────────────

    @abstractmethod
    async def add_relationship(self, relationship: Relationship) -> UUID:
        """Store a relationship between entities."""
        pass

    @abstractmethod
    async def traverse_from_entities(
        self,
        entity_ids: list[UUID],
        group_id: str,
        depth: int = 2,
    ) -> list[dict]:
        """Traverse graph from entities to find related context."""
        pass

    # ─── Cleanup ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def delete_by_group(self, group_id: str) -> int:
        """Delete all data for a group. Returns count deleted."""
        pass
```

**Implementations**:

| Backend | Graph Traversal | Vector Search | Best For |
|---------|-----------------|---------------|----------|
| `Neo4jMemoryStore` | Native Cypher | HNSW | Complex traversals |
| `PostgresMemoryStore` | CTEs/recursive | pgvector | Simple deployments |
| `MongoDBMemoryStore` | $graphLookup | Atlas Vector | Document-centric |
| `FalkorDBMemoryStore` | Native | Built-in | Low-latency |
| `InMemoryMemoryStore` | Dict-based | Linear | Testing |

---

### SessionStore

```python
class SessionStore(ABC):
    """
    Two-tier storage for conversation state.

    - Cache (Redis): Fast access, TTL-based (default 1 hour)
    - Persistent (PostgreSQL/MongoDB): Long-term storage

    On cache miss, session is loaded from persistent and re-cached.
    """

    @abstractmethod
    async def get(self, session_id: str) -> Session | None:
        """Get session (cache first, then persistent)."""
        pass

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Save to both cache and persistent store."""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete from both cache and persistent."""
        pass

    @abstractmethod
    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 100,
    ) -> list[Session]:
        """List sessions for an agent (from persistent store)."""
        pass
```

**Two-Tier Architecture**:

| Tier | Backend | TTL | Purpose |
|------|---------|-----|---------|
| Cache | Redis | 1 hour | Fast read/write during active conversation |
| Persistent | PostgreSQL or MongoDB | None | Long-term storage, survives cache eviction |

Flow:
1. `get()`: Check Redis → if miss, load from PostgreSQL → cache in Redis
2. `save()`: Write to Redis (with TTL) AND PostgreSQL
3. User returns after 2 hours → cache miss → reload from PostgreSQL

---

### AuditStore

```python
class AuditStore(ABC):
    """
    Storage for audit trail: turn records, events, metrics.

    This is "what happened" - append-only, immutable, for compliance.
    """

    @abstractmethod
    async def save_turn(self, turn: TurnRecord) -> None:
        """Save a turn record."""
        pass

    @abstractmethod
    async def get_turn(self, turn_id: UUID) -> TurnRecord | None:
        """Get a turn by ID."""
        pass

    @abstractmethod
    async def list_turns_by_session(
        self,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TurnRecord]:
        """List turns for a session."""
        pass

    @abstractmethod
    async def list_turns_by_tenant(
        self,
        tenant_id: UUID,
        filters: TurnFilters | None = None,
        limit: int = 100,
    ) -> list[TurnRecord]:
        """List turns for a tenant with optional filters."""
        pass

    @abstractmethod
    async def save_event(self, event: AuditEvent) -> None:
        """Save an audit event (tool call, error, etc.)."""
        pass
```

**Implementations**:

| Backend | Time-Series | Best For |
|---------|-------------|----------|
| `PostgresAuditStore` | BRIN indexes | General purpose |
| `TimescaleAuditStore` | Hypertables | Time-series native |
| `MongoDBAuditStore` | Time indexes | Document storage |
| `ClickHouseAuditStore` | MergeTree | High-volume analytics |
| `InMemoryAuditStore` | List | Testing |

---

## Provider Interfaces

### LLMProvider

```python
class LLMProvider(ABC):
    """
    Interface for Large Language Model providers.

    Used for: context extraction, LLM filtering, response generation, self-critique.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'anthropic', 'openai')."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Generate text completion."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        """Generate structured output matching a Pydantic schema."""
        pass


class LLMResponse(BaseModel):
    """Response from LLM generation."""
    text: str
    usage: TokenUsage
    model: str
    finish_reason: str


class TokenUsage(BaseModel):
    """Token usage for a generation."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

**Implementations**:

| Provider | Models | Best For |
|----------|--------|----------|
| `AnthropicProvider` | claude-3-haiku, claude-sonnet-4-5-20250514, claude-opus-4 | Best quality |
| `OpenAIProvider` | gpt-4o, gpt-4o-mini | Alternative |
| `BedrockProvider` | Various | AWS integration |
| `VertexProvider` | Gemini | Google Cloud |
| `OllamaProvider` | Llama, Mistral | Local/self-hosted |
| `MockLLMProvider` | - | Testing |

---

### EmbeddingProvider

```python
class EmbeddingProvider(ABC):
    """
    Interface for embedding models.

    Used for: rule retrieval, scenario matching, memory search.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimensions for this model."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        pass

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        pass
```

**Implementations**:

| Provider | Models | Dimensions | Best For |
|----------|--------|------------|----------|
| `OpenAIEmbeddings` | text-embedding-3-small/large | 1536/3072 | General |
| `CohereEmbeddings` | embed-english-v3.0 | 1024 | Multilingual |
| `VoyageEmbeddings` | voyage-large-2 | 1024 | Retrieval |
| `SentenceTransformers` | all-MiniLM-L6-v2 | 384 | Local, fast |
| `MockEmbeddings` | - | 384 | Testing |

---

### RerankProvider

```python
class RerankProvider(ABC):
    """
    Interface for reranking models.

    Used for: improving retrieval quality after initial vector search.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """
        Rerank documents by relevance to query.

        Returns results sorted by relevance score (highest first).
        """
        pass


class RerankResult(BaseModel):
    """Result from reranking."""
    index: int          # Original index in documents list
    score: float        # Relevance score (0-1)
    document: str       # The document text
```

**Implementations**:

| Provider | Models | Best For |
|----------|--------|----------|
| `CohereRerank` | rerank-english-v3.0 | General |
| `VoyageRerank` | rerank-1 | Technical |
| `CrossEncoderRerank` | ms-marco-MiniLM | Local |
| `MockRerank` | - | Testing |

---

## Configuration

### Full Configuration Example

```toml
# config.toml

# ─── Storage ─────────────────────────────────────────────────────────────────

[storage.config]
backend = "postgres"

[storage.config.connection]
host = "${POSTGRES_HOST}"
port = 5432
database = "soldier"
username = "${POSTGRES_USER}"
password = "${POSTGRES_PASSWORD}"

[storage.memory]
backend = "postgres"  # Or "neo4j" for complex graph needs

[storage.memory.connection]
# Same as config, or separate DB
host = "${POSTGRES_HOST}"

[storage.session]
backend = "redis"
ttl_days = 30

[storage.session.connection]
url = "redis://${REDIS_HOST}:6379"

[storage.audit]
backend = "postgres"

[storage.audit.connection]
host = "${POSTGRES_HOST}"

# ─── Providers ───────────────────────────────────────────────────────────────

[providers.llm.anthropic]
api_key = "${ANTHROPIC_API_KEY}"

[providers.llm.openai]
api_key = "${OPENAI_API_KEY}"

[providers.embedding.openai]
api_key = "${OPENAI_API_KEY}"

[providers.embedding.sentence_transformers]
model = "all-MiniLM-L6-v2"

[providers.rerank.cohere]
api_key = "${COHERE_API_KEY}"

# ─── Pipeline (per-step configuration) ───────────────────────────────────────

[pipeline.context_extraction]
mode = "llm"
llm_provider = "anthropic"
llm_model = "claude-3-haiku"

[pipeline.retrieval]
embedding_provider = "openai"
embedding_model = "text-embedding-3-small"
top_k = 20

[pipeline.reranking]
enabled = true
rerank_provider = "cohere"
rerank_model = "rerank-english-v3.0"
top_k = 10

[pipeline.llm_filtering]
enabled = true
llm_provider = "anthropic"
llm_model = "claude-3-haiku"

[pipeline.generation]
llm_provider = "anthropic"
llm_model = "claude-sonnet-4-5-20250514"
temperature = 0.7
max_tokens = 1024

[pipeline.enforcement]
self_critique_enabled = false
```

### Deployment Profiles

**Development / Testing**
```toml
[storage]
config = { backend = "inmemory" }
memory = { backend = "inmemory" }
session = { backend = "inmemory" }
audit = { backend = "inmemory" }

[providers]
llm = { mock = {} }
embedding = { mock = {} }
```

**Simple Production**
```toml
[storage]
config = { backend = "postgres" }
memory = { backend = "postgres" }      # pgvector
session = { backend = "redis" }
audit = { backend = "postgres" }
```

**Scaled Production**
```toml
[storage]
config = { backend = "postgres" }
memory = { backend = "neo4j" }         # Dedicated graph DB
session = { backend = "redis" }
audit = { backend = "timescale" }      # Time-series optimized
```

---

## Consequences

### Positive

- **Clear mental model**: 4 stores map to 4 questions (behavior, memory, now, history)
- **Flexibility**: Swap backends without code changes
- **Testability**: In-memory implementations for fast tests
- **Per-step providers**: Each pipeline step can use optimal model

### Negative

- **Multiple implementations**: Need to maintain several backends
- **Integration testing**: Need tests for each backend
- **Configuration complexity**: More options to configure

### Mitigations

- Provide well-tested reference implementations (Postgres + Redis)
- Document recommended configurations per scale
- Include integration test suite

---

## References

- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Anthropic API](https://docs.anthropic.com/)
- [OpenAI API](https://platform.openai.com/docs/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Neo4j](https://neo4j.com/docs/)
