# Folder Architecture

A human-readable guide to Focal's codebase organization.

## Philosophy

```
Code follows concepts, not technical layers.

Ask: "Where would I look for X?"
Answer: In the folder named after X.
```

## Top-Level Structure

```
ruche/
├── config/                  # TOML configuration files (per environment)
│   ├── default.toml        # Base defaults (committed)
│   ├── development.toml    # Local development overrides
│   ├── staging.toml        # Staging environment
│   ├── production.toml     # Production environment
│   └── test.toml           # Test environment
│
├── ruche/                 # Main Python package
│   ├── runtime/            # Conversation runtime infrastructure
│   ├── mechanics/          # CognitivePipeline implementations
│   ├── infrastructure/     # Consolidated infrastructure layer
│   ├── domain/             # Pure domain models
│   ├── asa/                # Agent Setter Agent (meta-agent)
│   ├── api/                # External interfaces
│   ├── observability/      # Logging, tracing, metrics
│   └── config/             # Configuration loading (Pydantic models)
│
├── tests/                   # Mirrors ruche/ structure
├── docs/                    # Documentation
└── deploy/                  # Kubernetes, Docker, etc.
```

---

## Core Domains

### `ruche/runtime/` — Conversation Runtime Infrastructure

**Purpose**: Manages conversation lifecycle, concurrency, and proactive task scheduling.

```
runtime/
├── __init__.py
│
├── acf/                    # Agent Conversation Fabric
│   ├── __init__.py
│   ├── mutex.py            # Per-session turn serialization
│   ├── turns.py            # Turn queueing and execution
│   └── supersede.py        # Message supersession logic
│
├── agent/                  # AgentRuntime
│   ├── __init__.py
│   ├── runtime.py          # Main AgentRuntime class
│   ├── lifecycle.py        # Agent initialization and cleanup
│   ├── cache.py            # Config/schema caching
│   └── invalidation.py     # Cache invalidation on config changes
│
└── agenda/                 # Proactive task scheduling
    ├── __init__.py
    ├── scheduler.py        # Task scheduler (bypasses ACF mutex)
    └── tasks.py            # Proactive task definitions
```

**Key Classes**:
```python
# runtime/agent/runtime.py
class AgentRuntime:
    """Manages agent lifecycle, caching, and turn routing."""

    async def process_turn(
        self,
        turn_input: TurnInput,
    ) -> TurnResult: ...

    async def schedule_proactive_task(
        self,
        task: ProactiveTask,
    ) -> None: ...
```

---

### `ruche/brain/` — CognitivePipeline Implementations

**Purpose**: Different cognitive mechanics (FOCAL alignment, future alternatives).

```
mechanics/
├── __init__.py
├── protocol.py             # CognitivePipeline abstract interface
│
└── ruche/                  # FOCAL alignment mechanic
    ├── __init__.py
    ├── pipeline.py         # FocalCognitivePipeline (main orchestrator)
    │
    ├── phases/             # 12-phase pipeline
    │   ├── __init__.py
    │   ├── p01_identification.py      # Context loading
    │   ├── p02_situational_sensor.py  # Intent + variable extraction
    │   ├── p03_customer_data_update.py # Variable validation/update
    │   ├── p04_retrieval.py           # Candidate retrieval
    │   ├── p05_reranking.py           # Reranking
    │   ├── p06_scenario_orchestration.py # Scenario state management
    │   ├── p07_tool_execution.py      # Tool execution
    │   ├── p08_rule_filtering.py      # LLM rule filtering
    │   ├── p09_generation.py          # Response generation
    │   ├── p10_enforcement.py         # Constraint validation
    │   ├── p11_persistence.py         # State persistence
    │   └── p12_memory_ingestion.py    # Memory updates
    │
    ├── models/             # FOCAL-specific models
    │   ├── __init__.py
    │   ├── turn_context.py         # TurnContext (aggregated context)
    │   ├── turn_input.py           # TurnInput (inbound event)
    │   ├── situational_snapshot.py # Intent + candidate variables
    │   └── glossary.py             # GlossaryItem
    │
    ├── migration/          # Scenario version migration
    │   ├── __init__.py
    │   ├── planner.py      # MigrationPlanner, MigrationDeployer
    │   ├── executor.py     # MigrationExecutor (JIT reconciliation)
    │   ├── composite.py    # CompositeMapper (multi-version gaps)
    │   ├── gap_fill.py     # GapFillService (data retrieval)
    │   ├── diff.py         # Content hashing, transformation computation
    │   └── models.py       # Migration models
    │
    └── prompts/            # Jinja2 templates
        ├── situational_sensor.jinja2
        ├── rule_filter.jinja2
        ├── generation.jinja2
        └── ...
```

