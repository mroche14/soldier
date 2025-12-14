# Architecture Reconsideration (Pre-Refactor)

> **Status**: DECISIONS FINALIZED — ready for doc rewrite
> **Goal**: Remove ambiguity before rewriting docs / implementing more code
> **Non-goal**: This document does not change the architecture yet; it clarifies the target model and the decisions required.
> **Reviewed by**: Claude Opus 4.5 (2025-12-13, revised 2025-12-14) — see OPUS paragraphs throughout
> **Decisions finalized**: 2025-12-14 — see §13 for full decision summary

## 0) Why This Document Exists

This repo started as **Soldier** (alignment engine focus), then evolved into **Focal** (alignment pipeline + persistence), and then expanded in scope via **FOCAL 360** (ACF + multi-agent platform framing).

That history left the docs with mixed assumptions:
- "Focal = alignment engine" vs "Focal = agent platform"
- framework-driven terms (`pipeline_type = agno/langgraph`) vs mechanic-driven intent ("alignment pipeline" vs "react agent")
- "Focal API" language that can incorrectly imply "pipeline endpoints" rather than "agent endpoints"
- unclear value/necessity of some abstractions (e.g., `AgentRuntime`, `AgentContext`)

This doc re-states the intended end-state architecture in your current terms (**Smartbeez / Ruche / ASA**) and enumerates the concrete decisions required to make documentation and implementation unambiguous.

---

## 1) Your Current Vision (Restated)

### 🐝 1.1 Business/product shape

- **Smartbeez offering (default)**: each tenant gets a **Ruche** swarm by default — a standard pack of agents (marketing, legal support, etc.) provisioned automatically on tenant creation.
- **Extensibility**: tenants can extend their swarm; Smartbeez may provide **ASA** to help design/build agents and enforce safety constraints.
- **Possible future (optional)**: sell some agents as standalone products (impact study in §5.6).

### 🧠 1.2 Technical shape

- An **Agent** is something that can receive **work items** and act:
  - inbound **messages** (human → agent)
  - scheduled **tasks** as **Agenda entries** (time-triggered work planned now and executed later)
- Each Agent contains a **CognitivePipeline** (the "thinking/logic layer").
- **FOCAL** is one CognitivePipeline implementation: an **alignment-focused cognitive architecture** (scenario-following + rule injection at the right time, learning via rules/scenarios rather than "put everything in prompt and pray").
- You want more "cognitive skeletons" (other mechanics): simpler, more complex, different security levels.
- Not all CognitivePipelines will use **rules/scenarios**. Those are FOCAL-alignment-specific primitives; other mechanics may be rule-free or scenario-free.
- **ACF** is the conversation infrastructure that ensures turns are safe/reliable (mutex, LogicalTurn, supersede signals, durable orchestration).
- **ChannelGateway / MessageRouter** live in another project and provide normalized message ingress (phone number, Slack user, etc.).

### 1.3 Decision: what does "Focal" refer to?

> **How to answer**: replace `☐` with `☑` and/or fill the "Your input" cell.

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What does "Focal" refer to? | Current docs mix "platform runtime" vs "alignment pipeline". This choice drives doc structure and naming everywhere. | ☐ Focal = **platform runtime** (ACF + agent runtime + toolbox + stores), and the alignment pipeline is "Focal Alignment" | ☑ Focal = **alignment pipeline only**; platform gets a different name (e.g., "Ruche Runtime") | ☐ Other: ________ | **OPUS recommends B** |

**Recommendation (based on your message):**
- Prefer **Option B**: treat **FOCAL** as the *alignment mechanic/pipeline*, not the entire platform. That matches: "At the end FOCAL is an instance of cognitive pipeline focusing on alignment."
- If you still want the repo/service to be named "focal", that's compatible with Option B — you just keep docs careful: "Focal runtime" vs "FOCAL alignment pipeline".

> **🔮 OPUS Analysis (§1):**
> The vision is sound, but I'd push harder on one clarification: the document says "Not all CognitivePipelines will use rules/scenarios" — this is critical. The current codebase (`focal/alignment/`) is **deeply coupled to rules/scenarios**. I examined `rule_retriever.py`, `scenario_filter.py`, and the entire filtering module. When you add ReAct or other mechanics, you'll need to: (1) extract the rule/scenario primitives into a FOCAL-specific subpackage, or (2) make them optional at the engine level. The current `AlignmentEngine.process_turn()` assumes rules/scenarios exist — it queries `config_store.get_rules()` unconditionally. This isn't a blocker, but **document the refactoring path now** so the decision on "Focal = alignment pipeline only" doesn't surprise you when implementing mechanics that don't use these primitives.
>
> **Codebase evidence**: `focal/alignment/engine.py` (77KB) is the brain. The package structure already reflects "alignment" as a domain concept. Option B is strongly supported by code reality.

---

## 2) Core Invariants (Must Stay True)

1) **Mechanic-first, framework-agnostic**
   The architecture describes mechanics ("alignment", "react", "planner-executor"), not frameworks (Agno/LangGraph).

2) **API addresses Agents, not pipelines**
   External callers talk to an Agent; pipelines are internal to Agents.

3) **ACF is infrastructure, not business logic**
   ACF owns mutex/aggregation/supersede facts/orchestration. It does not interpret scenarios, rules, tools, or domain decisions.

4) **Multi-tenant + horizontally scalable**
   Any pod can serve any request; canonical state is persisted in stores.

5) **LLMExecutor is a reusable primitive**
   `LLMExecutor` (Agno-backed) is a platform building block that any CognitivePipeline may use; FOCAL uses it heavily.

> **🔮 OPUS Analysis (§2):**
> These five invariants are excellent and match what I see implemented. However:
>
> **Invariant #2 ("API addresses Agents, not pipelines") is NOT yet implemented.** Current API (`/v1/chat`) talks to the `AlignmentEngine` directly without an Agent abstraction layer. The `focal/alignment/engine.py` receives `tenant_id`, `agent_id`, `session_id` but there's no `AgentRuntime` or `AgentContext` wrapper yet (Phase 6.5 in `IMPLEMENTATION_PLAN.md` is incomplete). This is fine — just be aware that implementing the agent-centric API is a **precondition** for the vision in this doc.
>
> **Invariant #5 (LLMExecutor as reusable primitive)** is already solid — see `focal/providers/llm/executor.py` with Agno integration, fallback chains, and model string routing.
>
> **Codebase stats**: 258 Python files, 44,138 LOC. The four-store pattern (ConfigStore, SessionStore, CustomerDataStore, AuditStore) plus MemoryStore are all implemented with in-memory and PostgreSQL backends. Multi-tenancy is enforced throughout.

---

## 🧭 3) Runtime Boundaries and Message Ingress

### 🧭 3.1 Conceptual layering

```
External projects (out of this repo)
  ├─ ChannelGateway: provider webhooks/protocol adapters + integration routing
  └─ MessageRouter: selects tenant/agent + backpressure/retries

This repo (agent runtime)
  ├─ Agent Ingress: receives normalized envelope for a chosen agent
  ├─ ACF: LogicalTurn + mutex + supersede facts + orchestration
  ├─ Agent runtime assembly: constructs agent runtime bundle
  ├─ CognitivePipelines: thinking/logic implementations (FOCAL alignment is one)
  ├─ Toolbox: safe tool execution boundary (semantics, confirmation, side effects)
  └─ Stores/Providers: persistence + LLMExecutor/embeddings/rerank
```

### 🧭 3.2 "Agents have API, pipelines are internal"

When docs say "API", the mental model should be:
- The runtime exposes **message ingress to an Agent**, not a pipeline endpoint.
- The request is already routed to a specific Agent (typically `tenant_id + agent_id` are known upstream).
- The Agent runs its CognitivePipeline **inside** the ACF turn lifecycle.

### 🧭 3.3 Decision: what is the runtime message API surface?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What should the runtime message API represent? | You said "agents should have API". ChannelGateway/Router is external. This determines naming and endpoint shapes in docs. | ☑ One ingress endpoint that routes by `tenant_id + agent_id` in the request body/headers | ☐ Per-agent endpoint style (`/v1/agents/{id}/chat`) (same semantics) | ☐ No public API here; only internal ingestion from Router | **OPUS recommends A** |

**Recommendation (practical + consistent with your current setup):**
- Prefer **Option A** as the canonical contract; document Option B as syntactic sugar if you like.
- Avoid Option C unless you truly want to forbid direct integration/testing against this runtime.

### 📨 3.4 What MessageRouter does (external project) + the ingress contract

You asked what the MessageRouter "really does" and how "resolution" happens. The MessageRouter/ChannelGateway are the place where *transport identities* become *routing keys*.

#### Responsibilities (typical)

- **Protocol adapters**: receive provider webhooks/endpoints (Meta WhatsApp, Slack events, webchat, email, voice).
- **Integration routing** ("resolution"):
  - Identify the integration from the inbound endpoint / token / workspace / phone number.
  - Map that integration → `tenant_id`.
  - Map that integration (and sometimes path/params) → `agent_id`.
  - Determine `channel` and extract `channel_user_id`.
