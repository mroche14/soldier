# FOCAL 360 Customer-Facing Agent

## Reliability-first architecture add-ons around the existing 11-phase turn pipeline

### Why this document exists

You already have a robust **11-phase, turn-scoped alignment pipeline** with strong multi-tenant boundaries, schema-driven customer data, LLM-as-sensor/judge, and full observability via TurnRecord.
This rewrite reframes your latest ideas as a coherent **platform layer** around that pipeline, so you can scale from "a safe turn engine" to a **360 customer support / sales / after-sales system** across channels, with controlled side effects and tenant-friendly configuration.

---

## 1. North-star product goals (what your additions optimize for)

1. **Reliability & alignment by construction**
   The pipeline already encodes that LLMs should not be policy engines; they are sensors/judges inside deterministic control.
   Your proposed add-ons mainly strengthen *system-level* integrity: concurrency, abuse, side effects, and configurability.

2. **Transparency & auditability**
   Every turn yields a TurnRecord audit trail.
   The new pieces should also emit structured audit events and map cleanly into Phase 11.

3. **Controllability for tenants**
   Your configuration is currently **TOML-based at startup**, with a plan to move to a DB/event-driven config system.
   The agent-level customization you want is a direct extension of P1.6's "Load static config" step.

---

## 2. Existing core: your 11 phases (short recap with "why it stays")

You already have an excellent turn pipeline backbone. This document treats it as stable:

### Phase 1 – Identification & context loading

This already includes the essential shape for multi-channel, multi-tenant routing, customer/session resolution, static config load, and **scenario reconciliation**.
P1.7 explicitly acknowledges version changes and points to your scenario migration methods doc.

**Why this stays**
It's the correct anchor for adding:

* channel-aware customer reconciliation,
* agent-level configuration selection,
* concurrency/turn sequencing policies (as a pre-step or P1 substep).

### Phase 2 – Schema-aware situational sensor

You already designed the right privacy boundary: the sensor sees **masked schema**, not raw values.

**Why this stays**
It is the best place to keep low-risk "understanding" tasks: intent hints, extraction candidates, scenario cues, etc., without letting policy drift into the LLM.

### Phase 4 – Unified retrieval + selection

Your "per-object-type rerank + strategy" pipeline is a strong scaling primitive.
And you already document how it's tuned per object type.

### Phase 7 – Tool execution

This is the natural home for **side-effect gating** and "commit points", because tool bindings live at steps.

### Phase 8 – Response planning

Your ResponsePlan already supports synthesizing multiple scenario contributions.
This is where "multi-message answer generation" belongs as a *plan-level option*.

### Phase 9 – Generation + semantic categories

Your design cleanly separates:

* categories detected by the generation LLM
* categories the pipeline already knew earlier
  This is crucial for observability and for your "parallel scenarios in one turn" use case.

### Phase 10 – Enforcement

You already provision a strict enforcement block with retries.

### Phase 11 – Persistence & audit

This is where all your new features should leave durable traces.

---

## 3. The missing platform layer: **Ingress Control** (new wrapper around the turn)

Your earlier description about handling "two or three messages back to back" is less about classic throttling and more about **debouncing / coalescing / turn-gating**.

### 3.1 Key concept: "debouncing" at the conversational level

Debouncing means: when multiple events arrive quickly, you **delay/merge** so you don't emit multiple outputs for essentially one user burst.
In your context:

* User sends 2–3 messages in rapid succession.
* System should avoid generating 2–3 separate answers if the second message clarifies the first.

### 3.2 Why this is distinct from throttling

* **Throttling / rate limiting**: caps volume over time.
* **Debouncing / coalescing**: avoids duplicate *responses* within a micro-window because the user is still "typing the thought."

You can implement both, but they solve different problems.

### 3.3 Where it fits in your pipeline

Introduce a **pre-P1 Ingress Control layer** (or P1.0):

**Inbound burst policy**

1. Detect burst window by (tenant_id, agent_id, customer_key, channel).
2. If new message arrives before the previous turn reaches a safe checkpoint:

   * **Coalesce** into one "logical turn input"
   * Or **cancel** the in-flight turn if it has no irreversible side effects yet.

This is consistent with your execution model idea of defining which operations are sequential vs parallel.

### 3.4 "Irreversible checkpoints" and tool side effects

Your instincts are exactly right: you can cancel/merge turns **unless** a tool has already produced a side effect you cannot safely undo.

So define a small contract:

**ToolSideEffectPolicy**

* `reversible`: safe to cancel or replay
* `compensatable`: can be undone via a defined compensating action
* `irreversible`: cannot be rolled back; commit point reached

This is the missing "transaction semantics" layer above Phase 7.

---

## 4. A formal **Side-Effect Registry** (strengthening Phase 7)

### 4.1 Why you need it

