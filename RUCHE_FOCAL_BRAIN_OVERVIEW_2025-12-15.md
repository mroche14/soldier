# Ruche + FOCAL Brain Overview

**Date**: 2025-12-15  
**Scope**: High-level architecture + intermediary concepts, with a deep focus on what the FOCAL Brain does once ACF has produced a LogicalTurn.

---

## Executive Summary

**Ruche** is the runtime platform that hosts conversational agents at scale. It is designed to be **API-first, multi-tenant, horizontally scalable**, and **fully persistent** (no “agents in memory” as the system of record).

Ruche’s “thin waist” is **ACF (Agent Conversation Fabric)**: the conversation control plane that turns raw message streams into reliable, serialized **LogicalTurns** and then calls `agent.process_turn(...)`. The Agent encapsulates a **Brain** (thinking) and a **Toolbox** (tool execution boundary).

**FOCAL** is a Brain implementation focused on **alignment**: it converts a LogicalTurn into a **validated, policy-compliant response** by combining:
- deterministic policies (scenarios, rules, templates, tool bindings),
- retrieval (embeddings + optional lexical + rerank + selection strategies),
- LLMs as **sensors/judges** (not the policy engine),
- post-generation enforcement and audit.

---

## Why These Architectural Choices (Justification)

This section justifies the major architecture decisions referenced throughout this document, with pointers to the source specs/ADRs.

### 1) ACF exists (and “a message is not a turn”)

**Decision**: Use ACF to aggregate raw message bursts into a **LogicalTurn**, serialize turn execution per `session_key` (mutex), and provide **supersede signals** as facts.

**Why**:
- Humans send message bursts; treating each message as a turn creates fragmented UX and wasted model calls.
- Without per-session serialization, parallel turn processing creates race conditions and inconsistent state.
- Supersede signaling prevents “ignored corrections” and protects irreversible actions.
- Workflow orchestration and idempotency boundaries reduce crash/retry double-actions.

**Primary refs**: `docs/acf/architecture/ACF_JUSTIFICATION.md`, `docs/acf/architecture/ACF_ARCHITECTURE.md`, `docs/acf/architecture/ACF_SPEC.md`, `docs/acf/architecture/topics/01-logical-turn.md`, `docs/acf/architecture/topics/02-session-mutex.md`, `docs/acf/architecture/topics/03-adaptive-accumulation.md`, `docs/acf/architecture/topics/12-idempotency.md`.

### 2) “Thin waist” separation (ACF vs Agent vs Brain)

**Decision**: ACF owns infrastructure only; Agent owns Brain + Toolbox; Brain owns business decisions for the LogicalTurn.

**Why**:
- Keeps infrastructure generic so you can plug in different brains (FOCAL, LangGraph, Agno) without rewriting turn mechanics.
- Prevents infrastructure from accumulating business semantics (scenarios/rules/tools), reducing coupling and drift.

**Primary refs**: `docs/acf/architecture/ACF_ARCHITECTURE.md`, `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`.

### 3) Toolbox is the execution boundary (MCP for discovery, not execution)

**Decision**: Tools execute natively via `Toolbox → ToolGateway`, and MCP is used for **tool discovery** only.

**Why**:
- Tool execution needs enforced semantics: side-effect policy (PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE), confirmation, idempotency, audit emission.
- Separating semantics (Toolbox) from mechanics (ToolGateway) keeps policies consistent even as providers change.
- Keeping execution out of MCP avoids protocol overhead and reduces the “LLM tool call = real side effect” footguns.

**Primary refs**: `docs/acf/architecture/TOOLBOX_SPEC.md`, `docs/architecture/event-model.md`, `docs/acf/architecture/ACF_SPEC.md`.

### 4) Stateless pods: persistence-first, multi-tenant everywhere

**Decision**: No pod-local conversational state; all state lives in stores, and every read/write is scoped by `tenant_id`.

**Why**:
- Horizontal scaling: any pod can serve any request.
- Hot-reload behavior updates: config changes take effect without rebuilding/restarting.
- Prevents cross-tenant leakage by design (IDs and keying are tenant-scoped).

**Primary refs**: `docs/architecture/overview.md`, `docs/architecture/kernel-agent-integration.md`, `docs/design/decisions/001-storage-choice.md`.

