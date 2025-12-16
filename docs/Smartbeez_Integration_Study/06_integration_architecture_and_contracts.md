# Integration Architecture + Contracts (Smartbeez ↔ Ruche)

This document defines the **recommended target architecture** and the **concrete contracts** between:

- `sb_agent_hub` (SmartBeez Agent Hub) as **Control Plane + Channel Layer**
- `soldier` (Ruche runtime + ACF + brains) as **Cognitive/Runtime Layer**

It is written to be implementable incrementally, starting from what exists today in both repos.

---

## 0) Summary (Decisions This Doc Implies)

1) **Boundary**: `sb_agent_hub` owns channel protocol handling + auth + tenant resolution; `soldier` owns conversation orchestration (ACF) + brains + tool semantics.
2) **Ingress contract**: `sb_agent_hub → soldier` uses a stable envelope equivalent to `soldier`’s `POST /v1/chat` / `POST /v1/chat/stream` today, evolving toward the multimodal envelope in `docs/architecture/api-layer.md`.
3) **Streaming contract**: `sb_agent_hub` keeps AG‑UI SSE for the browser and maps `soldier` streaming outputs/events into AG‑UI events.
4) **Tools contract**: `soldier` decides *if/when* tools run (semantics), `sb_agent_hub` can execute tools (ecosystem integrations) via a ToolGateway provider boundary.
5) **Config contract**: `sb_agent_hub` is the system of record for agent revisions/config and publishes bundles to `soldier` (push or pull).

---

## 1) Target Integration Architecture (Recommended)

This mirrors `soldier/docs/architecture/kernel-agent-integration.md` and `soldier/docs/architecture/architecture_reconsideration.md`, and matches what `sb_agent_hub` already implements operationally.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         sb_agent_hub (SmartBeez)                            │
│                                                                            │
│  Control Plane                                                              │
│  - auth (WorkOS/Supabase)                                                   │
│  - org/tenant resolution                                                    │
│  - agent specs + revisions + publishing                                     │
│  - tool catalog / connected accounts (future ToolHub)                       │
│                                                                            │
│  Channel Layer (ChannelGateway + MessageRouter semantics)                    │
│  - webchat (CopilotKit / AG‑UI SSE)                                         │
│  - voice webhooks (VAPI/Twilio)                                             │
│  - websocket chat                                                          │
│  - routing/backpressure                                                     │
│                                                                            │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │  (trusted service-to-service)
                                ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                             soldier (Ruche)                                 │
│                                                                            │
│  Cognitive / Runtime Layer                                                  │
│  - ACF: mutex, aggregation, supersede facts, orchestration, ACFEvents        │
│  - AgentRuntime / AgentContext                                               │
│  - Brains (FOCAL alignment brain, LangGraph, …)                              │
│  - Toolbox: tool semantics + audit events                                    │
│  - Stores (Config/Session/Memory/Audit)                                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Why this boundary is “clean”

- `soldier` docs explicitly want **ChannelGateway/MessageRouter external** to the cognitive runtime.
- `sb_agent_hub` already has the *right “product surface”* for that: frontends, auth, and real channel protocols.
- The cognitive layer can be scaled/hardened independently once the contract is stable.

---

## 2) Contract Surfaces (What Must Be Defined)

1) **Ingress envelope**: how `sb_agent_hub` submits inbound user/voice events to `soldier`
2) **Streaming**: how `soldier` returns incremental output (tokens + lifecycle)
3) **Events**: how `soldier` emits ACFEvents and how `sb_agent_hub` consumes them (UI, audit feed, webhooks)
4) **Tools**: how `soldier` requests tool execution (or executes via gateway) and how results flow back
5) **Config publishing**: how agent config/tool defs/channel policy move from `sb_agent_hub` (SoT) to `soldier`
6) **Security & identity**: tenant/user mapping, auth between services, secret boundaries
7) **Observability**: trace/context propagation across services

### Note: kernel_agent already implemented parts of these contracts

`/home/marvin/Projects/kernel_agent` contains concrete implementations for:
- ToolHub (catalog + per-tenant activation + NDJSON streaming execution): `kernel_agent/apps/toolhub/`
- ChannelGateway (webhook verification + normalization + dedup + outbound worker): `kernel_agent/apps/channel-gateway/`
- Redis Streams contract between ChannelGateway and a future MessageRouter: `kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`

When deciding what to build next in sb_agent_hub/soldier, treat kernel_agent as:
- a reference design for “external scalable services”
- a source of reusable patterns (stable tool IDs, envelope model, Redis-stream ingestion, pointer swaps)

