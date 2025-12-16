# kernel_agent Deep Dive (3rd Repo) — What It Adds, What To Reuse, What Conflicts

This document analyzes `/home/marvin/Projects/kernel_agent` and folds it into the SmartBeez ↔ Ruche integration story.

**Why this repo matters** (historically and practically):
- It is an earlier attempt at the same “multi-plane” platform architecture, built around **Parlant** as the brain.
- It contains the most concrete, production-shaped implementations of:
  - a **ToolHub** service (catalog + per-tenant activation + streaming execution)
  - a **Channel Gateway** service (webhooks normalization + dedup + outbound delivery worker)
  - a **Redis Streams contract** between ChannelGateway and a future MessageRouter
  - a **control-plane publish workflow** writing versioned bundles to Redis (pointer swap + invalidation)

Now that Parlant is no longer viable for the brain, `kernel_agent` is best treated as:
> a reference implementation of “channel + tool + config distribution”, with the brain swapped out for `soldier`’s ACF + FOCAL.

---

## 1) Repo Map (What Exists)

### 1.1 Services (apps/)

From `kernel_agent/README.md`:
- `kernel_agent/apps/control-api/` — control plane (authoring + compiler + publish workflow) (port 8003)
- `kernel_agent/apps/channel-gateway/` — multi-channel ingress + outbound worker (**implemented**) (placeholder in README, but code exists)
- `kernel_agent/apps/message-router/` — routing/coalescing/interrupt service (**docs only**, not implemented)
- `kernel_agent/apps/toolhub/` — tool catalog + execution (**implemented**) (port 8100)
- `kernel_agent/apps/parlant-adapter/` + `kernel_agent/apps/parlant-server/` — Parlant-specific runtime plane (historical; now mostly “brain adapter” reference)

### 1.2 Shared libs/

Notable shared components:
- `kernel_agent/libs/clients/redis/keys.py` — key patterns for bundles + pointers
- `kernel_agent/libs/messaging/redis_bus.py` — Redis Streams “MessageBus” abstraction (publish_raw, consumer groups, pending reclaim)
- `kernel_agent/libs/core/idempotency.py` — deterministic hash for compiled config apply dedupe
- `kernel_agent/libs/generated/smartbeez_toolhub/common.py` — tool wrapper helper (streaming tool execution; tenant resolution notes)

---

## 2) What kernel_agent Implements That Is Immediately Useful For soldier ↔ sb_agent_hub

### 2.1 ToolHub as a real service (stable tool IDs + streaming execution)

Tool execution endpoint:
- `kernel_agent/apps/toolhub/src/toolhub/api/execution.py`
  - `POST /execute-stream` returning `application/x-ndjson`
  - event types: `status`, `progress`, `final_result`, `error`

Execution orchestration:
- `kernel_agent/apps/toolhub/src/toolhub/services/execution.py`
  - validates tenant authorization via `tenant_tools` table
  - loads tool definition from `tools` table
  - provider dispatch via registry
  - writes execution logs to `execution_logs`

Tool identity scheme:
- **stable string** tool names like `gmail.send_email` (`toolhub/models/tool.py`, `toolhub_architecture.md`)

Why this matters for the soldier study:
- It matches the recommended “stable string tool identity” proposed earlier.
- It provides a concrete “ToolGateway-as-a-service” implementation that soldier can call from its runtime toolbox.

### 2.2 Channel Gateway as an actual ingress/outbound system (more complete than soldier runtime adapters)

Inbound webhook handling:
- `kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py`
  - signature verification for Meta
  - webchat token validation
  - dedup via Redis `SET NX` (see `services/deduplication.py`)
  - resolves channel config using Supabase + Redis cache (see `services/channel_resolver.py`)
  - publishes raw payload to Redis stream: `channel:inbound:{tenant_id}` (per contract)

Normalization:
- `kernel_agent/apps/channel-gateway/src/channel_gateway/models/envelope.py` defines a canonical `Envelope`
  - includes `attachments[]` and a typed sender identity model

Outbound delivery worker:
- `kernel_agent/apps/channel-gateway/src/channel_gateway/workers/outbound.py`
  - consumes outbound streams (e.g., `events.outbound.*`)
  - uses per-tenant rate limiting and provider senders
  - robust retry paths and token refresh handling

Why this matters:
- soldier’s docs say ChannelGateway/MessageRouter are external to the cognitive runtime; kernel_agent is concrete proof of that pattern.
- sb_agent_hub currently implements webchat + voice endpoints, but kernel_agent channel-gateway is much closer to the “enterprise channel gateway” shape (verification, dedup, normalization, outbound worker, rate limiting).

### 2.3 MessageRouter contract (even if not implemented)

Contract document:
- `kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`

Key points:
- transport: Redis Streams with consumer groups
- stream names: `channel:inbound:{tenant_id}` → `events.routed:{tenant_id}`
- session coordination keys: `session:{tenant}:{channel}:{user_channel_id}`, `pending:*`, `coalesce:*`
- interrupt protocol: Redis pub/sub `interrupt:{tenant}:{session_id}` and ack channel `interrupt_ack:*`