### 5) Domain-aligned stores (+ why InterlocutorDataStore exists)

**Decision**: Split persistence into domain-aligned store interfaces (Config/Session/Memory/Audit). Additionally, maintain a persistent **InterlocutorDataStore** for verified, structured cross-session facts.

**Why**:
- Each store has different access patterns (read-heavy config, append-heavy memory, low-latency sessions, immutable audit), so separate interfaces let you optimize per domain.
- InterlocutorDataStore prevents repeated questions across sessions and enables scenario step skipping with verified facts, without forcing everything into unstructured “memory episodes”.

**Primary refs**: `docs/design/decisions/001-storage-choice.md` (4 stores), `docs/design/interlocutor-data.md` (InterlocutorDataStore), `docs/architecture/memory-layer.md`.

### 6) FOCAL: multi-stage alignment instead of “just prompts”

**Decision**: Implement a Brain that uses LLMs as **sensors/judges** inside a deterministic pipeline (retrieval → filtering → orchestration → tools → planning → generation → enforcement → persistence).

**Why**:
- Reduces the “prompt trap” by making policy explicit and enforceable at runtime.
- Keeps latency/cost predictable by confining LLM judgment to small candidate sets and structured tasks.
- Makes behavior auditable (“why did it match this rule / take this action?”).

**Primary refs**: `docs/focal_brain/spec/brain.md`, `docs/architecture/alignment-engine.md`.

### 7) Hybrid retrieval + dynamic k selection

**Decision**: Use embeddings (and optionally lexical/BM25) for candidate retrieval, then apply **selection strategies** (adaptive k / elbow / entropy / clustering) before LLM filtering.

**Why**:
- Pure vector retrieval can miss exact tokens (IDs) and can include noisy tails; hybrid improves robustness.
- Fixed `top_k` is brittle; dynamic selection uses score distributions to keep recall while minimizing noise and downstream LLM cost.

**Primary refs**: `docs/design/decisions/002-rule-matching-strategy.md`, `docs/architecture/selection-strategies.md`.

### 8) Scenario updates and step skipping

**Decision**: Support long-lived sessions with scenario version reconciliation and migration plans; allow step skipping when required data already exists.

**Why**:
- Real deployments need urgent workflow updates without corrupting active sessions.
- Step skipping improves UX by avoiding redundant questions when the system already knows required fields.

**Primary refs**: `docs/design/scenario-update-methods.md`, `docs/focal_brain/spec/brain.md`.

### 9) Enforcement after generation (always-enforce GLOBAL hard constraints)

**Decision**: Post-generation enforcement validates responses against hard constraints, including **always** applying GLOBAL hard constraints even if retrieval didn’t surface them.

**Why**:
- Retrieval is probabilistic; safety/compliance constraints must not be “missed” due to similarity thresholds.
- Two-lane enforcement (deterministic expressions + LLM judge for subjective policies) keeps strict rules strict while still enforcing “soft” policies.

**Primary refs**: `docs/focal_brain/spec/brain.md` (Phase 10), `docs/design/old/enhanced-enforcement.md`.

### 10) Two-layer events (AgentEvent semantic, ACFEvent transport)

**Decision**: Emit semantic AgentEvents and wrap them in ACFEvents for routing/persistence; ACF interprets only reserved `infra.*` for invariants.

**Why**:
- Decouples platform routing from business meaning so new Brain/Toolbox events don’t require ACF changes.
- Preserves infrastructure invariants (commit points, tool lifecycle tracking) without coupling ACF to domain semantics.

**Primary refs**: `docs/architecture/event-model.md`, `docs/acf/architecture/ACF_SPEC.md`.

### 11) Typed config + secret hygiene

**Decision**: TOML configuration validated by Pydantic; secrets resolved from env/secret managers (never committed). Per-step provider configuration (models + fallbacks) is explicit.

**Why**:
- Typed config catches errors early and keeps runtime behavior stable across environments.
- Prevents secret leakage and supports safe ops practices.
- Per-step model selection enables cost/quality tuning where it matters (sensor vs generation vs judge).

**Primary refs**: `docs/architecture/configuration-overview.md`, `docs/architecture/configuration-secrets.md`, `docs/focal_brain/spec/configuration.md`.

