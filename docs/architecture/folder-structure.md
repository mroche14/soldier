# Folder Architecture

A human-readable guide to Soldier's codebase organization.

## Philosophy

```
Code follows concepts, not technical layers.

Ask: "Where would I look for X?"
Answer: In the folder named after X.
```

## Top-Level Structure

```
soldier/
├── config/                  # TOML configuration files (per environment)
│   ├── default.toml        # Base defaults (committed)
│   ├── development.toml    # Local development overrides
│   ├── staging.toml        # Staging environment
│   ├── production.toml     # Production environment
│   └── test.toml           # Test environment
│
├── soldier/                 # Main Python package
│   ├── alignment/          # The brain: rules, scenarios, context
│   ├── memory/             # Long-term memory: episodes, entities
│   ├── conversation/       # Live conversation state
│   ├── audit/              # What happened: turns, logs
│   ├── observability/      # Logging, tracing, metrics
│   ├── providers/          # External services: LLMs, embeddings
│   ├── api/                # HTTP/gRPC interfaces
│   └── config/             # Configuration loading (Pydantic models)
│
├── tests/                   # Mirrors soldier/ structure
├── docs/                    # Documentation
└── deploy/                  # Kubernetes, Docker, etc.
```

---

## Core Domains

### `soldier/alignment/` — The Brain

**Purpose**: Determines what the agent should do on each turn.

```
alignment/
├── __init__.py
├── engine.py               # Main AlignmentEngine class
│
├── context/                # Step 1-2: Understand the message
│   ├── __init__.py
│   ├── extractor.py        # ContextExtractor interface + implementations
│   ├── models.py           # Context, UserIntent, ExtractedEntities
│   └── prompts/            # Prompt templates for context extraction
│       └── extract_intent.txt
│
├── retrieval/              # Step 3: Find relevant rules/scenarios
│   ├── __init__.py
│   ├── rule_retriever.py   # RuleRetriever: vector search + filters
│   ├── scenario_retriever.py
│   └── reranker.py         # Reranking strategies
│
├── filtering/              # Step 4: LLM judges relevance
│   ├── __init__.py
│   ├── rule_filter.py      # LLM-based rule filtering
│   ├── scenario_filter.py  # Scenario start/continue/exit decisions
│   └── prompts/
│       ├── filter_rules.txt
│       └── evaluate_scenario.txt
│
├── execution/              # Step 5: Run tools
│   ├── __init__.py
│   ├── tool_executor.py    # Execute tools from matched rules
│   └── variable_resolver.py
│
├── generation/             # Step 6: Generate response
│   ├── __init__.py
│   ├── prompt_builder.py   # Assemble final prompt
│   ├── generator.py        # ResponseGenerator
│   └── prompts/
│       └── system_prompt.txt
│
├── enforcement/            # Step 7: Validate response
│   ├── __init__.py
│   ├── validator.py        # Check against hard constraints
│   └── fallback.py         # Template fallback logic
│
└── models/                 # Domain models for alignment
    ├── __init__.py
    ├── rule.py             # Rule, MatchedRule
    ├── scenario.py         # Scenario, ScenarioStep, StepTransition
    ├── template.py         # Template, TemplateMode
    └── variable.py         # Variable, VariableUpdatePolicy
```

**Key Classes**:
```python
# alignment/engine.py
class AlignmentEngine:
    """Orchestrates the full alignment flow."""

    def __init__(
        self,
        context_extractor: ContextExtractor,
        rule_retriever: RuleRetriever,
        scenario_retriever: ScenarioRetriever,
        rule_filter: RuleFilter,
        scenario_filter: ScenarioFilter,
        tool_executor: ToolExecutor,
        response_generator: ResponseGenerator,
        enforcement: EnforcementValidator,
    ): ...

    async def process_turn(
        self,
        message: str,
        conversation: Conversation,
        config: AgentConfig,
    ) -> AlignmentResult: ...
```

---

### `soldier/memory/` — Long-term Memory

**Purpose**: Stores and retrieves episodic memory (what happened) and semantic knowledge (entities, relationships).