- **Normalization**: produce a stable envelope independent of provider payload shape.
- **Delivery**: push to the runtime ingress (HTTP/gRPC) or to a queue the runtime consumes.
- **Idempotency + dedupe** (recommended): forward provider message IDs and a stable idempotency key so the runtime can safely dedupe.
- **Traceability**: attach `trace_id`/`request_id`/`integration_id` metadata so the runtime can correlate audit logs.

#### Proposed ingress envelope (what the runtime expects)

```json
{
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "channel": "whatsapp|slack|webchat|email|voice",
  "channel_user_id": "string",

  "content_type": "text|image|audio|document|location|contact|mixed",
  "content": {
    "text": "string | null",
    "media": [
      {
        "type": "image|audio|video|document",
        "url": "string",
        "mime_type": "image/jpeg",
        "filename": "string | null",
        "caption": "string | null",
        "thumbnail_url": "string | null"
      }
    ],
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060,
      "name": "string | null"
    },
    "structured": {}
  },

  "provider_message_id": "string|null",
  "idempotency_key": "string|null",
  "session_hint": "string|null",
  "received_at": "iso8601",
  "metadata": { "integration_id": "uuid", "locale": "en-US" }
}
```

**Content type handling**:
- `text`: Simple text message (`content.text` only)
- `image`/`audio`/`video`/`document`: Media message (`content.media` array)
- `location`: Location share (`content.location`)
- `contact`: Contact card (use `content.structured`)
- `mixed`: Multimodal — text + images, voice memo + caption, etc.

**Key point:** the router does **not** "question each agent". It routes to one agent based on integration config and forwards the envelope.

> **🔮 OPUS Analysis (§3.4 Envelope) — REVISED:**
> The envelope now supports multimodal content (images, audio, documents, locations) which is essential for WhatsApp, email attachments, and webchat file uploads. The `session_hint` field allows upstream systems to suggest session continuity when the interlocutor returns after a gap or crosses channels.

#### "Resolution" examples (how tenant_id/agent_id are determined)

- **WhatsApp (Meta/Twilio)**: inbound webhook is tied to a phone-number integration. The webhook secret/verify token identifies the integration; the integration record maps → `tenant_id` and default `agent_id`.
- **Slack**: the `team_id` (workspace) + app installation maps → `tenant_id`; the incoming event can map to an `agent_id` by configuration (e.g., "#support channel goes to SupportAgent").
- **Webchat**: the widget/site key in the inbound request maps → `tenant_id`; the widget config chooses an `agent_id` (or routes by page/path).

This mapping data typically lives in the ChannelGateway/MessageRouter project (an "IntegrationStore"), not inside the agent runtime.

### ⏰ 3.5 Scheduled tasks live in Agenda (time-triggered work items)

Agents need to handle **tasks**: "do X at time T" (or "do X every day at 09:00").

Clarification based on your intent:
- tasks are not "just another inbound message" from the MessageRouter
- tasks are **created and stored in the Agent's Agenda** (Agenda entries)
- a scheduler reads due Agenda entries and submits them for execution in the runtime

So tasks "enter the runtime" only when they are due, but they **live in Agenda** as the system of record.

Two common shapes:
- **Agent-level tasks** (no end-user): "refresh catalog", "recompute embeddings", "send proactive outreach".
- **Contact/session-level tasks**: "follow up with this contact in 2 days", "retry tool after backoff".

#### Decision: how do due Agenda tasks get executed?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| How are due tasks executed? | Tasks are stored in Agenda; the question is how the scheduler submits them, and whether execution is ACF-orchestrated (mutex/turn lifecycle) or not. | ☐ Scheduler submits to the same ingress endpoint with `kind = "task"` | ☐ Scheduler publishes to an internal queue/endpoint consumed by the runtime (still runs inside ACF) | ☑ Scheduler calls the mechanic/pipeline directly (bypasses ACF) | **DECIDED: Option C** |

**Decision rationale:**
- **Tasks ≠ Conversations.** A task is a work item, not a conversational turn. It doesn't need message accumulation, LogicalTurn semantics, or supersede signals.
- **Agenda→Hatchet direct link.** Hatchet orchestrates two separate workflow types:
  1. `LogicalTurnWorkflow` (ACF-managed) — for conversations
  2. `TaskWorkflow` (Agenda-managed) — for scheduled tasks
- **If a task sends an outbound message**, the response coordination happens at the ChannelGateway level, NOT by running the task through ACF.

```
┌──────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER (Hatchet)                 │
│                                                                   │
│   ┌─────────────────────┐       ┌─────────────────────┐         │
│   │  LogicalTurnWorkflow │       │   TaskWorkflow       │         │
│   │  (ACF-managed)       │       │   (Agenda-managed)   │         │
│   │  - mutex            │       │   - no mutex         │         │
│   │  - accumulate       │       │   - no accumulate    │         │
│   │  - supersede        │       │   - direct execute   │         │
│   └─────────────────────┘       └─────────────────────┘         │
│            ↑                              ↑                       │
│   ChannelGateway.receive()      AgendaScheduler.execute_due()    │
└──────────────────────────────────────────────────────────────────┘
```

> **🔮 OPUS Analysis (§3.5) — REVISED:**
> Option C is correct. Tasks and conversations are fundamentally different work item types:
> - **Conversations**: Interactive, need mutex (one turn at a time), need message accumulation, need supersede handling
> - **Tasks**: Non-interactive, execute once, may or may not involve an interlocutor
>
> Both use Hatchet for durable orchestration, but through separate workflow types. This keeps ACF focused on conversation semantics while Agenda handles scheduled work directly.

---

## 🧩 4) Contracts: ACF ↔ Agent ↔ CognitivePipeline

### 🏷️ 4.0 If we renamed "ACF", what would we call it?

You asked for 4 better names that capture what ACF actually does (mutex + turn aggregation + supersede facts + durable orchestration + event routing).

| Question | Context | Option A | Option B | Option C | Option D | Your input |
|---|---|---|---|---|---|---|
| If we renamed ACF, which name best captures its role? | The goal is semantic clarity for builders (and for AI-assisted development). | ☐ **Conversation Runtime** (emphasizes lifecycle + orchestration) | ☐ **Turn Orchestrator** (emphasizes durable workflows) | ☐ **Conversation Control Plane** (emphasizes "thin waist" control) | ☐ **Turn Fabric** (emphasizes routing + event fabric + mutex) | |

**Recommendation (if you rename):**
- I'd pick **Conversation Runtime** or **Turn Fabric**. "Fabric" nicely matches the event + routing role; "Runtime" matches orchestration + mutex + aggregation.

### 🧩 4.1 Terminology (Protocol vs Mechanic vs Framework)

This is *intentionally* a three-layer split and, in my view, it reduces confusion:

- **CognitivePipeline (protocol)**: the *contract* ACF calls: `run(ctx) -> PipelineResult` (+ optional capabilities like supersede handling).
- **Mechanic / Cognitive Architecture**: the *semantics* of how the pipeline thinks (alignment, react, planner-executor, etc.).
- **Framework**: the *implementation vehicle* (plain Python, Agno workflow, LangGraph). Framework should not leak into architecture unless it materially affects ops/runtime.

**Example:**
- Mechanic: "Alignment"
  Pipeline implementation: "FOCAL Alignment" (11-phase spec)
  Framework: plain Python today; could become an Agno workflow later without changing the mechanic.

**Important:** a mechanic can be *rule/scenario-driven* (FOCAL alignment) or *rule-free* (e.g., ReAct). Rules/scenarios are not universal platform concepts; they are part of specific mechanics.

> **🔮 OPUS Analysis (§4.1 Terminology):**
> The three-layer split is excellent and matches my mental model. However, the document uses "CognitivePipeline" as the protocol name, but the codebase uses `AlignmentEngine` (see `focal/alignment/engine.py`). **Reconcile this terminology.** Either:
> 1. Rename `AlignmentEngine` to `FocalCognitivePipeline` (implementing `CognitivePipeline` protocol), or
> 2. Document clearly that `AlignmentEngine` IS the FOCAL-specific implementation of the abstract protocol.
>
> The current `AlignmentEngine.process_turn()` is essentially the `run()` method of a `CognitivePipeline`. Make this mapping explicit.

### 🧩 4.2 Decision: what do we name the ACF ↔ Pipeline contract objects?

You asked what the "interface between ACF and CognitivePipelines" should be called. That interface has two pieces:
- the **input context** object ACF provides per turn
- the **output result** object the pipeline returns

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What names should we standardize for the ACF ↔ Pipeline boundary? | Names must be unambiguous so humans + AI can extend components safely. | ☑ Keep FOCAL 360 naming: `CognitivePipeline`, `FabricTurnContext`, `PipelineResult`, `FabricEvent` | ☐ Rename to more generic: `AgentBrain`, `TurnContext`, `TurnResult`, `AgentEvent` | ☐ Other scheme: ________ | **OPUS recommends A** |