### 12) Observability and auditability as first-class requirements

**Decision**: Structured logs + traces + metrics, plus a durable TurnRecord in AuditStore.

**Why**:
- Production failures are often “mechanics” or “policy” bugs that require step-level visibility.
- Audit trails are required for regulated workflows and for explaining agent behavior.

**Primary refs**: `docs/architecture/observability.md`, `docs/design/decisions/001-storage-choice.md` (AuditStore), `docs/architecture/event-model.md`.

---

## The Mental Model (What Lives Where)

### Layering (who owns what)

| Layer | Owns | Does NOT own |
|---|---|---|
| **ChannelGateway (often external)** | Channel protocol, webhooks, provider quirks | Brain logic, scenarios/rules, tool semantics |
| **API layer (Ruche)** | Request validation, turn ingestion endpoints | Channel-specific delivery mechanics |
| **ACF (Ruche runtime)** | Session mutex, turn aggregation, supersede *signals*, workflow orchestration, ACFEvent routing | Tool semantics/execution, business logic, Brain choice |
| **Agent (runtime)** | Brain + Toolbox + channel policies/bindings | Turn lifecycle orchestration |
| **Brain (FOCAL)** | “What to do” and “what to say” for a LogicalTurn | Infrastructure invariants (mutex/aggregation) |
| **Toolbox / ToolGateway** | Tool execution boundary, policy/idempotency/audit | Business meaning of conversations |
| **Stores + Providers** | Persistence + external AI/tool capabilities | Cross-layer decision making |

### Core “units” you see everywhere

- **Raw Message**: one inbound message from a channel.
- **LogicalTurn**: one *conversational beat* (1+ raw messages aggregated by ACF).
- **Session**: the ongoing conversation state for a `session_key` (tenant + agent + interlocutor + channel).
- **Interlocutor**: the conversation participant (usually the human customer), identified across channels.

### Canonical IDs (ACF-centric)

From `docs/acf/README.md`:
- `message_id`: one raw inbound message
- `logical_turn_id`: the aggregated processing unit
- `turn_group_id`: idempotency scope across supersede chain
- `session_key`: concurrency boundary (e.g., `{tenant}:{agent}:{customer}:{channel}`)

---

## Tenant Capabilities (What Customers of This Service Can Do)

This section describes what a **tenant** (a customer organization using Ruche) can configure, operate, and integrate.

### 1) Choose how configuration is owned (deployment mode)

From `docs/architecture/overview.md` and `docs/design/api-crud.md`:

- **Standalone mode**: Ruche is the source of truth for configuration.
  - Tenants (or the service operator on their behalf) use Ruche’s configuration APIs to create/update agents, scenarios, rules, templates, tools, etc.
- **External control plane mode**: Ruche consumes read-only configuration bundles (e.g., Redis bundles) published by an external Control Plane.
  - Tenants integrate Ruche into a broader platform where configuration is managed elsewhere and pushed to Ruche via bundle updates.

**Tenant identity & access** (deployment-dependent):
- In an “external platform” style deployment, authentication/tenant resolution can happen upstream and requests arrive already labeled with `tenant_id`/`agent_id` (see `docs/architecture/api-layer.md`, `docs/architecture/kernel-agent-integration.md`).
- In standalone mode, the API design assumes JWT-based tenant scoping and auditable CRUD mutations (see `docs/design/api-crud.md`).

### 2) Create and manage Agents

An **Agent** is the top-level container for behavior and integrations (see `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`, `docs/design/api-crud.md`):
- Create multiple agents per tenant (each with its own policies, tools, scenarios, rules, channels).
- Select which **brain mechanic** the agent uses (FOCAL alignment, or another Brain implementing the protocol).
- Configure agent-level defaults (system prompt, generation settings, limits, feature flags).

### 3) Define conversational workflows with Scenarios (and update them safely)

Tenants can model workflows (returns, onboarding, KYC) as **Scenario graphs**:
- Steps + transitions + step metadata (including checkpoint semantics for irreversible business actions).
- Per-step templates and/or overrides (e.g., channel formatting expectations; optional step-level model overrides per the config hierarchy).
- **Safe mid-flight updates** via scenario migration planning (anchor-based migration), so long-lived sessions don’t corrupt when scenarios change.

