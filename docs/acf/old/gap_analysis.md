# FOCAL 360 Gap Analysis

> **Generated**: 2025-12-09
> **Purpose**: Map proposed FOCAL 360 concepts to existing Focal implementations, identifying vocabulary conflicts, partial implementations, and genuine gaps.

---

## Executive Summary

The FOCAL 360 document proposes 9 major platform additions around the existing 11-phase turn brain. This analysis reveals:

| Category                   | Already Implemented | Partial | New/Missing |
| -------------------------- | ------------------- | ------- | ----------- |
| Ingress Control            | 2                   | 2       | 3           |
| Side-Effect Registry       | 3                   | 2       | 2           |
| Channel System             | 6                   | 1       | 2           |
| Config Hierarchy           | 3                   | 1       | 2           |
| Agenda/Goals               | 3                   | 1       | 4           |
| Meta-Agents (ASA/Reporter) | 1                   | 0       | 3           |
| Offerings Catalog          | 1                   | 0       | 2           |
| Persistence Ports          | 5                   | 0       | 0           |

**Key Finding**: The DB-agnostic persistence layer is **fully implemented**. Most other areas have strong foundations but need specific extensions.

---

## 1. Ingress Control & Concurrency

### Vocabulary Mapping

| FOCAL 360 Term          | Existing Term                        | Status            | Notes                                                           |
| ----------------------- | ------------------------------------ | ----------------- | --------------------------------------------------------------- |
| **Ingress Control**     | Rate Limit Middleware                | DIFFERENT CONCEPT | Rate limiting exists; ingress control (pre-P1 wrapper) does not |
| **Debouncing**          | `burst_size` (unused)                | NOT IMPLEMENTED   | Config field exists but is never used in code                   |
| **Rate Limiting**       | `RateLimiter`, `RateLimitMiddleware` | IMPLEMENTED       | Full implementation with Redis + in-memory backends             |
| **Turn Cancellation**   | —                                    | NOT IMPLEMENTED   | No abort/supersede mechanism                                    |
| **Coalescing**          | —                                    | NOT IMPLEMENTED   | No message merging                                              |
| **Idempotency**         | `IdempotencyCache`                   | PARTIAL           | Infrastructure exists but NOT integrated into chat route        |
| **Concurrency Control** | `max_simultaneous_scenarios`         | PARTIAL           | Scenario-level only; no request-level mutex                     |

### Existing Implementation Details

**Rate Limiting** (Full):

- `ruche/api/middleware/rate_limit.py` (387 lines)
- Tier-based: Free (60/min), Pro (600/min), Enterprise (6000/min)
- Backends: `SlidingWindowRateLimiter` (in-memory), `RedisRateLimiter`
- Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

**Idempotency** (Partial):

- `ruche/api/middleware/idempotency.py` (166 lines)
- 5-minute TTL cache, SHA256 fingerprinting
- **GAP**: Chat route has TODOs at lines 189-193 and 232-234

### What Needs to Be Built

1. **Ingress Control Layer** (pre-P1)
   
   - Burst window detection by (tenant_id, agent_id, customer_key, channel)
   - Turn cancellation before commit points
   - Message coalescing for rapid-fire inputs

2. **Debounce Implementation**
   
   - Use existing `burst_size` config field
   - Add actual debouncing logic to rate limit middleware

3. **Integrate Idempotency**
   
   - Connect `IdempotencyCache` to chat endpoint
   - Add Redis backend for production

---

## 2. Side-Effect Registry & Tool Policies

### Vocabulary Mapping

| FOCAL 360 Term           | Existing Term                | Status          | Notes                                            |
| ------------------------ | ---------------------------- | --------------- | ------------------------------------------------ |
| **Side-Effect Registry** | —                            | NOT IMPLEMENTED | Concept doesn't exist                            |
| **ToolSideEffectPolicy** | —                            | NOT IMPLEMENTED | No reversible/compensatable/irreversible marking |
| **Tool Scheduling**      | `ToolBinding.when`           | IMPLEMENTED     | BEFORE_STEP, DURING_STEP, AFTER_STEP             |
| **Checkpoints**          | `ScenarioStep.is_checkpoint` | IMPLEMENTED     | Marks irreversible actions                       |
| **Tool Dependencies**    | `ToolBinding.depends_on`     | IMPLEMENTED     | Topological sort for execution order             |
| **Compensation**         | —                            | NOT IMPLEMENTED | No undo/compensation mechanism                   |
| **Idempotency Keys**     | — (at tool level)            | NOT IMPLEMENTED | Only at API request level                        |