```
memory/
├── __init__.py
├── models/                 # Domain models
│   ├── __init__.py
│   ├── episode.py          # Episode (atomic memory unit)
│   ├── entity.py           # Entity (person, order, product)
│   └── relationship.py     # Relationship (edges between entities)
│
├── store.py                # MemoryStore interface
│
├── stores/                 # Implementations
│   ├── __init__.py
│   ├── neo4j.py            # Neo4jMemoryStore
│   ├── postgres.py         # PostgresMemoryStore (pgvector)
│   ├── mongodb.py          # MongoDBMemoryStore (Atlas)
│   └── inmemory.py         # InMemoryMemoryStore (testing)
│
├── ingestion/              # Adding to memory
│   ├── __init__.py
│   ├── ingestor.py         # MemoryIngestor
│   ├── entity_extractor.py # Extract entities from text
│   └── summarizer.py       # Summarize long conversations
│
└── retrieval/              # Searching memory
    ├── __init__.py
    ├── retriever.py        # MemoryRetriever (hybrid search)
    └── reranker.py         # Memory-specific reranking
```

---

### `soldier/conversation/` — Live State

**Purpose**: Manages active conversation state (sessions).

```
conversation/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── session.py          # Session (active conversation)
│   └── turn.py             # Turn (single exchange)
│
├── store.py                # SessionStore interface
│
└── stores/
    ├── __init__.py
    ├── redis.py            # RedisSessionStore
    ├── mongodb.py          # MongoDBSessionStore
    ├── dynamodb.py         # DynamoDBSessionStore
    └── inmemory.py         # InMemorySessionStore (testing)
```

---

### `soldier/audit/` — What Happened

**Purpose**: Immutable record of all interactions for compliance and debugging.

```
audit/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── turn_record.py      # Full turn with all metadata
│   └── event.py            # System events (tool calls, errors)
│
├── store.py                # AuditStore interface
│
└── stores/
    ├── __init__.py
    ├── postgres.py         # PostgresAuditStore
    ├── timescale.py        # TimescaleAuditStore
    ├── mongodb.py          # MongoDBAuditStore
    ├── clickhouse.py       # ClickHouseAuditStore
    └── inmemory.py         # InMemoryAuditStore (testing)
```

---

### `soldier/observability/` — Logging, Tracing, Metrics

**Purpose**: Structured logging, distributed tracing, and Prometheus metrics. See [observability.md](./observability.md) for full architecture.

```
observability/
├── __init__.py
├── logging.py              # structlog setup, JSON/console formatters
├── tracing.py              # OpenTelemetry setup, span helpers
├── metrics.py              # Prometheus counters, histograms, gauges
└── middleware.py           # Request context binding for FastAPI
```

**Key Functions**:
```python
# observability/logging.py
def setup_logging(level: str, format: str, include_trace_id: bool) -> None:
    """Configure structured logging for Soldier."""

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name."""


# observability/tracing.py
def setup_tracing(service_name: str, otlp_endpoint: str | None) -> None:
    """Setup OpenTelemetry tracing."""


# observability/middleware.py
async def logging_context_middleware(request: Request, call_next):
    """Bind tenant_id, agent_id, session_id, trace_id to all logs."""
```

**Note**: Soldier integrates with kernel_agent's existing OpenTelemetry Collector and Prometheus setup. Logs go to stdout (JSON), traces to OTLP, metrics scraped at `/metrics`.

---

### `soldier/providers/` — External Services

**Purpose**: Interfaces for LLMs, embeddings, and other external services. Each step in the pipeline can use a different provider.

```
providers/
├── __init__.py
│
├── llm/                    # Large Language Models
│   ├── __init__.py
│   ├── base.py             # LLMProvider interface
│   ├── anthropic.py        # AnthropicProvider (Claude)
│   ├── openai.py           # OpenAIProvider (GPT-4, etc.)
│   ├── bedrock.py          # AWSBedrockProvider
│   ├── vertex.py           # GoogleVertexProvider
│   ├── ollama.py           # OllamaProvider (local)
│   └── mock.py             # MockProvider (testing)
│
├── embedding/              # Embedding Models
│   ├── __init__.py
│   ├── base.py             # EmbeddingProvider interface
│   ├── openai.py           # OpenAIEmbeddings
│   ├── cohere.py           # CohereEmbeddings
│   ├── voyage.py           # VoyageEmbeddings
│   ├── sentence_transformers.py  # Local SentenceTransformers
│   └── mock.py             # MockEmbeddings (testing)
│
└── rerank/                 # Reranking Models
    ├── __init__.py
    ├── base.py             # RerankProvider interface
    ├── cohere.py           # CohereRerank
    ├── voyage.py           # VoyageRerank
    └── cross_encoder.py    # Local CrossEncoder
```

