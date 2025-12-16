# Gap Analysis + Work Plan (Smartbeez ↔ Ruche)

This document turns the study findings into a **prioritized, implementable work plan** to integrate `sb_agent_hub` and `soldier` without creating a third “half system”.

It assumes the boundary in `docs/Smartbeez_Integration_Study/06_integration_architecture_and_contracts.md`:
- `sb_agent_hub` = Control Plane + Channel Layer
- `soldier` = Cognitive/Runtime Layer

---

## 0) Readiness Snapshot (What Works / What Doesn’t)

| Surface | Current status | Why |
|---|---|---|
| Webchat streaming | **Partial / MVP-ready** | `sb_agent_hub` already speaks AG‑UI SSE; `soldier` has `/v1/chat/stream` but it’s simulated streaming |
| Ingress envelope | **Partial** | `soldier` API expects `ChatRequest`; multimodal envelope is documented but not implemented as the primary path |
| Events (ACFEvent) | **Partial** | `soldier` has ACFEvent model + EventRouter, but tool/runtime code doesn’t consistently emit canonical ACFEvents |
| Tools execution | **Partial** | `soldier` has runtime toolbox + ToolGateway, but has drift/duplication and no real ToolDefinition SoT; `sb_agent_hub` tool execution is largely placeholder |
| ChannelGateway/MessageRouter | **Partial** | `sb_agent_hub` has channel endpoints; `soldier` expects upstream routing; “router/backpressure” is not a first-class implemented subsystem in either |
| Config publishing (bundles) | **Missing (as integration path)** | both repos describe it; neither has a stable cross-repo bundle contract implemented end-to-end |
| Auth between services | **Partial** | `soldier` requires JWT with `tenant_id` claim; `sb_agent_hub` uses Supabase/WorkOS tokens; no explicit service-to-service token pattern is implemented |

---

## 1) Gaps That Block Integration (Highest Priority)

### 1.1 Streaming protocol mismatch (AG‑UI vs soldier SSE)

- `sb_agent_hub` expects AG‑UI events (see `sb_agent_hub/3-backend/app/api/user/ag_ui_langgraph.py`)
- `soldier` emits SSE events (`token|done|error`) from `ruche/api/routes/turns.py`

**Impact**: you need a translation layer, otherwise frontends must change.

**Work**: Implement a “soldier runtime adapter” inside `sb_agent_hub` that:
- maps AG‑UI input → `soldier` `ChatRequest`
- maps `soldier` SSE → AG‑UI SSE

### 1.2 Tool model mismatch inside soldier (string IDs vs UUIDs; dual tool stacks)

Soldier currently has at least three overlapping “tool universes”:

- Runtime toolbox models (UUID ToolDefinition/ToolActivation): `ruche/runtime/toolbox/models.py`
- Brain-level ToolHub references (string `tool_id`): `ruche/brains/focal/models/tool_binding.py`, `ruche/brains/focal/models/tool_activation.py`, API `ruche/api/routes/tools.py`
- Legacy/infrastructure toolbox stubs (string IDs): `ruche/infrastructure/toolbox/*`

**Impact**: even if sb_agent_hub provides a ToolHub, soldier has no single place to “plug it in”.

**Work**: pick a cross-service tool identity scheme (recommended: stable string ids like `crm.create_ticket`) and converge soldier’s runtime to it (or provide an explicit mapping layer).

**New evidence from `kernel_agent`**:
- ToolHub is already built around stable string IDs (e.g., `gmail.send_email`) and per-tenant activation:
  - `kernel_agent/apps/toolhub/src/toolhub/models/execution.py`
  - `kernel_agent/docs/target/toolhub_architecture.md`
So the “stable string ID” choice is not theoretical; it matches an existing implementation you already wrote.

### 1.3 Tool event emission mismatch (Toolbox → ACFEvents)

- ACF expects `FabricTurnContext.emit_event(event: ACFEvent)` (see `ruche/runtime/acf/models.py`)
- EventRouter routes canonical types (see `ruche/runtime/acf/events.py`, `ruche/runtime/acf/event_router.py`)
- Runtime toolbox currently emits ad-hoc string event types (`TOOL_SIDE_EFFECT_*`) (see `ruche/runtime/toolbox/toolbox.py`)

**Impact**: you can’t reliably drive UI/audit/events from tool execution yet.

### 1.4 Side-effect policy enum drift

- Toolbox spec/runtime toolbox: `PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE` (`ruche/runtime/toolbox/models.py`)
- ACF side-effect storage enum: `REVERSIBLE/IDEMPOTENT/IRREVERSIBLE` (`ruche/runtime/acf/models.py`)

**Impact**: ambiguity around commit points, compensation semantics, and event payload normalization.

### 1.5 ChannelPolicy “single source of truth” not implemented

Docs (channel capability topic + ACF architecture) say ChannelPolicy comes from config and is shared across:
- ACF
- AgentRuntime/AgentContext
- ChannelGateway