### Existing Implementation Details

**Tool Scheduling** (Full):

- `ruche/alignment/models/tool_binding.py` (25 lines)
- `ruche/alignment/execution/tool_scheduler.py` (162 lines)
- Topological sorting via Kahn's algorithm
- `FutureToolQueue` for AFTER_STEP tools

**Checkpoint Support** (Full):

- `ScenarioStep.is_checkpoint`, `checkpoint_description`
- `StepVisit.is_checkpoint` in session tracking
- Migration logic respects checkpoints (no teleportation across them)

**Tool Execution** (Full):

- `ruche/alignment/execution/tool_executor.py` (131 lines)
- Parallel execution, per-tool timeout, fail-fast mode
- `ToolResult` with success/failure tracking

### What Needs to Be Built

1. **Side-Effect Registry**
   
   - New model: `ToolSideEffectPolicy(reversible, compensatable, irreversible)`
   - Attach to `ToolBinding` or separate registry
   - Ingress Control consults registry for cancel decisions

2. **Compensation Mechanism**
   
   - Optional `compensation_tool_id` field on `ToolBinding`
   - Rollback workflow when turn is cancelled after tool execution

---

## 3. Channel System

### Vocabulary Mapping

| FOCAL 360 Term             | Existing Term       | Status          | Notes                                       |
| -------------------------- | ------------------- | --------------- | ------------------------------------------- |
| **Channel**                | `Channel` enum      | IMPLEMENTED     | WhatsApp, Slack, Webchat, Email, Voice, API |
| **TurnInput.channel**      | `TurnInput.channel` | IMPLEMENTED     | Exact match                                 |
| **ChannelCapability**      | —                   | NOT IMPLEMENTED | No delivery receipts, rich media metadata   |
| **ChannelConfig**          | —                   | NOT IMPLEMENTED | No per-channel configuration object         |
| **Channel Formatters**     | `ChannelFormatter`  | IMPLEMENTED     | WhatsApp, Email, SMS, Default formatters    |
| **Multi-channel Identity** | `ChannelIdentity`   | IMPLEMENTED     | Links customer across channels              |
| **Channel Fallback**       | —                   | NOT IMPLEMENTED | No automatic escalation ladder              |
| **Delivery Receipts**      | —                   | NOT IMPLEMENTED | No webhook handling for receipts            |

### Existing Implementation Details

**Channel Enum** (`ruche/conversation/models/enums.py`):

```python
class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    WEBCHAT = "webchat"
    EMAIL = "email"
    VOICE = "voice"
    API = "api"
```

**Channel Identity** (`ruche/interlocutor_data/models.py`):

- `ChannelIdentity(channel, channel_user_id, verified, verified_at, primary)`
- `InterlocutorDataStore.channel_identities: list[ChannelIdentity]`
- `get_by_channel_identity()` method on stores

**Channel Formatters** (`ruche/alignment/generation/formatters/`):

- WhatsApp: Max 4096 chars, markdown conversion
- Email: Greeting/signature injection
- SMS: 160 char limit, multi-part handling
- Factory: `get_formatter(channel: str) -> ChannelFormatter`

### What Needs to Be Built

1. **ChannelCapability Model**
   
   - Rich media support flags
   - Delivery/read receipt support
   - Max message length
   - Supported content types

2. **Channel Fallback Strategy**
   
   - Escalation ladder: WhatsApp → SMS → Email
   - Configurable per-agent fallback preferences

---

## 4. Configuration Hierarchy

### Vocabulary Mapping

| FOCAL 360 Term         | Existing Term         | Status          | Notes                                      |
| ---------------------- | --------------------- | --------------- | ------------------------------------------ |
| **Tenant Defaults**    | `config/default.toml` | IMPLEMENTED     | Base configuration                         |
| **Agent Overrides**    | `AgentConfig`         | PARTIAL         | Model exists, not integrated into brain |
| **Scenario Overrides** | —                     | NOT IMPLEMENTED | No per-scenario config model               |
| **Step Overrides**     | `[brain.{step}]`   | IMPLEMENTED     | Per-step config in TOML                    |
| **Hot Reload**         | Config Watcher        | DOCUMENTED      | Not implemented in code                    |
| **Dynamic Config**     | —                     | NOT IMPLEMENTED | Static TOML only                           |

### Existing Implementation Details