Primary refs: `docs/design/api-crud.md`, `docs/design/scenario-update-methods.md`, `docs/focal_brain/spec/brain.md` (Phase 6).

### 4) Define behavioral policies with Rules (including enforcement)

Tenants can author **Rules** (“when X, then Y”) and tune how they apply:
- Scope (GLOBAL / SCENARIO / STEP), priority, enable/disable, cooldowns, fire limits.
- Retrieval configuration (hybrid matching strategies and selection cutoffs).
- Hard constraints and enforcement behavior (deterministic expressions + subjective “LLM judge” lane).
- Attach rule actions: templates, tool bindings, response constraints (“must include / must avoid”).

Primary refs: `docs/design/decisions/002-rule-matching-strategy.md`, `docs/architecture/selection-strategies.md`, `docs/focal_brain/spec/brain.md` (Phases 4–5, 10).

### 5) Control language with Templates

Tenants can create **Templates** for controlled responses:
- **SUGGEST**: LLM may adapt phrasing.
- **EXCLUSIVE**: bypass the LLM (fully deterministic).
- **FALLBACK**: used for safe fallback when enforcement blocks or repeated retries fail.

Primary refs: `docs/design/domain-model.md` (Template modes), `docs/focal_brain/spec/brain.md` (Phases 8–10).

### 6) Define and manage Interlocutor Data (structured facts across sessions)

Tenants can define a structured “customer facts” layer that persists across sessions:
- Define the **schema** (`InterlocutorDataField`) including type/validation, PII markings, encryption/retention semantics.
- Persist **verified values** per interlocutor in InterlocutorDataStore, enabling:
  - step skipping (“don’t ask again if we already know this”),
  - safer tool calls (validated inputs),
  - consistent behavior across multiple scenarios and channels.
- Maintain cross-channel presence awareness (without merging sessions).

Primary refs: `docs/design/interlocutor-data.md`, `docs/focal_brain/spec/data_models.md`, `docs/focal_brain/spec/brain.md` (Phases 2–3, 6–7, 11).

### 7) Add domain vocabulary and intent catalogs (optional, but powerful)

Tenants can add:
- A **Glossary** (business terms and usage notes) to improve situational sensing and consistent phrasing.
- An **Intent Registry** (canonical intent labels + example phrases) to stabilize analytics and improve retrieval/selection.

Primary refs: `docs/focal_brain/spec/brain.md` (Phase 2 + Phase 4 note), `docs/architecture/intent-registry.md`.

### 8) Connect Tools and control tool safety

Tenants can connect tools and decide how/when tools can execute:
- Tool definitions + activations enable the three-tier model: catalog → tenant-available → agent-enabled.
- Side-effect policy declarations (PURE/IDEMPOTENT/COMPENSATABLE/IRREVERSIBLE), confirmation requirements, idempotency keys, retries/timeouts.
- Tool discovery via MCP endpoints; execution is via Toolbox for reliability and audit.

Primary refs: `docs/acf/architecture/TOOLBOX_SPEC.md`, `docs/acf/architecture/topics/04-side-effect-policy.md`, `docs/acf/architecture/topics/12-idempotency.md`.

### 9) Configure channels and channel-specific behavior

Tenants can control channel behavior through **ChannelPolicy** (single source of truth):
- Accumulation window and supersede default mode (QUEUE/INTERRUPT/IGNORE).
- Formatting and capability constraints (markdown support, max message length, rich media support).
- Outbound rate limits and UX behaviors (typing indicators, natural response delay).

Primary refs: `docs/acf/architecture/AGENT_RUNTIME_SPEC.md` (ChannelPolicy), `docs/acf/architecture/topics/10-channel-capabilities.md`, `docs/architecture/channel-gateway.md`.

### 10) Choose providers and per-step model routing (LLMs, embeddings, rerank, multimodal)

Tenants (or the service operator) can configure which models/providers are used per brain step:
- Separate models for situational sensing, filtering, generation, and enforcement/judging.
- Fallback chains and (when using OpenRouter) provider routing preferences.
- Embedding and rerank providers for retrieval quality/latency trade-offs.