But runtime code:
- returns empty policies (`ruche/runtime/agent/runtime.py`)
- uses adapter defaults (`ruche/runtime/channels/gateway.py`)
- uses hardcoded defaults (`ruche/runtime/acf/turn_manager.py`)

**Impact**: channel behavior is inconsistent and can’t be centrally managed from sb_agent_hub control plane.

**Related kernel_agent implementation**:
- `kernel_agent/apps/channel-gateway/` demonstrates a concrete “channel config lookup + caching” pattern:
  - Supabase lookup RPC + Redis cache: `kernel_agent/apps/channel-gateway/src/channel_gateway/services/channel_resolver.py`
This is a candidate to port into sb_agent_hub (or to deploy as a separate ChannelGateway service).

---

## 2) Gaps That Don’t Block MVP (But Will Bite Quickly)

### 2.1 Request idempotency at the message-ingress boundary

- soldier `/v1/chat` has TODOs for Idempotency-Key enforcement (`ruche/api/routes/turns.py`)
- channel providers retry aggressively (webhooks/voice)

**Impact**: duplicated turns, duplicated tools, duplicated side effects.

### 2.2 Auth trust boundary is not explicit

- soldier requires a JWT but does not currently enforce that JWT tenant matches the request body (`ruche/api/middleware/auth.py` + `ruche/api/routes/turns.py`)
- sb_agent_hub uses Supabase/WorkOS tokens which soldier cannot validate without sharing secret/issuer assumptions

**Impact**: tenant leakage risk and brittle deployment.

### 2.3 Webhook system exists in soldier but isn’t wired to events

- `ruche/api/webhooks/*` exists (models, dispatcher, routes)
- nothing subscribes it to `EventRouter`

**Impact**: harder to integrate run state and side-effect audit into sb_agent_hub UI/admin features.

### 2.4 sb_agent_hub runtime uses in-memory “active_instances”

- `sb_agent_hub/3-backend/app/services/agent_runtime_service.py` stores active instances in memory

**Impact**: this conflicts with soldier’s “stateless pods” principle; it’s OK for channel layer/websockets, but not for runtime/cognitive state if sb_agent_hub is expected to scale horizontally.

---

## 3) Decision Points (Must Choose To Avoid Duplication)

These are “forks” that determine the simplest integration path.

1) **ToolDefinitions system of record**
   - Recommended: `sb_agent_hub` (control plane) is SoT and publishes tool defs; soldier consumes and enforces semantics.

2) **Tool execution location**
   - Recommended: default to `sb_agent_hub` executing (Composio/MCP/connected accounts), with soldier requesting execution via ToolGateway provider.
   - Alternate: soldier executes directly (then sb_agent_hub only configures); only works if soldier hosts all connector infra.

3) **Event transport**
   - MVP: SSE/webhook between services
   - Long-term: message bus (NATS/Redis Streams/Kafka), aligned with sb_agent_hub platform docs

4) **Do we integrate on soldier’s current `/v1/chat` or wait for ACF turn gateway?**
   - Recommended: MVP uses `/v1/chat/stream` now; parallel effort migrates soldier to ACF-managed execution later.

---

## 4) Work Plan (Prioritized Phases)

### Phase 1 — Webchat MVP “brain swap” (Fastest value)

**Goal**: Keep CopilotKit/AG‑UI frontend unchanged; swap the backend execution from LangGraph → soldier.

**sb_agent_hub tasks**
- [ ] Implement a `SoldierClient` (HTTP client) that calls `soldier POST /v1/chat/stream`
- [ ] Implement an AG‑UI adapter endpoint that:
  - [ ] accepts AG‑UI input (`messages`, `thread_id`, `run_id`)
  - [ ] builds `soldier` `ChatRequest`
  - [ ] proxies/transforms soldier SSE (`token|done|error`) → AG‑UI SSE events
- [ ] Persist mapping `thread_id ↔ soldier.session_id` if you need stable threads across reconnects
- [ ] Emit/record basic audit events in sb_agent_hub (run started/finished, latency, errors)

**soldier tasks**
- [ ] Decide service-to-service auth mechanism (see Phase 1 security tasks below)
- [ ] Enforce token/body tenant match on `/v1/chat` and `/v1/chat/stream` (security correctness for integration)
- [ ] (Optional for MVP) make `/v1/chat/stream` do true model streaming instead of word-splitting

**Acceptance criteria**
- CopilotKit UI works against the new runtime without frontend changes
- Session continuity works (thread ↔ session mapping)
- No auth regressions

**Optional accelerator from kernel_agent**
- If you want an external “channel gateway” service rather than direct sb_agent_hub endpoints, kernel_agent already contains:
  - webhook verification + normalization + dedup + outbound worker: `kernel_agent/apps/channel-gateway/`
But MessageRouter is only documented (not implemented), so this is best treated as a pattern source rather than a drop-in.

### Phase 1b — Service-to-service security baseline (do alongside Phase 1)

**Goal**: sb_agent_hub calls soldier as a trusted peer.