Why this matters:
- It overlaps heavily with soldier’s ACF goals (coalescing, interruption/supersede, backpressure), but uses different primitives.
- It must be reconciled: keep MessageRouter semantics external, or rely on ACF for “message ≠ turn” and supersede facts.

### 2.4 Control-plane publish workflow + Redis bundles (implemented patterns)

Publish workflow:
- `kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py`
  - validate → compile → apply → write bundles → swap pointer → invalidate cache → notify

Bundle writing + pointer swap:
- `kernel_agent/apps/control-api/src/control_api/publisher/bundle_writer.py`
- `kernel_agent/apps/control-api/src/control_api/publisher/pointer_manager.py`
- `kernel_agent/libs/clients/redis/keys.py` (key patterns)

This is a concrete instantiation of the “Redis bundles + soft pin” approach that soldier also describes in `docs/architecture/kernel-agent-integration.md`.

---

## 3) Where kernel_agent Conflicts With soldier (and What To Do About It)

### 3.1 “Brain adapter” expectations

kernel_agent runtime plane assumes a “brain service” with:
- session creation
- message sending
- event polling/streaming

See:
- `kernel_agent/apps/parlant-adapter/src/parlant_adapter/services/session_router.py`
  - stores session metadata in Redis (`session:{session_id}` + reverse `customer_session:*`)
  - pins sessions to agent version

If soldier replaces Parlant:
- sb_agent_hub / channel-gateway / message-router will call soldier’s `POST /v1/chat`/`/v1/chat/stream` or future ACF gateway.
- Session pinning needs to be defined in soldier’s SessionStore/config versioning story (soldier has docs; partial code).

### 3.2 Tool facade policy vs soldier side-effect policy

kernel_agent tool orchestration is framed as:
- Path A/B/C + sync/async mode per tool (`docs/target/Execution Pattern Decision.md`)

soldier tool semantics are framed as:
- side-effect policy (PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE) + commit point + ACFEvents (Toolbox spec + ACF architecture)

These can be reconciled, but **they are not the same vocabulary**:
- kernel_agent’s Path A/B/C is an execution topology choice (durable workflows vs direct vs MQ boundary)
- soldier’s side-effect policy is a semantic risk classification and supersede/commit decision driver

Integration implication:
- keep “execution topology choice” as configuration (can live in sb_agent_hub control plane)
- keep “side-effect semantics” as soldier toolbox responsibility
- allow a mapping layer: semantic policy → allowed execution modes (e.g., IRREVERSIBLE tools default to durable async path)

### 3.3 ChannelGateway vs MessageRouter: separate or same service?

kernel_agent and soldier docs treat them as distinct responsibilities:
- ChannelGateway: protocol normalization + verification + identity resolution + outbound delivery
- MessageRouter: routing/backpressure + session coordination + coalescing + interrupt signaling

Your preference (“they’re the same for me”) is viable as a deployment choice:
- One scalable service can host both modules behind separate internal components.
But the study must preserve the conceptual split because:
- “protocol correctness” and “routing/backpressure/state coordination” scale differently
- you may want to scale them independently later, even if initially deployed together

This is captured as an explicit decision in `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md`.

---

## 4) What To Port/Reuse (Recommended)

### 4.1 Reuse: kernel_agent ToolHub design (service boundary + NDJSON)

Even if sb_agent_hub remains the “control plane + UI”, the ToolHub shape from kernel_agent is directly reusable:
- stable tool IDs
- per-tenant activation state machine
- streaming execution events
- provider abstraction (Composio + custom)

Recommended integration direction:
- soldier ToolGateway provider → calls ToolHub `/execute-stream`
- sb_agent_hub owns ToolDefinition/activation publishing to ToolHub

### 4.2 Reuse: kernel_agent Channel Gateway patterns (verification, dedup, envelope)

Even if sb_agent_hub keeps channel endpoints, porting these patterns improves production readiness:
- webhook signature verification + retries
- dedup via Redis SETNX
- canonical envelope model with attachments + sender identity
- outbound worker pattern (consumer groups + rate limiting + sender registry)

### 4.3 Reuse: Redis Streams contract for channel ingestion (if you want true decoupling)

If you want ChannelGateway/Router as scalable services, kernel_agent’s contract is a ready baseline.
But you must decide how it interacts with ACF:
- either MessageRouter does coalescing/interrupt and sends “already coalesced messages” to soldier
- or soldier ACF owns turn aggregation and supersede, and MessageRouter becomes primarily routing/backpressure

---

## 5) Concrete Updates Needed in the Smartbeez ↔ Ruche Study

This repo changes the integration study in four concrete ways:

1) **Tool identity**: kernel_agent proves stable string tool names are the practical cross-service key.
2) **Tool execution service**: kernel_agent provides a complete ToolHub service; soldier’s ToolGateway can target it instead of duplicating.
3) **Channel gateway implementation**: kernel_agent channel-gateway is closer to the “external gateway” soldier docs want than soldier’s internal adapters.
4) **Router vs ACF overlap**: kernel_agent’s MessageRouter contract overlaps with ACF; you must decide where “coalescing/interrupt/supersede” lives.

Those decisions are tracked in:
- `docs/Smartbeez_Integration_Study/09_integration_decision_questions.md`

