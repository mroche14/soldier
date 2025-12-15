# Gap Analysis Reassessment

> **Date**: 2025-12-10
> **Updated**: 2025-12-11 (ACF Orchestration Modes, AG-UI integration, 12 ambiguity resolutions)
> **Context**: The original gap analysis was written before the LogicalTurn architecture vision
> **Purpose**: Mark which items are obsolete, superseded, or still relevant
> **See Also**: [ACF_SPEC.md](../architecture/ACF_SPEC.md) for the authoritative implementation specification

---

## ACF Context

The **Agent Conversation Fabric (ACF)** specification formalizes and refines the LogicalTurn architecture. Key refinements:

1. **ACF vs CognitiveBrain boundary** - Clear separation of mechanics (ACF) from meaning (Brain)
2. **Four-state SupersedeDecision** - SUPERSEDE, ABSORB, QUEUE, FORCE_COMPLETE
3. **Two-phase commit for tools** - Brain proposes, ACF authorizes
4. **Brain-declared artifact reuse** - Brain knows semantics, ACF enforces fingerprints
5. **Channel facts vs policies** - Facts are immutable, policies are configurable
6. **ACF Orchestration Modes** - Three modes for tool execution (Mode 0, 1, 2)
7. **Three-layer idempotency** - API, Beat, Tool layers (not one unified system)
8. **AG-UI integration** - Standardized event protocol for real-time UI streaming

---

## Summary

The LogicalTurn architecture (now formalized as ACF) fundamentally changes how we approach FOCAL 360. This reassessment categorizes original gap items into:

| Status | Meaning |
|--------|---------|
| **OBSOLETE** | Concept replaced by LogicalTurn architecture |
| **ABSORBED** | Functionality now part of a larger component |
| **SUPERSEDED** | Different solution now preferred |
| **STILL RELEVANT** | Original analysis still applies |
| **ELEVATED** | Now more important than originally thought |

---

## 1. Ingress Control & Concurrency

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Ingress Control** | "NOT IMPLEMENTED" | **ABSORBED → TurnGateway** | Now topic 07-turn-gateway.md |
| **Debouncing** | "NOT IMPLEMENTED" | **OBSOLETE** | Replaced by AdaptiveAccumulation (topic 03) |
| **Rate Limiting** | "IMPLEMENTED" | **STILL RELEVANT** | Now part of TurnGateway (topic 07) |
| **Turn Cancellation** | "NOT IMPLEMENTED" | **ABSORBED → Supersede** | Now in LogicalTurn.status (topic 01) |
| **Coalescing** | "NOT IMPLEMENTED" | **OBSOLETE** | Replaced by LogicalTurn message aggregation |
| **Idempotency** | "PARTIAL" | **ELEVATED** | Now beat-level (topic 12-idempotency.md) |
| **Concurrency Control** | "PARTIAL" | **ABSORBED → SessionMutex** | Now topic 02-session-mutex.md |

### What Changed

The entire "Ingress Control" section is now the **Agent Conversation Fabric (ACF)**:
- "Debouncing" is replaced by **Adaptive Accumulation** - not a fixed window, but intelligent completion detection
- "Coalescing" is inherent in **LogicalTurn** - messages accumulate into one turn
- "Turn Cancellation" is the **four-state SupersedeDecision** model (SUPERSEDE, ABSORB, QUEUE, FORCE_COMPLETE)
- "Concurrency Control" is the **Session Mutex** - single-writer rule
- **TurnGateway is absorbed into ACF** - it's not a separate component

### Obsolete Recommendations

The original roadmap item "Implement Debounce using existing `burst_size` field" is **obsolete**. The `burst_size` field should be removed; it represented the wrong mental model.

---

## 2. Side-Effect Registry & Tool Policies

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Side-Effect Registry** | "NOT IMPLEMENTED" | **ELEVATED** | Now topic 04-side-effect-policy.md |
| **ToolSideEffectPolicy** | "NOT IMPLEMENTED" | **ELEVATED** | Critical for supersede decisions |
| **Tool Scheduling** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Checkpoints** | "IMPLEMENTED" | **ELEVATED** | Now tied to IRREVERSIBLE policy |
| **Tool Dependencies** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Compensation** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Needed for COMPENSATABLE tools |
| **Tool Idempotency Keys** | "NOT IMPLEMENTED" | **ABSORBED** | Part of SideEffectPolicy |

### What Changed