**Configuration Loading** (`ruche/config/loader.py`):

1. Pydantic model defaults
2. `config/default.toml`
3. `config/{RUCHE_ENV}.toml`
4. `RUCHE_*` environment variables

**AgentConfig Model** (`ruche/config/models/agent.py`):

```python
class AgentConfig(BaseModel):
    name: str
    model: str | None = None  # Override default model
    temperature: float | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None
```

**Status**: Defined but not wired into brain config resolution.

**Hot Reload Architecture** (Documented in `docs/architecture/kernel-agent-integration.md`):

- Redis pub/sub on `cfg-updated` channel
- Config Watcher loads new bundles
- TTL-based cache invalidation

### What Needs to Be Built

1. **Integrate AgentConfig**
   
   - Wire into P1.6 (Load static config)
   - Merge agent overrides onto brain defaults

2. **ScenarioConfig Model**
   
   - Per-scenario model/temperature overrides
   - Merge into config resolution chain

3. **Implement Hot Reload**
   
   - Build Config Watcher service
   - Redis pub/sub integration
   - Cache invalidation on config change

---

## 5. Agenda, Goals & Proactive Outreach

### Vocabulary Mapping

| FOCAL 360 Term         | Existing Term                    | Status          | Notes                                  |
| ---------------------- | -------------------------------- | --------------- | -------------------------------------- |
| **AgendaTask**         | —                                | NOT IMPLEMENTED | No scheduled follow-up model           |
| **Goals**              | —                                | NOT IMPLEMENTED | No conversation objective tracking     |
| **Proactive Outreach** | —                                | NOT IMPLEMENTED | No agent-initiated messaging           |
| **Follow-ups**         | —                                | NOT IMPLEMENTED | No reminder system                     |
| **Lifecycle Stages**   | `ScenarioInstance.status`        | PARTIAL         | active/paused/completed/cancelled      |
| **Job Scheduling**     | Hatchet framework                | IMPLEMENTED     | Cron jobs, workers, retries            |
| **Outcome Tracking**   | `TurnOutcome`, `OutcomeCategory` | IMPLEMENTED     | ANSWERED, BLOCKED, KNOWLEDGE_GAP, etc. |

### Existing Implementation Details

**Hatchet Job Framework** (`ruche/jobs/`):

- `HatchetClient` wrapper with health checking
- Existing workflows: `orphan_detection`, `profile_expiry`, `schema_extraction`
- Configurable cron schedules and worker pools

**Scenario Lifecycle** (`ruche/conversation/models/session.py`):

- `ScenarioInstance`: current_step_id, status, timestamps
- `StepVisit`: transition history with checkpoints
- Multi-scenario support via `Session.active_scenarios`

**Outcome Categories** (`ruche/alignment/models/outcome.py`):

```python
class OutcomeCategory(str, Enum):
    AWAITING_USER_INPUT = "awaiting_user_input"
    KNOWLEDGE_GAP = "knowledge_gap"
    CAPABILITY_GAP = "capability_gap"
    OUT_OF_SCOPE = "out_of_scope"
    SAFETY_REFUSAL = "safety_refusal"
    ANSWERED = "answered"
```

### What Needs to Be Built

1. **AgendaTask Model**
   
   - `task_type`, `scheduled_at`, `customer_id`, `scenario_context`
   - Store in SessionStore or new AgendaStore

2. **Goal Model**
   
   - Expected response type, completion criteria
   - Attach to `ResponsePlan` in P8

3. **Follow-up Workflow**
   
   - Hatchet job for checking unresolved goals
   - Trigger proactive outreach on timeout

4. **Proactive Message Trigger**
   
   - New channel-aware outbound endpoint
   - Respect channel outbound permissions

---

## 6. Meta-Agents (ASA & Reporter)

### Vocabulary Mapping

| FOCAL 360 Term               | Existing Term                       | Status          | Notes                        |
| ---------------------------- | ----------------------------------- | --------------- | ---------------------------- |
| **Agent Setter Agent (ASA)** | —                                   | NOT IMPLEMENTED | No meta-agent concept        |
| **Reporter Agent**           | —                                   | NOT IMPLEMENTED | No analytics narrator        |
| **Admin APIs**               | `/v1/agents/*`, `/v1/rules/*`, etc. | IMPLEMENTED     | REST endpoints for humans    |
| **Simulation Sandbox**       | —                                   | NOT IMPLEMENTED | No dry-run mode              |
| **Builder Tools**            | —                                   | NOT IMPLEMENTED | No agent-facing config tools |