Tools like **refund**, order cancellation, ticket creation, or CRM writes are business-dangerous.
You already bind tools to scenario steps.
What's missing is a **central policy map** that tells the runtime what concurrency rules apply when these tools are in play.

### 4.2 Proposed minimal model (conceptual)

* Tool metadata:

  * side-effect level
  * idempotency key strategy
  * compensation tool (optional)

### 4.3 How it integrates

* P6 decides intended step path.
* P7 consults **SideEffectRegistry** before executing tools.
* Ingress Control uses the same registry to decide whether a turn can be canceled/merged.

---

## 5. Abuse "firewall" & safety escalation

You want a flagging system if users abuse the agent. This is best treated as **two layers**:

### 5.1 Real-time guardrails (pre-P1)

* Detect spam patterns, harassment bursts, prompt-injection storms per customer/channel.
* Apply rate limits and temporary cool-down.

### 5.2 Behavioral risk classification (P9/P10 + audit)

The generation LLM already emits semantic categories like SAFETY_REFUSAL; your pipeline already merges categories into TurnOutcome.
Add a **pipeline-owned "ABUSE_SUSPECTED"** category that can be set deterministically based on:

* repeated policy blocks
* repeated harassment
* volumetric anomalies

Log these in TurnRecord for the reporter agent to summarize later.

---

## 6. Multi-model inputs/outputs & "multi-message responses"

### 6.1 Multi-model by phase is already natural in your config system

Each step can pick models and fallback providers.
Your modes (Minimal/Balanced/Maximum) prove you already think in "pipeline tiering."

### 6.2 The missing hierarchy: tenant → agent → scenario → step

Right now you load static config in P1.6.
You can evolve this to:

1. tenant defaults
2. agent overrides
3. scenario overrides
4. step overrides (already implicit)

This achieves "each tenant can tune each agent differently" without breaking your architecture.

### 6.3 Multi-message response generation

You mentioned: "answer one user message with several agent messages."
This fits cleanly in Phase 8:

* P8 produces a ResponsePlan that can specify `segments[]`
* P9 generates per-segment text with channel formatting per segment

This is consistent with P8's "merge scenario contributions into one plan."

---

## 7. Channels as first-class objects (building on TurnInput)

You already have `TurnInput.channel` and `channel_id` to represent WhatsApp/email/webchat/phone/etc.
Your new idea is to "lift" this into a richer object.

### 7.1 Why that's useful

Because channels aren't just I/O formats; they have capabilities:

* delivered/read receipts (WhatsApp)
* fallbacks (WhatsApp → SMS)
* outbound permissions
* rich media support

### 7.2 Suggested extension

Keep TurnInput as-is (clean contract), but add:

**ChannelConfig / ChannelCapability** loaded in P1.6 and attached to TurnContext. That's fully compatible with your existing TurnContext pattern.

### 7.3 Customer reconciliation across channels

You already planned in P1.2 to map channel_id to existing customer or create new.
Extend your CustomerDataStore or a separate CustomerIdentityMap to store:

* whatsapp_id
* email
* phone
* webchat_id
  and allow "confirm identity on channel A then notify on channel B."

---

## 8. Scenario updates, caching, and safe migrations

You already defined explicit scenario migration patterns (gap-fill, teleportation, re-routing) referenced in P1.7.
Your composite migration benefits are well-argued in your doc.

### 8.1 What your new concerns add

You're worried about:

* caches holding old scenario graphs
* sessions mid-ticket creation
* frequent non-state-heavy scenarios

### 8.2 Practical integration points

* Maintain **scenario version stamps** in SessionState.
* Invalidate caches on "scenario updated" events.
* Use your two-phase deployment option where appropriate.

---

## 9. Agenda, goals, and proactive outreach

This is your bridge from "reactive customer support" to "360 lifecycle agent."

### 9.1 Agenda as a separate engine

Treat **AgendaTask** as a durable object in your StateStore/Audit flow.
This aligns with your storage category separation:
Config/Knowledge vs State vs Audit.

### 9.2 Goals as conversation contracts

Your intuition is strong: after a response is generated, you can attach an "expected next answer" or "required user response".

Where this can live:

* As a small object attached to ResponsePlan
* Then persisted into SessionState in Phase 11

This turns "follow-up if no answer" into a deterministic, auditable behavior.

---

## 10. Offerings catalog (products + services)

You described "offerings" as a unified catalog.
This can be modeled as **config/knowledge** with embeddings for retrieval.
That maps cleanly to your ConfigStore responsibility.

---

## 11. Database-agnostic persistence (formalizing your intent)

You already drafted the right approach:
separate interfaces for ConfigStore, StateStore, AuditStore (or a single PersistencePort early on).
You also already note concurrency concerns in StateStore.

**Your new features depend on this**
Because debouncing, side-effect commits, agenda tasks, and multi-channel identity mapping all raise concurrency pressure; they must be handled behind stable ports.

---