Side-Effect Registry moved from "nice to have" to **foundational ACF requirement**:
- **Two-phase commit** - ACF authorizes tool execution, not just Brain
- LogicalTurn.can_supersede() depends on SideEffectPolicy
- Checkpoint placement now derives from IRREVERSIBLE tool presence
- ASA Validator (topic 13) validates side-effect declarations at design time

### ACF Tool Authorization Flow

```
Brain proposes PlannedToolExecution[] → ACF validates → ACF authorizes → ToolHub executes → ACF records
```

### Still Needed

The compensation mechanism is still needed for COMPENSATABLE tools. The original analysis is correct.

---

## 3. Channel System

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Channel** | "IMPLEMENTED" | **STILL RELEVANT** | Add more channels |
| **TurnInput.channel** | "IMPLEMENTED" | **ABSORBED → TurnInput** | Now topic 07 |
| **ChannelCapability** | "NOT IMPLEMENTED" | **ELEVATED** | Now topic 10-channel-capabilities.md |
| **ChannelConfig** | "NOT IMPLEMENTED" | **ABSORBED** | Part of ChannelCapability |
| **Channel Formatters** | "IMPLEMENTED" | **STILL RELEVANT** | Enhanced in topic 10 |
| **Multi-channel Identity** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Channel Fallback** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now in topic 10 |
| **Delivery Receipts** | "NOT IMPLEMENTED" | **DEPRIORITIZED** | Low value for MVP |

### What Changed

ChannelCapability became **critical for ACF**, with a **facts vs policies split**:

| Type | Owner | Example |
|------|-------|---------|
| **Fact** (immutable) | ACF | SMS max 160 chars |
| **Policy** (configurable) | Configuration | Wait 1200ms on WhatsApp |

- Each channel has `default_turn_window_ms` (policy, not fact)
- WhatsApp (1200ms) vs Email (0ms) vs Web (600ms)
- Channel facts inform formatting, policies inform accumulation

### Original Recommendation Still Valid

The "ChannelCapability Model" recommendation is still valid but split into facts/policies per ACF spec.

---

## 4. Configuration Hierarchy

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Tenant Defaults** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Agent Overrides** | "PARTIAL" | **STILL RELEVANT** | Still needs integration |
| **Scenario Overrides** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now in topic 08 |
| **Step Overrides** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Hot Reload** | "DOCUMENTED" | **DEPRIORITIZED** | MVP without hot reload OK |
| **Dynamic Config** | "NOT IMPLEMENTED" | **DEPRIORITIZED** | Static config sufficient for now |

### What Changed

The original analysis is **mostly still relevant**. Configuration hierarchy is documented in topic 08-config-hierarchy.md with the same concepts.

Hot Reload is **deprioritized** - it's nice to have but not blocking. Static TOML + restart is acceptable for initial deployment.

---

## 5. Agenda, Goals & Proactive Outreach

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **AgendaTask** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now topic 09-agenda-goals.md |
| **Goals** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now topic 09 |
| **Proactive Outreach** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now topic 09 |
| **Follow-ups** | "NOT IMPLEMENTED" | **STILL RELEVANT** | Now topic 09 |
| **Lifecycle Stages** | "PARTIAL" | **STILL RELEVANT** | Enhanced with Goal status |
| **Job Scheduling** | "IMPLEMENTED" | **STILL RELEVANT** | Hatchet workflows |
| **Outcome Tracking** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |

### What Changed

This section is **still fully relevant**. The Agenda/Goals system is now detailed in topic 09-agenda-goals.md with:
- Goal model (PENDING, ACHIEVED, EXPIRED, CANCELLED)
- AgendaTask model (SCHEDULED, EXECUTING, COMPLETED, FAILED)
- FollowUpWorkflow and AgendaSchedulerWorkflow for Hatchet

No concepts were replaced or made obsolete.

---

## 6. Meta-Agents (ASA & Reporter)

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Agent Setter Agent (ASA)** | "NOT IMPLEMENTED" | **SUPERSEDED** | Now design-time validator only |
| **Reporter Agent** | "NOT IMPLEMENTED" | **DEPRIORITIZED** | Low value for MVP |
| **Admin APIs** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Simulation Sandbox** | "NOT IMPLEMENTED" | **DEPRIORITIZED** | Nice to have |
| **Builder Tools** | "NOT IMPLEMENTED" | **ABSORBED** | ASA Validator tools |

### What Changed

**Major reframe**: ASA is no longer a runtime meta-agent. It's a **design-time validator**:
- ToolValidator: Ensures side-effect policies are declared
- ScenarioValidator: Checks for unreachable steps, missing checkpoints
- EdgeCaseGenerator: Suggests additional rules
- PolicySuggester: Recommends side-effect policies for new tools