**Recommendation (minimize churn + preserve meaning):**
- Prefer **Option A**. `FabricTurnContext` / `FabricEvent` being ACF-specific is useful (they name the boundary).
- If you dislike "Fabric*", rename later globally — but avoid mixed vocab.

### 🧩 4.3 Decision: do Agents "link to ACF" directly (policy/config)?

Your intuition is right that Agents may need a *data-level link* to ACF — not a pointer/reference, but **ACF policy config**:
- accumulation/aggregation windows (per channel)
- supersede default mode (per channel or agent)
- mutex scope hints (rare; mostly stable)

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Where do we configure ACF behavior knobs? | This is the "agent↔ACF link": ACF reads config; pipeline runs in ACF context. | ☑ Per **ChannelBinding** (channel-dependent defaults) | ☐ Per **Agent** (same across all channels) | ☐ Global only (one policy for all) | **DECIDED: Option A** |

**Decision rationale:**
- Prefer **Option A**: WhatsApp vs webchat vs voice have different natural aggregation behaviors.
- Option B can be an override layer later; avoid global-only.

#### ChannelPolicy as Single Source of Truth

**Key principle:** Channel policy is configuration, not runtime state. It lives in ConfigStore, loaded once, and passed through context. **Everyone reads from the same source** — no independent lookups by ACF, Agent, or ChannelGateway.

```python
class ChannelPolicy(BaseModel):
    """Single source of truth for channel behavior."""
    channel: str  # "whatsapp", "webchat", "email", "voice"

    # ACF needs these
    aggregation_window_ms: int = 3000
    supersede_default: SupersedeMode = SupersedeMode.QUEUE

    # ChannelAdapter needs these
    supports_typing_indicator: bool = True
    supports_read_receipts: bool = True
    max_message_length: int | None = None

    # Agent/Pipeline may need these
    natural_response_delay_ms: int = 0  # "human-like" delay
```

**Location**: ConfigStore → loaded into `AgentContext.channel_policies: dict[str, ChannelPolicy]`