**Key Interfaces**:
```python
# providers/llm/base.py
class LLMProvider(ABC):
    """Interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel: ...


# providers/embedding/base.py
class EmbeddingProvider(ABC):
    """Interface for embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

---

### `soldier/config/` — Configuration Loading

**Purpose**: Load TOML configuration files with Pydantic validation. See [configuration.md](./configuration.md) for full details.

```
config/
├── __init__.py
├── loader.py               # TOML loader + environment resolution
├── settings.py             # Root Settings class (Pydantic)
│
└── models/                 # Pydantic models for each config section
    ├── __init__.py
    ├── api.py              # APIConfig (host, port, CORS, rate limits)
    ├── pipeline.py         # PipelineConfig (each step's settings)
    ├── providers.py        # LLM, Embedding, Rerank provider configs
    ├── selection.py        # Selection strategy configs (elbow, adaptive_k, etc.)
    ├── storage.py          # Store backend configs (Postgres, Redis, etc.)
    ├── observability.py    # ObservabilityConfig (logging, tracing, metrics)
    └── agent.py            # Per-agent configuration overrides
```

**Key Principle**: No hardcoded values in code. All configurable values have:
1. **Defaults** in Pydantic models
2. **Base config** in `config/default.toml`
3. **Environment overrides** in `config/{env}.toml`
4. **Runtime overrides** via `SOLDIER_*` environment variables

```python
# Usage
from soldier.config.settings import get_settings

settings = get_settings()
port = settings.api.port
llm_model = settings.providers.default_llm.model
rule_strategy = settings.pipeline.retrieval.rule_selection.strategy
```

---

### `soldier/api/` — External Interfaces

**Purpose**: HTTP and gRPC APIs.

```
api/
├── __init__.py
├── app.py                  # FastAPI app factory
│
├── routes/
│   ├── __init__.py
│   ├── chat.py             # POST /v1/chat
│   ├── sessions.py         # Session CRUD
│   ├── config.py           # Rules, Scenarios, Templates CRUD
│   └── health.py           # Health checks
│
├── grpc/
│   ├── __init__.py
│   ├── server.py           # gRPC server
│   └── protos/             # .proto files
│
├── middleware/
│   ├── __init__.py
│   ├── auth.py             # JWT validation, tenant extraction
│   └── rate_limit.py       # Per-tenant rate limiting
│
└── models/                 # API request/response models
    ├── __init__.py
    ├── chat.py             # ChatRequest, ChatResponse
    └── errors.py           # Error responses
```

---

## Configuration: Pipeline Steps

Each step in the alignment pipeline can be configured via TOML files with Pydantic validation. See [configuration.md](./configuration.md) for full details.

```toml
# config/default.toml
[pipeline.context_extraction]
enabled = true
mode = "llm"
llm_provider = "haiku"           # References providers.llm.haiku
history_turns = 5

[pipeline.retrieval]
embedding_provider = "default"
max_k = 30