### Existing Implementation Details

**Admin CRUD APIs** (`ruche/api/routes/`):

- `agents.py`: Agent CRUD
- `rules.py`: Rule management (17KB)
- `scenarios.py`: Scenario management (13KB)
- `templates.py`: Template management
- `variables.py`: Variable management
- `tools.py`: Tool activation/deactivation
- `publish.py`: Version publishing with rollback

**Status**: These are HTTP REST APIs for human administrators, not agent-facing.

### What Needs to Be Built

1. **ASA Meta-Agent**
   
   - Agent persona with access to admin APIs as tools
   - Edge-case generation and stress testing
   - Side-effect policy recommendation

2. **Reporter Agent**
   
   - Read-only access to AuditStore
   - Natural language summarization of metrics
   - Trend analysis and anomaly detection

3. **Simulation Sandbox**
   
   - Non-production mode flag
   - Separate audit stream for simulated turns
   - Dry-run tool execution (no side effects)

---

## 7. Offerings Catalog

### Vocabulary Mapping

| FOCAL 360 Term        | Existing Term             | Status          | Notes                                   |
| --------------------- | ------------------------- | --------------- | --------------------------------------- |
| **Offerings Catalog** | —                         | NOT IMPLEMENTED | No product/service catalog              |
| **Products**          | `Entity.type = "product"` | PARTIAL         | Memory extraction only, not catalog     |
| **Services**          | —                         | NOT IMPLEMENTED | No service model                        |
| **Template Library**  | `Template`                | IMPLEMENTED     | Response templates, not product catalog |
| **Knowledge Base**    | —                         | NOT IMPLEMENTED | No KB/FAQ system                        |

### Existing Implementation Details

**Template System** (`ruche/alignment/models/template.py`):

- Response templates with `{placeholders}`
- Modes: SUGGEST, MANDATE
- Scopes: GLOBAL, SCENARIO, STEP

**Entity Extraction** (`ruche/memory/ingestion/entity_extractor.py`):

- Extracts "product" as entity type from conversations
- Used for memory, not catalog management

### What Needs to Be Built

1. **Offerings Model**
   
   - `Offering(id, name, type, description, attributes, embedding)`
   - Type: product, service, plan, tier

2. **Offerings Store**
   
   - Extend ConfigStore or new store interface
   - Vector search for semantic product matching

3. **KB Integration**
   
   - Article/FAQ model with embeddings
   - Retrieval in P4 alongside rules/scenarios

---

## 8. DB-Agnostic Persistence Ports

### Vocabulary Mapping

| FOCAL 360 Term        | Existing Term                | Status      | Notes                               |
| --------------------- | ---------------------------- | ----------- | ----------------------------------- |
| **ConfigStore**       | `AgentConfigStore`           | IMPLEMENTED | 397 methods, Postgres + InMemory    |
| **MemoryStore**       | `MemoryStore`                | IMPLEMENTED | 148 methods, Postgres + Neo4j stubs |
| **SessionStore**      | `SessionStore`               | IMPLEMENTED | 89 methods, Redis + Postgres        |
| **AuditStore**        | `AuditStore`                 | IMPLEMENTED | 72 methods, 5 backends              |
| **InterlocutorDataStore** | `InterlocutorDataStoreInterface` | IMPLEMENTED | 457 methods, lineage tracking       |
| **VectorStore**       | `VectorStore`                | IMPLEMENTED | pgvector, Qdrant                    |
| **PersistencePort**   | ABC pattern                  | IMPLEMENTED | All stores use ABC                  |

### Existing Implementation Details

**This is FULLY IMPLEMENTED**. The Focal codebase has a production-grade, multi-backend persistence layer:

| Store             | Backends Available                                     |
| ----------------- | ------------------------------------------------------ |
| AgentConfigStore  | PostgreSQL, InMemory                                   |
| MemoryStore       | PostgreSQL, InMemory, Neo4j (stub), MongoDB (stub)     |
| SessionStore      | Redis, PostgreSQL, MongoDB, DynamoDB, InMemory         |
| AuditStore        | PostgreSQL, TimescaleDB, MongoDB, ClickHouse, InMemory |
| InterlocutorDataStore | PostgreSQL, InMemory, Cached decorator                 |
| VectorStore       | pgvector, Qdrant, InMemory                             |