> **🔮 OPUS Analysis (§4.3) — REVISED:**
> The shared ChannelPolicy model eliminates redundant lookups. ACF, Agent, and ChannelGateway all reference the same policy object loaded into AgentContext. This keeps ACF channel-agnostic (it doesn't interpret the policy, just applies it) while ensuring consistency across layers.

### 🧩 4.4 AgentEvent-first event model (and what it implies for ACF)

You said you like **AgentEvent reporting everything**. Here's the clean way to do that without turning ACF into business logic:

#### Proposed split

- **AgentEvent** (semantic): the thing builders care about ("scenario_activated", "tool_planned", "policy_blocked", "task_scheduled", …).
- **FabricEvent** (transport): an envelope ACF routes/persists that carries an AgentEvent plus routing keys (`tenant_id`, `agent_id`, `session_key`, `logical_turn_id`, etc.).

In other words: "everything is an AgentEvent", but ACF still uses FabricEvent as the delivery mechanism.

#### What ACF must do if AgentEvent is the canonical stream

ACF stays infrastructure if it:
- **routes** events (to logs, metrics, live UI streams, audit)
- **persists** events needed for infra invariants (mutex ownership, supersede chain, commit points)
- **does not interpret** agent semantics (scenario/rule logic remains in mechanics)

But there are implications:
- **Volume**: AgentEvent can become high-cardinality/high-volume; you need rate limits and payload size limits.
- **Stability**: if clients/UI consume events, you need versioned schemas for AgentEvent payloads.
- **Privacy**: event policy is required (what can be emitted at INFO vs DEBUG; PII redaction).
- **Infra coupling**: ACF still needs a small set of "infra-relevant" events (tool side effects, commit point reached). Those can be represented as AgentEvents with reserved types or flags, but the rule must be explicit.

#### Decision: adopt AgentEvent as the canonical event surface?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What is the canonical event surface? | You want AgentEvent "reporting everything". This choice affects observability contracts and what ACF must persist. | ☑ AgentEvent is canonical; FabricEvent is transport | ☐ FabricEvent is canonical; agent semantics are informal | ☐ Other: ________ | |

**Recommendation (minimize ambiguity + keep ACF thin):**
- Keep a minimal, versioned AgentEvent schema (stable top-level fields), and allow mechanics to extend via typed payloads.
- Reserve a small namespace (e.g., `infra.*`) for ACF/Toolbox invariants so ACF doesn't need to parse arbitrary payloads.

> **🔮 OPUS Analysis (§4.4 Reserved Event Namespace):**
> The doc mentions "reserved namespace `infra.*`" but doesn't define it. **This is critical to define now.** Proposed reserved events:
> - `infra.tool.started`, `infra.tool.completed`, `infra.tool.failed`
> - `infra.commit.reached` (when irreversible tool succeeds)
> - `infra.mutex.acquired`, `infra.mutex.released`
> - `infra.turn.superseded`, `infra.turn.queued`
>
> Without this namespace, ACF will end up parsing arbitrary event payloads to track commit points. Define the contract now.

### 🧩 4.5 Decision: how does an Agent select a CognitivePipeline mechanic (not framework)?

You don't want framework-specific `pipeline_type`, but if multiple mechanics exist you still need selection.

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| How does the runtime know which CognitivePipeline implementation to run for an Agent? | Selection must be mechanic-driven and remain framework-agnostic. | ☑ Agent references a **mechanic ID** (e.g., `"alignment"`, `"react"`) + mechanic-specific config | ☐ Pipeline is **structurally described** (graph/steps) and built generically | ☐ Code-wired only for now; multiple mechanics later | **OPUS recommends A** |

**Recommendation (matches your "cognitive skeletons" goal):**
- Prefer **Option A** as the target architecture (mechanic-first, extensible).
- Implementation can start as **Option C** (only FOCAL exists), but docs should describe the intended shape to avoid drift.

> **🔮 OPUS Analysis (§4.5 Mechanic ID):**
> Option A is correct, but the current `AGENT_RUNTIME_SPEC.md` §1 shows `pipeline_type: str = "focal"` with values `"focal", "langgraph", "agno"` — these are **framework names**, not mechanic names. **Rename to mechanic IDs**: `"alignment"`, `"react"`, `"planner_executor"`. Framework is an implementation detail inside the mechanic. This is a doc fix, not code change (since ACF isn't implemented yet).

### 🧩 4.6 Decision: what is LLMExecutor's role across mechanics?

You created `LLMExecutor` as a reusable harness for LLM calls (model string routing + fallback + structured outputs). Other mechanics might also need it.

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Is `LLMExecutor` a platform primitive for all pipelines, or a FOCAL-only helper? | This determines where `LLMExecutor` is documented (platform layer vs FOCAL-only). | ☐ Platform primitive: any mechanic can use it | ☐ FOCAL-only: other mechanics bring their own LLM layer | ☑ Hybrid: platform provides it; some mechanics require it, others don't | **OPUS recommends C** |

**Recommendation (consistent with your statement):**
- Prefer **Option C**: keep `LLMExecutor` as a platform building block, but don't force all mechanics to use it.

### 🔗 4.7 Execution link: how ACF, Agents, and CognitivePipelines connect

You asked for a clearer "link" between ACF, agents, and pipelines.

#### Call chain (per work item)

```
MessageRouter/Scheduler
  → Agent Ingress (this runtime)
    → ACF (mutex + aggregation) builds LogicalTurn
      → load agent runtime bundle (Agent config + toolbox + pipeline)
        → pipeline.run(FabricTurnContext + agent runtime)
          → emits AgentEvents (via ACF transport)
          → may call tools via toolbox
      → ACF commit_and_respond (persist + release mutex)
```

Key ideas:
- **ACF owns the lifecycle** (mutex, aggregation, durable orchestration).
- **Agent owns the business bundle** (toolbox + chosen mechanic/pipeline + channel policies).
- **CognitivePipeline owns thinking/logic** and returns a result; it does not own turn lifecycle.
- **Events** flow outward through ACF; ACF routes/persists them but does not interpret most of them.

### 🧵 4.8 Durable orchestration (Hatchet today, portable tomorrow)

You asked how Hatchet should be used, and whether we should generalize so we can swap Hatchet for another durable runtime later (Temporal, Restate, Step Functions, etc.).

#### What Hatchet is doing in the current architecture

Hatchet is not "the brain". In this architecture it is a **durable turn orchestrator** used by ACF to enforce conversation-lifecycle invariants:
- one in-flight turn per session key (mutex)
- durable aggregation window (accumulate messages into a LogicalTurn)
- durable retries around transient failures
- step boundaries for observability and recovery

In other words: Hatchet is how ACF implements `acquire_mutex → accumulate → run_pipeline → commit_and_respond`.

#### Advice: how to use Hatchet safely (without leaking it everywhere)

- Keep Hatchet usage **inside ACF only**. Pipelines should never import Hatchet APIs; they only see `FabricTurnContext` methods (`has_pending_messages`, `emit_event`, etc.).
- Make workflows **idempotent under retry**:
  - any external side effects go through Toolbox/ToolGateway with idempotency keys
  - workflow steps are safe to re-run (or are guarded by "already did this" checks in stores)
- Avoid "workflow list scans". Keep a deterministic mapping:
  - `session_key → workflow_run_id` (active index)
  - start-or-signal semantics by session_key
- Use Hatchet timers/cron only for orchestration concerns; **tasks still live in Agenda** (system of record), and the scheduler decides what is due.

#### Portability: define an Orchestrator interface at the ACF boundary

To keep Hatchet swappable, the key is to define the *minimum* contract ACF needs from an orchestration engine:

```python
class DurableOrchestrator(Protocol):
    async def start_or_signal(self, key: str, event: dict) -> None: ...
    async def get_status(self, key: str) -> dict | None: ...
    async def schedule(self, run_at: datetime, payload: dict) -> None: ...
```

ACF would depend on `DurableOrchestrator`, and Hatchet becomes just one implementation (`HatchetOrchestrator`). Temporal/Restate/etc. would be other implementations.

**Required semantics (what the orchestrator must provide):**
- Durable execution with retries (at-least-once)
- A stable "workflow key" or deterministic instance identity (for session-keyed workflows)
- A signal/event mechanism to deliver inbound messages to an active workflow instance
- Durable timers (optional if you move all scheduling to the Agenda scheduler)

#### Decision: do we treat Hatchet as an implementation detail?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| How do we position Hatchet in the architecture? | You want flexibility without adding unnecessary abstraction now. | ☐ Hatchet is "the orchestrator", but hidden behind a `DurableOrchestrator` interface | ☐ Commit to Hatchet explicitly everywhere (no abstraction) | ☑ Defer; keep docs Hatchet-specific for now, refactor later | **OPUS recommends C (defer)** |

**Recommendation (balance abstraction vs clarity):**
- Prefer **Option A**: keep Hatchet as the first implementation but keep the rest of the architecture Hatchet-agnostic.

> **🔮 OPUS Analysis (§4.8 Hatchet Abstraction):**
> I **disagree with the recommendation** here. Option C (defer) is more pragmatic given that:
> 1. ACF is not yet implemented (Phase 6.5 incomplete)
> 2. You don't have a second orchestrator candidate
> 3. YAGNI applies — don't abstract until you have two implementations
>
> **My recommendation**: Keep Hatchet usage confined to ACF (which the doc already mandates), but don't build the `DurableOrchestrator` interface until you have a concrete second orchestrator to test against. The interface in the doc is reasonable, but premature abstraction adds complexity without proven benefit.

---

## 🏗️ 5) Provisioning Model: Skeletons → Blueprints → Tenant Agents (Ruche)

To go from "we can build cognitive architectures" to "tenants have standard agents + can extend", you need distinct artifacts.

### 5.1 Cognitive skeletons (engineer-owned)

**What**: a code implementation + a spec/schema for configuration.
Examples:
- `FOCAL Alignment` mechanic (scenario/rule-driven alignment)
- `ReAct` mechanic (future)

**Output**: a runnable `CognitivePipeline` implementation.

### 5.2 Agent blueprints (product/ops owned, ASA-assisted)

**What**: templates that say "create an agent that uses mechanic X + toolset Y + initial config Z".
Blueprints are what allow "Ruche default agents" and tenant customization without editing code.

### 5.3 Agent instances (tenant-scoped runtime entities)

**What**: actual agents for a tenant (IDs, channel bindings, enabled tools, chosen mechanic/config).

### 5.4 ASA's role (design-time)

ASA primarily helps at design-time:
- propose scenarios/rules/templates/tool safety metadata
- generate/validate blueprint/agent configs
- enforce side-effect policy/confirmation/compensation metadata

ASA does not need to be in the runtime path for every turn.

### 🐝 5.5 Decision: what is "Ruche" in architecture terms?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| How do we represent "8 standard agents per tenant" in architecture terms? | This affects config entities, versioning, and how ASA interacts with creation. | ☑ Ruche is an **AgentBlueprint pack** applied at tenant creation | ☐ Ruche is a **set of prebuilt Agent instances** copied per tenant | ☐ Other: ________ | **OPUS recommends A** |

**Recommendation (scales cleanly):**
- Prefer **Option A**: blueprint packs can be versioned/upgraded and are easy for ASA to edit safely.

> **🔮 OPUS Analysis (§5 - Missing: Blueprint Version Propagation):**
> This section introduces important concepts (skeletons, blueprints, agent instances) but is **missing one critical piece**: how scenarios/rules/templates get versioned and upgraded when a blueprint changes. You already have scenario migration (Phase 15 complete in `focal/alignment/migration/`), but blueprint updates cascade differently.
>
> When "Ruche blueprint v2" adds a new scenario to an existing agent type, what happens to existing tenant agents? Options:
> 1. **Opt-in migration**: Tenant explicitly upgrades
> 2. **Automatic migration**: New blueprint applied, scenario migration kicks in
> 3. **Fork-on-write**: Tenant gets a snapshot, blueprint updates don't affect them
>
> This decision affects your entire upgrade story. The current scenario migration system handles **single-agent scenario version changes**; it doesn't handle **multi-agent blueprint version propagation**. Document this gap.

### 📦 5.6 Impact study: "sell some agents as standalone products"

This is a go-to-market packaging concern that *can* stay mostly orthogonal to the runtime architecture, **if** we model "products" as packaged configurations rather than new runtime primitives.

**Baseline definition (for this doc):** a "standalone agent product" is a curated, supported bundle that results in one (or a small set of) Agent instances with:
- a chosen mechanic/skeleton (e.g., FOCAL alignment)
- opinionated toolset + policies (ToolActivations, confirmations, side-effect semantics)
- default prompts/scenarios/rules/templates/customer schema
- channel binding defaults and (optionally) ACF policy defaults

**What this impacts (architecture concerns):**
- **Packaging artifact**: we need a distributable unit (e.g., a Ruche-like blueprint pack) with versioning.
- **Provisioning workflow**: "install product into tenant" becomes a first-class operation (create agents + config + tools).
- **Upgrades & migrations**: product versions must be upgradable (scenario migrations, config compatibility).
- **Billing/usage metering**: requires stable audit signals (tool calls, tokens, turn counts) per product/agent.
- **Customization boundary**: define what customers can change vs what's locked (safety + supportability).
- **Credential isolation**: product uses tenant credentials via CredentialStore; never embed credentials in the product bundle.

**What should *not* change (if designed well):**
- ACF remains the same infrastructure layer.
- CognitivePipeline protocol remains the same (products do not require a new "pipeline interface").
- Toolbox/ToolGateway remain the same (products are configuration of tools/policies, not a new execution path).

#### Decision: how are standalone products delivered/deployed?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What is the delivery model for "standalone agent products"? | This determines how much additional architecture is needed (control plane, upgrades, isolation). | ☑ Hosted multi-tenant: product = versioned blueprint pack applied to a tenant | ☐ Dedicated deployment per customer (single-tenant runtime, managed/self-hosted) | ☐ Library/SDK embedded into customer systems | **OPUS recommends A** |

**Recommendation (keep scope controlled):**
- Prefer **Option A** first. It uses the same multi-tenant architecture and makes "productization" mostly a packaging + provisioning problem.
- Option B is compatible later if you keep "external control plane mode" + bundle-based config distribution.
- Avoid Option C until much later; it tends to fracture contracts (and makes ACF/tooling semantics harder to keep consistent).

### 🧾 5.7 What happens when a new tenant arrives (Ruche provisioning, end-to-end)

You asked for "how it works in real life" when a new tenant arrives. This is the concrete lifecycle if Ruche is the default offering.

#### Provisioning time (control plane / onboarding)

1) **Create tenant** in ConfigStore (tenant record + initial settings).
2) **Apply Ruche blueprint pack** (versioned):
   - Create the default Agent configs (e.g., 8 agents).
   - For each Agent:
     - set `mechanic_id` (e.g., `"alignment"` for FOCAL, `"react"` for others)
     - store mechanic-specific config in ConfigStore
     - create ChannelBinding placeholders (channels are enabled when integrations exist upstream)
     - create ToolActivations (which tools this agent can use + policy overrides)
     - if the mechanic is rules/scenarios-based (FOCAL): create initial Scenarios/Rules/Templates/Variables
     - create the per-agent "contact schema" (CustomerDataStore schema) if the mechanic needs structured customer/contact data
     - create Agenda defaults if used (see §8.4)
3) **Credentials are not created** automatically; they appear when the tenant connects providers (OAuth/API keys) into CredentialStore.
4) **Publish/activate** config versions:
   - standalone mode: records become active immediately (with version numbers)
   - external control plane mode: compile + publish bundles; runtime hot-reloads via bundle pointer update

#### Runtime (first message/task after provisioning)

