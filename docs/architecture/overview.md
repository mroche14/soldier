# Architecture Overview

This document describes the runtime platform architecture that hosts conversational agents. The platform includes:

- **FOCAL**: An alignment-focused cognitive pipeline (11-phase spec) that implements the Brain protocol
- **Agent Conversation Fabric (ACF)**: Turn boundary detection and LogicalTurn accumulation
- **AgentRuntime**: Multi-tenant agent execution environment
- **Stores**: ConfigStore, MemoryStore, SessionStore, AuditStore interfaces
- **Providers**: LLM, embedding, reranking, multimodal capabilities
- **Toolbox**: Tool execution and orchestration

The platform is **API-first, multi-tenant**, with pluggable storage and AI providers. Every component is designed for horizontal scaling.

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **API-first** | All configuration via REST/gRPC. No SDK required. |
| **Zero in-memory state** | All state in external stores via interfaces |
| **Pluggable everything** | Storage backends, LLM providers, embedding models |
| **Multi-tenant native** | `tenant_id` on every record and operation |
| **Per-step configuration** | Each brain step can use different providers |
| **Stateless pods** | Any pod can serve any request |

---

## Deployment Modes

Focal supports two deployment modes to accommodate different integration patterns:

### Standalone Mode (Default)

Focal is the **source of truth** for all configuration. Use this mode when:
- Deploying Focal as an independent service
- Managing configuration via Focal's REST API
- Building your own admin UI on top of Focal

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Admin UI   │────▶│   Focal   │────▶│ PostgreSQL  │
│  (custom)   │     │   REST API  │     │  (config)   │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Characteristics:**
- Full CRUD API for Agents, Scenarios, Rules, Templates (see [api-crud.md](../design/api-crud.md))
- Configuration persisted in PostgreSQL
- Version history and rollback support
- Direct API access for automation

### External Control Plane Mode

Focal is a **consumer** of configuration from an external Control Plane. Use this mode when:
- Integrating into a larger platform architecture
- An external Control Plane is the source of truth
- Configuration is managed via an external Admin UI

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Admin UI   │────▶│  Database   │────▶│  Publisher  │────▶│   Redis     │
│  (external) │     │   (SoT)     │     │  (Restate)  │     │  Bundles    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                    cfg-updated    │
                                                                   ▼
                                                            ┌─────────────┐
                                                            │   Focal   │
                                                            │ (read-only) │
                                                            └─────────────┘
```

**Characteristics:**
- Configuration loaded from Redis bundles (compiled by Publisher)
- Hot-reload via pub/sub notifications (`cfg-updated`)
- CRUD endpoints disabled or read-only
### Configuration

```toml
# config/default.toml

[deployment]
mode = "standalone"  # or "external"

