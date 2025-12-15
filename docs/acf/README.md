# ACF: Agent Conversation Fabric

> **Purpose**: Reliability-first conversation infrastructure for AI agents at scale
> **Core Abstraction**: Agent Conversation Fabric (ACF) - the conversation control plane
> **Core Insight**: A message is not a turn - the semantic unit is a *conversational beat*
> **Version**: 3.0 (Agent/Toolbox ownership model)
> **Platform**: Ruche

---

## Quick Start

**Start here**: [ACF Architecture](architecture/ACF_ARCHITECTURE.md) - The canonical architecture document

Then see:
- [Agent Runtime Spec](architecture/AGENT_RUNTIME_SPEC.md) - Agent lifecycle management
- [Toolbox Spec](architecture/TOOLBOX_SPEC.md) - Tool execution layer
- [ACF Spec](architecture/ACF_SPEC.md) - Detailed ACF mechanics

Or see the [Architecture Index](architecture/README.md) for the full document map.

---

## What is ACF?

ACF (Agent Conversation Fabric) is the **conversation infrastructure layer** that sits above Agents. It handles the "mechanics" of conversations - message accumulation, concurrency, superseding, workflow orchestration - so that Agents (and their Brains) can focus on understanding and responding.

**Key principle**: ACF calls `agent.process_turn()`. Agent owns its Brain and uses it internally. ACF doesn't know or care what Brain an agent has.

ACF transforms raw message streams into reliable, scalable conversational experiences across channels.

### Architecture Overview (v3.0)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            ACF LAYER                                        │
│                     (Pure Conversation Infrastructure)                      │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │SessionMutex  │  │ TurnManager  │  │ Supersede    │  │ Hatchet      │  │
│  │- acquire     │  │- aggregate   │  │ Coordinator  │  │ Workflow     │  │
│  │- release     │  │- accumulate  │  │- signal      │  │- orchestrate │  │
│  │- extend      │  │- boundary    │  │- query state │  │- retry       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                            │
│  ACF provides: FabricTurnContext (logical_turn, has_pending, emit)        │
│  ACF calls: agent.process_turn(fabric_ctx)                                │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            AGENT LAYER                                      │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentRuntime                                      │  │
│  │   Lifecycle manager for Agent instances (caching, invalidation)     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    AgentContext                                      │  │
│  │   agent: Agent | brain: Brain | toolbox: Toolbox                   │  │
│  │   process_turn(fabric_ctx) → brain.think() → BrainResult           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         Brain                                        │  │
│  │   FocalBrain | LangGraphBrain | AgnoBrain | Custom                  │  │
│  │   think(ctx) → internal processing → BrainResult                    │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                               │
│                                                                            │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│
│  │ToolGateway          │  │ChannelGateway       │  │ Stores + Providers  ││
│  │- Composio, HTTP     │  │- AG-UI, Twilio      │  │- ConfigStore, etc.  ││
│  │- Idempotency cache  │  │- Protocol adapters  │  │- LLM, Embedding     ││
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘
```

### Key Boundaries (v3.0)

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| **ACF** | Mutex, turns, workflow, supersede signals, ACFEvent routing | Tool execution, tool semantics, business logic, what Brain an agent uses |
| **Agent** | Brain, Toolbox, ChannelBindings, process_turn() | Turn lifecycle, workflow orchestration |
| **Brain** | Thinking logic (e.g., FOCAL's 11-phase pipeline) | Infrastructure concerns |
| **Toolbox** | Tool resolution, side effect recording, execute via gateway | Infrastructure, idempotency storage |
| **ToolGateway** | Provider adapters, operation idempotency | Tool semantics, policies |

### Execution Model

ACF calls `agent.process_turn()`. Agent uses its Brain internally:

```
ACF → agent.process_turn(fabric_ctx)
              ↓
      Agent → brain.think(agent_turn_ctx)
              ↓
      Brain → ctx.toolbox.execute() → ToolGateway → Provider
              ↓
         Policy enforcement
         Idempotency
         Audit events
