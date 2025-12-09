# Focal Integration with External Platforms

This document describes how Focal integrates into a multi-plane architecture as the cognitive layer.

## Architecture Position

Focal is the **Cognitive Layer** in a multi-plane architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONTROL PLANE                                      │
│                                                                              │
│  ┌──────────┐     ┌─────────────┐     ┌──────────┐     ┌──────────────┐    │
│  │ Admin UI │────▶│ Control API │────▶│ Supabase │────▶│   Publisher  │    │
│  │ (Next.js)│     │  (FastAPI)  │     │   (SoT)  │     │  (Restate)   │    │
│  └──────────┘     └─────────────┘     └──────────┘     └──────────────┘    │
│                                                                │             │
│  Entities: Agents, Scenarios, Rules, Templates, Tools, Variables            │
│                                                                ▼             │
│                                                       ┌──────────────┐       │
│                                                       │ Redis Bundles│       │
│                                                       │ + Pub/Sub    │       │
│                                                       └──────────────┘       │
└───────────────────────────────────────────────────────────────┬─────────────┘
                                                                │
                                         cfg-updated pub/sub    │
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHANNEL LAYER                                      │
│                                                                              │
│  WhatsApp   Slack   Webchat   Email   Voice                                 │
│      │        │        │        │       │                                   │
│      └────────┴────────┴────────┴───────┘                                   │
│                        │                                                     │
│                        ▼                                                     │
│              ┌─────────────────┐                                            │
│              │ Channel-Gateway │  Normalize, verify, tenant resolve         │
│              └─────────────────┘                                            │
│                        │                                                     │
│           events.inbound.{tenant}.{channel}                                 │
│                        ▼                                                     │
│              ┌─────────────────┐                                            │
│              │ Message-Router  │  Coalesce, interrupt, backpressure         │
│              └─────────────────┘                                            │
│                        │                                                     │
│           events.routed.{tenant}.{channel}                                  │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COGNITIVE LAYER                                    │
│                                                                              │
│                              FOCAL                                         │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Config Watcher                                │   │
│  │                                                                       │   │
│  │  - Subscribes to Redis pub/sub (cfg-updated)                         │   │
│  │  - Loads agent bundles into cache                                    │   │
│  │  - Invalidates stale configs                                         │   │
│  │  - TTL-based eviction per tenant/agent                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         Turn Pipeline                                 │   │
│  │                                                                       │   │
│  │  1. Load session state (Redis)                                       │   │
│  │  2. Parallel evaluation:                                             │   │
│  │     ├── Scenario Manager: track flow, transitions                    │   │
│  │     ├── Rule Matcher: semantic + keyword, scopes, priorities         │   │
│  │     └── Memory Retriever: vector + BM25 + graph                      │   │
│  │  3. Merge context                                                    │   │
│  │  4. Template check (EXCLUSIVE → skip LLM)                            │   │
│  │  5. Tool execution (pre-LLM tools)                                   │   │
│  │  6. LLM call (build prompt, generate)                                │   │
│  │  7. Enforcement (validate, regenerate, fallback)                     │   │
│  │  8. Tool execution (post-LLM tools)                                  │   │
│  │  9. Update state + log                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Storage (pluggable backends per store type):                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │
│  │  PostgreSQL  │ │    Neo4j     │ │    Redis     │ │   MongoDB    │      │
│  │  + pgvector  │ │              │ │              │ │  (optional)  │      │
│  │              │ │              │ │              │ │              │      │
│  │  - Rules     │ │  - Episodes  │ │  - Sessions  │ │  - Config    │      │
│  │  - Scenarios │ │  - Entities  │ │  - Agent cfg │ │  - Memory    │      │
│  │  - Templates │ │  - Relations │ │  - Rule fire │ │  - Audit     │      │
│  │  - Audit     │ │  - Embeddings│ │  - Variables │ │  (alt backend│      │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘      │
│                                                                              │
│  See docs/architecture/overview.md for full backend options per store type  │
│                                                                              │
└───────────────────────────────────────────────────────────────┬─────────────┘
                                                                │
                         events.outbound.{tenant}.{channel}     │
                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TOOL LAYER                                         │
│                                                                              │
│  Focal Tool Orchestrator                                                  │
│         │                                                                    │
│         ├── ToolHub (registry, schemas, activation)                         │
│         │                                                                    │
│         ├── Path A: Restate (durable, multi-step, compensation)             │
│         │   └── RabbitMQ → Celery workers                                   │
│         │                                                                    │
│         ├── Path B: Direct Celery (single-step, fast)                       │
│         │                                                                    │
│         └── Path C: MQ edges (partner integrations)                         │
│                                                                              │
│  Tool results flow back via:                                                │
│  - Sync: immediate return                                                   │
│  - Async: POST /internal/tool-results callback                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## What Focal Provides

| Capability | Implementation |
|------------|----------------|
| API Layer | Focal API + Session Router |
| Core Engine | Focal Core (Scenario, Rule, Memory, LLM) |
| Config Loading | Config Watcher (loads from Redis) |
| Framework | FastAPI + PostgreSQL + Redis |
| Session Storage | Redis (sessions) + Neo4j (memory) |

## Data Flow

### Inbound Message

```
1. Channel-Gateway receives message from WhatsApp/Slack/etc.
2. Normalizes to Envelope:
   {
     tenant_id, agent_id, channel, user_channel_id,
     message, timestamp, metadata
   }
3. Publishes to Redis stream: events.inbound.{tenant}.{channel}

4. Message-Router consumes:
   - Checks session state (idle/processing)
   - Coalesces rapid messages (debounce)
   - Sends interrupt if needed
   - Publishes to: events.routed.{tenant}.{channel}

5. Focal consumes:
   - Loads session state
   - Runs turn pipeline
   - Returns response
   - Publishes to: events.outbound.{tenant}.{channel}

6. Message-Router routes outbound to Channel-Gateway
7. Channel-Gateway sends via provider API
```

### Configuration Update

```
1. Admin UI: User edits Scenario/Rule/Template
2. Control API: Validates, writes to Supabase
3. Publisher (Restate workflow):
   - Compiles to bundle format
   - Writes versioned bundles to Redis
   - Atomic pointer swap: {tenant}:{agent}:cfg → N
   - Publishes cfg-updated

4. Focal Config Watcher:
   - Receives cfg-updated
   - Loads bundle from Redis
   - Updates local cache
   - Old sessions continue on old version (soft-pin)
   - New sessions use new version
```

## Tenant Isolation

Every layer enforces tenant isolation:

| Layer | Isolation Mechanism |
|-------|---------------------|
| Control API | Supabase RLS on `organization_id` |
| Redis Keys | Prefix: `{tenant_id}:{agent_id}:...` |
| Redis Streams | Per-tenant channels |
| PostgreSQL | `tenant_id` column + indexes |
| Neo4j | `group_id = {tenant_id}:{session_id}` on all nodes |
| Sessions | Namespaced: `session:{tenant}:{channel}:{user_id}` |
| Logs/Traces | `tenant_id` attribute on all spans |

## Cache Strategy

Focal uses **Redis with TTL-based eviction**:

### Agent Configuration Cache

```python
# Key pattern
agent_bundle:{tenant_id}:{agent_id}:v{version}

# TTL strategy
- Default: 1 hour
- On cfg-updated: invalidate immediately
- Per-tenant override: configurable
```

### Session State Cache

```python
# Key pattern
session:{tenant_id}:{channel}:{user_channel_id}

# TTL strategy
- Default: 30 days (configurable per tenant)
- Refresh on each message
- Explicit invalidation via API
```

### Rule Matching Cache

```python
# Embedding cache
embedding:{hash(text)}

# TTL: 24 hours
# Embeddings are immutable for same text

# Match result cache (optional)
match:{tenant}:{agent}:{hash(message)}

# TTL: 5 minutes (short—context changes)
```

## API Endpoints

### Message Handling

```
POST /v1/messages
  → Process message, return response
  → Used by message-router

POST /v1/messages/stream
  → SSE stream for real-time responses
```

### Session Management

```
GET  /v1/sessions/{session_id}
POST /v1/sessions
DELETE /v1/sessions/{session_id}
PATCH /v1/sessions/{session_id}  (update variables, force step)
```

### Configuration (if Focal manages directly)

```
# Scenarios
GET    /v1/agents/{agent_id}/scenarios
POST   /v1/agents/{agent_id}/scenarios
GET    /v1/agents/{agent_id}/scenarios/{id}
PUT    /v1/agents/{agent_id}/scenarios/{id}
DELETE /v1/agents/{agent_id}/scenarios/{id}

# Rules
GET    /v1/agents/{agent_id}/rules
POST   /v1/agents/{agent_id}/rules
GET    /v1/agents/{agent_id}/rules/{id}
PUT    /v1/agents/{agent_id}/rules/{id}
DELETE /v1/agents/{agent_id}/rules/{id}

# Templates
GET    /v1/agents/{agent_id}/templates
POST   /v1/agents/{agent_id}/templates
...

# Tools (read-only—managed by ToolHub)
GET    /v1/agents/{agent_id}/tools
GET    /v1/agents/{agent_id}/tools/{id}
```

### Internal (service-to-service)

```
POST /internal/tool-results
  → Async tool completion callback

POST /internal/cache/invalidate
  → Force cache invalidation

GET /internal/health
GET /internal/ready
GET /internal/metrics
```

## Compatibility with External Control Plane

Focal reads configuration from **Redis bundles** produced by an external publisher. The bundle format is:

```
Redis Keys:
  {tenant}:{agent}:cfg → {version}  (pointer)
  {tenant}:{agent}:v{version}:scenarios
  {tenant}:{agent}:v{version}:rules
  {tenant}:{agent}:v{version}:templates
  {tenant}:{agent}:v{version}:tools
  {tenant}:{agent}:v{version}:variables
```

### Bundle Schema (Focal-native)

```json
// {tenant}:{agent}:v{version}:scenarios
[
  {
    "id": "uuid",
    "name": "Return Process",
    "description": "...",
    "entry_step_id": "step-1",
    "steps": [
      {
        "id": "step-1",
        "name": "Identify Order",
        "transitions": [
          {"to_step_id": "step-2", "condition_text": "User provides order ID"}
        ],
        "template_ids": ["tmpl-1"],
        "rule_ids": ["rule-1"]
      }
    ]
  }
]

// {tenant}:{agent}:v{version}:rules
[
  {
    "id": "uuid",
    "name": "Refund Check",
    "condition_text": "User asks about refunds",
    "action_text": "Check order status before answering",
    "scope": "global",
    "priority": 10,
    "max_fires_per_session": 0,
    "cooldown_turns": 0,
    "attached_tool_ids": ["tool-1"],
    "embedding": [0.1, 0.2, ...]
  }
]
```

## Migration Path

### Phase 1: Deploy Focal in shadow mode
- Route subset of traffic to Focal
- Compare responses (shadow mode)
- Validate parity

### Phase 2: Gradual cutover
- Route 10% → 50% → 100% to Focal
- Monitor latency, error rates
- Keep legacy system as fallback

### Phase 3: Full migration
- Remove legacy adapters and services
- Remove legacy SDK dependencies
- Migrate session storage

## Docker Compose Example

```yaml
focal:
  build:
    context: ../..
    dockerfile: apps/focal/Dockerfile
  container_name: focal
  environment:
    # Database
    POSTGRES_URL: postgresql://postgres:password@postgres:5432/focal
    NEO4J_URL: bolt://neo4j:7687
    REDIS_URL: redis://redis:6379/0

    # LLM
    LLM_PROVIDER: anthropic  # or openai, cerebras, etc.
    LLM_API_KEY: ${ANTHROPIC_API_KEY}

    # Embedding
    EMBEDDING_PROVIDER: openai
    EMBEDDING_MODEL: text-embedding-3-small

    # Observability (integrates with kernel_agent's stack)
    # See docs/architecture/observability.md
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    OTEL_SERVICE_NAME: focal
    LOG_LEVEL: INFO
    FOCAL_OBSERVABILITY__LOG_FORMAT: json
    FOCAL_OBSERVABILITY__TRACING_SAMPLE_RATE: 0.1

    # Service
    ENVIRONMENT: development

  depends_on:
    postgres:
      condition: service_healthy
    neo4j:
      condition: service_healthy
    redis:
      condition: service_healthy
  ports:
    - "8800:8800"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8800/internal/health"]
    interval: 10s
    timeout: 5s
    retries: 10
  networks:
    - focal

neo4j:
  image: neo4j:5.15
  container_name: focal-neo4j
  environment:
    NEO4J_AUTH: neo4j/password
    NEO4J_PLUGINS: '["apoc"]'
  ports:
    - "7474:7474"  # Browser
    - "7687:7687"  # Bolt
  volumes:
    - neo4j_data:/data
  healthcheck:
    test: ["CMD", "neo4j", "status"]
    interval: 10s
    timeout: 5s
    retries: 10
  networks:
    - focal

volumes:
  neo4j_data:
```

## Key Architecture Principles

| Aspect | Focal Approach |
|--------|------------------|
| **State** | Redis + PostgreSQL (no in-memory state) |
| **Config updates** | Hot-reload via pub/sub |
| **Tenancy** | Native tenant_id everywhere |
| **Sessions** | Redis (cache) + PostgreSQL/MongoDB |
| **Rules** | Hybrid matching + scopes + priorities |
| **Scenarios** | API-defined state machines |
| **Memory** | Temporal knowledge graph |
| **Enforcement** | Post-generation validation |
| **Observability** | Structured logs + OTEL traces + Prometheus metrics |
| **Horizontal scale** | Trivial (stateless pods) |
