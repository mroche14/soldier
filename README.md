# Soldier

![Soldier](docs/pic.png)

**Production-grade cognitive engine for conversational AI**

Soldier is an API-first, multi-tenant, fully persistent architecture designed for horizontal scaling. It replaces code-centric frameworks with a hot-reloadable configuration system where agent behavior is defined via API, not code.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Core Concepts](#core-concepts)
- [API Reference](#api-reference)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Observability](#observability)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

### The Problem

Building production-grade conversational AI agents is hard. Current frameworks fall into two traps:

**The Prompt Trap**: Stuff everything into a system prompt and hope the LLM follows instructions. This fails at scale—more rules means more ignored instructions and unpredictable behavior.

**The Code Trap**: Many frameworks require code to define agent behavior:
- Journeys defined via SDK calls (`agent.create_journey()`)
- No hot-reload—restart the process to update behavior
- Agents live in memory—no persistence, no horizontal scaling
- Single-tenant by design—multi-tenancy bolted on as an afterthought

### The Solution

Soldier shifts from *hoping* the LLM follows instructions to *explicitly enforcing* them at runtime:

| Principle | Implementation |
|-----------|----------------|
| **API-first** | All configuration via REST/gRPC. No SDK required. |
| **Zero in-memory state** | All state in external stores. Any pod can serve any request. |
| **Hot-reload** | Update Scenarios/Rules/Templates via API → instant effect. No restarts. |
| **Multi-tenant native** | `tenant_id` on every record and operation. Not an afterthought. |
| **Full auditability** | Every decision logged: why rules matched, what memory was retrieved. |

---

## Key Features

### Scenarios
Multi-step conversational flows (onboarding, returns, KYC) managed via CRUD API:
- State transitions with conditions
- Live updates without restart
- Automatic step reconciliation when updated mid-session

### Rules
"When X, then Y" behavioral policies:
- Scoped: GLOBAL → SCENARIO → STEP
- Priority ordering, cooldowns, fire limits
- Semantic + keyword matching
- Post-generation enforcement

### Templates
Pre-written responses for critical points:
- **SUGGEST**: LLM can adapt the text
- **EXCLUSIVE**: Bypass LLM entirely
- **FALLBACK**: Use when enforcement fails

### Memory Layer
Temporal knowledge graph for long-term context:
- Episodes, Entities, Relationships
- Hybrid retrieval: vector + BM25 + graph traversal
- Bi-temporal modeling for point-in-time queries
- Automatic summarization for long conversations

### Tools
Deterministic side-effect actions:
- Only execute when their attached Rule matches
- Configurable timeout, retries, async execution
- Integration with external orchestration (Restate, Celery)

### Enforcement
Post-generation validation:
- Check responses against hard constraint rules
- Automatic regeneration or fallback
- Optional LLM self-critique

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT                                    │
│                       (REST, gRPC, WebSocket, Voice)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  API LAYER                                   │
│   Authentication (JWT)  │  Rate Limiting  │  Request Validation             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ALIGNMENT ENGINE                                │
│                                                                              │
│   Context Extraction → Retrieval → Rerank → LLM Filter → Generate → Enforce │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                           PROVIDERS                                  │   │
│   │   LLMProvider  │  EmbeddingProvider  │  RerankProvider              │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   STORES                                     │
│                                                                              │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────┐ │
│   │  ConfigStore  │   │  MemoryStore  │   │ SessionStore  │   │AuditStore │ │
│   │               │   │               │   │               │   │           │ │
│   │ "How should   │   │ "What does    │   │ "What's       │   │ "What     │ │
│   │  it behave?"  │   │  it remember?"│   │  happening?"  │   │ happened?"│ │
│   └───────────────┘   └───────────────┘   └───────────────┘   └───────────┘ │
│         │                   │                   │                   │       │
│         ▼                   ▼                   ▼                   ▼       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                          BACKENDS                                    │   │
│   │   PostgreSQL  │  Neo4j  │  MongoDB  │  Redis  │  InMemory           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
soldier/
├── alignment/          # The "brain" - turn pipeline processing
│   ├── context/        # Context extraction from user messages
│   ├── retrieval/      # Rule, scenario, and memory retrieval
│   ├── filtering/      # LLM-based rule and scenario filtering
│   ├── execution/      # Tool execution
│   ├── generation/     # Response generation
│   └── enforcement/    # Post-generation validation
├── memory/             # Long-term memory (knowledge graph)
│   ├── stores/         # Neo4j, PostgreSQL, MongoDB, InMemory
│   ├── retrieval/      # Hybrid retrieval (vector + BM25 + graph)
│   └── ingestion/      # Entity extraction, embedding, summarization
├── conversation/       # Session management
│   └── stores/         # Redis, PostgreSQL implementations
├── audit/              # Immutable audit trail
│   └── stores/         # Turn records, events
├── providers/          # AI provider interfaces
│   ├── llm/            # Anthropic, OpenAI, Bedrock, Ollama
│   ├── embedding/      # OpenAI, Cohere, Voyage, SentenceTransformers
│   └── rerank/         # Cohere, Voyage, CrossEncoder
├── config/             # Configuration loading and models
│   └── models/         # Pydantic settings models
├── api/                # External interfaces
│   ├── routes/         # REST endpoints
│   ├── grpc/           # gRPC service
│   └── middleware/     # Auth, rate limiting, logging
├── observability/      # Logging, tracing, metrics
└── profile/            # Customer profile management
```

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/soldier.git
cd soldier

# Install dependencies
uv sync

# Install dev dependencies
uv sync --dev

# Verify installation
uv run python -c "from soldier.config import get_settings; print('OK')"
```

### Run Tests

```bash
uv run pytest
```

### Start Development Stack

```bash
# Start PostgreSQL, Redis, Neo4j (optional)
docker-compose up -d

# Run the application
make run
# or
uv run python -m soldier.api
```

---

## Installation

### Using uv (Recommended)

```bash
# Install production dependencies
uv sync

# Install with dev dependencies
uv sync --dev
```

### Docker

```bash
# Build the image
docker build -t soldier .

# Run with environment variables
docker run -e SOLDIER_ENV=production \
           -e ANTHROPIC_API_KEY=your-key \
           -e DATABASE_URL=postgresql://... \
           -p 8000:8000 \
           soldier
```

### From Source

```bash
pip install -e .
```

---

## Configuration

Soldier uses TOML configuration files with Pydantic validation. Configuration is loaded in layers:

```
1. Pydantic model defaults (code)
2. config/default.toml (base configuration)
3. config/{SOLDIER_ENV}.toml (environment-specific)
4. Environment variables (SOLDIER_* prefix)
```

### Configuration Files

```
config/
├── default.toml      # Base defaults (committed)
├── development.toml  # Local development overrides
├── staging.toml      # Staging environment
├── production.toml   # Production environment
└── test.toml         # Test configuration
```

### Environment Selection

```bash
export SOLDIER_ENV=development  # or production, staging, test
```

### Environment Variable Overrides

Override any setting with `SOLDIER_` prefix using double underscores for nesting:

```bash
# API settings
export SOLDIER_API__PORT=9000
export SOLDIER_API__RATE_LIMIT__REQUESTS_PER_MINUTE=100

# Pipeline settings
export SOLDIER_PIPELINE__GENERATION__LLM_PROVIDER=anthropic

# Storage settings
export SOLDIER_STORAGE__SESSION__BACKEND=redis
```

### Secrets Management

**Never commit secrets to TOML files or code.**

1. Copy the example file: `cp .env.example .env`
2. Fill in your API keys and credentials
3. The `.env` file is gitignored

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...
DATABASE_URL=postgresql://soldier:password@localhost:5432/soldier
REDIS_URL=redis://localhost:6379/0
```

### Provider Configuration

Each pipeline step can use different AI providers:

```toml
# config/default.toml

[pipeline.context_extraction]
enabled = true
mode = "llm"
llm_provider = "haiku"

[pipeline.retrieval]
embedding_provider = "default"
max_k = 30

[pipeline.generation]
llm_provider = "sonnet"
temperature = 0.7
max_tokens = 1024

[providers.llm.haiku]
provider = "anthropic"
model = "claude-3-haiku-20240307"

[providers.llm.sonnet]
provider = "anthropic"
model = "claude-sonnet-4-5-20250514"
```

---

## Core Concepts

### Rules

A Rule is a "when X, then Y" behavioral policy:

```python
Rule(
    name="Refund Policy Check",
    condition_text="Customer asks about refunds",
    action_text="Check order status before explaining refund policy",
    scope=Scope.GLOBAL,       # GLOBAL | SCENARIO | STEP
    priority=10,              # Higher wins in conflicts
    max_fires_per_session=0,  # 0 = unlimited
    cooldown_turns=0,         # Minimum turns between re-firing
    attached_tool_ids=["check_order_status"],
    is_hard_constraint=False, # Enforce post-generation
)
```

**Scope Hierarchy**: STEP > SCENARIO > GLOBAL (when same priority)

### Scenarios

A Scenario is a multi-step conversational flow:

```
Scenario: "Return Process"
│
├── Step: "Identify Order" (entry)
│   ├── templates: ["ask_order_id"]
│   └── transitions: → "Verify Eligibility"
│
├── Step: "Verify Eligibility"
│   ├── tools: [check_return_policy]
│   └── transitions: → "Process Return" | → "Deny Return"
│
├── Step: "Process Return"
│   ├── tools: [initiate_return]
│   └── transitions: → "Confirm"
│
└── Step: "Confirm" (terminal)
```

### Templates

Pre-written responses with variable interpolation:

```python
Template(
    name="Refund Confirmation",
    text="Your refund for order {order_id} has been processed. "
         "Amount: {refund_amount}. Method: {payment_method}.",
    mode=TemplateMode.EXCLUSIVE,  # SUGGEST | EXCLUSIVE | FALLBACK
    scope=Scope.STEP,
    scope_id=step_id,
)
```

### Memory (Episodes, Entities, Relationships)

```
User: "I ordered a laptop last week but it arrived damaged"

Extracted:
  Episodes: [Message about damaged laptop]
  Entities: [Order, Laptop, DamageIssue]
  Relationships: [Order -contains-> Laptop, Order -has_issue-> DamageIssue]
```

All data is bi-temporal:
- `valid_from` / `valid_to`: When the fact was true
- `recorded_at`: When Soldier learned it

---

## API Reference

### Base URL

```
https://soldier.example.com/v1
```

### Authentication

All endpoints require JWT authentication:

```
Authorization: Bearer <jwt_token>

JWT Claims:
{
  "sub": "user_id",
  "tenant_id": "uuid",
  "roles": ["agent_admin", "viewer"]
}
```

### Core Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /v1/chat` | Process a conversation turn |
| `GET/POST /v1/agents` | Agent CRUD |
| `GET/POST /v1/agents/{id}/scenarios` | Scenario CRUD |
| `GET/POST /v1/agents/{id}/rules` | Rule CRUD |
| `GET/POST /v1/agents/{id}/templates` | Template CRUD |
| `GET/POST /v1/sessions` | Session management |
| `GET /v1/sessions/{id}/turns` | Turn history |
| `POST /v1/agents/{id}/publish` | Publish configuration changes |

### Chat Request

```bash
curl -X POST https://soldier.example.com/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "uuid",
    "session_id": "uuid",
    "channel": "webchat",
    "user_channel_id": "user123",
    "message": "I want to return my order"
  }'
```

### Chat Response

```json
{
  "turn_id": "uuid",
  "response": "I'd be happy to help with your return. Can you provide your order number?",
  "matched_rules": ["refund_check"],
  "tools_called": [],
  "scenario": {
    "id": "return_flow",
    "step": "identify_order"
  },
  "latency_ms": 342
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid rule configuration",
    "details": [
      {"field": "condition_text", "message": "Required field"}
    ]
  }
}
```

---

## Development

### Make Commands

```bash
make install      # Install production dependencies
make install-dev  # Install dev dependencies
make test         # Run all tests
make test-cov     # Run tests with coverage
make lint         # Check code with ruff
make lint-fix     # Auto-fix lint issues
make format       # Format code with ruff
make typecheck    # Type check with mypy
make clean        # Remove build artifacts
make run          # Run the application
```

### Docker Commands

```bash
make docker-up       # Start development stack
make docker-down     # Stop development stack
make docker-rebuild  # Rebuild and start containers
make docker-logs     # View container logs
```

### Code Style

- **Formatter**: ruff format (line length 100)
- **Linter**: ruff check
- **Type Checker**: mypy (strict mode)

### Naming Conventions

**Classes**: Domain-specific nouns
```python
# Good
class RuleRetriever:
class MemoryStore:
class AlignmentEngine:

# Bad
class Manager:
class Handler:
class Utils:
```

**Methods**: Verb phrases that describe the action
```python
# Good
def extract_intent()
def filter_by_scope()
def generate_response()

# Bad
def process()
def handle()
def do()
```

### Dependency Injection

Classes receive their dependencies, they don't create them:

```python
# Good
class AlignmentEngine:
    def __init__(
        self,
        context_extractor: ContextExtractor,
        rule_retriever: RuleRetriever,
        response_generator: ResponseGenerator,
    ):
        ...

# Bad
class AlignmentEngine:
    def __init__(self):
        self.extractor = ContextExtractor()  # Tight coupling
```

---

## Testing

### Test Pyramid

| Layer | Purpose | Speed | Coverage |
|-------|---------|-------|----------|
| **Unit** (80%) | Single class/function | < 10ms | In-memory, mocks |
| **Integration** (15%) | Component boundaries | < 1s | Real backends |
| **E2E** (5%) | Full request flow | < 10s | Full stack |

### Coverage Requirements

- **Overall**: 85% line coverage, 80% branch coverage
- **Alignment/Memory modules**: 85% minimum

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=soldier --cov-report=html

# Specific file
uv run pytest tests/unit/test_rules.py -v

# Specific test
uv run pytest tests/unit/test_rules.py::test_rule_matching -v
```

### Writing Tests

```python
# test_<method>_<scenario>_<expected_behavior>
async def test_retrieve_when_no_rules_exist_returns_empty_list(self, store):
    # Arrange
    tenant_id = uuid4()

    # Act
    rules = await store.get_rules(tenant_id)

    # Assert
    assert rules == []
```

### Test Fixtures

```python
@pytest.fixture
def config_store():
    return InMemoryConfigStore()

@pytest.fixture
def llm_provider():
    return MockLLMProvider(default_response="Test response")
```

---

## Deployment

### Deployment Modes

**Standalone Mode** (Default): Soldier is the source of truth for configuration.

```toml
[deployment]
mode = "standalone"
```

### Environment Variables

```bash
# Required
SOLDIER_ENV=production
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Optional
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
SOLDIER_API__PORT=8000
SOLDIER_API__WORKERS=4
```

### Docker Compose

```yaml
services:
  soldier:
    build: .
    environment:
      - SOLDIER_ENV=production
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DATABASE_URL=postgresql://soldier:password@postgres:5432/soldier
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: soldier
      POSTGRES_PASSWORD: password
      POSTGRES_DB: soldier

  redis:
    image: redis:7-alpine
```

### Kubernetes

See `deploy/kubernetes/` for Helm charts and manifests.

### Health Checks

```
GET /health         # Liveness probe
GET /health/ready   # Readiness probe
GET /metrics        # Prometheus metrics
```

---

## Observability

### Three Pillars

| Pillar | Stack | Purpose |
|--------|-------|---------|
| **Logs** | structlog → stdout | Structured JSON logs |
| **Traces** | OpenTelemetry → Jaeger/Tempo | Request tracing |
| **Metrics** | Prometheus → Grafana | Performance monitoring |

### Log Schema

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "info",
  "event": "turn_processed",
  "tenant_id": "tenant_abc123",
  "agent_id": "agent_xyz789",
  "session_id": "sess_456",
  "turn_id": "turn_789",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "latency_ms": 342,
  "rules_matched": 3
}
```

### Key Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `soldier_requests_total` | Counter | Total requests by endpoint/status |
| `soldier_request_duration_seconds` | Histogram | Request latency |
| `soldier_pipeline_step_duration_seconds` | Histogram | Per-step latency |
| `soldier_llm_calls_total` | Counter | LLM provider calls |
| `soldier_llm_tokens_total` | Counter | Token consumption |
| `soldier_rules_matched` | Histogram | Rules matched per turn |
| `soldier_errors_total` | Counter | Error counts |

### Trace Structure

```
turn_process (root span)
├── context_extraction
│   └── llm_call (provider: anthropic, model: haiku)
├── retrieval
│   ├── rule_retrieval
│   ├── scenario_retrieval
│   └── memory_retrieval
├── reranking
├── llm_filtering
├── tool_execution
├── generation
└── enforcement
```

### Configuration

```toml
[observability]
log_format = "json"           # "json" or "console"
log_level = "INFO"
tracing_enabled = true
tracing_sample_rate = 0.1     # 10% in production
metrics_enabled = true
metrics_path = "/metrics"
```

---

## Performance Targets

| Operation | Target |
|-----------|--------|
| Context Extraction | 200ms |
| Retrieval (parallel) | 50ms |
| Reranking | 100ms |
| LLM Filtering | 200ms |
| Tool Execution | 200ms |
| Generation | 500ms |
| Enforcement | 50ms |
| **Full Turn** | 600ms - 1400ms |

### Memory Retrieval

| Operation | Target |
|-----------|--------|
| Vector search (top-10) | < 50ms |
| BM25 search | < 30ms |
| Graph traversal (depth 2) | < 100ms |
| Full hybrid retrieval | < 200ms |

---

## Contributing

1. Read `CLAUDE.md` for development guidelines
2. Check `IMPLEMENTATION_PLAN.md` for current phase
3. Follow the documentation in `docs/`
4. Write tests for all new code
5. Run `make all` before committing

### Pull Request Process

1. Create a feature branch from `main`
2. Make changes following the style guide
3. Ensure all tests pass: `make all`
4. Update documentation as needed
5. Submit PR with clear description

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/vision.md`](docs/vision.md) | Project vision and goals |
| [`docs/architecture/overview.md`](docs/architecture/overview.md) | System architecture |
| [`docs/architecture/alignment-engine.md`](docs/architecture/alignment-engine.md) | Turn pipeline details |
| [`docs/architecture/memory-layer.md`](docs/architecture/memory-layer.md) | Knowledge graph |
| [`docs/architecture/observability.md`](docs/architecture/observability.md) | Logging, tracing, metrics |
| [`docs/design/domain-model.md`](docs/design/domain-model.md) | Data models |
| [`docs/design/turn-pipeline.md`](docs/design/turn-pipeline.md) | Request flow |
| [`docs/design/api-crud.md`](docs/design/api-crud.md) | REST API reference |
| [`docs/development/testing-strategy.md`](docs/development/testing-strategy.md) | Testing guidelines |
| [`CLAUDE.md`](CLAUDE.md) | Development guidelines |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Implementation phases |

---

## Roadmap

See `IMPLEMENTATION_PLAN.md` for the complete 20-phase implementation plan.

**Current Status**: Phase 1 (Project Foundation) - Complete

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [structlog](https://www.structlog.org/) - Structured logging
- [OpenTelemetry](https://opentelemetry.io/) - Observability
- [LiteLLM](https://github.com/BerriAI/litellm) - Unified LLM interface