```

**Key principle**: The Toolbox is the enforcement boundary. ACF calls Agent, not Brain directly.

| Layer | Owns |
|-------|------|
| **ACF** | Conversation infrastructure (turns, mutex, workflow, event routing) |
| **Agent** | Owns Brain, exposes process_turn() to ACF |
| **Brain** | Decisions (what to do, when to call tools) |
| **Toolbox** | Execution + guardrails (policy, idempotency, confirmation, audit) |

**Why this is simple**: Your team controls all brains. Agent encapsulates Brain. Toolbox enforcement + ASA validation ensures correctness.

---

## Documentation Governance

### Document Tiers (RFC-Style)

When documents conflict, higher tiers win. Implement from Tier 1, reference Tier 2, understand context from Tier 3.

| Tier | Status | Documents | Rule |
|------|--------|-----------|------|
| **Tier 1** | Canonical (Normative) | ACF_ARCHITECTURE, AGENT_RUNTIME_SPEC, TOOLBOX_SPEC | **Implement from these** |
| **Tier 2** | Supporting (Informative) | ACF_SPEC, topic files (01-13) | Reference, may have legacy sections |
| **Tier 3** | Vision (Historical) | LOGICAL_TURN_VISION, analysis/ | Context only, not for implementation |

**Enforcement Rules**:
- Tier 2 documents cannot introduce new types not defined in Tier 1
- When Tier 2 conflicts with Tier 1, Tier 1 wins
- Sections marked `> **HISTORICAL v2**` are deprecated patterns

---

## Canonical ID Glossary

**Use these names consistently across all documents and code.**

| ID | Type | Description | Scope |
|----|------|-------------|-------|
| `message_id` | UUID | Single inbound raw message | Per message |
| `logical_turn_id` | UUID | Aggregated processing unit (one or more messages forming one beat) | Per turn |
| `turn_group_id` | UUID | Idempotency scope - shared across supersede chain, NEW on QUEUE | Per conversation attempt |
| `session_key` | String | Concurrency boundary: `{tenant}:{agent}:{customer}:{channel}` | Per conversation stream |
| `workflow_run_id` | String | Hatchet workflow instance | Per workflow |
| `tenant_id` | UUID | Tenant identifier | Global |
| `agent_id` | UUID | Agent identifier | Per tenant |
| `customer_id` | UUID | Customer identifier | Per tenant |

**Deprecated Terms** (do not use in new code):
- ~~`beat_id`~~ → use `logical_turn_id`
- ~~`turn_id`~~ → use `logical_turn_id` (full name preferred for clarity)

---

## Core Architecture Documents

| Document | Purpose |
|----------|---------|
| [ACF_ARCHITECTURE.md](architecture/ACF_ARCHITECTURE.md) | **Canonical architecture** - Start here |
| [AGENT_RUNTIME_SPEC.md](architecture/AGENT_RUNTIME_SPEC.md) | Agent lifecycle, AgentContext, caching |
| [TOOLBOX_SPEC.md](architecture/TOOLBOX_SPEC.md) | Tool execution, SideEffectPolicy, ToolGateway |
| [ACF_SPEC.md](architecture/ACF_SPEC.md) | Detailed ACF mechanics (mutex, turns, supersede) |

---

## Key Principles

### 1. A Message is Not a Turn

The semantic unit is a **conversational beat** - one or more rapid messages forming one coherent user intent:

```
User: "Hello"          ┐
User: "How are you?"   ├─→ ONE LogicalTurn → ONE Response
                       ┘
```

### 2. ACF Owns Infrastructure, Agent Owns Business Logic

| ACF (Infrastructure) | Agent (Business Logic) |
|---------------------|------------------------|
| When to respond | What to say |
| Turn boundaries | Customer intent understanding |
| Supersede **signals** | Supersede **decisions** |
| ACFEvent routing | ACFEvent emission |
| Workflow orchestration | Brain execution |

### 3. Toolbox is the Enforcement Boundary

Toolbox handles all tool execution concerns:

| Concern | How Toolbox Handles |
|---------|---------------------|
| **Policy enforcement** | Checks `side_effect_policy` before execution |
| **Confirmation** | Validates `requires_confirmation` via scenario state |
| **Idempotency** | Uses `turn_group_id` + business key for deduplication |
| **Audit** | Emits ACFEvents for all tool operations |

Brain calls `ctx.toolbox.execute()` - Toolbox ensures correctness.

### 4. Supersede: Facts vs Decisions

- **ACF provides FACTS**: `has_pending_messages() → bool`
- **Brain makes DECISIONS**: SUPERSEDE / ABSORB / QUEUE / FORCE_COMPLETE

```python
# ACF signal (fact)
if await ctx.has_pending_messages():
    # Brain decides (action)
    if metadata.is_irreversible:
        return SupersedeAction.SUPERSEDE  # Enum: SUPERSEDE, ABSORB, QUEUE, FORCE_COMPLETE
```

### 5. ACFEvents: Single Write Path

```
Toolbox/Brain → emit_event() → ACF EventRouter → TurnManager
                                                  → AuditStore
                                                  → Live UI listeners
```

No direct Toolbox → TurnManager calls. Events are the glue.

### 6. Hatchet as ACF Runtime

The `LogicalTurnWorkflow` IS the Agent Conversation Fabric. No sticky sessions needed.

### 7. ACF is Channel-Agnostic

ACF does not contain channel-specific logic. Channel adapters handle protocol translation:

```
Channels: WhatsApp | Email | Voice | Webchat
                       │
        ┌──────────────┴──────────────┐
        │      Channel Adapters       │  ← Protocol-specific (AG-UI, Twilio, etc.)
        └──────────────┬──────────────┘
                       │
                       ▼
                      ACF  ← Channel-agnostic