Primary refs: `docs/focal_brain/spec/configuration.md`, `docs/architecture/configuration-secrets.md`, `docs/architecture/configuration-models.md` (provider categories; marked partially stale).

### 11) Run conversations via the API (chat, streaming, sessions, memory)

Tenants can operate the system through the Ruche API surface (exact auth/routing depends on deployment):
- **Chat**: submit inbound messages (multimodal envelope) and receive the agent response; optionally stream via SSE.
- **Idempotency**: provide an idempotency key to safely retry requests without double-processing.
- **Sessions**: query and manage session state (channel-scoped sessions, scenario state, etc.).
- **Memory**: ingest episodes and query memory/search endpoints when enabled.

Primary refs: `docs/architecture/api-layer.md`, `docs/design/api-crud.md`.

### 12) Observe, integrate, and export events

Tenants can observe and integrate via:
- **AuditStore / TurnRecords**: durable “why did it do that” trace per turn.
- **Webhooks**: push delivery of platform events to tenant endpoints, filtered by patterns, signed (HMAC-SHA256), with durable retries.
- **Metrics and tracing**: Prometheus (`/metrics`) + OpenTelemetry spans per step.

Primary refs: `docs/architecture/observability.md`, `docs/architecture/event-model.md`, `docs/architecture/webhook-system.md`.

### 13) Safety and lifecycle features tenants can enable

Depending on deployment and product surface, tenants can leverage:
- **Abuse detection** (rate limiting + background pattern analysis).
- **Agenda & goals** for proactive follow-ups and reminders (Hatchet-driven).
- **ASA** (Agent Setter Agent) for design-time validation, conformance testing, and configuration assistance.

Primary refs: `docs/acf/architecture/topics/11-abuse-detection.md`, `docs/acf/architecture/topics/09-agenda-goals.md`, `docs/acf/architecture/topics/13-asa-validator.md`.

### 14) The configuration hierarchy (tenant → agent → scenario → step)

Tenants can customize behavior at multiple levels and override progressively:
`tenant defaults → agent overrides → scenario overrides → step overrides`.

Primary refs: `docs/acf/architecture/topics/08-config-hierarchy.md`.

---

## Ruche Platform: How a Message Becomes a Turn

**Key principle**: *a message is not a turn*. Ruche treats the semantic unit as a **LogicalTurn**, not a single message.

### End-to-end (platform) flow

```
External Channel (WhatsApp/Slack/Web/Voice)
  └─> ChannelGateway (normalize + verify + tenant resolve)
        └─> Message Router (agent routing, backpressure)
              └─> Ruche API (POST /v1/chat)
                    └─> ACF:
                          - acquire session mutex
                          - aggregate raw messages -> LogicalTurn
                          - run workflow steps
                          - call agent.process_turn(fabric_ctx)
                                └─> Agent (Brain + Toolbox)
                                      └─> Brain.think(...)  [FOCAL]
                                            └─> Toolbox.execute(...) as needed
                    └─> response -> outbound routing -> ChannelGateway -> user
```

### ACF (Agent Conversation Fabric) in one page

ACF is **pure conversation infrastructure** (see `docs/acf/architecture/ACF_ARCHITECTURE.md`, `docs/acf/architecture/ACF_SPEC.md`):

- **SessionMutex**: prevents concurrent brain runs for the same `session_key`.
- **TurnManager**: aggregates message bursts into a LogicalTurn (timing windows, channel hints).
- **SupersedeCoordinator**: provides *facts* (“new message arrived”) via `has_pending_messages()`. The Brain decides how to react.
- **Workflow orchestration**: durable steps (Hatchet-backed) for retries and recovery.
- **ACFEvent routing**: transports events; does not interpret business semantics.

---

## Agent Runtime + Toolbox (the “business container”)

### AgentRuntime

The runtime manages Agent lifecycles and constructs `AgentContext` (see `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`):
- loads Agent configuration (and associated policies)
- instantiates a Brain (FOCAL, or another Brain implementing the protocol)
- instantiates a Toolbox (tool registry + execution facade)
- caches “warm” agent contexts and invalidates them on config change

### Toolbox / ToolGateway

Tool execution is intentionally *not* done by ACF and is not “just an LLM function call”.

