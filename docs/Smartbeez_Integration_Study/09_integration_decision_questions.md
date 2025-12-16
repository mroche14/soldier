# Integration Decision Questions (Answer These to Converge Cleanly)

This file centralizes the **decisions you need to make** to finalize how `sb_agent_hub` and `soldier` integrate, with **contextual options** and a simple way to select an option or specify another.

Use it as a “decision sheet”: copy it into an issue/PR description and tick choices as you decide.

---

## A) Boundary + Ownership (Core)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| What is the primary boundary between repos? | `soldier` docs want ChannelGateway/MessageRouter outside runtime; `sb_agent_hub` already has UI/auth/channels. | **A: sb_agent_hub = Control Plane + Channel Layer; soldier = Cognitive Runtime** (matches `docs/architecture/kernel-agent-integration.md`) | B: soldier owns channels too (sb_agent_hub becomes mostly UI) | C: merge runtimes/monolith | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Who owns the “public client protocol” for webchat? | Browser currently speaks CopilotKit/AG‑UI via sb_agent_hub. | **A: sb_agent_hub owns AG‑UI; maps soldier output/events → AG‑UI** (matches `docs/architecture/event-model.md`) | B: soldier exposes AG‑UI endpoint directly | C: drop AG‑UI and change frontend | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Where do you want “message router/backpressure” to live? | `soldier` docs treat it as external layer. | **A: sb_agent_hub implements it (HTTP/SSE now, bus later)** | B: soldier implements it internally | C: separate third service | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Do you conceptually separate ChannelGateway and MessageRouter? | `soldier` docs and `kernel_agent` contracts treat them as distinct responsibilities; you said they “are the same” for you. | **A: Keep as separate modules, but can be deployed together** (scale independently later) | B: Merge into one service/module (single deployable “GatewayRouter”) | C: ChannelGateway only (no router; rely on soldier ACF for coalescing/supersede) | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## B) Auth + Tenancy (Service-to-Service Trust)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| How does sb_agent_hub authenticate to soldier? | soldier expects JWT with `tenant_id` claim (`ruche/api/middleware/auth.py`). | **A: sb_agent_hub mints internal JWT for soldier (shared secret / dedicated issuer)** | B: forward end-user Supabase/WorkOS tokens to soldier | C: mTLS only + no JWT | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Should soldier enforce token/body tenant match? | Needed to prevent tenant leakage in service integration. | **A: Yes, strict match required** | B: No, trust body only | C: No, trust token only (ignore body tenant_id) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Tenant ID mapping: org_id vs tenant_id | sb_agent_hub uses `organization_id`; soldier uses `tenant_id`. | **A: same UUID (1:1)** | B: mapping table in sb_agent_hub | C: mapping table in soldier | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## C) Sessions + Correlation IDs

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| What is the canonical “conversation/session id”? | sb_agent_hub has `thread_id` (AG‑UI); soldier has `session_id` (API + SessionStore). | **A: soldier `session_id` is canonical; sb_agent_hub stores mapping `thread_id ↔ session_id`** | B: sb_agent_hub thread_id is canonical and passed through | C: derive from channel_user_id only (no explicit sessions) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| What is the canonical “run/turn id”? | sb_agent_hub uses `run_id` (AG‑UI); soldier has `turn_id` / `logical_turn_id` conceptually. | **A: soldier emits `turn_id` and sb_agent_hub maps it to run_id** | B: sb_agent_hub run_id is canonical and passed through | C: both exist; only correlate via trace_id | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## D) Streaming + Events (UI + Audit)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| How do you want soldier → sb_agent_hub streaming to work? | soldier has SSE (`token/done/error`) and ACFEvent model; sb_agent_hub needs AG‑UI SSE. | **A: sb_agent_hub proxies soldier SSE and emits AG‑UI SSE** | B: soldier emits AG‑UI directly | C: sb_agent_hub uses WebSocket only | ☐ A ☐ B ☐ C ☐ Other: ____ |
| How should ACFEvents be transported to sb_agent_hub? | soldier has EventRouter; webhooks exist but not wired. | A: soldier → sb_agent_hub internal webhook delivery | B: sb_agent_hub subscribes to soldier SSE events stream | C: shared message bus (NATS/Redis Streams/Kafka) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Who owns “audit/event store of record”? | Both systems may store audit/run events. | **A: sb_agent_hub is SoT for enterprise audit (UI/activity feed)** | B: soldier is SoT and sb_agent_hub reads | C: separate audit service | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## E) Tools (Definitions, Execution, Semantics)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| ToolDefinitions system of record | soldier currently lacks stable ToolDefinition store; sb_agent_hub has control plane + docs envision manifests. | **A: sb_agent_hub is SoT; publishes ToolDefinitions to soldier** | B: soldier is SoT; sb_agent_hub only activates/connects | C: separate ToolHub service (in sb_agent_hub) is SoT | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Tool identity scheme across services | soldier currently has UUID-based runtime toolbox + string-based brain tools. | **A: stable string tool names as integration key (e.g., `crm.create_ticket`)** | B: UUID tool ids everywhere | C: dual identity (name + uuid mapping) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Where are tools executed? | soldier docs split semantics (Toolbox) vs mechanics (ToolGateway). sb_agent_hub has integration intent (Composio/MCP). | **A: sb_agent_hub executes tools; soldier requests via ToolGateway provider** | B: soldier executes tools directly | C: hybrid: fast tools in soldier, durable tools in sb_agent_hub | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Do you want a dedicated external ToolHub/ToolGateway service? | `kernel_agent/apps/toolhub/` is a concrete standalone ToolHub. You said ToolHub/ToolGateway are “the same”. | **A: Yes, dedicated ToolHub service; soldier calls it** | B: No, keep tool execution inside sb_agent_hub backend | C: No, keep tool execution inside soldier runtime | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Tool execution mode default | Needed for reliability + UX. | A: synchronous (request/response) | B: asynchronous (enqueue + callback) | C: both; per-tool policy | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Side-effect policy canonical enum | soldier has drift between toolbox and ACF side-effect storage. | **A: toolbox enum is canonical; ACF stores opaque records** | B: map COMPENSATABLE→REVERSIBLE etc | C: redefine enums across code/docs | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## F) Config Publishing (Bundles / Revisions / Hot Reload)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| How does sb_agent_hub publish config to soldier? | soldier docs mention Redis bundles + watcher; sb_agent_hub has manifest compiler concept. | A: HTTP push bundles to soldier | B: soldier pulls bundles from sb_agent_hub API | C: publish to shared Redis (bundle store + pub/sub) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Session pinning behavior on config change | Needed for determinism. | **A: soft-pin existing sessions to old config version** | B: always upgrade sessions immediately | C: per-tenant/per-agent policy | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## G) Voice Integration (High-impact, needs explicit choice)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| Who owns voice provider webhooks/protocol? | sb_agent_hub already ingests voice webhooks; soldier expects channel layer outside runtime. | **A: sb_agent_hub owns voice provider integration; calls soldier with transcripts/events** | B: soldier owns provider webhooks | C: separate comms service | ☐ A ☐ B ☐ C ☐ Other: ____ |
| How should transcripts map to ACF “message ≠ turn”? | Voice has partial + final transcripts; barge-in; multi-utterance turns. | **A: send finalized utterances as messages; optionally send partial as “absorb candidates”** | B: stream partial tokens as messages (no final concept) | C: only send post-call full transcript | ☐ A ☐ B ☐ C ☐ Other: ____ |
| What should “barge-in” do? | Needs mapping to supersede decisions. | A: treat as supersede before commit point; restart turn | B: always queue new utterance | C: depends on tool commit point / policy | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Voice provider selection | User explicitly requested internet research (Vapi, Bland.ai, others). | A: Vapi | B: Bland.ai | C: Twilio/Plivo/Vonage/etc | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## H) Stickiness / Session Affinity (Scaling Reality Check)

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| Do you require sticky sessions anywhere? | soldier design target is “stateless pods”; `kernel_agent` also states “zero sticky sessions”, but MessageRouter docs mention session affinity as a routing strategy. | **A: No sticky sessions; use deterministic session keys + shared stores** | B: Sticky only at UI transport (WebSocket/SSE fanout), not at runtime | C: Sticky at router layer for performance (consistent hashing) | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## I) Orchestration + Messaging Stack (Celery / RabbitMQ / Restate / Hatchet / Redis)