## 12. The **Agent Setter Agent (ASA)** as a first-class meta-agent

This is the most powerful new idea you added.

### 12.1 ASA scope

ASA should have access to the same endpoints as humans in the UI, plus specialized "builder" tools.

Use-case categories:

1. Build/update rules, scenarios, glossary, customer data schema
2. Recommend safe side-effect policies
3. Stress-test agent behavior with edge cases
4. Propose migration-safe edits (anchors, gap-fill strategies)

### 12.2 The "side-effect design assistant" role

You described exactly the right loop:

1. Tenant says what they want the agent to do.
2. ASA proposes new/updated rules + scenarios + tool bindings.
3. ASA proactively asks:

   * "What if a customer does X then cancels?"
   * "What if two refunds are requested across channels?"
4. ASA recommends:

   * additional constraints
   * confirmation steps
   * compensation tool design
   * debouncing exceptions for irreversible steps

This pairs perfectly with your Phase 7 + Ingress Control design.

---

## 13. Reporter agent (tenant-facing observability companion)

You want a "reporter agent" that can discuss activity with tenants anytime.

### 13.1 Why it's natural in your architecture

Your pipeline is already **observable** and produces full TurnRecords.
So the reporter agent is essentially a **read-only analytics persona** over AuditStore.

### 13.2 Capabilities

* Summarize top intents, outcome categories, escalation rates
* Detect knowledge gaps vs out-of-scope patterns
* Show scenario completion rates (scenario-level) vs turn outcomes (turn-level)
* Highlight abuse flags and suspicious bursts

---

## 14. Concrete additions you can encode without breaking your phases

### 14.1 Add "Ingress Control" as a wrapper

**New conceptual step** before Phase 1:

* debounce/coalesce window
* rate limits
* early abuse detection
* cancel/merge decisions based on ToolSideEffectPolicy

### 14.2 Extend configuration hierarchy

Move from single tenant pipeline config to:

* tenant defaults
* agent overrides
* optional scenario overrides
  This is consistent with your future move from TOML to dynamic config storage.

### 14.3 Add side-effect registry

Minimal metadata that both P7 and Ingress Control consult.

### 14.4 Channel capabilities object

Build on the existing TurnInput design rather than replacing it.

---

## 15. A compact mental model (how everything fits)

* **Turn Pipeline (11 phases)** = deterministic alignment engine per message.
* **Ingress Control** = prevents the world from breaking the turn abstraction.
* **Side-effect registry** = defines safe commit semantics.
* **Config hierarchy** = enables tenant/agent customization without code changes.
* **Scenario migration** = protects long-lived sessions.
* **Agenda/goals** = enables proactive lifecycle workflows.
* **ASA** = meta-agent that *builds and hardens* the rest.
* **Reporter agent** = transparency layer over AuditStore.
* **Persistence ports** = keeps the whole platform DB-agnostic and scalable.

---

## 16. Extra out-of-the-box ideas (small but high leverage)

### 16.1 "Simulation sandbox" for ASA

Let ASA generate adversarial and edge-case conversations and run them through a **non-production simulation mode** that writes to a separate audit stream.
This helps validate rule/scenario updates before deployment.

### 16.2 "Channel escalation ladder"

When WhatsApp delivery fails, auto-fallback to SMS or email if the channel policy allows, using the channel capabilities layer.

### 16.3 "Outcome-driven KB gaps"

Since P9 outputs structured categories, you can automatically open a KB ticket when KNOWLEDGE_GAP repeats above a threshold.

---

## 17. Summary of the new objects/concerns you've effectively defined

1. **Ingress Control**

   * debouncing/coalescing
   * rate limits
   * abuse firewall
   * optional turn cancellation before commit points

2. **Tool Side-Effect Policy & Registry**

   * reversible / compensatable / irreversible
   * dependency-aware tool sequences

3. **ChannelCapability / ChannelConfig**

   * delivery/read semantics
   * fallback strategies
   * outbound permissions

4. **Config hierarchy**

   * tenant → agent → scenario → step

5. **Agenda + Goal contracts**

   * proactive follow-ups
   * outbound tasks

6. **ASA**

   * builder + edge-case strategist
   * side-effect hardening assistant

7. **Reporter Agent**

   * tenant-facing observability narrator

8. **Offerings Catalog**

   * unified products + services config layer

9. **DB-agnostic ports**

   * necessary foundation for all of the above

---

## Related Documents

- [Gap Analysis](gap_analysis.md) - Mapping of FOCAL 360 concepts to existing Soldier implementations
- [Turn Pipeline](../focal_turn_pipeline/README.md) - The 11-phase turn pipeline this platform wraps
- [Subagent Protocol](SUBAGENT_PROTOCOL.md) - Protocol for implementing FOCAL 360 features
- [Wave Execution Guide](WAVE_EXECUTION_GUIDE.md) - Orchestration guide for wave-based implementation