From `docs/acf/architecture/TOOLBOX_SPEC.md`:
- **Toolbox** owns tool semantics (side-effect policy, confirmation, availability tiers) and is the enforcement boundary.
- **ToolGateway** owns execution mechanics (provider adapters, idempotency plumbing).
- **MCP is for discovery**, not execution (execution is native via Toolbox → ToolGateway).

Tool visibility is a **three-tier model**:
1. Catalog (ecosystem-wide)
2. Tenant-available (connected/purchased)
3. Agent-enabled (what the agent can execute right now)

---

## Stores, Providers, and Configuration (the “horizontal scaling” enablers)

### Domain-aligned stores (persistence split by intent)

Ruche’s persistence is explicitly divided so each pod can be stateless. Canonically this is described as **4 domain-aligned stores** (Config/Session/Memory/Audit), and the design also introduces **InterlocutorDataStore** for persistent, structured cross-session facts.

| Store | Question | Typical contents |
|---|---|---|
| **ConfigStore** | “How should it behave?” | Agents, Scenarios, Rules, Templates, InterlocutorDataFields, Glossary, Intents |
| **SessionStore** | “What’s happening now?” | SessionState: active scenarios, step positions, turn variables |
| **MemoryStore** | “What does it remember long-term?” | Episodes, Entities, Relationships; vector + graph retrieval |
| **AuditStore** | “What happened?” | TurnRecords, immutable events for audit/compliance |

**InterlocutorDataStore**: “What do we know about this interlocutor across sessions?” → verified/structured facts + cross-channel presence (`docs/design/interlocutor-data.md`).

See also: `docs/design/decisions/001-storage-choice.md`, `docs/design/interlocutor-data.md`, `docs/architecture/memory-layer.md`.

### Providers (pluggable AI capabilities)

The Brain calls abstract provider interfaces (LLM, embeddings, rerank) rather than hardcoding a vendor. LLM routing and fallbacks are configured per task/step.

### Configuration (TOML + Pydantic models)

See `docs/architecture/configuration-overview.md` and `docs/architecture/configuration-secrets.md`:
- defaults in Pydantic models
- `config/default.toml` + environment override TOML
- secret values resolved from env / secret managers (never committed)

---

## FOCAL Brain: What It Does (Once ACF Gives It a LogicalTurn)

FOCAL is an **alignment-focused** Brain: it transforms a LogicalTurn into a response that follows business policies (rules/scenarios/templates) and is post-validated (enforcement), producing a full audit trail.

**Key stance**: LLMs are **sensors and judges**, not the policy engine.

### Key inputs/outputs

- **Input**: LogicalTurn (1+ messages) + `tenant_id` + `agent_id` + channel context
- **Output**: user-facing response + a `TurnRecord` (audit) + updated session/profile state

### The 11-phase FOCAL Brain (spec)

From `docs/focal_brain/spec/brain.md` (runs once per LogicalTurn):

1. **Identification & context loading**: resolve session/interlocutor; load SessionState, InterlocutorData, config, glossary; build `TurnContext`
2. **Situational sensor (LLM)**: schema-aware + glossary-aware understanding; produce `SituationalSnapshot` incl. candidate variables
3. **InterlocutorDataStore update**: validate/coerce candidate variables; apply in-memory updates; track deltas to persist
4. **Retrieval & selection**: embeddings + lexical features; retrieve intents/rules/scenarios; rerank + selection strategies choose dynamic k
5. **Rule selection**: scope/lifecycle filters + optional LLM filter; *then* relationship expansion; produce `applied_rules`
6. **Scenario orchestration**: lifecycle + step transitions + step skipping; produce a `ScenarioContributionPlan`
7. **Tool scheduling & execution**: run tools bound to contributing rules/steps; produce `engine_variables`
8. **Response planning**: merge scenario contributions + rule constraints; decide ASK/ANSWER/MIXED/ESCALATE; produce `ResponsePlan`
9. **Generation (LLM)**: prompt from plan + rules + variables + glossary; produce `channel_answer` + outcome categories
10. **Enforcement & guardrails**: always-enforce GLOBAL hard constraints + matched constraints; deterministic expressions + LLM-as-judge; retry/fallback as needed
11. **Persistence & output**: update/persist SessionState + InterlocutorData + TurnRecord; emit metrics/traces; return response