This is documented in topic 13-asa-validator.md.

**Why**: A runtime agent that modifies production config is dangerous. Design-time validation is safer.

Reporter Agent is **deprioritized** - existing observability (metrics, logs, traces) is sufficient for MVP.

---

## 7. Offerings Catalog

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **Offerings Catalog** | "NOT IMPLEMENTED" | **OUT OF SCOPE** | Not in FOCAL 360 core |
| **Products** | "PARTIAL" | **OUT OF SCOPE** | Tenant-specific |
| **Services** | "NOT IMPLEMENTED" | **OUT OF SCOPE** | Tenant-specific |
| **Template Library** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **Knowledge Base** | "NOT IMPLEMENTED" | **OUT OF SCOPE** | Tenant-specific |

### What Changed

The Offerings Catalog is **out of scope** for FOCAL 360 architecture. It's a tenant-specific concern, not a platform feature:
- Each tenant will have different products/services
- Memory extraction handles product mentions
- If needed, tenants can add custom retrieval sources

The original gap analysis incorrectly treated this as a platform feature.

---

## 8. DB-Agnostic Persistence Ports

### Original Items

| Item | Original Status | New Status | Notes |
|------|-----------------|------------|-------|
| **ConfigStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **MemoryStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **SessionStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **AuditStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **InterlocutorDataStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |
| **VectorStore** | "IMPLEMENTED" | **STILL RELEVANT** | Unchanged |

### What Changed

**Nothing** - the persistence layer is complete. This remains the most solid part of the codebase.

New stores to add:
- `LogicalTurnStore` - for turn state persistence (topic 01)
- `IdempotencyStore` - for beat-level idempotency (topic 12)

These follow the same ABC + InMemory + Postgres pattern.

---

## Revised Priority Roadmap

Based on the ACF specification, here's the revised implementation order:

### Phase 1: ACF Core (Foundational)

| Priority | Component | ACF Role | Topic |
|----------|-----------|----------|-------|
| 1.1 | LogicalTurn model + SupersedeDecision | Core abstraction | 01 |
| 1.2 | SessionMutex | Concurrency | 02 |
| 1.3 | ChannelCapability (facts + policies) | Channel model | 10 |
| 1.4 | AdaptiveAccumulation | Aggregation | 03 |
| 1.5 | SideEffectPolicy + Two-Phase Commit | Commit gating | 04 |
| 1.6 | CheckpointReuse (brain-declared) | Optimization | 05 |
| 1.7 | Beat-level Idempotency | Safety | 12 |
| 1.8 | Hatchet LogicalTurnWorkflow | ACF runtime | 06 |
| 1.9 | TurnGateway (ACF ingress) | Entry point | 07 |

### Phase 2: Configuration & Operations

| Priority | Component | Brain Role | Topic |
|----------|-----------|---------------|-------|
| 2.1 | ConfigHierarchy | Configuration | 08 |
| 2.2 | AbuseDetection | Safety | 11 |
| 2.3 | ASA Validator | Design-time | 13 |

### Phase 3: Proactive Features

| Priority | Component | Brain Role | Topic |
|----------|-----------|---------------|-------|
| 3.1 | Agenda/Goals | Proactive | 09 |
| 3.2 | Proactive Outreach | Proactive | 09 |

---

## Obsolete Documents

The following documents from the original gap analysis should be considered **historical context only**:

| Document | Status | Reason |
|----------|--------|--------|
| `gap_analysis.md` (this doc's parent) | HISTORICAL | Superseded by topic files |
| `WAVE_EXECUTION_GUIDE.md` (v1) | OBSOLETE | Replaced by v2 with Wave 0 |
| `wave_analysis_report.md` | HISTORICAL | Concepts absorbed into topics |

The new authoritative documentation is:
- `docs/acf/architecture/ACF_SPEC.md` - **Authoritative** implementation specification
- `docs/acf/architecture/LOGICAL_TURN_VISION.md` - Founding vision
- `docs/acf/architecture/README.md` - Index
- `docs/acf/architecture/topics/*.md` - Detailed specifications (with ACF context)

---

## Appendix A: Vocabulary Changes

| Original Term | New Term | Reason |
|---------------|----------|--------|
| Debouncing | Adaptive Accumulation | Not fixed window |
| Ingress Control | Agent Conversation Fabric (ACF) | Complete control plane |
| Turn Gateway | ACF ingress | Absorbed into ACF |
| Coalescing | LogicalTurn accumulation | Native to model |
| Turn Cancellation | SupersedeDecision (4 states) | SUPERSEDE, ABSORB, QUEUE, FORCE_COMPLETE |
| Burst Coalescing | (removed) | Part of LogicalTurn |
| ChannelProfile | ChannelCapability (facts + policies) | Split into immutable/configurable |
| ConfigBuilderAgent | ASA Validator | Not an agent, design-time only |
| Tool Authorization | Two-Phase Commit | ACF authorizes, ToolHub executes |
| Checkpoint Reuse | Brain-Declared Reuse | Brain declares policy, ACF enforces |

---

## Appendix B: Resolved Ambiguities (2025-12-11)

The following 12 ambiguities were identified and resolved during ACF specification review:

### 1. turn_group_id for Idempotency Scoping ✅

**Solution**: Add `turn_group_id: UUID` to `LogicalTurn`:
- Supersede chain shares same turn_group_id (inherited)
- QUEUE creates NEW turn_group_id
- Tool idempotency: `{tool}:{business_key}:turn_group:{turn_group_id}`

### 2. ABSORB Strategy Semantics ✅

**Solution**: SupersedeDecision is a model with nested strategy:
```python
class SupersedeDecision(BaseModel):
    action: SupersedeAction  # SUPERSEDE | ABSORB | QUEUE | FORCE_COMPLETE
    absorb_strategy: AbsorbStrategy | None  # RESTART | CONTINUE
```

### 3. Mutex Lifecycle in Hatchet ✅ (CRITICAL)

**Problem**: Using context manager releases lock when step exits!
**Solution**: Acquire WITHOUT context manager, release explicitly in commit_and_respond or on_failure.

### 4. Three-Layer Idempotency ✅

**Solution**: Three separate layers (not one unified):
- **API** (5min TTL): Duplicate HTTP requests
- **Beat** (60s TTL): Duplicate turn processing
- **Tool** (24h TTL): Duplicate business actions

### 5. Artifact Storage Strategy ✅

**Solution**: Dual storage model:
- Expensive phases → `ArtifactStorage.TURN_STORE`
- Cheap phases → `ArtifactStorage.EPHEMERAL`
- `on_artifact_created` callback for incremental persistence

### 6. Brain Hints Mechanism ✅

**Solution**: Previous-turn storage (no circular dependency):
- Turn N returns `accumulation_hint`
- ACF stores in `session.last_pipeline_result`
- Turn N+1 loads hint during accumulation

### 7. ACF Orchestration Modes ✅ (MAJOR)

**Solution**: Three modes for tool execution:

| Mode | Name | Workflow | Default For |
|------|------|----------|-------------|
| Mode 0 | Simple | 4 steps | Text-only |
| Mode 1 | Single-Pass | 4 steps + callbacks | FOCAL, LangGraph, Agno |
| Mode 2 | Two-Pass | 6 steps | High-stakes only |

**Mode selection is explicit config, NOT implicit protocol detection.**

### 8. Channel Model Consolidation ✅

**Solution**: Single authoritative model:
- `ChannelFacts` - Immutable (max_length, supports_markdown)
- `ChannelPolicy` - Configurable (turn_window_ms, fallback_channels)
- `ChannelModel` - Runtime combo

Remove `ChannelCapabilities` (plural) and mixed types.

### 9. Supersede Decision Ownership ✅

**Solution**: Three-phase model:
1. ACF checks automatic rules FIRST (IRREVERSIBLE → always QUEUE)
2. Brain makes semantic decision IF implements `SupersedeCapable`
3. ACF validates & enforces (can downgrade, never upgrade)

### 10. Message Queue vs Events ✅

**Solution**: Decision tree:
- No workflow → Start new
- Workflow exists → Send event
- WorkflowNotRunningError → Start new (race)
- Other failures → Queue message

Add `dequeue_all()`, `max_queue_size`, `OverflowStrategy`.

### 11. dep_fp Version Sources ✅

**Solution**: Content hashes (not sequence numbers):
- ConfigStore computes on save
- ACF captures at turn start via `VersionCaptureService`
- Capture BEFORE brain runs, after mutex acquired

### 12. FabricTurnContext vs TurnContext ✅

**Solution**: They coexist at different layers:
- `FabricTurnContext` - ACF's external contract
- `TurnContext` - FOCAL's internal state
- `FocalCognitiveBrain` adapter translates between them