1) MessageRouter routes inbound envelope to one Agent (`tenant_id`, `agent_id`, `channel`, `channel_user_id`, …).
2) ACF acquires the session mutex and aggregates into a LogicalTurn.
3) Agent runtime assembly loads the Agent config and builds the runtime bundle:
   - instantiate the mechanic's CognitivePipeline
   - instantiate Toolbox from tool defs/activations
   - apply ChannelBinding policies and ACF policy config
4) The pipeline runs:
   - resolves identity/session (see §6)
   - uses stores according to the mechanic (FOCAL uses scenarios/rules; other mechanics may not)
   - emits AgentEvents (for observability, UI, audit)
5) ACF persists what must be persisted (turn record/events) and releases the mutex.

---

## 🆔 6) Identity Resolution: `channel_user_id` → `customer_id` → `session_id`

You were concerned that the model implied "ChannelGateway would question each agent." It should not.

### 🆔 6.1 What the external project does (ChannelGateway / Router)

- Receives provider-specific webhooks/endpoints (Meta, Slack, webchat, etc.).
- Resolves routing keys:
  - `tenant_id` (which tenant owns this integration)
  - `agent_id` (which agent this inbound number/channel maps to)
  - `channel` (whatsapp/slack/webchat)
  - `channel_user_id` (phone number, Slack user ID, webchat session ID, etc.)
- Sends the normalized envelope **to the runtime ingress for that agent**.

It does **not** broadcast to multiple agents.

### 🆔 6.2 What this repo does (ACF + stores + pipeline Phase 1)

Inside the runtime:
1) ACF uses a session key (mutex + aggregation) to form a **LogicalTurn**
2) The Agent's CognitivePipeline runs once per LogicalTurn
3) Phase 1 resolves:
   - `customer_id` (internal identity)
   - `session_id` (conversation state reference)

### 🆔 6.3 Decision: where does `channel_user_id → customer_id` mapping live?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Where should the mapping from external identity to internal customer live? | ChannelGateway knows the provider identity; identity resolution can be its own service. | ☐ Inside this repo (CustomerDataStore resolves/creates customer_id) | ☐ Upstream (ChannelGateway/Router provides customer_id; runtime trusts it) | ☑ Separate Identity service shared by both | |

**Current choice (per your note):** Option C.

#### Concrete flow for Option C (IdentityService)

At runtime (inside this repo), Phase 1 can call an IdentityService:
1) `resolve_or_create_contact(tenant_id, agent_id, channel, channel_user_id)` → returns `contact_id`
2) `get_or_create_session(tenant_id, agent_id, contact_id, channel)` → returns `session_id`

Implementation detail:
- IdentityService uses a DB table keyed by `(tenant_id, agent_id, channel, channel_user_id)` with a unique constraint.
- It returns a stable `contact_id` (your current "customer_id") and supports linking multiple channel identities to the same contact (see §6.5).

Why this is nice:
- ChannelGateway and the runtime can share the same identity resolution logic (if needed).
- Customer/contact identity does not have to live inside the same store as "customer variables" if you want separation of concerns.

Concrete DB-oriented shape (example, not a commitment):
- `contacts`: `(tenant_id, agent_id, contact_id, created_at, ...)`
- `contact_channel_identities`: `(tenant_id, agent_id, channel, channel_user_id, contact_id, created_at, ...)` with `UNIQUE(tenant_id, agent_id, channel, channel_user_id)`

Resolution algorithm:
1) `SELECT contact_id FROM contact_channel_identities WHERE tenant_id=? AND agent_id=? AND channel=? AND channel_user_id=?`
2) if found → return
3) else create `contact_id`, insert into `contacts`, then insert identity link (or insert identity link first with conflict handling)
4) on concurrent insert conflict → re-select and return the winner

> **🔮 OPUS Analysis (§6.3 IdentityService Latency):**
> Option C (IdentityService) is architecturally sound but introduces an **important latency concern**. Every Phase 1 will call `resolve_or_create_contact()` — this is a synchronous dependency before any processing happens. Options to mitigate:
> 1. **Cache contact mappings in Redis** (hot path optimization)
> 2. **Batch lookups when accumulating** (reduce round-trips for multi-message LogicalTurns)
> 3. **Accept the latency** (identity resolution is fast, ~5-10ms with PostgreSQL)
>
> The current codebase has `CustomerDataLoader` in `focal/alignment/loaders/customer_data_loader.py` but it works differently — it loads customer data AFTER `customer_id` is resolved. The identity resolution step itself isn't implemented yet. Plan for the caching layer.

### 🆔 6.4 Decision: what does "session" mean with multiple agents?

You said Options B/C "don't make sense"; that's likely because your current routing is "one entrypoint per agent".

This decision only matters if you later run "multiple agents behind one entrypoint" (swarm orchestration).

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What is the scope of SessionStore + session mutex? | With "one entrypoint per agent", per-agent sessions are the natural default. | ☑ Per-agent session: `sess:{tenant}:{agent}:{channel}:{channel_user_id}` | ☐ Shared session per customer+channel: `sess:{tenant}:{channel}:{channel_user_id}` | ☐ Defer; assume per-agent sessions until swarm-orchestrator exists | **OPUS recommends A** |

**Recommendation (given your described routing):**
- Prefer **Option A** (or Option C if you want to explicitly defer). Shared sessions complicate concurrency and ownership unless you have a swarm orchestrator concept.

### 🔄 6.5 Cross-channel reconciliation (one agent, multiple channels)

You noted: "an agent could have several channels it is accessed from". That implies:
- one agent can be reachable via WhatsApp + webchat + email
- the same person may appear under different `channel_user_id` values

The reconciliation mechanism (independent of whether you call it customer/contact) is:
- IdentityService supports linking multiple `(channel, channel_user_id)` identities to the same `contact_id` for a given `(tenant_id, agent_id)`.
- the runtime can ask IdentityService to "link identity" when a user proves they are the same person (OTP/email match, order ID, CRM lookup, etc.).

This gives you cross-channel continuity *within an agent* without sharing state across different agents.

### 🔁 6.6 Decision: is "session" shared across channels for the same contact (within one agent)?

Cross-channel reconciliation can mean just "same contact_id", or it can also mean "same conversation session".

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| For one agent, do sessions span multiple channels for the same contact? | If a user starts on WhatsApp then continues on webchat, do we want one continuous session or separate sessions per channel? | ☑ Separate sessions per channel (simpler UX isolation) | ☐ One session per contact across all channels (continuous context) | ☐ Hybrid (default per channel; allow linking/merging sessions) | **DECIDED: Option A** |

**Decision rationale:**
- Start with per-channel sessions; add cross-channel session linking later only if the product UX demands it.

#### Cross-Channel Awareness (without merging sessions)

**Key principle:** Sessions stay separate, but the agent knows interactions happen across multiple places.

```python
class InterlocutorChannelPresence(BaseModel):
    """Where this interlocutor can be reached / has interacted."""
    channel: str
    channel_user_id: str
    last_active_at: datetime
    session_status: Literal["active", "idle", "closed"]
    message_count: int
    first_interaction_at: datetime

class InterlocutorData(BaseModel):
    """Extended with presence awareness."""
    interlocutor_id: UUID
    # ... existing fields ...

    # Cross-channel awareness
    channel_presence: list[InterlocutorChannelPresence]
```

**Pipeline usage:**
```python
# In TurnContext or via InterlocutorDataStore
presence = interlocutor_data.channel_presence

# Pipeline can now say:
if len(presence) > 1:
    other_channels = [p for p in presence if p.channel != current_channel]
    # "I see you also reached out via WhatsApp earlier..."
```

This gives awareness WITHOUT merging sessions — the agent can reference cross-channel history while keeping session state isolated.

> **🔮 OPUS Analysis (§6.6) — REVISED:**
> Separate sessions + cross-channel awareness is the right balance. The `InterlocutorChannelPresence` model gives the pipeline visibility into multi-channel interactions without the complexity of shared session state. The agent can say "I see you messaged us on WhatsApp too" while maintaining UX isolation per channel.

---

## 7) Tools and Credentials: Tenant Connectors → ToolGateway → Agent Toolbox

You asked how tenants "plug tools into agents," how ToolGateway/CredentialStore fit, and whether toolbox is a registry.

### 7.1 Tool artifacts (what exists conceptually)

- **ToolDefinition**: what the tool is (name, JSON schema, side-effect policy, confirmation policy, gateway route).
- **ToolActivation**: per-agent enablement and overrides ("this agent can use this tool with these constraints").
- **Credential**: tenant secrets (OAuth tokens, API keys) stored in a **CredentialStore** (never in agent config).
- **ToolGateway**: execution infrastructure + provider adapters. It uses credentials to call external systems.
- **Toolbox**: agent-facing facade that:
  - resolves "enabled tools"
  - enforces semantic policies (side effects, confirmation, compensation)
  - emits events about tool side effects
  - calls ToolGateway to execute

### 7.2 How tools become available at runtime (hot updates without "mutating objects")

"Realtime updates" should mean:
- configuration changes propagate quickly
- new turns use new configs
- in-flight turns are not corrupted