---

## 3) Ingress Envelope Contract (sb_agent_hub → soldier)

### 3.1 MVP contract (works with soldier today)

Use the existing `soldier` endpoints:
- `POST /v1/chat`
- `POST /v1/chat/stream`

And the existing payload shape:
- `ruche/api/models/chat.py::ChatRequest`

Minimal request fields:
```json
{
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "channel": "webchat|voice|slack|…",
  "user_channel_id": "string",
  "message": "string",
  "session_id": "uuid-or-null",
  "metadata": {}
}
```

**Tenant resolution**: happens in `sb_agent_hub`. `soldier` should treat `tenant_id`/`agent_id` as already resolved (aligned with `docs/architecture/api-layer.md`), but note that `soldier` currently still requires JWT auth middleware (`ruche/api/middleware/auth.py`).

### 3.2 Target contract (matches soldier’s API-layer spec)

Move toward the multimodal envelope described in `soldier/docs/architecture/api-layer.md`:
- `content_type`
- `content.text`, `content.media[]`, `content.location`, `content.structured`
- `provider_message_id`
- `received_at`
- explicit idempotency key

This can remain a REST JSON contract; AG‑UI stays **above** it (front-end protocol).

### 3.5 Alternative ingress transport (if you want a MessageRouter/ChannelGateway service)

If you want the “channel gateway + router” to be a horizontally scalable service (your preference), `kernel_agent` already defines a concrete transport:
- ChannelGateway publishes raw inbound events to Redis Streams `channel:inbound:{tenant_id}`
- MessageRouter consumes, coalesces/interrupts, then publishes normalized envelopes to `events.routed:{tenant_id}`

That contract is defined in:
- `kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`

In that model, sb_agent_hub can remain the UI/control plane, while the channel+router layer is deployed as services.
However, you must decide how coalescing/interrupt interacts with soldier’s ACF (see §5 and the decision sheet).

### 3.3 Field mapping from sb_agent_hub (webchat / AG‑UI)

`sb_agent_hub` AG‑UI request model (see `sb_agent_hub/3-backend/app/api/user/ag_ui_langgraph.py`) includes:
- `messages[]`, `thread_id`, `run_id`

Recommended mapping:
- `thread_id` → `session_id` (store mapping; if absent, let `soldier` create and then persist mapping)
- `run_id` → correlation only (maps well to `turn_id`/`logical_turn_id`, but doesn’t need to be 1:1)
- `messages[-1].content` (last user message) → `message`
  - if you want full conversation context, it must be provided as config/brain input; **do not** blindly concatenate long history at the channel layer.

### 3.4 Idempotency keys

Channel providers frequently retry webhooks / messages. Recommended:
- Pass upstream message id as `Idempotency-Key` header when calling `soldier`
  - webchat: client-generated message uuid
  - voice: provider event id or transcript segment id
  - slack/whatsapp: provider message id

Note: `soldier` currently has TODOs for request idempotency at `/v1/chat` (`ruche/api/routes/turns.py`), but its toolbox/tool idempotency story is much richer (ACF docs).

---

## 4) Streaming Contract (soldier → sb_agent_hub → browser)

### 4.1 MVP: map soldier SSE to AG‑UI SSE

What `soldier` emits today:
- `POST /v1/chat/stream` returns SSE events: `token`, `done`, `error`
  - currently “simulated streaming” (split words), not true model streaming

What the browser expects (sb_agent_hub AG‑UI):
- `RUN_STARTED`, `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CHUNK`, `TEXT_MESSAGE_END`, `RUN_FINISHED`, `RUN_ERROR` (+ optional `TOOL_CALL_CHUNK`)

Recommended mapping:

| soldier SSE event | Payload | sb_agent_hub emits to AG‑UI |
|---|---|---|
| (request start) | N/A | `RUN_STARTED(thread_id, run_id)` |
| `token` | `{"content":"…"}` | `TEXT_MESSAGE_START` (once), then `TEXT_MESSAGE_CHUNK(delta)` for each token |
| `done` | `{"turn_id":"…","session_id":"…",…}` | `TEXT_MESSAGE_END`, then `RUN_FINISHED` |
| `error` | `{"code":"…","message":"…"}` | `RUN_ERROR(message=…)` |

Practical notes:
- AG‑UI `message_id` can be derived from `run_id` or from `turn_id` once available.
- `thread_id` should remain stable across the browser session; if it’s not stable, keep a server-side mapping to `soldier.session_id`.