---

### `ruche/infrastructure/` — Consolidated Infrastructure Layer

**Purpose**: All external dependencies (stores, providers, toolbox, channels).

```
infrastructure/
├── __init__.py
│
├── stores/                 # Data persistence abstractions
│   ├── __init__.py
│   │
│   ├── config/             # ConfigStore: rules, scenarios, templates
│   │   ├── __init__.py
│   │   ├── base.py         # ConfigStore interface
│   │   ├── postgres.py     # PostgresConfigStore
│   │   ├── mongodb.py      # MongoDBConfigStore
│   │   └── inmemory.py     # InMemoryConfigStore (testing)
│   │
│   ├── session/            # SessionStore: active conversation state
│   │   ├── __init__.py
│   │   ├── base.py         # SessionStore interface
│   │   ├── redis.py        # RedisSessionStore
│   │   ├── mongodb.py      # MongoDBSessionStore
│   │   └── inmemory.py     # InMemorySessionStore (testing)
│   │
│   ├── interlocutor/       # InterlocutorDataStore (was: customer_data)
│   │   ├── __init__.py
│   │   ├── base.py         # InterlocutorDataStore interface
│   │   ├── postgres.py     # PostgresInterlocutorDataStore
│   │   └── inmemory.py     # InMemoryInterlocutorDataStore
│   │
│   ├── memory/             # MemoryStore: episodes, entities, relationships
│   │   ├── __init__.py
│   │   ├── base.py         # MemoryStore interface
│   │   ├── postgres.py     # PostgresMemoryStore (pgvector)
│   │   ├── neo4j.py        # Neo4jMemoryStore
│   │   └── inmemory.py     # InMemoryMemoryStore (testing)
│   │
│   ├── audit/              # AuditStore: immutable history
│   │   ├── __init__.py
│   │   ├── base.py         # AuditStore interface
│   │   ├── postgres.py     # PostgresAuditStore
│   │   ├── timescale.py    # TimescaleAuditStore
│   │   └── inmemory.py     # InMemoryAuditStore (testing)
│   │
│   └── vector/             # VectorStore: generic vector search
│       ├── __init__.py
│       ├── base.py         # VectorStore interface
│       └── postgres.py     # PostgresVectorStore (pgvector)
│
├── providers/              # AI capability providers
│   ├── __init__.py
│   │
│   ├── llm/                # LLMExecutor (text generation)
│   │   ├── __init__.py
│   │   ├── base.py         # LLMMessage, LLMResponse
│   │   ├── executor.py     # LLMExecutor (uses Agno for routing)
│   │   └── mock.py         # MockLLMProvider (testing)
│   │
│   ├── embedding/          # EmbeddingProvider (vector embeddings)
│   │   ├── __init__.py
│   │   ├── base.py         # EmbeddingProvider interface
│   │   ├── openai.py       # OpenAIEmbeddings
│   │   ├── cohere.py       # CohereEmbeddings
│   │   ├── voyage.py       # VoyageEmbeddings
│   │   └── mock.py         # MockEmbeddings (testing)
│   │
│   └── rerank/             # RerankProvider (result reranking)
│       ├── __init__.py
│       ├── base.py         # RerankProvider interface
│       ├── cohere.py       # CohereRerank
│       └── voyage.py       # VoyageRerank
│
├── toolbox/                # Tool execution
│   ├── __init__.py
│   ├── toolbox.py          # Toolbox (tool registry)
│   └── gateway.py          # ToolGateway (execution environment)
│
└── channels/               # Channel adapters
    ├── __init__.py
    ├── base.py             # ChannelAdapter interface
    ├── webchat.py          # WebChatAdapter
    ├── whatsapp.py         # WhatsAppAdapter
    └── slack.py            # SlackAdapter
```

---

### `ruche/domain/` — Pure Domain Models

**Purpose**: Domain models with no infrastructure dependencies.

```
domain/
├── __init__.py
│
├── interlocutor/           # Interlocutor data models (was: customer_data)
│   ├── __init__.py
│   ├── field.py            # InterlocutorDataField (schema definition)
│   ├── entry.py            # VariableEntry (runtime value + history)
│   ├── store.py            # InterlocutorDataStore (collection of variables)
│   └── source.py           # VariableSource (where variable came from)
│
├── rules/                  # Rule domain models
│   ├── __init__.py
│   ├── rule.py             # Rule
│   └── matched_rule.py     # MatchedRule
│
├── scenarios/              # Scenario domain models
│   ├── __init__.py
│   ├── scenario.py         # Scenario, ScenarioStep
│   └── transition.py       # StepTransition
│
└── memory/                 # Memory domain models
    ├── __init__.py
    ├── episode.py          # Episode (atomic memory unit)
    ├── entity.py           # Entity (person, order, product)
    └── relationship.py     # Relationship (edges between entities)
```

