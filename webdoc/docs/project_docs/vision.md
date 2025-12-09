# Focal: Vision

## Problem

Building production-grade conversational AI agents is hard. Current frameworks fall into two traps:

### The Prompt Trap
Stuff everything into a system prompt and hope the LLM follows instructions. Fails at scale—more rules means more ignored instructions and unpredictable behavior.

### The Code Trap
Many frameworks require **code to define agent behavior**:
- Journeys defined via SDK calls (`agent.create_journey()`)
- No hot-reload—restart the process to update behavior
- Agents live in memory—no persistence, no horizontal scaling
- Single-tenant by design—multi-tenancy bolted on as an afterthought
- No way for non-developers to modify agent behavior

**The result**: You ship a product, then tell customers "we'll update the agent behavior in the next release." That's not how SaaS works.

## Solution

Focal is a **production-grade cognitive engine** for conversational AI. It replaces code-centric frameworks with an **API-first, multi-tenant, fully persistent** architecture.

### Core Principles

| Principle | What It Means |
|-----------|---------------|
| **API-first** | Everything via REST/gRPC. No SDK required. Non-developers can modify agents via UI. |
| **Zero in-memory state** | All state in external stores (Redis, PostgreSQL, MongoDB). Any pod can serve any request. |
| **Hot-reload** | Update Scenarios/Rules/Templates via API → instant effect. No restarts. |
| **Multi-tenant native** | Tenant isolation at every layer. Not an afterthought. |
| **Cache with TTL** | Per-tenant, per-channel, per-session cache policies. No stale data. |
| **Full auditability** | Every decision logged: why rules matched, what memory was retrieved, what was enforced. |

### What Focal Provides

1. **Scenarios**
   - Multi-step conversational flows
   - CRUD via API—no code required
   - State transitions with conditions
   - Live updates without restart

2. **Rules**
   - "When X, then Y" policies
   - Scoped: GLOBAL → SCENARIO → STEP
   - Priority ordering, cooldowns, fire limits
   - Semantic + keyword matching
   - Post-generation enforcement

3. **Templates**
   - Pre-written responses for critical points
   - Modes: SUGGEST, EXCLUSIVE (bypass LLM), FALLBACK
   - Variable interpolation

4. **Tools**
   - Side-effect actions attached to Rules
   - Execution policies (sync/async, timeout, retries)
   - Integration with external tool orchestration (Restate, Celery)

5. **Memory**
   - Temporal knowledge graph (episodes, entities, relationships)
   - Hybrid retrieval: vector + BM25 + graph traversal
   - Per-tenant isolation
   - Automatic summarization for long conversations

6. **Enforcement**
   - Post-generation validation against Rules
   - Automatic regeneration or fallback
   - Hard constraints that cannot be violated

## Goals

- **API-first**: All agent configuration via REST/gRPC
- **Multi-tenant native**: Tenant isolation at every layer
- **Zero in-memory state**: All state persistent or cached with TTL
- **Hot-reload**: Update behavior instantly without restarts
- **Observable**: Structured logging, metrics, traces for every decision
- **Scalable**: Horizontal scaling—any pod can serve any request

## Non-Goals

- Building a general-purpose LLM framework
- Multi-agent orchestration (single agent with tools preferred)
- Managed cloud service (self-hostable priority)

## Key Concepts

| Term | Definition |
|------|------------|
| **Scenario** | A multi-step conversational flow (onboarding, returns, KYC, etc.) |
| **Scenario Step** | A single step within a Scenario, with transitions to other steps |
| **Rule** | A "when X, then Y" policy with scope, priority, and enforcement |
| **Template** | Pre-written response text with variable interpolation |
| **Tool** | A side-effect action attached to Rules or Steps |
| **Episode** | A unit of memory (message, event, observation) in the knowledge graph |
| **Entity** | A named thing extracted from episodes (person, order, product) |

## Success Criteria

- **Latency**: Sub-500ms for rule matching + memory retrieval
- **Hot-reload**: Config changes effective in < 2 seconds
- **Determinism**: Tools only execute when their Rule matches
- **Auditability**: Full trace of every decision for any turn
- **Isolation**: Zero data leakage between tenants
- **Availability**: 99.9% uptime SLO