**Recommended approach**
- sb_agent_hub signs a short-lived JWT for soldier, using `RUCHE_JWT_SECRET` (or a dedicated internal secret)
- claims: `tenant_id`, optional `sub=user_id`, optional `roles`

**Tasks**
- [ ] sb_agent_hub: implement token minting for soldier calls (do not forward Supabase end-user tokens)
- [ ] soldier: validate required claims and enforce tenant match with request body

### Phase 2 — Event plumbing (ACFEvents into sb_agent_hub)

**Goal**: sb_agent_hub can drive UI activity feeds, tool timelines, and admin observability from runtime events.

**soldier tasks**
- [ ] Standardize event emission to canonical `ACFEvent` for:
  - [ ] turn lifecycle
  - [ ] tool lifecycle
- [ ] Wire `ruche/api/webhooks/*` into `EventRouter` (or expose SSE events stream)

**sb_agent_hub tasks**
- [ ] Create an internal “runtime event ingest” endpoint/consumer (webhook or SSE client)
- [ ] Store events in sb_agent_hub audit tables (or forward to its event bus)

**Acceptance criteria**
- sb_agent_hub UI can show “run timeline”: turn started → tool authorized/executed → response

### Phase 3 — Tool execution bridging (ToolGateway join point)

**Goal**: soldier requests tool execution; sb_agent_hub executes in its integration ecosystem; soldier records semantics and side effects.

**soldier tasks**
- [ ] Resolve tool-ID identity scheme (recommended: stable string IDs at integration boundary)
- [ ] Resolve ToolDefinition SoT and implement soldier-side consumption (bundle/API)
- [ ] Fix toolbox ↔ ACF event emission mismatch
- [ ] Fix idempotency interface mismatch (`ruche/runtime/toolbox/gateway.py` vs `ruche/runtime/idempotency/*`)
- [ ] Resolve side-effect policy mapping (COMPENSATABLE vs REVERSIBLE) and document the canonical mapping
- [ ] Implement a ToolGateway provider that calls sb_agent_hub “tool executor” endpoint (sync + async)

**sb_agent_hub tasks**
- [ ] Implement ToolExecutor API that can execute a tool by `tool_name` with args under an org’s connected accounts
- [ ] Integrate Composio/MCP gradually (start with 1–2 real tools)
- [ ] Return results in a deterministic schema (success/error + metadata)

**Alternative: reuse kernel_agent ToolHub directly**
- ToolHub already exists as a standalone service with:
  - per-tenant activation checks
  - Composio provider integration
  - NDJSON execution streaming
- If you keep it, the work becomes:
  - soldier ToolGateway provider → call ToolHub `/execute-stream`
  - sb_agent_hub control plane → manage ToolHub tool catalog + tenant activation state

**Acceptance criteria**
- A tool call requested by soldier results in an executed action in sb_agent_hub and a `tool.executed` ACFEvent, with correct idempotency behavior.

### Phase 4 — Voice channel integration (ACF message accumulation value)

**Goal**: voice transcript events become proper “messages” and are accumulated into logical turns.

**sb_agent_hub tasks**
- [ ] Convert voice provider webhook events → soldier ingress envelope (`channel="voice"`, stable `user_channel_id`)
- [ ] Decide partial vs final transcript handling; align with soldier ACF’s “message ≠ turn”

**soldier tasks**
- [ ] Ensure ACF turn aggregation handles multi-message cadence well for voice
- [ ] Ensure commit point semantics work when voice continues while tools run

### Phase 5 — Config bundle publishing (real control plane)

**Goal**: agent revisions in sb_agent_hub become runtime bundles in soldier, with safe hot reload.

**sb_agent_hub tasks**
- [ ] Define bundle schema (agent revision → brain config + rules/scenarios/templates + tools + channel policy)
- [ ] Implement publisher (HTTP push / shared Redis / pull API)

**soldier tasks**
- [ ] Implement bundle ingestion into ConfigStore
- [ ] Implement cache invalidation and “soft pin” by session/config_version

---

## 5) Deprecation / Consolidation Targets (Avoid Permanent Duplication)

These are not required for MVP, but leaving them unresolved makes later work harder:

- soldier:
  - `ruche/infrastructure/toolbox/*` (legacy/stub) vs `ruche/runtime/toolbox/*` (real implementation)
  - `ruche/infrastructure/channels/*` (legacy/stub) vs `ruche/runtime/channels/*`
  - brain tool models (`ruche/brains/focal/models/*tool*`) vs runtime toolbox models

Recommendation: explicitly mark one path as canonical (runtime packages) and treat the others as deprecated until removed.

---

## 6) Minimal “MVP Integration” Checklist (Single Page)

If you do nothing else, this is the smallest integration that proves the boundary:

- [ ] sb_agent_hub: AG‑UI endpoint proxies to soldier `/v1/chat/stream`
- [ ] sb_agent_hub: stable thread ↔ session mapping
- [ ] sb_agent_hub: internal service token for soldier calls
- [ ] soldier: enforce tenant token/body match
- [ ] soldier: reliable SSE streaming (even if coarse-grained)