### 4.2 Target: stream tokens *and* runtime events

Once `soldier`’s ACF/Toolbox wiring is the main execution path (vs the current alignment engine endpoint), the stream should carry:

1) **assistant output** (token chunks)
2) **ACFEvents** (`turn.*`, `tool.*`, `session.*`, …)

Two common ways to do this:
- **Single SSE stream** with multiple event names (`token`, `acf_event`, `done`)
- **Two streams**: one token stream for the UI, one event stream for activity feeds/observability

The soldier docs explicitly keep “AG‑UI mapping in channel adapters” (`docs/architecture/event-model.md`), so it is consistent for `sb_agent_hub` to remain the adapter that maps ACFEvents → AG‑UI.

---

## 5) Event Contract (ACFEvents) + Delivery Strategy

### 5.1 Canonical event model (soldier)

`soldier` defines:
- `ruche/runtime/acf/events.py::ACFEventType` and `ACFEvent`
- `ruche/runtime/acf/event_router.py` routes events by patterns (`turn.*`, `tool.executed`, `*`, …)
- `soldier/docs/architecture/event-model.md` defines payload expectations

### 5.2 How sb_agent_hub should consume events (options)

**Option A — soldier → sb_agent_hub webhooks**
- soldier emits ACFEvents to an internal webhook endpoint in sb_agent_hub
- sb_agent_hub persists to its audit stream + fan-out to UI

Pros: simple, works cross-network.  
Cons: backpressure/retries are harder; ordering isn’t guaranteed unless designed.

**Option B — sb_agent_hub subscribes to soldier SSE**
- soldier exposes `GET /v1/events/stream?session_id=…` (or similar)
- sb_agent_hub proxies/consumes and stores

Pros: natural for UIs, fewer moving parts.  
Cons: connection management.

**Option C — shared message bus (NATS/Redis Streams/Kafka)**
- soldier publishes `events.outbound` and `events.acf` topics
- sb_agent_hub consumes as the “platform hub”

Pros: best for fan-out + replay.  
Cons: more infra.

**Recommendation**:
- MVP: Option A or B (whichever is fastest in your deployment environment)
- Long-term: Option C once you want enterprise-grade auditing, replay, and multi-consumer event processing

---

## 6) Tool Execution Contract (soldier ↔ sb_agent_hub)

### 6.1 The split to preserve

From `soldier/docs/acf/architecture/TOOLBOX_SPEC.md` + `ACF_ARCHITECTURE.md`:
- **Toolbox** owns semantics (policy, confirmation gating, side-effect records, audit events)
- **ToolGateway** owns execution mechanics (provider adapters + idempotency)

For integration:
- `sb_agent_hub` is the natural home for “integration execution” (Composio/MCP/connected accounts).
- `soldier` should remain the place where tool calls are *decided and constrained* (alignment + safety semantics).

### 6.2 Minimal request/response schema (sync execution)

The contract should be “tool call” oriented, not “LangChain tool” oriented.

**ToolExecutionRequest**
```json
{
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "session_id": "uuid",
  "turn_id": "uuid-or-string",
  "tool_name": "crm.create_ticket",
  "arguments": { "subject": "...", "priority": "..." },
  "idempotency_key": "string",
  "side_effect_policy": "PURE|IDEMPOTENT|COMPENSATABLE|IRREVERSIBLE",
  "requested_at": "iso8601",
  "context": {
    "channel": "webchat",
    "channel_user_id": "string",
    "actor_user_id": "uuid-or-null"
  }
}
```

**ToolExecutionResult**
```json
{
  "status": "success|error",
  "tool_name": "crm.create_ticket",
  "idempotency_key": "string",
  "output": { "ticket_id": "..." },
  "error": { "code": "…", "message": "…" },
  "metadata": { "provider": "composio", "latency_ms": 1234 }
}
```

### 6.3 Async execution (durable tools)

For long-running tools, use an explicit async shape:

- `soldier → sb_agent_hub`: enqueue tool execution request
- `sb_agent_hub → soldier`: callback `POST /internal/tool-results` with `idempotency_key` and result

This aligns with both repos’ stated intent:
- `soldier` wants durable orchestration at the runtime layer (ACF + Hatchet)
- `sb_agent_hub` docs discuss durable workers/queues and tool sandboxing

### 6.4 Tool identity and versioning

To avoid the current tool-ID mismatch between repos:
- Use **stable string identities** as the cross-service key (e.g., `crm.create_ticket`)
- Treat UUIDs as internal storage identifiers only
- Include optional `tool_revision`/`schema_hash` when you need strict compatibility