# External control plane settings (only used when mode = "external")
[deployment.external]
redis_bundle_prefix = "{tenant}:{agent}"
config_pointer_key = "cfg"
pubsub_channel = "cfg-updated"
bundle_ttl_seconds = 3600
```

See [configuration.md](./configuration.md) for full deployment configuration options.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT                                        │
│                       (REST, gRPC, WebSocket, Voice, Images)                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  API LAYER                                       │
│                                                                                  │
│   Authentication (JWT)  │  Rate Limiting  │  Request Validation                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INPUT PROCESSING (Pre-Brain)                        │
│                                                                                  │
│   Audio ──▶ STT ──┐                                                             │
│   Image ──▶ Vision LLM ──┼──▶ Text                                              │
│   Document ──▶ Doc Processing ──┘                                               │
│   Text ──────────────────────▶ Text                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ALIGNMENT ENGINE                                    │
│                                                                                  │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐          │
│   │ Context │──▶│Retrieval│──▶│ Rerank  │──▶│  LLM    │──▶│ Generate│          │
│   │ Extract │   │         │   │         │   │ Filter  │   │         │          │
│   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘          │
│       │             │             │             │             │                  │
│       ▼             ▼             ▼             ▼             ▼                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                           PROVIDERS                                      │   │
│   │   LLMExecutor  │  EmbeddingProvider  │  RerankProvider                  │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          OUTPUT PROCESSING (Post-Brain)                       │
│                                                                                  │
│   Text ──────────────────────▶ Text                                             │
│   Text ──▶ TTS ──────────────▶ Audio (if voice output enabled)                  │
│   Text ──▶ Image Gen ────────▶ Image (if image generation requested)            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   STORES                                         │
│                                                                                  │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌─────────────┐  │
│   │  ConfigStore  │   │  MemoryStore  │   │ SessionStore  │   │ AuditStore  │  │
│   │               │   │               │   │               │   │             │  │
│   │ "How should   │   │ "What does    │   │ "What's       │   │ "What       │  │
│   │  it behave?"  │   │  it remember?"│   │  happening?"  │   │  happened?" │  │
│   │               │   │               │   │               │   │             │  │
│   │ Rules         │   │ Episodes      │   │ Sessions      │   │ Turns       │  │
│   │ Scenarios     │   │ Entities      │   │ Variables     │   │ Events      │  │
│   │ Templates     │   │ Relationships │   │ Rule fires    │   │ Metrics     │  │
│   └───────────────┘   └───────────────┘   └───────────────┘   └─────────────┘  │
│         │                   │                   │                   │           │
│         ▼                   ▼                   ▼                   ▼           │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                          BACKENDS                                        │   │
│   │   PostgreSQL  │  Neo4j  │  MongoDB  │  Redis  │  TimescaleDB            │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. API Layer

Handles all external communication.

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/chat` | Process a conversation turn |
| `GET/POST /v1/sessions` | Session management |
| `GET/POST /v1/rules` | Rule CRUD |
| `GET/POST /v1/scenarios` | Scenario CRUD |
| `GET/POST /v1/templates` | Template CRUD |
| `GET /v1/turns` | Audit log queries |

**Authentication**: JWT with `tenant_id` and `agent_id` claims.
**Rate Limiting**: Per-tenant token bucket.

### 2. FOCAL Alignment Brain

**FOCAL** is an alignment-focused implementation of the Brain protocol. It processes LogicalTurns through an 11-phase brain focused on rule matching, scenario orchestration, and constraint enforcement.

See [alignment-engine.md](./alignment-engine.md) for details.

```
LogicalTurn (1+ messages) → Context Extraction → Retrieval → Rerank → LLM Filter → Tools → Generate → Enforce → Response
```

**Note**: Turn boundaries (message accumulation, supersede signals) are handled by the **Agent Conversation Fabric (ACF)**, which is a platform component that sits above the Agent. ACF calls `agent.process_turn(fabric_ctx)`, which delegates to `brain.think(ctx) -> BrainResult`. See `docs/acf/architecture/ACF_ARCHITECTURE.md`.

**Other brain mechanics** (e.g., ReAct, planner-executor) can be implemented alongside FOCAL by implementing the same Brain protocol.

Each step is independently configurable via TOML:

```toml
# config/default.toml
[brain.context_extraction]
model = "openrouter/anthropic/claude-3-haiku-20240307"
fallback_models = ["anthropic/claude-3-haiku-20240307"]

[brain.retrieval]
embedding_provider = "default"

[brain.generation]
model = "openrouter/anthropic/claude-sonnet-4-5-20250514"
fallback_models = ["anthropic/claude-sonnet-4-5-20250514", "openai/gpt-4o"]
```

### 3. Providers

External AI services accessed via abstract interfaces. LLM providers use **Agno** for unified access with fallback chains.

**Core Providers (Alignment Engine):**

| Provider | Purpose | Implementations |
|----------|---------|-----------------|
| **LLMExecutor** | Text generation | Agno (OpenRouter, Anthropic, OpenAI, Groq) |
| **EmbeddingProvider** | Vector embeddings | OpenAI, Cohere, Voyage, SentenceTransformers |
| **RerankProvider** | Result reranking | Cohere, Voyage, CrossEncoder |