**Connection Pooling**: `ruche/db/pool.py` (asyncpg)
**Contract Tests**: `tests/contract/test_interlocutor_data_store_contract.py`
**Documentation**: ADR-001, `alignment_engine_persistence_abstraction.md`

### What Needs to Be Built

**Nothing** - this layer is complete. Future stores (AgendaStore, OfferingsStore) should follow the same ABC + InMemory + Postgres pattern.

---

## 9. Priority Implementation Roadmap

Based on dependencies and value:

### Tier 1: Foundation (Enables Others)

1. **Integrate AgentConfig into Brain** (2-3 days)
   
   - Wire P1.6 to load agent-specific overrides
   - Enables per-agent customization

2. **Implement Idempotency in Chat Route** (1 day)
   
   - Connect existing middleware to chat endpoint
   - Add Redis backend

3. **Add ChannelCapability Model** (1-2 days)
   
   - Metadata for channel features
   - Used by formatters and fallback logic

### Tier 2: Safety & Reliability

4. **Build Side-Effect Registry** (2-3 days)
   
   - `ToolSideEffectPolicy` model
   - Integrate with P7 and future Ingress Control

5. **Implement Ingress Control** (3-5 days)
   
   - Pre-P1 wrapper
   - Debouncing, coalescing, cancel decisions

### Tier 3: Lifecycle & Proactive

6. **Agenda/Goal Models** (2-3 days)
   
   - New models attached to ResponsePlan/Session
   - Hatchet workflow for follow-up checks

7. **Hot Reload Config Watcher** (3-5 days)
   
   - Redis pub/sub integration
   - Cache invalidation

### Tier 4: Meta-Agents (Future)

8. **ASA Meta-Agent** (1-2 weeks)
   
   - Requires stable admin API surface
   - Needs simulation sandbox first

9. **Reporter Agent** (1 week)
   
   - Simpler: read-only access to AuditStore
   - Natural language analytics

---

## 10. Vocabulary Standardization Recommendations

To avoid confusion, recommend these standard terms:

| FOCAL 360 Term       | Recommended Focal Term | Reason                                        |
| -------------------- | ------------------------ | --------------------------------------------- |
| Ingress Control      | `TurnGateway`            | "Ingress" implies network; this is turn-level |
| Debouncing           | `BurstCoalescer`         | More specific to behavior                     |
| Side-Effect Registry | `ToolEffectRegistry`     | Aligns with `ToolBinding`                     |
| ChannelCapability    | `ChannelProfile`         | Matches `CustomerProfile` pattern             |
| AgendaTask           | `ScheduledAction`        | Clearer than "agenda"                         |
| ASA                  | `ConfigBuilderAgent`     | Describes function                            |
| Reporter Agent       | `AnalyticsAgent`         | More specific                                 |

---

## Appendix: File Reference

### Key Existing Files

| Component          | Primary File                                                 |
| ------------------ | ------------------------------------------------------------ |
| Rate Limiting      | `ruche/api/middleware/rate_limit.py`                       |
| Idempotency        | `ruche/api/middleware/idempotency.py`                      |
| Tool Scheduling    | `ruche/alignment/execution/tool_scheduler.py`              |
| Tool Execution     | `ruche/alignment/execution/tool_executor.py`               |
| Channel Enum       | `ruche/conversation/models/enums.py`                       |
| Channel Identity   | `ruche/interlocutor_data/models.py`                            |
| Channel Formatters | `ruche/alignment/generation/formatters/`                   |
| Agent Config       | `ruche/config/models/agent.py`                             |
| Config Loading     | `ruche/config/loader.py`                                   |
| Hatchet Jobs       | `ruche/jobs/`                                              |
| Session Model      | `ruche/conversation/models/session.py`                     |
| Outcome Model      | `ruche/alignment/models/outcome.py`                        |
| Admin APIs         | `ruche/api/routes/`                                        |
| Store Interfaces   | `ruche/alignment/stores/`, `ruche/memory/store.py`, etc. |

### Documentation References

| Topic                   | Document                                                  |
| ----------------------- | --------------------------------------------------------- |
| 11-Phase Brain       | `docs/focal_brain/README.md`                      |
| Storage Architecture    | `docs/design/decisions/001-storage-choice.md`             |
| Persistence Abstraction | `docs/design/alignment_engine_persistence_abstraction.md` |
| Hot Reload Design       | `docs/architecture/kernel-agent-integration.md`           |
| Scenario Migration      | `docs/design/scenario-update-methods.md`                  |