### 6.5 Practical execution service option (kernel_agent ToolHub)

If you want ToolHub/ToolGateway to be an external scalable service, `kernel_agent` already implements:
- `POST /execute-stream` returning `application/x-ndjson` events (`status/progress/final_result/error`)
  - `kernel_agent/apps/toolhub/src/toolhub/api/execution.py`

This maps cleanly to soldier’s ToolGateway concept:
- soldier ToolGateway provider calls ToolHub for execution (mechanics)
- soldier Toolbox enforces semantics (policy + audit events + idempotency keys)

---

## 7) Config Publishing Contract (sb_agent_hub → soldier)

### 7.1 What must be publishable

At minimum, to run an agent in `soldier`, it needs:
- brain selection + brain configuration
- scenarios/rules/templates/variables (FOCAL-specific config)
- tool definitions + tool activations
- channel policies + bindings

In sb_agent_hub terms, this is “agent revision/manifest”.

### 7.2 Publishing mechanisms (choose one)

**A) Push bundles to soldier (HTTP)**
- `sb_agent_hub` posts compiled bundles to a soldier internal endpoint
- soldier stores in ConfigStore and invalidates caches

**B) Publish bundles to Redis (shared infra)**
- `sb_agent_hub` is the publisher; soldier runs a watcher
- matches `soldier/docs/architecture/kernel-agent-integration.md`

**C) Pull bundles from sb_agent_hub**
- soldier requests bundles on demand from sb_agent_hub
- simplest operationally if sb_agent_hub is always reachable and fast

Recommendation:
- MVP: (A) or (C) depending on deployment constraints
- Long-term: (B) for scalable config distribution

### 7.3 Versioning rules

To preserve correctness with “hot reload”:
- bundles are immutable and versioned (`revision_id`, `hash`, or incrementing version)
- sessions can be **soft-pinned** to a config version
- new sessions use newest version by default

---

## 8) Security + Identity Contract

### 8.1 Tenant ID mapping

`sb_agent_hub` uses `organization_id`; `soldier` uses `tenant_id`.

Recommended:
- Treat them as the same UUID (1:1 mapping) to reduce translation risk.

### 8.2 Service-to-service auth

`soldier` currently validates JWT locally using `RUCHE_JWT_SECRET` (`ruche/api/middleware/auth.py`).

Pragmatic integration:
- `sb_agent_hub` calls `soldier` with an **internal** Bearer token signed with `RUCHE_JWT_SECRET`
  - claims: `tenant_id`, optional `sub` (user_id), optional `roles`
- Do not forward end-user Supabase tokens directly to `soldier` unless you intentionally align auth stacks.

Hardening options:
- mTLS between services
- separate “internal audience” JWT with narrow scopes (only ingress + tool callbacks)

### 8.3 Tenant isolation and validation

Integration must enforce:
- the caller’s tenant in the token matches `tenant_id` in the request body
- no cross-tenant session access

`soldier` does not currently enforce the token/body match on `/v1/chat` (it only requires auth presence). This should be treated as a gap to close in the integration work plan.

---

## 9) Observability Contract (Tracing + Correlation)

To keep runs traceable across repos:
- propagate W3C `traceparent` headers from browser → sb_agent_hub → soldier (and back)
- ensure both services log correlation IDs (`tenant_id`, `agent_id`, `session_id`, `turn_id/run_id`)

Where possible:
- ACFEvents should include the same routing identifiers used in `sb_agent_hub`’s audit stream.

---

## 10) Compatibility Strategy (How to Integrate Without Waiting for Refactors)

### Phase 1 — Webchat “brain swap” MVP

- Keep CopilotKit + AG‑UI SSE endpoints in `sb_agent_hub`
- Replace the internal LangGraph execution with a call to `soldier /v1/chat/stream`
- Translate soldier token/done/error SSE to AG‑UI events

This proves:
- auth + routing + session mapping
- streaming UX

### Phase 2 — Add tool execution bridging

- Teach soldier to emit canonical tool lifecycle events (`tool.authorized/executed/failed`) as ACFEvents
- Add a ToolGateway provider in soldier that calls sb_agent_hub for execution (or enqueue + callback)

### Phase 3 — Adopt ACF as the primary runtime path

- Route all channel ingress to soldier’s ACF turn gateway (LogicalTurn semantics, supersede)
- Move alignment brain calls behind ACF’s “Brain” interface

This is where soldier’s “message ≠ turn” architecture starts paying off for voice and multi-message aggregation.
