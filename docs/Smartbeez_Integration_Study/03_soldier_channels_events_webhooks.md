# soldier Deep Dive: Channels + Events (ChannelGateway / MessageRouter / ACFEvent / Webhooks)

## 1) Canonical Intent in soldier (Docs)

The channel/event story in `soldier` is spread across:

- `docs/architecture/channel-gateway.md` (**PROPOSED**) — external ChannelGateway + adapters + identity linking
- `docs/acf/architecture/topics/10-channel-capabilities.md` — ChannelPolicy as single source of truth (ACF/Agent/ChannelGateway all read it)
- `docs/architecture/event-model.md` (**AUTHORITATIVE**) — `ACFEvent` schema + category filtering + AG‑UI mapping owned by channel adapters
- `docs/architecture/webhook-system.md` (**PROPOSED**) — webhook subscriptions fed by ACF EventRouter
- `docs/architecture/architecture_reconsideration.md` — MessageRouter responsibilities + ingress envelope contract
- `docs/architecture/api-layer.md` — Focal/Ruche receives already-routed envelopes from upstream services

**Canonical boundary claim:**
- **ChannelGateway/MessageRouter live outside** the cognitive runtime (another repo/service).
- The cognitive runtime expects already resolved `tenant_id`, `agent_id`, `channel`, `channel_user_id` + payload.

This aligns extremely well with what `sb_agent_hub` is already doing in practice.

**What `kernel_agent` adds**:
- A concrete ChannelGateway implementation with:
  - webhook verification + dedup + normalization to a canonical Envelope
  - publishing raw events to Redis Streams (`channel:inbound:{tenant_id}`)
  - outbound delivery worker consuming outbound streams
- A concrete contract for a MessageRouter (not implemented in code) with:
  - coalescing + interrupt protocol + routing strategy

Refs:
- `kernel_agent/apps/channel-gateway/src/channel_gateway/api/routes/webhooks.py`
- `kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`

## 2) What Exists in Code (Inventory)

### 2.1 Runtime “ChannelGateway” (lightweight, outbound-focused)

- `ruche/runtime/channels/adapter.py`
  - Defines protocols for `ChannelAdapter`, `OutboundMessage`, etc (minimal surface)
  - No webhook ingestion, no multimodal content model
- `ruche/runtime/channels/gateway.py`
  - Adapter registry + `send()` with policy application hook
  - `load_policy()` currently derives policy from adapter capabilities, not ConfigStore
- `ruche/runtime/channels/models.py`
  - `ChannelPolicy` and `ChannelBinding` (matches docs’ “single policy model” shape)
- `ruche/runtime/channels/adapters/webchat.py`
  - Example adapter with a stub “deliver” implementation

### 2.2 ACF event model + routing

- `ruche/runtime/acf/events.py`
  - `ACFEventType` uses `{category}.{name}` (e.g., `turn.started`, `tool.executed`)
  - `ACFEvent` is a flat event model with routing context
- `ruche/runtime/acf/event_router.py`
  - Pattern subscription (exact, `category.*`, `*`)
  - Records side effects in `LogicalTurn.side_effects` **only when** `event.type == tool.executed`
- `ruche/runtime/acf/models.py`
  - Defines `FabricTurnContext.emit_event(event: ACFEvent)` contract
  - `LogicalTurn.side_effects` store ACF’s own `SideEffect` model

### 2.3 Webhook API surface exists (but is not wired to events yet)

- `ruche/api/webhooks/models.py` + `dispatcher.py` + `routes.py`
  - Subscription model + HMAC signing + matcher
  - Current routes use in-memory storage (“temporary”)
  - No code currently subscribes the dispatcher to EventRouter

### 2.4 Duplicate / legacy channels stack under `ruche/infrastructure/channels/`

Like tools, `ruche/infrastructure/channels/*` defines:
- `ChannelGateway` + adapters (mostly stubs)
- Separate `ChannelPolicy` and message models

This conflicts with the runtime `ruche/runtime/channels/*` types and the newer docs.

## 3) Major Spec ↔ Code Drift (Integration-Relevant)

### 3.1 ChannelPolicy is not actually the “single source of truth” in runtime