Typical lifecycle:
1) Tenant connects a provider → credentials stored in CredentialStore
2) Tools are defined/updated (ToolDefinition) and enabled per agent (ToolActivation)
3) Runtime loads an Agent and builds a Toolbox view from (definitions + activations)
4) When definitions/activations change, the runtime invalidates cached agent runtime bundles and rebuilds them

> **🔮 OPUS Analysis (§7 - Toolbox Gap):**
> The Toolbox → ToolGateway → Provider model is clean, but there's a **tension with the existing codebase**. The current `focal/alignment/execution/tool_executor.py` is a simple executor without the policy enforcement layer described in `TOOLBOX_SPEC.md`. The proposed Toolbox has:
> - `SideEffectPolicy` checking
> - `requires_confirmation` enforcement
> - Idempotency key extraction
> - `FabricEvent` emission
>
> None of this exists in the current `ToolExecutor`. **This is Phase 6.5 work** — the existing executor will need to be wrapped or replaced by the ACF-aware Toolbox. Document this migration path.

### 7.3 Decision: is ToolGateway also a tool registry (MCP), or execution-only?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| What should ToolGateway expose? | You suggested "toolbox would be registry endpoints (MCP or direct tool)". We must decide where discovery lives. | ☐ Execution-only API; discovery lives in ConfigStore/Control Plane | ☐ ToolGateway exposes an MCP server per tenant; Toolbox calls MCP | ☑ Hybrid: MCP for discovery; execution via known tools | **DECIDED: Option C (Hybrid)** |

**Decision rationale:**
- **MCP for discovery**: Agents should know what tools they COULD have access to but don't within a tenant environment.
- **Execution via known tools**: Whether discovered via MCP or manually configured, execution goes through Toolbox→ToolGateway.

#### Three-Tier Tool Visibility Model

| Tier | Description | Who Sees It |
|------|-------------|-------------|
| **Catalog** | All tools in the ecosystem (marketplace) | Discovery UI, ASA |
| **Tenant-available** | Tools the tenant has connected/purchased | Tenant admin, Agent config, MCP discovery |
| **Agent-enabled** | Tools this specific agent can use | Toolbox, Pipeline |

#### MCP Discovery + Toolbox Awareness

```
┌─────────────────────────────────────────────────────────────────┐
│                      Tool Discovery Layer                        │
│                                                                  │
│  ┌────────────────────┐     ┌────────────────────┐             │
│  │  MCP Server        │     │  ToolCatalogStore  │             │
│  │  (exposes tools)   │◄────│  (ConfigStore)     │             │
│  └────────────────────┘     └────────────────────┘             │
│           │                          │                          │
│           │ MCP Protocol             │ Direct API               │
│           ▼                          ▼                          │
│  ┌────────────────────┐     ┌────────────────────┐             │
│  │  External LLMs     │     │  ASA / Admin UI    │             │
│  │  (Claude, etc.)    │     │  (tool config)     │             │
│  └────────────────────┘     └────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Tool Execution Layer                        │
│                                                                  │
│  ┌────────────────────┐     ┌────────────────────┐             │
│  │  Toolbox           │────►│  ToolGateway       │             │
│  │  (agent-enabled)   │     │  (execution)       │             │
│  └────────────────────┘     └────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

**Toolbox awareness of unavailable tools:**
```python
class Toolbox:
    def __init__(self, ...):
        self._enabled_tools: dict[str, ResolvedTool]  # Tier 3
        self._available_tools: dict[str, ToolDefinition]  # Tier 2 (full tenant catalog)

    def get_unavailable_tools(self) -> list[ToolDefinition]:
        """Tools available to tenant but not enabled for this agent."""
        return [
            t for name, t in self._available_tools.items()
            if name not in self._enabled_tools
        ]
```

This allows the agent to say: "I could help you schedule a meeting if you enable the Calendar tool for me" — awareness-based upselling/guidance.

**Future consideration:** MCP could also become an execution gateway (for external MCP-compatible tools), but execution via native ToolGateway providers remains the default.

> **🔮 OPUS Analysis (§7.3) — REVISED:**
> The hybrid model gives the best of both worlds: MCP provides standardized tool discovery (useful for external LLMs and ASA), while execution stays internal via Toolbox→ToolGateway. The three-tier visibility model (Catalog → Tenant-available → Agent-enabled) is clean and maps well to business needs.

### 7.4 Decision: how does an Agent reflect tool changes?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| How should toolbox updates work? | You want minimal abstractions but also quick propagation. | ☐ Build toolbox per turn (no caching) | ☑ Cache toolbox inside an Agent runtime bundle; invalidate on config/tool updates | ☐ TTL-only caching (eventual consistency) | **OPUS recommends B** |

**Recommendation (best tradeoff):**
- Prefer **Option B**. It gives quick propagation without per-turn overhead.

---

## 🗂️ 8) Stores and State (per agent, per tenant)

You asked what stores an agent needs and how shared state works across a tenant swarm (CustomerDataStore, Agenda, Offerings, etc.).

### 🗂️ 8.0 Terminology: what do we call the person talking to the agent?

You said "customer" is your term for "the person talking to the agent". That's workable, but it can be confusing if Smartbeez also has "customers" as a business concept.

| Question | Context | Option A | Option B | Option C | Option D | Your input |
|---|---|---|---|---|---|---|
| What do we call the person/entity interacting with an agent? | This name will propagate into stores, IDs, and docs. | ☐ `customer` (keep current) | ☐ `contact` (CRM-style, channel-identity friendly) | ☐ `participant` (neutral) | ☑ `interlocutor` (with type enum) | **DECIDED: Interlocutor** |

**Decision rationale:**
- **Interlocutor** is the correct term because it supports **typed entities**: human, agent, system, bot.
- This enables multi-agent scenarios where agents talk to each other (handoffs, swarm coordination).
- The existing code will adapt — naming is a refactoring concern, not an architectural concern.

#### Interlocutor Model

```python
class InterlocutorType(str, Enum):
    HUMAN = "human"      # End user
    AGENT = "agent"      # Another agent (handoff scenarios)
    SYSTEM = "system"    # System-initiated (tasks, webhooks)
    BOT = "bot"          # External bot (integrations)

class Interlocutor(BaseModel):
    interlocutor_id: UUID
    tenant_id: UUID
    agent_id: UUID  # Which agent this interlocutor interacts with
    type: InterlocutorType = InterlocutorType.HUMAN

    # Identity links (multiple channels → one interlocutor)
    channel_identities: list[ChannelIdentity]

    # Presence (cross-channel awareness, see §6.6)
    channel_presence: list[InterlocutorChannelPresence]