**Multimodal Providers (Input/Output Processing):**

| Provider | Purpose | Implementations |
|----------|---------|-----------------|
| **STTProvider** | Speech-to-text | OpenAI Whisper, Deepgram, AssemblyAI |
| **TTSProvider** | Text-to-speech | OpenAI TTS, ElevenLabs, Google TTS |
| **VisionLLMProvider** | Image understanding | Claude, GPT-4o, Gemini |
| **ImageGenProvider** | Image generation | DALL-E, Stable Diffusion |
| **DocumentProvider** | PDF/Doc parsing | LlamaParse, Unstructured, Azure Doc Intelligence |

See [configuration.md](./configuration.md) for full provider configuration with fallback chains.

### 4. Stores

Data persistence via domain-specific interfaces.

| Store | Question | Contents | Primary Backends |
|-------|----------|----------|------------------|
| **ConfigStore** | "How should it behave?" | Rules, Scenarios, Templates, Variables | PostgreSQL, MongoDB |
| **MemoryStore** | "What does it remember?" | Episodes, Entities, Relationships | PostgreSQL+pgvector, MongoDB+Atlas |
| **SessionStore** | "What's happening now?" | Sessions, active steps | Redis (cache) + PostgreSQL/MongoDB (persistent) |
| **AuditStore** | "What happened?" | Turns, events, metrics | PostgreSQL, MongoDB |

> **Note:** The interface pattern supports additional backends (Neo4j, DynamoDB, etc.) but PostgreSQL and MongoDB are the primary supported options.

See [ADR-001](../design/decisions/001-storage-choice.md) for full interface definitions.

---

## Request Flow

### Turn Processing

```
1. REQUEST ARRIVES
   POST /v1/chat { tenant_id, agent_id, channel, channel_user_id, message, customer_id? }
   (tenant_id and agent_id resolved upstream by channel-gateway/message-router)
   │
   ▼
2. VALIDATE REQUEST
   - Verify tenant_id and agent_id exist
   - Load agent configuration
   │
   ▼
3. ACF TURN GATEWAY (LogicalTurn)
   - Acquire session mutex
   - Accumulate one or more messages into a LogicalTurn
   - Provide supersede signal to the brain
   │
   ▼
4. PHASE 1: IDENTIFICATION & CONTEXT LOADING
   - Resolve / create Customer (customer_id)
   - Resolve / create session (SessionStore)
   - Load SessionState + InterlocutorDataStore + config + glossary
   │
   ▼
5. PHASE 2: SITUATIONAL SENSOR (LLMExecutor)
   - Schema-aware + glossary-aware situational snapshot
   │
   ▼
6. PHASE 3: CUSTOMER DATA UPDATE
   - Apply candidate variable updates (in-memory)
   │
   ▼
7. PHASE 4: RETRIEVAL (EmbeddingProvider + Stores)
   ├── Rules (ConfigStore.vector_search_rules)
   ├── Scenarios (ConfigStore.get_scenarios)
   └── Memory (MemoryStore.vector_search_episodes)
   │
   ▼
8. PHASE 4b: RERANK (RerankProvider)
   - Re-order candidates by relevance
   │
   ▼
9. PHASE 5: RULE FILTERING (LLMExecutor)
   - Judge which rules apply
   │
   ▼
10. PHASE 6: SCENARIO ORCHESTRATION
    - Scenario lifecycle + step transitions
    │
    ▼
11. PHASE 7: TOOL EXECUTION (Toolbox)
    - Execute tools, update variables
    │
    ▼
12. PHASE 8: RESPONSE PLANNING
    - Build ResponsePlan (ASK/ANSWER/MIXED/ESCALATE)
    │
    ▼
13. PHASE 9: GENERATION (LLMExecutor)
    - Generate final response from ResponsePlan
    │
    ▼
14. PHASE 10: ENFORCEMENT
    - Validate against hard constraints; retry/fallback
    │
    ▼
15. PHASE 11: PERSISTENCE
    ├── Session state (SessionStore)
    ├── Turn record (AuditStore)
    └── Memory ingestion (MemoryStore, async)
    │
    ▼
16. RESPOND
    { response, logical_turn_id, scenario, matched_rules }
```

