# System Map: `soldier` ↔ `sb_agent_hub`

## 1) What Each Repo “Is” Today (Practical Definition)

### `soldier` (Ruche runtime + FOCAL brain)

**What it wants to be (docs, especially `docs/acf/`)**
- A **production runtime** for conversational agents:
  - **ACF**: mutex + message accumulation into LogicalTurns + supersede facts + durable orchestration concepts
  - **AgentRuntime / AgentContext**: caching/lifecycle, brain selection (FOCAL/LangGraph/Agno)
  - **Toolbox / ToolGateway**: tool semantics + execution routing + idempotency + audit events
  - **Event model**: `ACFEvent` + pattern subscription + persistence
- Multi-tenant, “stateless pods”, external stores.

**What is actually wired in code today**
- Two partially overlapping layers coexist:
  1) **Older “AlignmentEngine/FOCAL pipeline” path** used by `ruche/api/routes/turns.py` (`POST /chat`).
  2) **New ACF/AgentRuntime/Toolbox/ChannelGateway packages** exist but are not consistently integrated end-to-end (spec ↔ code drift).

### `sb_agent_hub` (SmartBeez Agent Hub monorepo)

**What it is today (code)**
- A full product stack:
  - Multiple frontends (landing, user app, admin)
  - A FastAPI backend using **LangGraph/LangChain** agents
  - Auth + tenant/org management (WorkOS/Supabase)
  - Working **webchat** UX via CopilotKit + **AG‑UI SSE**
  - **Voice** plumbing via VAPI/Twilio webhook ingestion + session/transcript logging

**What it wants to be (docs)**
- A complete agent platform with:
  - Control plane concepts (agent compiler, manifests, revisions)
  - Dynamic endpoints per agent/channel
  - Tool ecosystem via Composio/MCP (mostly “planned” in code)

### `kernel_agent` (historical multi-plane platform attempt)

**What it was trying to be**
- A microservices multi-plane architecture where:
  - Control plane compiles/publishes bundles (Supabase SoT → Redis bundles)
  - ChannelGateway handles webhook ingress/outbound delivery
  - MessageRouter coordinates sessions, coalescing, interrupts (Redis Streams contract)
  - ToolHub centralizes tool catalog + per-tenant activation + execution streaming
  - Parlant was used as the brain (later abandoned)

**What is actually implemented and reusable now**
- A production-shaped **ToolHub service** (`kernel_agent/apps/toolhub/`)
- A production-shaped **ChannelGateway service** (`kernel_agent/apps/channel-gateway/`)
- A concrete **ChannelGateway ↔ MessageRouter contract** (docs-only MessageRouter)
- A control-plane **publish workflow** writing Redis bundles + pointer swaps (`kernel_agent/apps/control-api/`)

## 2) Terminology Mapping (Critical for Integration)

| Concept | `soldier` term | `sb_agent_hub` term | Notes |
|---|---|---|---|
| Tenant | `tenant_id` | `organization_id` / `org_id` | Map 1:1 in integration |
| Agent | `agent_id` | `agent_id` | Conceptually similar; “manifest/revision” is more explicit in sb_agent_hub docs |
| End user identity | `interlocutor_id` + `channel_user_id` | `user_id` + channel identity | sb_agent_hub distinguishes authenticated user vs channel user (phone/email) |
| Conversation state | `SessionStore` (`session_id`, `session_key`) | `session_id` (websocket, zep, voice session tables) | Soldier expects stateless runtime; sb_agent_hub often keeps in-memory maps |
| Channel | `channel` (`whatsapp`, `webchat`, `voice`, …) | Similar | sb_agent_hub already has webchat + voice endpoints |
| Tool | `Toolbox` + external provider via `ToolGateway` (canonical docs) | LangChain tools + planned Composio/MCP + workflow engine tool nodes | Integration must pick “system of record” for tool definitions |
| ToolHub service | “external ToolHub” (docs; partially implemented) | “tools/workflow engine” (partially implemented) | `kernel_agent` has a concrete ToolHub service implementation (catalog + activation + NDJSON execution) |

## 3) The Shared “North Star” Architecture (Already Written in `soldier`)

`docs/architecture/kernel-agent-integration.md` and `docs/architecture/architecture_reconsideration.md` describe a layered system:

1. **Control Plane**: Admin UI + config store + publisher (“source of truth”)
2. **Channel Layer**: ChannelGateway + MessageRouter (normalize, resolve tenant/agent, backpressure)
3. **Cognitive Layer**: Ruche/Focal runtime (ACF + Brain + Toolbox)
4. **Tool Layer**: ToolHub / tool orchestrator (Composio/MCP/workflows)

This is extremely close to what `sb_agent_hub` already is:
- It already has **Control Plane-ish** data (agents, revisions/manifests in docs, Supabase as SoT)
- It already has **Channel Layer** for webchat (AG‑UI SSE) and voice (webhook ingestion)

So the cleanest integration is:

> `sb_agent_hub` becomes the Control Plane + Channel Layer, and `soldier` becomes the Cognitive Layer (runtime).

`kernel_agent` is evidence that this architecture was already being built once:
- it implemented ToolHub + ChannelGateway patterns and Redis bundle distribution
- the only piece that “doesn’t port” cleanly is the Parlant brain itself

## 4) What “Joining the Projects” Likely Means

There are two reasonable “join” interpretations:

### A) Runtime-service integration (recommended)
- Keep repos separate.
- `sb_agent_hub` routes inbound channel events → calls `soldier`’s chat/turn endpoints.
- `sb_agent_hub` handles AG‑UI/webchat UX, voice provider webhooks, and enterprise auth.
- `soldier` focuses on ACF + brains + persistence + audit/event model.

### B) Single-runtime integration (monolith)
- Move `soldier` runtime into `sb_agent_hub/3-backend` as a library, or merge repos.
- Higher coupling, harder deployment separation, but fewer moving pieces.

The rest of this study assumes (A) unless explicitly stated otherwise, because it matches both repos’ own docs most closely.