```

**Renames required:**
- `customer_id` → `interlocutor_id`
- `CustomerDataStore` → `InterlocutorDataStore`
- `CustomerDataField` → `InterlocutorDataField`
- `CustomerSchemaMask` → `InterlocutorSchemaMask`
- `channel_user_id` → remains (this is the channel-specific identity, not the internal ID)

> **🔮 OPUS Analysis (§8.0) — REVISED:**
> "Interlocutor" is the right choice. It's semantically precise (someone you're in dialogue with), supports typed entities (human/agent/system/bot), and enables multi-agent architectures where agents can be interlocutors to other agents. The rename is mechanical and should be done in one pass across the codebase.

### 🗂️ 8.1 Store interfaces an agent uses

Even if the store *types* are common across all agents, you stated you prefer **no shared state across agents**. That implies most data is scoped at least by `(tenant_id, agent_id)`.

- **ConfigStore** (tenant+agent): agent configuration (mechanic choice/config; if alignment mechanic: scenarios/rules/templates; tool defs/activations; blueprints)
- **IdentityService / IdentityStore** (tenant+agent+channel identity): maps `(channel, channel_user_id)` → `contact_id` (your "customer_id") for that agent
- **CustomerDataStore** (tenant+agent+contact): structured contact/customer variables for that agent (if the mechanic uses them)
- **SessionStore** (tenant+agent+contact+channel by default): conversation state for one agent ↔ one contact on one channel
- **AuditStore** (tenant-wide, tagged with agent_id): immutable turn records + tool side effects + events (including AgentEvents)
- **MemoryStore** (optional, likely per-agent): semantic memory/episodes for that agent
- **CredentialStore** (tenant-wide): provider credentials used by ToolGateway (not embedded in agent configs)
- **Agenda** (tasks + goals): system of record for scheduled tasks and long-lived objectives (location decided in §8.4)
- **Scheduler** (runtime service): reads due Agenda entries and submits them for execution (see §3.5)

### 🗂️ 8.2 Where do domain concepts go? (Offerings, etc.)

Rule of thumb:
- **Configuration / catalogs / playbooks** → ConfigStore
- **Customer-specific fields** → CustomerDataStore
- **Ephemeral conversation state** → SessionStore
- **System-of-record business data** → access via Tools (do not duplicate in stores unless necessary)
- **Learned/semantic memory** → MemoryStore

### 🗂️ 8.3 Decision: is anything shared across agents?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| For a tenant swarm, what is shared across agents? | You stated "nothing should be shared". We can still share *infrastructure stores* (ConfigStore, AuditStore, CredentialStore) while keeping *contact/session/memory* isolated per agent. | ☐ Share contact identity + contact data across agents | ☑ Nothing shared across agents (contact/session/memory isolated per agent) | ☐ Other: ________ | |

**Implication of "nothing shared":**
- Each agent has its own `contact_id` universe and its own CustomerDataStore/SessionStore/MemoryStore partitions.
- Cross-channel reconciliation happens **within** an agent (multiple channel identities → one contact_id), not across different agents.

### 🗂️ 8.4 Decision: where does "Agenda/Goals" live?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Where should Agenda/Goals state live? | Agenda includes scheduled tasks. With "nothing shared across agents", Agenda is either contact-level (persistent) or session-level (ephemeral) *for this agent*. | ☐ CustomerDataStore (contact-level, persistent) | ☐ SessionStore (conversation-level, ephemeral) | ☑ Separate AgendaStore (new domain store) | **OPUS recommends C** |

**Recommendation (minimize new abstractions):**
- If Agenda contains scheduled tasks that must survive restarts and be queryable by `due_at`, you will almost always want **Option A** (or Option C).
- Prefer **Option B** only if "agenda" is *strictly* in-session objectives and tasks are not scheduled across time (or are short-lived with TTL).
- Avoid Option C until a strong need emerges.

> **🔮 OPUS Analysis (§8.4 - Agenda Store Recommendation Change):**
> I **disagree with the recommendation** here. I'd push for **Option C (separate AgendaStore)** over Option A (CustomerDataStore). Here's why:
> 1. Agenda entries have different access patterns (time-indexed queries: "what's due in the next 5 minutes?")
> 2. Agenda entries may be agent-level (no customer), contact-level, or session-level
> 3. CustomerDataStore is already complex with lineage tracking, status management, etc. (see Phase 17.5 work)
>
> An AgendaStore with a simple interface (`schedule`, `get_due`, `mark_complete`, `cancel`) is worth the abstraction. It's a sixth domain store, but it has clear separation of concerns.

---

## 🔍 9) Abstraction Audit: AgentRuntime / AgentContext

You said you don't see what AgentRuntime/AgentContext bring and you fear too many abstractions.

### 🔍 9.1 What they can provide (if kept)

- **AgentContext**: a runtime bundle:
  - agent configuration
  - a concrete CognitivePipeline instance (mechanic implementation)
  - Toolbox instance (resolved tools + policies)
  - channel bindings/policies
- **AgentRuntime**: lifecycle:
  - build AgentContext once
  - cache it for reuse
  - invalidate on config changes (hot reload)

### 🔍 9.2 Decision: is "Agent" config-only or also the runtime instance?

This is mostly a naming clarity decision, but it has big downstream effects in docs and code:
- cache keys and invalidation are about runtime bundles, not config objects
- ASA modifies configs/blueprints, not runtime bundles

#### Implications (why this matters)

If **Agent = config only**:
- Clear separation between **design-time** (ASA/control plane edits) and **runtime** (cached constructed bundles).
- It becomes easy to talk about "Agent versioning" vs "AgentContext cache invalidation".
- It avoids the classic confusion "why is my Agent mutated in memory?" (the Agent config is immutable-ish; runtime bundle is rebuilt).

If **Agent = config + runtime**:
- Docs are shorter but ambiguity grows: "Agent" refers to two different things (a DB record and a live runtime object).
- It becomes harder to reason about caching, especially with hot reload and multiple pods.

Given your stated goal ("no ambiguity so AI can help build components"), the config-only definition tends to pay off quickly.

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Is "Agent" strictly a persisted config entity, or also the runtime instance? | This drives naming and docs clarity: Agent vs AgentContext vs AgentInstance. | ☑ Agent = config only; runtime is separate (`AgentContext`/`AgentInstance`) | ☐ Agent = both; runtime wrapper names are internal-only | ☐ Other naming scheme: ________ | **OPUS recommends A** |

**Recommendation (reduce ambiguity for humans + AI):**
- Prefer **Option A** in docs: "Agent" is config; runtime is `AgentContext` (or rename to `AgentInstance`).

### 🔍 9.3 Decision: keep, rename, or remove AgentRuntime/AgentContext?

| Question | Context | Option A | Option B | Option C | Your input |
|---|---|---|---|---|---|
| Do we keep `AgentRuntime` and `AgentContext` as first-class concepts? | You're concerned about abstraction count; we can simplify. | ☑ Keep them (mechanic-agnostic; no framework-driven `pipeline_type`) | ☐ Rename to clearer intent (`AgentLoader`/`AgentInstance`) | ☐ Remove for now; construct pipeline/toolbox per request | **OPUS recommends A** |

**Recommendation (pragmatic):**
- Prefer **Option A** or **Option B**, but remove framework-driven routing fields (`pipeline_type = agno/langgraph`) from the Agent model. If multiple mechanics exist, select by mechanic, not framework.
- Option C is valid for maximum simplicity, but docs should still describe how caching/invalidation will be added later.

> **🔮 OPUS Analysis (§9 - Abstractions ARE Needed):**
> The concern about "too many abstractions" is valid but **somewhat overblown**. The proposed abstractions (`AgentRuntime`, `AgentContext`) serve real purposes:
> - `AgentContext` = the runtime bundle (pipeline + toolbox + channels)
> - `AgentRuntime` = lifecycle manager (create, cache, invalidate)
>
> These ARE necessary. Current `AlignmentEngine.process_turn()` receives raw identifiers with no caching, no lifecycle management. Adding this layer is a **prerequisite for multi-mechanic support**.
>
> What's NOT necessary is naming confusion. The doc proposes Agent = config only, AgentContext = runtime. **Stick with it.**

---

## 10) Documentation Governance (AI-friendly, ambiguity-free)

Your stated goal: "interfaces + docs allowing me to build new components with AI easily because there is no ambiguity."

Recommended governance pattern:
- **One canonical vocabulary** (Agent, CognitivePipeline, Mechanic, ACF, Toolbox, CustomerDataStore, SessionStore, LogicalTurn).
- **Spec-first docs** for interfaces/protocols (ACF ↔ Pipeline, Pipeline ↔ Toolbox, Toolbox ↔ Gateway, Stores).
- **Mechanic specs**: each skeleton gets a short "mechanic spec" describing:
  - guarantees (safety/constraint model)
  - config schema (what needs to be provided)
  - events/audit surface
  - dependencies (stores/tools/providers)

---

## 11) Next Step After You Fill This Doc

Once the decisions above are filled:
1) Rewrite docs so the vocabulary is consistent (Soldier history becomes "historical").
2) Update FOCAL 360 authoritative specs to match the mechanic-first model.
3) Create "mechanic specs" for each CognitivePipeline skeleton (starting with FOCAL alignment).
4) Only then resume implementation work with minimal ambiguity.

---

## 🔮 12) OPUS: What's Missing (Additional Considerations)

> **Author**: Claude Opus 4.5
> **Date**: 2025-12-13
> **Context**: Deep review of architecture_reconsideration.md grounded in codebase exploration (44K+ LOC, 258 Python files, FOCAL 360 specs, IMPLEMENTATION_PLAN.md)

After thorough analysis, these are **gaps I'd address before finalizing this document**:

### 12.1 Error Taxonomy and Recovery

The doc doesn't define how errors propagate across boundaries:
- What happens when ToolGateway fails?
- What happens when the pipeline throws?
- What happens when ACF can't acquire mutex?

**Need**: An error taxonomy (retriable vs fatal vs degraded) and how each layer handles upstream/downstream failures.

**Proposed categories**:
| Error Class | Examples | Handler | Recovery |
|-------------|----------|---------|----------|
| **Retriable** | Rate limit, timeout, network glitch | Toolbox/ACF | Exponential backoff, max 3 retries |
| **Fatal** | Auth failure, invalid config, schema violation | Surface to caller | No retry, return error |
| **Degraded** | LLM fallback triggered, tool unavailable | Pipeline | Continue with reduced capability, emit event |
| **Conflict** | Mutex already held, concurrent identity creation | ACF/IdentityService | Wait or fail-fast based on config |

### 12.2 Observability Contract

§4.4 mentions event policies (volume limits, versioning, PII redaction) but doesn't specify:
- What's the cardinality budget per turn? (e.g., max 100 events)
- What events are mandatory vs optional?
- How do channel adapters subscribe to live events?

**Need**: An observability contract section or separate `OBSERVABILITY_CONTRACT.md`.

**Proposed mandatory events**:
- `turn.started`, `turn.completed`, `turn.failed`
- `tool.executed` (for audit)
- `response.generated` (for billing)

### 12.3 Testing Strategy for Multi-Mechanic

When you add ReAct or other mechanics, how do you test pipeline conformance?

**Clarification (per discussion):** ASA is **NOT FOCAL-specific**. ASA is a **mechanic-agnostic meta-agent** that can:
- Understand all available mechanics (alignment, react, planner-executor, custom)
- Configure ANY CognitivePipeline
- Validate conformance for ANY mechanic
- Design domain-specific artifacts per mechanic (scenarios/rules for alignment, tools/prompts for react)

**Need**: A pipeline conformance testing strategy that works across all mechanics.

**Conformance test suite** (every CognitivePipeline must pass):

```python
class PipelineConformanceTests:
    """Tests that ANY CognitivePipeline implementation must pass."""

    async def test_tools_go_through_toolbox(self, pipeline, ctx):
        """Verify no direct provider calls — all tools via Toolbox."""
        # ASA-assisted static analysis + runtime verification

    async def test_required_events_are_emitted(self, pipeline, ctx):
        """Verify required events are emitted."""
        result = await pipeline.run(ctx)
        events = ctx.captured_events
        assert any(e.type == "turn.started" for e in events)
        assert any(e.type == "turn.completed" for e in events)

    async def test_supersede_checked_before_irreversible(self, pipeline, ctx):
        """Verify supersede is checked before irreversible tools."""
        # Inject pending message, verify pipeline checks before tool

    async def test_pipelineresult_contract(self, pipeline, ctx):
        """Verify PipelineResult follows contract."""
        result = await pipeline.run(ctx)
        assert isinstance(result, PipelineResult)
        # Validate response_segments, staged_mutations, etc.