### Parallelism (where FOCAL can go fast)

From `docs/focal_brain/spec/execution_model.md`:
- P1 can parallelize loading InterlocutorDataStore and config/glossary once routing IDs are known.
- P4 retrievals (rules/scenarios/memory/intents) can run in parallel after embeddings.
- P11 persistence writes can run in parallel.

---

## Intermediary Concepts (How FOCAL “Thinks” Without Becoming a Prompt Monster)

This section is the glue: the concepts that sit *between* ACF and the final response.

### Interlocutor Data (schema + values + privacy mask)

FOCAL uses a two-part architecture (see `docs/design/interlocutor-data.md`, `docs/focal_brain/spec/data_models.md`):
- **InterlocutorDataField**: schema definition (what fields exist for an agent)
- **InterlocutorDataStore**: values per interlocutor (cross-session, cross-scenario)
- **InterlocutorSchemaMask**: privacy-safe view for LLM tasks (field exists/type/scope, but not values)
- **InterlocutorChannelPresence**: awareness of activity across channels (without merging sessions)

This is why the situational sensor can be schema-aware without leaking PII into prompts.

### Scenarios (multi-step flows) + migration

A Scenario is a directed graph of steps with transitions, used for workflows like onboarding, returns, KYC.

FOCAL’s orchestration phase (P6) supports:
- multiple active scenarios at once
- lifecycle decisions (start/continue/pause/complete/cancel)
- **step skipping / re-localization** when required data already exists

Scenario updates mid-session are handled via migration plans (see `docs/design/scenario-update-methods.md`).

### Rules (behavior policies)

Rules are “when X, then Y” policies, typically scoped (GLOBAL/SCENARIO/STEP) and ordered (priority + deterministic tiebreaking).

FOCAL’s rule path (P4–P5) is intentionally multi-stage:
1. retrieve candidates (semantic/lexical)
2. select dynamic k (score-distribution strategies)
3. filter by scope/lifecycle
4. optional LLM filter (APPLIES / NOT_RELATED / UNSURE)
5. expand rule relationships only after final selection

See: `docs/design/decisions/002-rule-matching-strategy.md`, `docs/architecture/selection-strategies.md`.

### Templates (controlled language)

Templates allow deterministic or semi-deterministic responses:
- **SUGGEST**: LLM may adapt
- **EXCLUSIVE**: bypass LLM
- **FALLBACK**: used when enforcement fails or hard constraints block

Templates can be attached to scenario steps (and are a candidate extension for rules).

### Intent Registry (canonical analytics + matching)

FOCAL can combine:
- situational sensor intent (LLM)
- retrieved canonical intents (hybrid)

This supports stable analytics (“refund_request intent”) and can improve downstream selection.
See: `docs/architecture/intent-registry.md`.

### Memory Layer (long-term context)

The memory layer stores Episodes + Entities + Relationships with bi-temporal modeling.
FOCAL can retrieve memory for grounding and can ingest new memories post-turn.
See: `docs/architecture/memory-layer.md`.

### Enforcement (post-generation truth serum)

Enforcement is post-generation validation and remediation (P10), including:
- “always-enforce GLOBAL” hard constraints even if they didn’t match retrieval
- deterministic expression evaluation (“Lane 1”)
- LLM-as-judge for subjective constraints (“Lane 2”)
- optional relevance/grounding checks with explicit bypass conditions

See: `docs/focal_brain/spec/brain.md` (Phase 10), `docs/architecture/error-handling.md`.

---

## Observability: Events, Logs, Traces, and Audit

### Event model (semantic vs transport)

From `docs/architecture/event-model.md`:
- **AgentEvent** = semantic meaning (scenario activated, tool execution completed, policy blocked…)
- **ACFEvent** = transport wrapper for routing/persistence; ACF does not interpret payloads except reserved `infra.*`

### Logs / traces / metrics

From `docs/architecture/observability.md`:
- structured JSON logs with context (`tenant_id`, `agent_id`, `session_id`, `logical_turn_id`, `trace_id`)
- OpenTelemetry spans per step
- Prometheus metrics (`/metrics`)

### AuditStore (TurnRecord)