```

AG-UI is just one webchat adapter - not an ACF concern.

---

## Brain Conformance Requirements

All brains (FOCAL, LangGraph, Agno, custom) must satisfy these invariants. Enforced by Toolbox + ASA validation.

### Required Invariants

| Invariant | Description | Enforcement |
|-----------|-------------|-------------|
| **Tool calls through Toolbox** | Never call vendor SDK directly | ASA lints brain code |
| **Confirmation binding** | If `requires_confirmation`, brain must enter confirm step and freeze args | Scenario state validation |
| **Idempotency keys** | Side-effect tools must provide stable business key | Toolbox extracts or hashes |
| **Supersede awareness** | Check `has_pending_messages()` before irreversible tools | Brain responsibility |

### How FOCAL Satisfies These

| Invariant | FOCAL Implementation |
|-----------|---------------------|
| Tool calls through Toolbox | P7 calls `ctx.toolbox.execute()` |
| Confirmation binding | Scenario step with `awaits_confirmation: true` |
| Idempotency keys | ToolBinding specifies `idempotency_key_fields` |
| Supersede awareness | `_check_supersede_before_tool()` in P7 |

---

## Component Topics

### ACF Components (Infrastructure)

| Component | Topic | Description |
|-----------|-------|-------------|
| **LogicalTurn** | [01](architecture/topics/01-logical-turn.md) | Atomic unit of user intent (beat) |
| **Session Mutex** | [02](architecture/topics/02-session-mutex.md) | Single-writer rule per session |
| **Adaptive Accumulation** | [03](architecture/topics/03-adaptive-accumulation.md) | Intelligent wait timing |
| **Side-Effect Policy** | [04](architecture/topics/04-side-effect-policy.md) | Tool effect classification (Toolbox owns) |
| **Checkpoint Reuse** | [05](architecture/topics/05-checkpoint-reuse.md) | Brain-declared artifact reuse |
| **Hatchet Integration** | [06](architecture/topics/06-hatchet-integration.md) | ACF runtime |
| **Turn Gateway** | [07](architecture/topics/07-turn-gateway.md) | Message ingress |
| **Channel Capabilities** | [10](architecture/topics/10-channel-capabilities.md) | Channel facts + policies |
| **Idempotency** | [12](architecture/topics/12-idempotency.md) | Three-layer idempotency |

### Agent Components (Business Logic)

| Component | Topic | Description |
|-----------|-------|-------------|
| **Config Hierarchy** | [08](architecture/topics/08-config-hierarchy.md) | Multi-level configuration |
| **Agenda & Goals** | [09](architecture/topics/09-agenda-goals.md) | Proactive follow-up |
| **Abuse Detection** | [11](architecture/topics/11-abuse-detection.md) | Pattern-based handling |
| **ASA Validator** | [13](architecture/topics/13-asa-validator.md) | Design-time validation |

---

## Document Structure

```
docs/acf/
├── README.md                      # This file
├── architecture/
│   ├── README.md                  # Master index
│   ├── ACF_ARCHITECTURE.md        # Canonical architecture (v3.0)
│   ├── AGENT_RUNTIME_SPEC.md      # Agent lifecycle spec
│   ├── TOOLBOX_SPEC.md            # Tool execution spec
│   ├── ACF_SPEC.md                # Detailed ACF mechanics
│   ├── LOGICAL_TURN_VISION.md     # Founding vision
│   └── topics/
│       ├── 01-logical-turn.md
│       ├── 02-session-mutex.md
│       ├── ... (13 topics)
│       └── 13-asa-validator.md
├── analysis/
│   ├── ag_ui_considerations.md    # AG-UI integration notes
│   ├── logical_turn_impact_analysis.md
│   └── multi_agent_handoffs.md    # Future planning
├── WAVE_EXECUTION_GUIDE_V2.md     # Implementation order
└── old/                           # Archived historical documents
```

---

## Implementation Roadmap

See [Wave Execution Guide V2](WAVE_EXECUTION_GUIDE_V2.md) for detailed implementation order.

### Phase 1: ACF Core
1. LogicalTurn model + SupersedeDecision
2. Session Mutex
3. FabricTurnContext interface
4. Adaptive Accumulation
5. Hatchet Integration (LogicalTurnWorkflow)

### Phase 2: Agent Layer
6. Agent model + AgentConfig
7. AgentContext + AgentRuntime
8. PipelineFactory (FOCAL, LangGraph, Agno)
9. AgentTurnContext

### Phase 3: Toolbox Layer (Enforcement Boundary)
10. ToolDefinition + ToolActivation
11. Toolbox class with policy enforcement
12. ToolExecutionContext (bridges turn_group_id)
13. ToolGateway + Providers

### Phase 4: Safety & Conformance
14. Side-Effect Policy enforcement in Toolbox
15. Three-Layer Idempotency
16. Brain Conformance validation (ASA)
17. Config Hierarchy

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| [ACF Architecture](architecture/ACF_ARCHITECTURE.md) | **Canonical** architecture document |
| [Founding Vision](architecture/LOGICAL_TURN_VISION.md) | Why we designed it this way |
| [FOCAL Brain](../focal_brain/README.md) | The 11-phase Brain implementation |
| [Architecture Overview](../architecture/overview.md) | Focal architecture overview |
| [Domain Models](../design/domain-model.md) | Core domain models |

---

## Historical Documents

Previous analysis documents are archived in [old/](old/). They contain useful historical context but should not be used for implementation decisions.