```

**ASA's role per mechanic:**

| Mechanic | ASA Helps Design | ASA Validates |
|----------|------------------|---------------|
| **Alignment (FOCAL)** | Scenarios, rules, templates, step design | Scenario completeness, rule conflicts |
| **ReAct** | Tool selection, prompt design, chain structure | Tool safety, prompt injection risks |
| **Planner-Executor** | Plan templates, execution policies | Plan feasibility, rollback coverage |
| **Custom** | Whatever the mechanic needs (via plugins) | Mechanic-specific constraints |

### 12.4 Hot Reload Semantics

The doc says agents cache with version-based invalidation, but doesn't specify:
- What triggers a version bump? (Any config change? Only breaking changes?)
- Can you hot-reload scenarios/rules without bumping agent version?
- What happens to in-flight turns when invalidation occurs?

**Need**: Explicit hot-reload semantics.

**Proposed rule**: In-flight turns complete with the config they started with. Next turn gets new config. Version bump happens on ANY agent config change (conservative).

### 12.5 The "Content-Based Routing" Question

§6.1 says MessageRouter does NOT question multiple agents — it routes to ONE agent. But what about scenarios like:
- "Route to Sales OR Support based on message content"
- "Route to primary agent, fail over to backup"

These require either:
- MessageRouter having some intelligence (classification), OR
- A "router agent" that receives all messages and hands off

**Need**: Acknowledge this as future consideration or explicitly say "MessageRouter does simple config-based routing, not content-based".

### 12.6 Credential Scope

§7.1 says CredentialStore is tenant-wide, but what about:
- Agent-specific credentials (agent A uses Salesforce sandbox, agent B uses production)?
- Per-tool credential overrides?

**Need**: Clarify if CredentialStore supports `tenant_id + agent_id + tool_id` scoping, or if it's strictly tenant-wide with tool-level selection.

### 12.7 Codebase → Architecture Mapping

For implementers, add a section mapping current code to target architecture:

| Current Code | Target Architecture | Status |
|--------------|---------------------|--------|
| `AlignmentEngine` | `FocalCognitivePipeline` implementing `CognitivePipeline` | Rename/wrap needed |
| `ToolExecutor` | `Toolbox` | Major refactor (add policy, idempotency) |
| (none) | `AgentRuntime`, `AgentContext` | Phase 6.5 - not started |
| (none) | ACF (`SessionMutex`, `TurnManager`, `SupersedeCoordinator`) | Phase 6.5 - not started |
| `CustomerDataStore` | `CustomerDataStore` | ✓ Implemented |
| `SessionStore` | `SessionStore` | ✓ Implemented |
| `/v1/chat` | Agent Ingress (via AgentRuntime) | Needs wrapping |

---

## 🔮 13) OPUS: Decision Summary Table

For quick reference, here are all decisions with final status:

| Section | Decision | Final Choice | Status |
|---------|----------|--------------|--------|
| §1.3 | What does "Focal" refer to? | **Option B** (alignment pipeline only) | ✅ DECIDED |
| §3.3 | Runtime API surface | **Option A** (one ingress endpoint) | ✅ DECIDED |
| §3.4 | Ingress envelope | **Multimodal content** (content_type + content object) | ✅ REVISED |
| §3.5 | Task execution | **Option C** (bypass ACF, Agenda→Hatchet direct) | ✅ DECIDED |
| §4.0 | ACF rename | **Turn Fabric** or **Conversation Runtime** | ⏳ PENDING |
| §4.2 | ACF ↔ Pipeline naming | **Option A** (keep FOCAL 360 naming) | ✅ DECIDED |
| §4.3 | ACF policy config | **Option A** (shared ChannelPolicy model) | ✅ REVISED |
| §4.4 | Event surface | **Option A** (AgentEvent canonical) | ✅ DECIDED |
| §4.5 | Mechanic selection | **Option A** (mechanic ID) | ✅ DECIDED |
| §4.6 | LLMExecutor role | **Option C** (hybrid/optional) | ✅ DECIDED |
| §4.8 | Hatchet abstraction | **Option C** (defer) | ✅ DECIDED |
| §5.5 | Ruche representation | **Option A** (blueprint pack) | ✅ DECIDED |
| §5.6 | Standalone products | **Option A** (hosted multi-tenant) | ✅ DECIDED |
| §6.3 | Identity service | **Option C** (separate service + Redis cache) | ✅ DECIDED |
| §6.4 | Session scope | **Option A** (per-agent) | ✅ DECIDED |
| §6.6 | Cross-channel sessions | **Option A** + **InterlocutorChannelPresence** | ✅ REVISED |
| §7.3 | ToolGateway role | **Option C** (MCP discovery + execution via Toolbox) | ✅ REVISED |
| §7.4 | Toolbox caching | **Option B** (cache, invalidate on change) | ✅ DECIDED |
| §8.0 | Interlocutor terminology | **Option D** (`interlocutor` with type enum) | ✅ DECIDED |
| §8.3 | Shared state | **Option B** (nothing shared) + tenant-scoped data | ✅ DECIDED |
| §8.4 | Agenda location | **Option C** (AgendaStore) | ✅ DECIDED |
| §9.2 | Agent definition | **Option A** (config only) | ✅ DECIDED |
| §9.3 | Keep AgentRuntime/Context | **Option A** (keep them) | ✅ DECIDED |

**Key revisions from discussion:**
- §3.4: Added multimodal envelope support (content_type, media, location, structured)
- §3.5: Tasks bypass ACF entirely (Agenda→Hatchet direct, not through turn workflow)
- §4.3: ChannelPolicy as single source of truth (shared model, not per-lookup)
- §6.6: Added InterlocutorChannelPresence for cross-channel awareness without session merging
- §7.3: MCP for discovery, Toolbox awareness of unavailable tools, execution stays native
- §8.0: Changed from "customer" to "interlocutor" with InterlocutorType enum (human/agent/system/bot)
- §12.3: ASA is mechanic-agnostic (can configure ANY CognitivePipeline)

---

## 🔮 14) OPUS: Final Assessment

This is a **high-quality architecture clarification document**. The vision is coherent, the boundaries are well-defined, and **all major decisions are now finalized**.

**Strengths**:
- Clear separation of concerns (ACF vs Agent vs Pipeline)
- Mechanic-first, framework-agnostic approach
- Strong multi-tenancy foundation already in code
- Realistic provisioning model (Ruche blueprints)
- Interlocutor model supports multi-agent scenarios
- MCP discovery + native execution gives best of both worlds
- Tasks bypass ACF keeps conversation semantics clean

**Key architectural decisions from this revision**:
- **Tasks ≠ Conversations**: Agenda→Hatchet direct, no ACF involvement
- **Interlocutor with types**: human/agent/system/bot enables multi-agent architectures
- **ChannelPolicy as shared model**: Single source of truth, not per-component lookups
- **Cross-channel awareness without session merging**: InterlocutorChannelPresence
- **MCP for discovery, Toolbox for execution**: Three-tier tool visibility model
- **ASA is mechanic-agnostic**: Can configure any CognitivePipeline, not just FOCAL

**Remaining risks**:
- ACF implementation complexity (Phase 6.5 is significant)
- Blueprint version propagation semantics (needs more design for upgrades)
- Interlocutor rename refactoring effort (~30-40 files to update)

**Confidence**: 90% that implementing this design as described will work. The refined decisions (especially Tasks bypassing ACF and Interlocutor typing) address the earlier ambiguities.

**Next actions**:
1. Proceed to doc rewrite with finalized decisions
2. Plan the `customer` → `interlocutor` rename refactoring
3. Address remaining gaps in §12 as implementation proceeds

---

*End of OPUS analysis — decisions finalized 2025-12-14*