# Selection strategies are configurable per retrieval type
[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"          # elbow | adaptive_k | entropy | clustering | fixed_k
alpha = 1.5
min_score = 0.5

[pipeline.retrieval.scenario_selection]
strategy = "entropy"
low_entropy_k = 1
medium_entropy_k = 2
high_entropy_k = 3

[pipeline.retrieval.memory_selection]
strategy = "clustering"
eps = 0.1
top_per_cluster = 3

[pipeline.reranking]
enabled = true
rerank_provider = "default"
top_k = 10

[pipeline.llm_filtering]
enabled = true
llm_provider = "haiku"

[pipeline.generation]
llm_provider = "sonnet"          # References providers.llm.sonnet
temperature = 0.7
max_tokens = 1024

[pipeline.enforcement]
self_critique_enabled = false

# Named provider configurations
[providers.llm.haiku]
provider = "anthropic"
model = "claude-3-haiku-20240307"

[providers.llm.sonnet]
provider = "anthropic"
model = "claude-sonnet-4-5-20250514"

# Storage backends
[storage.config]
backend = "postgres"             # postgres | mongodb | inmemory

[storage.memory]
backend = "postgres"             # postgres | neo4j | mongodb | inmemory

[storage.session]
backend = "redis"                # redis | mongodb | dynamodb | inmemory

[storage.audit]
backend = "postgres"             # postgres | timescale | clickhouse | mongodb | inmemory
```

Environment-specific overrides in `config/production.toml`, `config/development.toml`, etc.

---

## Data Flow Visualization

```
                                    ┌─────────────────────────────────────┐
                                    │           PROVIDERS                  │
                                    │  ┌─────────┐ ┌─────────┐ ┌────────┐ │
                                    │  │ LLM     │ │Embedding│ │Rerank  │ │
                                    │  │Anthropic│ │ OpenAI  │ │ Cohere │ │
                                    │  │ OpenAI  │ │ Cohere  │ │ Voyage │ │
                                    │  │ Bedrock │ │ Voyage  │ │        │ │
                                    │  └────┬────┘ └────┬────┘ └───┬────┘ │
                                    └───────┼──────────┼──────────┼──────┘
                                            │          │          │
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ALIGNMENT ENGINE                                 │
│                                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │  Context    │    │  Retrieval  │    │    LLM      │    │  Response   │   │
│  │ Extraction  │───▶│   + Rerank  │───▶│  Filtering  │───▶│ Generation  │   │
│  │             │    │             │    │             │    │             │   │
│  │ (LLM/Embed) │    │(Embed+Store)│    │   (LLM)     │    │   (LLM)     │   │
│  └─────────────┘    └──────┬──────┘    └─────────────┘    └─────────────┘   │
│                            │                                                  │
│                            ▼                                                  │
│                    ┌───────────────┐                                         │
│                    │  ConfigStore  │  Rules, Scenarios, Templates            │
│                    └───────────────┘                                         │
└──────────────────────────────────────────────────────────────────────────────┘
         │                                                           │
         ▼                                                           ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  MemoryStore    │  │  SessionStore   │  │   AuditStore    │  │  ConfigStore    │
│                 │  │                 │  │                 │  │                 │
│ Episodes        │  │ Sessions        │  │ Turn records    │  │ Rules           │
│ Entities        │  │ Active step     │  │ Events          │  │ Scenarios       │
│ Relationships   │  │ Variables       │  │ Metrics         │  │ Templates       │
│                 │  │                 │  │                 │  │ Variables       │
│ Neo4j/Postgres  │  │ Redis/MongoDB   │  │ Postgres/       │  │ Postgres/       │
│ /MongoDB        │  │ /DynamoDB       │  │ Timescale       │  │ MongoDB         │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Quick Reference: "Where do I find...?"

| Looking for... | Location |
|----------------|----------|
| Rule matching logic | `soldier/alignment/retrieval/rule_retriever.py` |
| Scenario state machine | `soldier/alignment/models/scenario.py` |
| Context extraction prompts | `soldier/alignment/context/prompts/` |
| Add a new LLM provider | `soldier/providers/llm/` |
| Add a new embedding provider | `soldier/providers/embedding/` |
| Memory storage implementations | `soldier/memory/stores/` |
| Session management | `soldier/conversation/` |
| API endpoints | `soldier/api/routes/` |
| Domain models for rules | `soldier/alignment/models/rule.py` |
| Pipeline configuration | `soldier/config/models/pipeline.py` |
| Logging setup | `soldier/observability/logging.py` |
| Tracing setup | `soldier/observability/tracing.py` |
| Metrics definitions | `soldier/observability/metrics.py` |

---

## Testing Structure

```
tests/
├── unit/                   # Fast, isolated tests
│   ├── alignment/
│   │   ├── test_context_extractor.py
│   │   ├── test_rule_retriever.py
│   │   └── test_enforcement.py
│   ├── memory/
│   ├── conversation/
│   └── providers/
│
├── integration/            # Tests with real backends
│   ├── stores/
│   │   ├── test_postgres_memory.py
│   │   ├── test_redis_session.py
│   │   └── test_neo4j_memory.py
│   └── providers/
│       ├── test_anthropic.py
│       └── test_openai.py
│
└── e2e/                    # Full pipeline tests
    ├── test_chat_flow.py
    └── test_scenario_flow.py
```

---

## Summary: 4 Stores + Providers

**Stores** (where data lives):
1. **MemoryStore** — Long-term memory (episodes, entities)
2. **ConfigStore** — Agent behavior (rules, scenarios, templates)
3. **SessionStore** — Live session state
4. **AuditStore** — Immutable history

**Providers** (external services):
1. **LLMProvider** — Text generation (Anthropic, OpenAI, Bedrock, etc.)
2. **EmbeddingProvider** — Vector embeddings (OpenAI, Cohere, Voyage, etc.)
3. **RerankProvider** — Result reranking (Cohere, Voyage, CrossEncoder)

Each pipeline step can use different providers, configured per-agent.