---

### `ruche/asa/` — Agent Setter Agent

**Purpose**: Mechanic-agnostic meta-agent for validating and suggesting improvements to agent configurations.

```
asa/
├── __init__.py
│
├── validator/              # Conformance validation
│   ├── __init__.py
│   ├── tool_validator.py   # Tool schema validation
│   ├── scenario_validator.py # Scenario state machine validation
│   └── pipeline_validator.py # Pipeline config validation
│
├── suggester/              # Policy suggestions
│   ├── __init__.py
│   ├── policy_suggester.py # Suggest missing policies
│   └── edge_case_generator.py # Generate edge case scenarios
│
└── ci/                     # Pre-deployment CI validation
    ├── __init__.py
    └── checks.py           # CI validation checks
```

---

### `ruche/observability/` — Logging, Tracing, Metrics

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
    """Configure structured logging for Focal."""

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name."""


# observability/tracing.py
def setup_tracing(service_name: str, otlp_endpoint: str | None) -> None:
    """Setup OpenTelemetry tracing."""


# observability/middleware.py
async def logging_context_middleware(request: Request, call_next):
    """Bind tenant_id, agent_id, session_id, trace_id to all logs."""
```

**Note**: Focal integrates with kernel_agent's existing OpenTelemetry Collector and Prometheus setup. Logs go to stdout (JSON), traces to OTLP, metrics scraped at `/metrics`.

---

### `ruche/config/` — Configuration Loading

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
4. **Runtime overrides** via `RUCHE_*` environment variables

```python
# Usage
from ruche.config.settings import get_settings

settings = get_settings()
port = settings.api.port
generation_model = settings.pipeline.generation.model
rule_strategy = settings.pipeline.retrieval.rule_selection.strategy
```

---

### `ruche/api/` — External Interfaces

**Purpose**: REST API and MCP server for external integrations.

```
api/
├── __init__.py
├── app.py                  # FastAPI app factory
│
├── routes/                 # REST endpoints
│   ├── __init__.py
│   ├── chat.py             # POST /v1/chat (turn processing)
│   ├── sessions.py         # Session CRUD
│   ├── config.py           # Rules, Scenarios, Templates CRUD
│   ├── interlocutor.py     # Interlocutor data CRUD
│   └── health.py           # Health checks
│
├── mcp/                    # MCP server for tool discovery
│   ├── __init__.py
│   ├── server.py           # MCP server implementation
│   └── handlers.py         # Tool discovery handlers
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
[pipeline.situational_sensor]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
history_turns = 5
temperature = 0.0
max_tokens = 800

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

[pipeline.rule_filtering]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]

[pipeline.generation]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
temperature = 0.7
max_tokens = 1024

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
                                    │      INFRASTRUCTURE/PROVIDERS        │
                                    │  ┌─────────┐ ┌─────────┐ ┌────────┐ │
                                    │  │ LLM     │ │Embedding│ │Rerank  │ │
                                    │  │Anthropic│ │ OpenAI  │ │ Cohere │ │
                                    │  │ OpenAI  │ │ Cohere  │ │ Voyage │ │
                                    │  │ OpenRouter│ │ Voyage │ │        │ │
                                    │  └────┬────┘ └────┬────┘ └───┬────┘ │
                                    └───────┼──────────┼──────────┼──────┘
                                            │          │          │
┌──────────────────────────────────────────────────────────────────────────────┐
│                          RUNTIME / MECHANICS                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │              AgentRuntime (lifecycle, caching, routing)                 │ │
│  │  ┌────────────────────────────────────────────────────────────────┐     │ │
│  │  │                  FocalCognitivePipeline                        │     │ │
│  │  │                                                                │     │ │
│  │  │  P01→P02→P03→P04→P05→P06→P07→P08→P09→P10→P11→P12             │     │ │
│  │  │  Identify | Sense | Update | Retrieve | Rerank | Orchestrate  │     │ │
│  │  │  | Execute | Filter | Generate | Enforce | Persist | Ingest   │     │ │
│  │  └────────────────────────────────────────────────────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
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
│ Postgres/Neo4j  │  │ Redis/MongoDB   │  │ Postgres/       │  │ Postgres/       │
│                 │  │                 │  │ Timescale       │  │ MongoDB         │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
       ┌────────────────────┐
       │InterlocutorDataStore│
       │                     │
       │ Variable entries    │
       │ History tracking    │
       │ Postgres            │
       └─────────────────────┘
```

---

## Quick Reference: "Where do I find...?"

| Looking for... | Location |
|----------------|----------|
| Turn processing orchestration | `ruche/runtime/agent/runtime.py` |
| Main pipeline logic | `ruche/brain/focal/pipeline.py` |
| Pipeline phases | `ruche/brain/focal/phases/` |
| Scenario migration | `ruche/brain/focal/migration/` |
| Rule domain models | `ruche/domain/rules/rule.py` |
| Scenario domain models | `ruche/domain/scenarios/scenario.py` |
| Interlocutor data models | `ruche/domain/interlocutor/` |
| Memory domain models | `ruche/domain/memory/` |
| ConfigStore implementations | `ruche/infrastructure/stores/config/` |
| SessionStore implementations | `ruche/infrastructure/stores/session/` |
| MemoryStore implementations | `ruche/infrastructure/stores/memory/` |
| InterlocutorDataStore implementations | `ruche/infrastructure/stores/interlocutor/` |
| LLM provider | `ruche/infrastructure/providers/llm/` |
| Embedding provider | `ruche/infrastructure/providers/embedding/` |
| Rerank provider | `ruche/infrastructure/providers/rerank/` |
| Tool execution | `ruche/infrastructure/toolbox/` |
| Channel adapters | `ruche/infrastructure/channels/` |
| API endpoints | `ruche/api/routes/` |
| MCP server | `ruche/api/mcp/` |
| Pipeline configuration | `ruche/config/models/pipeline.py` |
| Logging setup | `ruche/observability/logging.py` |
| Tracing setup | `ruche/observability/tracing.py` |
| Metrics definitions | `ruche/observability/metrics.py` |
| ASA validators | `ruche/asa/validator/` |

---

## Testing Structure

```
tests/
├── unit/                   # Fast, isolated tests
│   ├── runtime/
│   │   ├── test_agent_runtime.py
│   │   └── test_acf_mutex.py
│   ├── mechanics/
│   │   └── ruche/
│   │       ├── test_pipeline.py
│   │       ├── phases/
│   │       │   ├── test_p01_identification.py
│   │       │   ├── test_p02_situational_sensor.py
│   │       │   └── ...
│   │       └── migration/
│   │           ├── test_planner.py
│   │           └── test_executor.py
│   ├── domain/
│   │   ├── test_rule.py
│   │   ├── test_scenario.py
│   │   └── test_interlocutor.py
│   └── infrastructure/
│       ├── stores/
│       ├── providers/
│       └── toolbox/
│
├── integration/            # Tests with real backends
│   ├── stores/
│   │   ├── test_postgres_config_store.py
│   │   ├── test_redis_session_store.py
│   │   ├── test_postgres_memory_store.py
│   │   └── test_postgres_interlocutor_store.py
│   └── providers/
│       ├── test_anthropic_llm.py
│       └── test_openai_embeddings.py
│
└── e2e/                    # Full pipeline tests
    ├── test_chat_flow.py
    └── test_scenario_flow.py
```

---

## Summary: Architecture Layers

**Runtime Layer** (`ruche/runtime/`):
- **AgentRuntime** — Agent lifecycle, config caching, turn routing
- **ACF (Agent Conversation Fabric)** — Turn serialization, queueing, supersession
- **Agenda** — Proactive task scheduling

**Mechanics Layer** (`ruche/brain/`):
- **CognitivePipeline** — Abstract interface for cognitive mechanics
- **FocalCognitivePipeline** — 12-phase FOCAL alignment implementation
- **Migration** — Scenario version migration (JIT reconciliation)

**Infrastructure Layer** (`ruche/infrastructure/`):
- **Stores** — ConfigStore, SessionStore, MemoryStore, AuditStore, InterlocutorDataStore, VectorStore
- **Providers** — LLMExecutor (via Agno), EmbeddingProvider, RerankProvider
- **Toolbox** — Tool registry and execution gateway
- **Channels** — Channel adapters (webchat, WhatsApp, Slack)

**Domain Layer** (`ruche/domain/`):
- **Pure domain models** — Rules, Scenarios, Interlocutor data, Memory (no infrastructure dependencies)

**ASA (Agent Setter Agent)** (`ruche/asa/`):
- **Validators** — Tool, scenario, pipeline conformance validation
- **Suggester** — Policy suggestions, edge case generation
- **CI** — Pre-deployment validation checks

Each pipeline phase can use different models/providers, configured per-agent in TOML.