---

## Multi-Tenancy

Every operation is scoped by `tenant_id`:

| Layer | Isolation |
|-------|-----------|
| API | `tenant_id` required in request (resolved upstream) |
| ConfigStore | `tenant_id` column on all entities |
| MemoryStore | `group_id = tenant_id:session_id` |
| SessionStore | Session key includes `tenant_id`, `agent_id`, `customer_id`, `channel` |
| AuditStore | `tenant_id` on all records |

---

## Configuration

Focal uses **TOML configuration files** with **Pydantic validation**. No hardcoded values in code—only defaults in Pydantic models. See [configuration.md](./configuration.md) for full details.

### Configuration Files

```
config/
├── default.toml        # Base defaults (committed)
├── development.toml    # Local development overrides
├── staging.toml        # Staging environment
├── production.toml     # Production environment
└── test.toml           # Test environment
```

### Per-Agent Brain Configuration

Each agent can have different brain settings:

```toml
# config/default.toml

[brain.situational_sensor]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
history_turns = 5
temperature = 0.0
max_tokens = 800
# OpenRouter routing (optional; only applies to openrouter/* models)
provider_order = ["cerebras", "groq", "google-vertex", "sambanova"]
provider_sort = "latency"
allow_fallbacks = true
ignore_providers = []

[brain.retrieval]
embedding_provider = "default"
max_k = 30

# Selection strategies per retrieval type
[brain.retrieval.rule_selection]
strategy = "adaptive_k"
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

[brain.generation]
enabled = true
model = "openrouter/openai/gpt-oss-120b"
fallback_models = ["anthropic/claude-3-5-haiku-20241022"]
temperature = 0.7
max_tokens = 1024
```

### Deployment Profiles

Use environment-specific overrides: `config/development.toml`, `config/staging.toml`, `config/production.toml`.

### Environment Variable Overrides

Override any configuration via `RUCHE_*` environment variables:

```bash
export RUCHE_API__PORT=9000
export RUCHE_PIPELINE__GENERATION__MODEL=openrouter/openai/gpt-oss-120b
export RUCHE_STORAGE__CONFIG__POSTGRES__PASSWORD=secret
```

---

## Extensibility

| Extension | Mechanism |
|-----------|-----------|
| New LLM provider | Add model string routing in `LLMExecutor` (uses Agno) |
| New embedding model | Implement `EmbeddingProvider` interface |
| New reranker | Implement `RerankProvider` interface |
| New config backend | Implement `ConfigStore` interface |
| New memory backend | Implement `MemoryStore` interface |
| New session backend | Implement `SessionStore` interface |
| New audit backend | Implement `AuditStore` interface |

---

## Latency Targets

| Step | Target | Notes |
|------|--------|-------|
| Context Extraction | 200ms | Optional, can disable |
| Retrieval | 50ms | Parallel queries |
| Reranking | 100ms | Optional, can disable |
| LLM Filtering | 200ms | Optional, can disable |
| Tool Execution | 200ms | Depends on tools |
| Generation | 500ms | Main LLM call |
| Enforcement | 50ms | Usually no regen |
| Persist | 30ms | Async where possible |

**Total**: ~1400ms (all features) to ~600ms (minimal)

---

## Related Documentation

- [Configuration](./configuration.md) - TOML + Pydantic configuration system
- [Selection Strategies](./selection-strategies.md) - Dynamic k-selection algorithms
- [Folder Structure](./folder-structure.md) - Code organization
- [Alignment Engine](./alignment-engine.md) - Brain details
- [Memory Layer](./memory-layer.md) - Knowledge graph
- [FOCAL Brain](../focal_brain/spec/brain.md) - Step-by-step flow
- [ADR-001: Storage](../design/decisions/001-storage-choice.md) - Interface definitions