FOCAL produces a durable TurnRecord (P11) capturing:
- inputs and resolved context
- selected rules/scenarios and why
- tool calls + outcomes
- enforcement results and fallbacks
- timings and token usage

This enables debugging, compliance, and “why did it answer that way?” analysis.

---

## Where to Start in This Repo

If you want to *understand* Ruche and FOCAL quickly:

1. `docs/acf/README.md` (ACF overview + canonical terms)
2. `docs/acf/architecture/ACF_ARCHITECTURE.md` (platform boundaries, v3.0)
3. `docs/focal_brain/README.md` and `docs/focal_brain/spec/brain.md` (FOCAL phases)
4. `docs/architecture/overview.md` (system map)
5. `docs/design/interlocutor-data.md` + `docs/architecture/memory-layer.md` (state and memory)
6. `docs/architecture/event-model.md` (what gets emitted, and by whom)

Code map (high level):
- `ruche/runtime/` — ACF + AgentRuntime mechanics
- `ruche/brains/focal/` — FOCAL brain implementation (engine/pipeline/models/prompts)
- `ruche/infrastructure/` — stores, providers, toolbox, channels
- `ruche/domain/` — domain models (pure)
- `ruche/api/` — REST/gRPC/MCP interfaces

---

## Notes on Documentation Drift (What to Watch For)

Some documents explicitly warn they may be stale (e.g., `docs/doc_skeleton.md` and older readiness/gap analyses). Also:
- Some places refer to an “11-phase” FOCAL spec, while some code/docs mention a “12-phase” pipeline split (often just finer-grained separation like persistence as its own phase).
- A few older paths/names appear in older docs (e.g., `CustomerProfile` vs `InterlocutorDataStore`). Prefer the renamed, canonical terms in `docs/design/interlocutor-data.md` and `docs/acf/`.

When in doubt, treat these as “most authoritative”:
1. `docs/acf/architecture/*` (marked AUTHORITATIVE)
2. `docs/architecture/event-model.md` (AUTHORITATIVE)
3. `docs/focal_brain/spec/*` (FOCAL Brain normative spec)

---

## Source Docs (Primary References)

- `docs/acf/README.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/acf/architecture/ACF_JUSTIFICATION.md`
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- `docs/acf/architecture/TOOLBOX_SPEC.md`
- `docs/acf/architecture/topics/01-logical-turn.md`
- `docs/acf/architecture/topics/02-session-mutex.md`
- `docs/acf/architecture/topics/03-adaptive-accumulation.md`
- `docs/acf/architecture/topics/04-side-effect-policy.md`
- `docs/acf/architecture/topics/08-config-hierarchy.md`
- `docs/acf/architecture/topics/09-agenda-goals.md`
- `docs/acf/architecture/topics/10-channel-capabilities.md`
- `docs/acf/architecture/topics/11-abuse-detection.md`
- `docs/acf/architecture/topics/12-idempotency.md`
- `docs/acf/architecture/topics/13-asa-validator.md`
- `docs/architecture/overview.md`
- `docs/architecture/alignment-engine.md`
- `docs/architecture/api-layer.md`
- `docs/architecture/channel-gateway.md`
- `docs/architecture/configuration-overview.md`
- `docs/architecture/configuration-models.md`
- `docs/architecture/configuration-secrets.md`
- `docs/architecture/kernel-agent-integration.md`
- `docs/architecture/observability.md`
- `docs/architecture/event-model.md`
- `docs/architecture/memory-layer.md`
- `docs/architecture/selection-strategies.md`
- `docs/architecture/intent-registry.md`
- `docs/architecture/webhook-system.md`
- `docs/design/api-crud.md`
- `docs/design/domain-model.md`
- `docs/design/interlocutor-data.md`
- `docs/design/scenario-update-methods.md`
- `docs/design/decisions/001-storage-choice.md`
- `docs/design/decisions/002-rule-matching-strategy.md`
- `docs/design/old/enhanced-enforcement.md`
- `docs/focal_brain/README.md`
- `docs/focal_brain/spec/brain.md`
- `docs/focal_brain/spec/configuration.md`
- `docs/focal_brain/spec/data_models.md`
- `docs/focal_brain/spec/execution_model.md`
- `docs/vision.md`
