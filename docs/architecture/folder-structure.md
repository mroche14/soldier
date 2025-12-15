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
│   ├── brains/             # Brain implementations (FOCAL, etc.)
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

### `ruche/brains/` — Brain Implementations

**Purpose**: Different cognitive mechanics (FOCAL alignment, future alternatives).

```
brains/
├── __init__.py
│
└── focal/                  # FOCAL alignment brain
    ├── __init__.py
    ├── engine.py           # AlignmentEngine (main orchestrator)
    ├── pipeline.py         # Pipeline orchestration
    ├── result.py           # AlignmentResult
    │
    ├── phases/             # Processing phases (organized by function)
    │   ├── context/        # Context extraction and situational sensing
    │   ├── filtering/      # Rule and scenario filtering
    │   ├── generation/     # Response generation
    │   ├── enforcement/    # Two-lane enforcement (deterministic + LLM judge)
    │   ├── orchestration/  # Scenario orchestration
    │   ├── execution/      # Tool execution
    │   ├── planning/       # Response planning
    │   ├── loaders/        # Data loaders (glossary, interlocutor data)
    │   └── interlocutor/   # Interlocutor data updates
    │
    ├── models/             # FOCAL-specific domain models
    │   ├── __init__.py
    │   ├── rule.py             # Rule, MatchedRule
    │   ├── scenario.py         # Scenario, ScenarioStep
    │   ├── template.py         # Template, TemplateResponseMode
    │   ├── agent.py            # Agent, AgentSettings
    │   ├── turn_context.py     # TurnContext (aggregated context)
    │   ├── turn_input.py       # TurnInput (inbound event)
    │   ├── glossary.py         # GlossaryItem
    │   └── ...
    │
    ├── retrieval/          # Candidate retrieval with selection strategies
    │   ├── __init__.py
    │   ├── rule_retriever.py
    │   ├── scenario_retriever.py
    │   └── memory_retriever.py
    │
    ├── stores/             # FOCAL-specific store interfaces
    │   ├── __init__.py
    │   └── agent_config_store.py  # AgentConfigStore interface
    │
    ├── migration/          # Scenario version migration
    │   ├── planner.py      # MigrationPlanner, MigrationDeployer
    │   ├── executor.py     # MigrationExecutor (JIT reconciliation)
    │   ├── composite.py    # CompositeMapper (multi-version gaps)
    │   └── gap_fill.py     # GapFillService
    │
    └── prompts/            # Jinja2 templates
        ├── situational_sensor.jinja2
        ├── rule_filter.jinja2
        └── generation.jinja2
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
│   ├── interlocutor/       # InterlocutorDataStore (was: interlocutor_data)
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
├── db/                     # Database utilities
│   ├── __init__.py
│   ├── pool.py             # PostgresPool (asyncpg connection pool)
│   └── errors.py           # StoreError, ConnectionError, etc.
│
├── jobs/                   # Background job workflows (Hatchet)
│   ├── __init__.py
│   ├── client.py           # HatchetClient
│   └── workflows/          # Workflow definitions
│       ├── profile_expiry.py
│       ├── orphan_detection.py
│       └── schema_extraction.py
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
├── interlocutor/           # Interlocutor data models (was: interlocutor_data)
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
│   └── pipeline_validator.py # Brain config validation
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
    ├── brain.py         # PipelineConfig (each step's settings)
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
generation_model = settings.brain.generation.model
rule_strategy = settings.brain.retrieval.rule_selection.strategy
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

## Configuration: Brain Steps

Each step in the alignment brain can be configured via TOML files with Pydantic validation. See [configuration.md](./configuration.md) for full details.

```toml
# config/default.toml
[brain.situational_sensor]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
history_turns = 5
temperature = 0.0
max_tokens = 800

[brain.retrieval]
embedding_provider = "default"
max_k = 30

# Selection strategies are configurable per retrieval type
[brain.retrieval.rule_selection]
strategy = "adaptive_k"          # elbow | adaptive_k | entropy | clustering | fixed_k
alpha = 1.5
min_score = 0.5

[brain.retrieval.scenario_selection]
strategy = "entropy"
low_entropy_k = 1
medium_entropy_k = 2
high_entropy_k = 3

[brain.retrieval.memory_selection]
strategy = "clustering"
eps = 0.1
top_per_cluster = 3

[brain.reranking]
enabled = true
rerank_provider = "default"
top_k = 10

[brain.rule_filtering]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]

[brain.generation]
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
│  │  │                  FocalBrain                        │     │ │
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
| Main brain logic (AlignmentEngine) | `ruche/brains/focal/engine.py` |
| Brain phases | `ruche/brains/focal/phases/` |
| Two-lane enforcement | `ruche/brains/focal/phases/enforcement/` |
| Response generation | `ruche/brains/focal/phases/generation/` |
| Scenario migration | `ruche/brains/focal/migration/` |
| FOCAL domain models | `ruche/brains/focal/models/` |
| Rule domain models | `ruche/domain/rules/` |
| Scenario domain models | `ruche/domain/scenarios/` |
| Interlocutor data models | `ruche/interlocutor_data/` |
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
| Database pool/errors | `ruche/infrastructure/db/` |
| Background jobs (Hatchet) | `ruche/infrastructure/jobs/` |
| API endpoints | `ruche/api/routes/` |
| MCP server | `ruche/api/mcp/` |
| Pipeline configuration | `ruche/config/models/pipeline.py` |
| Logging setup | `ruche/observability/logging.py` |
| Tracing setup | `ruche/observability/tracing.py` |
| Metrics definitions | `ruche/observability/metrics.py` |
| ASA validators | `ruche/asa/validator/` |
| ACF/LogicalTurnWorkflow | `ruche/runtime/acf/workflow.py` |

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
└── e2e/                    # Full brain tests
    ├── test_chat_flow.py
    └── test_scenario_flow.py
```

---

## Summary: Architecture Layers

**Runtime Layer** (`ruche/runtime/`):
- **AgentRuntime** — Agent lifecycle, config caching, turn routing
- **ACF (Agent Conversation Fabric)** — LogicalTurnWorkflow (Hatchet), turn serialization, message accumulation
- **Agenda** — Proactive task scheduling

**Brains Layer** (`ruche/brains/`):
- **FOCAL Brain** (`brains/focal/`) — Alignment-focused brain with multi-phase pipeline
  - **AlignmentEngine** — Main orchestrator
  - **Phases** — Context, Filtering, Generation, Enforcement, etc.
  - **Two-Lane Enforcement** — Deterministic (simpleeval) + Subjective (LLM-as-Judge)
  - **Migration** — Scenario version migration (JIT reconciliation)

**Infrastructure Layer** (`ruche/infrastructure/`):
- **Stores** — ConfigStore, SessionStore, MemoryStore, AuditStore, InterlocutorDataStore, VectorStore
- **Providers** — LLMExecutor (via Agno), EmbeddingProvider, RerankProvider
- **Toolbox** — Tool registry and execution gateway
- **Channels** — Channel adapters (webchat, WhatsApp, Slack)

**Domain Layer** (`ruche/domain/`):
- **Pure domain models** — Rules, Scenarios, Memory (no infrastructure dependencies)
- **Interlocutor data** (`ruche/interlocutor_data/`) — Variable entries, field definitions

**ASA (Agent Setter Agent)** (`ruche/asa/`):
- **Validators** — Tool, scenario, brain conformance validation
- **Suggester** — Policy suggestions, edge case generation
- **CI** — Pre-deployment validation checks

Each brain phase can use different models/providers, configured per-agent in TOML.