See also: `docs/Smartbeez_Orchestration_Study/README.md`

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| What is the single “durable workflow/orchestration” engine? | Today: soldier runtime-plane is Hatchet-centric; kernel_agent control-plane is Restate-centric; sb_agent_hub uses Celery for background tasks. Two orchestration engines increases ambiguity and ops burden. | **A: Hatchet is canonical** (aligns with soldier ACF + webhooks; re-implement kernel publish in Hatchet) | B: Restate is canonical (migrate soldier ACF to Restate actors/workflows) | C: No workflow engine; Celery-only + outbox/state machines in app code | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Do we keep Celery at all? | sb_agent_hub currently uses Celery (Redis broker/backend) for async + periodic tasks; soldier already has Hatchet scheduled runs available (per upstream). | **A: Remove Celery; use Hatchet/Restate scheduling + workers** | B: Keep Celery only for “simple” background jobs (non-critical) | C: Keep Celery as primary execution engine | ☐ A ☐ B ☐ C ☐ Other: ____ |
| What is the message-bus for ChannelGateway↔MessageRouter? | kernel_agent has a concrete Redis Streams contract; soldier docs describe stream subjects; sb_agent_hub currently has mostly HTTP flows. | **A: Redis Streams** (consumer groups + ACK; reuse existing Redis) | B: RabbitMQ (queues/exchanges; mature routing) | C: “No bus”: HTTP push directly into soldier + rely on ACF accumulation | ☐ A ☐ B ☐ C ☐ Other: ____ |
| What is the minimum external dependency set we accept? | Your goal: scalable services, minimal ops, but reliable at enterprise scale. | **A: Postgres + Redis + 1 orchestrator** (Hatchet or Restate) | B: Postgres + Redis + orchestrator + RabbitMQ | C: Postgres + Redis + Celery + RabbitMQ (classic) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Where does idempotency/dedup live? | Needed for at-least-once delivery and retries (tools, messages, publish). | **A: Redis keys** (`SETNX` + TTL; deterministic op hashes) | B: DB outbox + unique constraints | C: Orchestrator-native only (no explicit dedup in app) | ☐ A ☐ B ☐ C ☐ Other: ____ |
| Do we need worker affinity (“stickiness”) as a first-class feature? | You said “maybe stickiness”; Hatchet documents sticky workflows; routers sometimes do consistent hashing. | **A: No, not required** (opt-in later as perf optimization) | B: Yes, for channel routing only (WebSocket fanout) | C: Yes, for runtime execution (per-session worker affinity) | ☐ A ☐ B ☐ C ☐ Other: ____ |

---

## J) “Definition of Done” for the Integration MVP

| Decision | Context | Option A | Option B | Option C | Your choice |
|---|---|---|---|---|---|
| What is the MVP scope? | Avoid “boil the ocean”. | **A: webchat AG‑UI proxy to soldier + auth + session mapping** | B: include tools bridging in MVP | C: include voice in MVP | ☐ A ☐ B ☐ C ☐ Other: ____ |