Docs demand:
- ChannelPolicy is loaded from ConfigStore into `AgentContext.channel_policies`
- ACF/Brain/ChannelGateway all use the same object

But current code has:
- `ruche/runtime/agent/runtime.py` returns empty `{}` for `_load_channel_policies()`
- `ruche/runtime/channels/gateway.py` falls back to adapter `get_capabilities()` (defaults), not ConfigStore
- `ruche/runtime/acf/turn_manager.py` uses hardcoded channel defaults (`CHANNEL_DEFAULTS`) rather than policies

Net: in an integration where sb_agent_hub is the ChannelGateway/Router, ChannelPolicy should likely be owned by sb_agent_hub as “control-plane config” and injected into soldier runtime consistently (bundles/API).

### 3.2 Inbound channel model in docs is richer than runtime code

Docs define:
- `InboundMessage` with multimodal envelope: `content_type`, `text`, `media[]`, `location`, `provider_message_id`, timestamps
- Identity resolution/linking as a first-class responsibility of channel layer

Runtime code currently:
- only models “content: str” in protocols
- has no webhook ingestion / normalization logic
- has no identity resolution store

This is fine if channel gateway truly lives outside soldier; it just means the runtime “ChannelGateway” package should either:
- stay minimal and internal-only, or
- be treated as reference adapter code, not the real channel layer

### 3.3 Webhook system exists as API but not connected to ACF events

The webhook dispatcher/matcher is implemented, but there is no integration point like:
- EventRouter listener `webhook.*` that triggers delivery workflows

For sb_agent_hub integration, this is important because external UI/admin systems often want:
- streaming run state
- tool events
- audit events

Webhooks could be one of the “join points” for sb_agent_hub to receive soldier runtime events.

### 3.4 AG‑UI mapping is explicitly a “channel adapter” concern (good fit)

`docs/architecture/event-model.md` explicitly says:
- ACF emits ACFEvents
- Mapping to AG‑UI protocol events is done by channel adapters, not ACF core

This matches sb_agent_hub’s current approach:
- webchat front-end expects AG‑UI SSE (CopilotKit runtimeUrl)

So, in the integrated architecture:
- sb_agent_hub’s webchat gateway can map soldier’s ACFEvents/stream outputs into AG‑UI SSE.

## 4) What sb_agent_hub Brings (Relevant Contrast)

### 4.1 Webchat already speaks AG‑UI

sb_agent_hub has:
- a working AG‑UI SSE endpoint (`3-backend/app/api/user/ag_ui_langgraph.py`)
- a simplified proxy architecture (`docs/COPILOTKIT_FINAL_ARCHITECTURE.md`)

Even if soldier becomes the “brain/runtime”, sb_agent_hub can keep:
- the AG‑UI SSE contract with the browser
- and only swap out the internal agent execution with a call to soldier

### 4.2 Voice channel ingestion exists

sb_agent_hub has:
- `POST /api/user/voice/webhooks/vapi` that stores transcript + function call events (VAPI)
- voice sessions + transcripts tables (in docs and code)

This can become the “voice channel adapter” in the ChannelGateway sense.

## 5) Integration Implications (Practical)

### 5.1 Treat sb_agent_hub as the ChannelGateway/MessageRouter

This matches both repos’ docs:
- sb_agent_hub already has the “channel protocol” concerns (webchat/voice)
- soldier wants channel gateway out of the runtime

The join contract becomes:
- sb_agent_hub normalizes inbound channel events → sends a stable ingress envelope to soldier
- sb_agent_hub formats outbound responses and/or streams events to the user

### 5.2 Decide how soldier emits “streaming UI events”

Two non-exclusive mechanisms:
1) soldier exposes `/v1/chat/stream` (token stream + done) and sb_agent_hub maps it to AG‑UI
2) soldier emits `ACFEvent`s (turn/tool/run lifecycle) and sb_agent_hub subscribes (via webhook, SSE, or a queue) and maps to AG‑UI

The best long-term alignment is (2) because:
- it preserves observability and audit as first-class
- it allows “tool events” and “progress events” to drive rich UIs (AG‑UI) without coupling ACF to the UI protocol
