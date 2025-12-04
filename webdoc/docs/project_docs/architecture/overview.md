# Architecture Overview

Soldier is an **API-first, multi-tenant cognitive engine** with pluggable storage and AI providers. Every component is designed for horizontal scaling.

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **API-first** | All configuration via REST/gRPC. No SDK required. |
| **Zero in-memory state** | All state in external stores via interfaces |
| **Pluggable everything** | Storage backends, LLM providers, embedding models |
| **Multi-tenant native** | `tenant_id` on every record and operation |
| **Per-step configuration** | Each pipeline step can use different providers |
| **Stateless pods** | Any pod can serve any request |

---

## Deployment Modes

Soldier supports two deployment modes to accommodate different integration patterns:

### Standalone Mode (Default)

Soldier is the **source of truth** for all configuration. Use this mode when:
- Deploying Soldier as an independent service
- Managing configuration via Soldier's REST API
- Building your own admin UI on top of Soldier

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Admin UI   │────▶│   Soldier   │────▶│ PostgreSQL  │
│  (custom)   │     │   REST API  │     │  (config)   │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Characteristics:**
- Full CRUD API for Agents, Scenarios, Rules, Templates (see [api-crud.md](../design/api-crud.md))
- Configuration persisted in PostgreSQL
- Version history and rollback support
- Direct API access for automation

### External Control Plane Mode

Soldier is a **consumer** of configuration from an external Control Plane. Use this mode when:
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
                                                            │   Soldier   │
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
│                           INPUT PROCESSING (Pre-Pipeline)                        │
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
│   │   LLMProvider  │  EmbeddingProvider  │  RerankProvider                  │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          OUTPUT PROCESSING (Post-Pipeline)                       │
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

### 2. Alignment Engine

The core processing pipeline. See [alignment-engine.md](./alignment-engine.md) for details.

```
Message → Context Extraction → Retrieval → Rerank → LLM Filter → Tools → Generate → Enforce → Response
```

Each step is independently configurable via TOML:

```toml
# config/default.toml
[pipeline.context_extraction]
llm_provider = "haiku"

[pipeline.retrieval]
embedding_provider = "default"

[pipeline.generation]
llm_provider = "sonnet"

[providers.llm.haiku]
provider = "anthropic"
model = "claude-3-haiku-20240307"

[providers.llm.sonnet]
provider = "anthropic"
model = "claude-sonnet-4-5-20250514"
```

### 3. Providers

External AI services accessed via abstract interfaces. All providers use **LiteLLM** for unified access with fallback chains.

**Core Providers (Alignment Engine):**

| Provider | Purpose | Implementations |
|----------|---------|-----------------|
| **LLMProvider** | Text generation | Anthropic, OpenAI, Bedrock, Vertex, Ollama |
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
   POST /v1/chat { tenant_id, agent_id, channel, user_channel_id, message }
   (tenant_id and agent_id resolved upstream by channel-gateway/message-router)
   │
   ▼
2. VALIDATE REQUEST
   - Verify tenant_id and agent_id exist
   - Load agent configuration
   │
   ▼
3. LOAD SESSION (SessionStore)
   - Get or create session
   - Get conversation history (last N turns)
   │
   ▼
4. CONTEXT EXTRACTION (LLMProvider)
   - Analyze message + history
   - Extract: intent, entities, sentiment
   - Output: Context object
   │
   ▼
5. RETRIEVAL (EmbeddingProvider + Stores)
   ├── Rules (ConfigStore.vector_search_rules)
   ├── Scenarios (ConfigStore.get_scenarios)
   └── Memory (MemoryStore.vector_search_episodes)
   │
   ▼
6. RERANK (RerankProvider)
   - Re-order candidates by relevance
   │
   ▼
7. LLM FILTER (LLMProvider)
   - Judge which rules apply
   - Decide scenario action (start/continue/exit)
   │
   ▼
8. TOOL EXECUTION
   - Run tools attached to matched rules
   - Update session variables
   │
   ▼
9. RESPONSE GENERATION (LLMProvider)
   - Check for EXCLUSIVE template
   - Build prompt with rules, memory, tools
   - Call LLM
   │
   ▼
10. ENFORCEMENT
    - Validate against hard constraints
    - Regenerate or use fallback if needed
    │
    ▼
11. PERSIST
    ├── Session state (SessionStore)
    ├── Turn record (AuditStore)
    └── Memory ingestion (MemoryStore, async)
    │
    ▼
12. RESPOND
    { response, turn_id, scenario, matched_rules }
```

---

## Multi-Tenancy

Every operation is scoped by `tenant_id`:

| Layer | Isolation |
|-------|-----------|
| API | `tenant_id` required in request (resolved upstream) |
| ConfigStore | `tenant_id` column on all entities |
| MemoryStore | `group_id = tenant_id:session_id` |
| SessionStore | Session key includes `tenant_id` |
| AuditStore | `tenant_id` on all records |

---

## Configuration

Soldier uses **TOML configuration files** with **Pydantic validation**. No hardcoded values in code—only defaults in Pydantic models. See [configuration.md](./configuration.md) for full details.

### Configuration Files

```
config/
├── default.toml        # Base defaults (committed)
├── development.toml    # Local development overrides
├── staging.toml        # Staging environment
├── production.toml     # Production environment
└── test.toml           # Test environment
```

### Per-Agent Pipeline Configuration

Each agent can have different pipeline settings:

```toml
# config/default.toml

[pipeline.context_extraction]
enabled = true
mode = "llm"
llm_provider = "haiku"
history_turns = 5

[pipeline.retrieval]
embedding_provider = "default"
max_k = 30

# Selection strategies per retrieval type
[pipeline.retrieval.rule_selection]
strategy = "adaptive_k"
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
llm_provider = "sonnet"
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
```

### Deployment Profiles

**Minimal (Low cost, fast)** — `config/minimal.toml`
```toml
[pipeline.context_extraction]
enabled = false

[pipeline.reranking]
enabled = false

[pipeline.llm_filtering]
enabled = false

[pipeline.generation]
llm_provider = "haiku"
```

**Balanced (Recommended)** — `config/default.toml`
```toml
[pipeline.context_extraction]
mode = "llm"
llm_provider = "haiku"

[pipeline.reranking]
enabled = true

[pipeline.llm_filtering]
enabled = true

[pipeline.generation]
llm_provider = "sonnet"
```

**Maximum Quality** — `config/production.toml`
```toml
[pipeline.context_extraction]
mode = "llm"
llm_provider = "sonnet"

[pipeline.reranking]
enabled = true

[pipeline.llm_filtering]
enabled = true
llm_provider = "sonnet"

[pipeline.generation]
llm_provider = "sonnet"

[pipeline.enforcement]
self_critique_enabled = true
self_critique_provider = "haiku"
```

### Environment Variable Overrides

Override any configuration via `SOLDIER_*` environment variables:

```bash
export SOLDIER_API__PORT=9000
export SOLDIER_PIPELINE__GENERATION__LLM_PROVIDER=haiku
export SOLDIER_STORAGE__CONFIG__POSTGRES__PASSWORD=secret
```

---

## Extensibility

| Extension | Mechanism |
|-----------|-----------|
| New LLM provider | Implement `LLMProvider` interface |
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
- [Alignment Engine](./alignment-engine.md) - Pipeline details
- [Memory Layer](./memory-layer.md) - Knowledge graph
- [Turn Pipeline](../design/turn-pipeline.md) - Step-by-step flow
- [ADR-001: Storage](../design/decisions/001-storage-choice.md) - Interface definitions
