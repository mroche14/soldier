# Ruche Implementation Waves

**Generated**: 2025-12-15
**Updated**: 2025-12-16 (Implementation Status Audit)
**Based on**: 14-agent parallel architecture analysis (8 initial + 6 deep dive)

This document organizes all identified implementation gaps into **independent waves** that can be executed in parallel within each wave. Later waves depend on earlier waves being complete.

## Related Documents

- `SUBAGENT_IMPLEMENTATION_PROTOCOL.md` - Protocol for implementing these tasks
- `FOCAL_BRAIN_PHASE_COMPLIANCE_MATRIX.md` - Detailed phase-by-phase compliance (74% overall)

---

## Executive Summary

| Wave | Focus | Tasks | Parallelizable |
|------|-------|-------|----------------|
| **Wave 1** | Foundation & Cleanup | 13 tasks | Yes (all independent) |
| **Wave 2** | Core Infrastructure | 10 tasks | Yes (all independent) |
| **Wave 3** | Integration | 7 tasks | Yes (all independent) |
| **Wave 4** | API & Runtime | 7 tasks | Yes (all independent) |
| **Wave 5** | Advanced Features | 9 tasks | Yes (all independent) |

**Total**: 46 tasks across 5 waves

### Key Metrics from Deep Analysis

| Area | Status | Notes |
|------|--------|-------|
| FOCAL Brain Phases | 74% (50/68 substeps) | Phases 1-3, 9-11 excellent; Phases 5-7 need work |
| ACF Topics | ~40% average | Turn Gateway MISSING (15%), Session Mutex good (85%) |
| Test Coverage | 59% | Target: 85%. Migration module has 3,539 lines with 0 tests |
| Empty Stub Files | 18 | Provider implementations, store backends |
| NotImplementedError | 23 | PostgreSQL ConfigStore templates, expression evaluator |
| Duplicate ABCs | 2 pairs | MemoryStore, InterlocutorDataStore |
| Orphaned Modules | 4 | client/, asa/, vector/, agenda/ |

---

## Implementation Status (as of 2025-12-16, Final Update)

### Overall Progress

| Wave | Complete | Partial | Not Done | Total | Progress |
|------|----------|---------|----------|-------|----------|
| **Wave 1** | 13 | 0 | 0 | 13 | **100%** |
| **Wave 2** | 10 | 0 | 0 | 10 | **100%** |
| **Wave 3** | 7 | 0 | 0 | 7 | **100%** |
| **Wave 4** | 7 | 0 | 0 | 7 | **100%** |
| **Wave 5** | 8 | 0 | 1 | 9 | 89% |
| **TOTAL** | **45** | **0** | **1** | **46** | **98%** |

### Test Suite Status
- Unit tests: 1703 passed, 1 skipped
- Integration tests: 14 Redis-related failures (need Redis running)
- Coverage: 59.2% (target: 85%)
- Tracking: See `IMPLEMENTATION_CHECKLIST.md` for quick status

### Wave 1 Checklist

| Task | Status | Evidence |
|------|--------|----------|
| 1A: FOCAL Brain Consolidation | ✅ | `engine.py` deleted, `pipeline.py` canonical |
| 1B: Missing Database Tables | ✅ | Migrations 013, 014, 015 created |
| 1C: Logging Middleware | ✅ | `middleware.py` 96 lines, LoggingContextMiddleware |
| 1D: Observability Config | ✅ | `default.toml` has [observability] section |
| 1E: Model Consolidation | ✅ | InterlocutorDataStore consolidated to domain/ |
| 1F: OpenAI Embedding Provider | ✅ | `openai.py` 100+ lines implemented |
| 1G: Cohere Embedding Provider | ✅ | `cohere.py` 80+ lines implemented |
| 1H: Cohere Rerank Provider | ✅ | `cohere.py` 50+ lines implemented |
| 1I: InterlocutorChannelPresence | ✅ | `channel_presence.py` created |
| 1J: History Trimming | ✅ | `updater.py` lines 213-215 |
| 1K: Remove Duplicate ABCs | ✅ | MemoryStore and InterlocutorDataStore consolidated |
| 1L: Clean Up Empty Stub Files | ✅ | Documented in docs/architecture/stub-files.md |
| 1M: Document Client SDK | ✅ | `client-sdk.md` 822 lines |

### Wave 2 Checklist

| Task | Status | Evidence |
|------|--------|----------|
| 2A: FabricTurnContext Protocol | ✅ | Protocol + FabricTurnContextImpl dataclass |
| 2B: AgentContext Rewrite | ✅ | Has agent, brain, toolbox, channel_bindings |
| 2C: AgentTurnContext | ✅ | Wraps FabricTurnContext + AgentContext |
| 2D: Brain Protocol | ✅ | `protocol.py` 68 lines, Brain + SupersedeCapable |
| 2E: Toolbox Implementation | ✅ | 4 files totaling 830+ lines |
| 2F: ChannelPolicy Model | ✅ | `models.py` with SupersedeMode enum |
| 2G: Complete Template Model | ✅ | Has `render()` method and `variables_used` property |
| 2H: Type TurnContext | ✅ | Proper types: Session, InterlocutorDataStore |
| 2I: Turn Gateway (CRITICAL) | ✅ | `gateway.py` 198 lines, TurnGateway + ActiveTurnIndex |
| 2J: Configuration Hierarchy | ✅ | Framework done, layer getters documented with tests |

### Wave 3 Checklist

| Task | Status | Evidence |
|------|--------|----------|
| 3A: Workflow AgentRuntime Integration | ✅ | AgentRuntime injected, brain.think() called |
| 3B: Tool Execution Integration (P7.1-P7.7) | ✅ | `_execute_tools()` calls ToolExecutionOrchestrator |
| 3C: Scenario Contributions (P6.4) | ✅ | `extract_scenario_contributions()` implemented |
| 3D: LLM Semantic Categories (P9.4) | ✅ | `GenerationResult.llm_categories` field |
| 3E: Relationship Expansion (P5.3) | ✅ | `RelationshipExpander` called from pipeline |
| 3F: Scope/Lifecycle Pre-Filter (P5.1) | ✅ | `ScopePreFilter` called before LLM filter |
| 3G: Language Validation (P2.6) | ✅ | `_validate_language()` with VALID_LANGUAGE_CODES |

### Wave 4 Checklist

| Task | Status | Evidence |
|------|--------|----------|
| 4A: Chat Endpoint | ✅ | `POST /v1/chat` in turns.py |
| 4B: Chat Streaming (SSE) | ✅ | `POST /v1/chat/stream` with EventSourceResponse |
| 4C: Memory Endpoints | ✅ | episodes, search, entities endpoints |
| 4D: EventRouter | ✅ | `event_router.py` with pattern matching |
| 4E: IdempotencyCache | ✅ | 3-tier cache (API/Beat/Tool) |
| 4F: Adaptive Accumulation | ✅ | Channel-aware, shape-aware timing |
| 4G: ACF Event Emission | ✅ | 17 event types, emitted in workflow |

### Wave 5 Checklist

| Task | Status | Evidence |
|------|--------|----------|
| 5A: Webhook System | ✅ | 4 files, HMAC signing, pattern matching |
| 5B: gRPC Services | ✅ | Proto files + 3 service implementations |
| 5C: ChannelGateway | ✅ | Gateway + Adapter pattern + webchat adapter |
| 5D: Row Level Security | ✅ | Migration 016 applies RLS to all tables |
| 5E: PostgreSQL Session Persistence | ✅ | Migration 017 creates sessions table |
| 5F: Regeneration Loop (P10.8) | ✅ | Retry loop with max_retries, violation feedback |
| 5G: Memory Ingestion (P11.5) | ✅ | `_ingest_memory()` in pipeline |
| 5H: Migration Module Tests | ✅ | 2,193 lines, 64 test functions |
| 5I: Test Coverage to 85% | ❌ | At 59.2%, need +25.8% improvement |

### Remaining Work

**High Priority:**
- **5I**: Test coverage improvement (25.8% gap to 85% target)
  - Focus on PRODUCTION code, not test fixtures (InMemory stores)
  - Priority 1: ACF Workflow (19.1% coverage) - Stateless pod orchestration
  - Priority 2: PostgreSQL Stores (12-13% coverage) - Production backends
  - Priority 3: FOCAL Brain Phases (33-70% coverage) - Core business logic
  - See `IMPLEMENTATION_CHECKLIST.md` for sub-task tracking

**Completed This Session (2025-12-16):**
- **2G**: Template model - `render()` and `variables_used` ✅
- **5F**: Regeneration retry loop with violation feedback ✅
- **2J**: ConfigResolver layer getters documented ✅
- **1E/1K**: InterlocutorDataStore consolidated (502 lines) ✅
- **1L**: Stub files documented in `stub-files.md` ✅
- Fixed 32+ failing unit tests
- Fixed 9 field_resolver tests (1 still skipped)
- Added `interlocutor_id` field to Session model

**Test Results:**
- Unit tests: 1703 passed, 1 skipped
- Coverage: 52.5%
- Test count increase: +24 tests

**Documentation Created:**
- `docs/implementation/PARALLEL_WORK_TASKS.md` - Task breakdowns
- `docs/architecture/stub-files.md` - Stub file catalog
- `COVERAGE_IMPROVEMENT_PLAN.md` - Coverage roadmap
- `COVERAGE_STATUS.md` - Coverage analysis

---

## Wave 1: Foundation & Cleanup

**Dependencies**: None
**Can run in parallel**: All tasks are independent

### 1A: FOCAL Brain Consolidation
**Priority**: CRITICAL
**Effort**: 1 day
**Files**:
- DELETE: `ruche/brains/focal/engine.py` (2076 lines - redundant)
- KEEP: `ruche/brains/focal/pipeline.py` (2098 lines - canonical)
- UPDATE: All imports referencing `AlignmentEngine` → `FocalCognitivePipeline`

**Rationale**: Two nearly-identical implementations exist. Consolidate to single source of truth.

---

### 1B: Missing Database Tables
**Priority**: CRITICAL
**Effort**: 1 day
**Files to create**:
- `ruche/infrastructure/db/migrations/versions/013_glossary.py`
- `ruche/infrastructure/db/migrations/versions/014_intents.py`
- `ruche/infrastructure/db/migrations/versions/015_rule_relationships.py`

**Tables**:
```sql
-- glossary_items
CREATE TABLE glossary_items (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    term VARCHAR(255) NOT NULL,
    definition TEXT NOT NULL,
    usage_hint TEXT,
    aliases TEXT[],
    category VARCHAR(100),
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- intents
CREATE TABLE intents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    label VARCHAR(255) NOT NULL,
    description TEXT,
    examples TEXT[],
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- rule_relationships
CREATE TABLE rule_relationships (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    from_rule_id UUID NOT NULL REFERENCES rules(id),
    to_rule_id UUID NOT NULL REFERENCES rules(id),
    relationship_type VARCHAR(50) NOT NULL, -- depends_on, implies, excludes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
```

**Then**: Update `PostgresAgentConfigStore` to remove `NotImplementedError` stubs.

---

### 1C: Logging Middleware
**Priority**: HIGH
**Effort**: 0.5 day
**File**: `ruche/observability/middleware.py` (currently empty)

**Implementation**:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

class LoggingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        clear_contextvars()
        bind_contextvars(
            tenant_id=request.headers.get("X-Tenant-ID"),
            agent_id=request.headers.get("X-Agent-ID"),
            session_id=request.headers.get("X-Session-ID"),
            trace_id=request.headers.get("X-Trace-ID"),
        )
        return await call_next(request)
```

**Then**: Register in `ruche/api/app.py`.

---

### 1D: Observability Config
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `config/default.toml`

**Add section**:
```toml
[observability]
[observability.logging]
level = "INFO"
format = "json"
include_trace_id = true
redact_pii = true

[observability.tracing]
enabled = true
otlp_endpoint = ""
service_name = "ruche"

[observability.metrics]
enabled = true
port = 9090
```

---

### 1E: Model Consolidation
**Priority**: MEDIUM
**Effort**: 0.5 day

**Duplicates to consolidate**:

1. **InterlocutorDataStore**:
   - KEEP: `ruche/domain/interlocutor/models.py`
   - DELETE: `ruche/interlocutor_data/models.py:269-320` (move imports)

2. **SchemaMask**:
   - KEEP: `ruche/domain/interlocutor/schema_mask.py` (InterlocutorSchemaMask)
   - UPDATE: `ruche/brains/focal/phases/context/customer_schema_mask.py` to import from domain
   - OR: Document why FOCAL needs its own `CustomerSchemaMask`

---

### 1F: OpenAI Embedding Provider
**Priority**: HIGH
**Effort**: 1 day
**File**: `ruche/infrastructure/providers/embedding/openai.py` (currently empty)

**Implementation**: Follow pattern from `jina.py`:
- Support models: `text-embedding-3-small`, `text-embedding-3-large`
- Use `openai` SDK
- Read `OPENAI_API_KEY` from env

---

### 1G: Cohere Embedding Provider
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/infrastructure/providers/embedding/cohere.py` (currently empty)

**Implementation**:
- Support model: `embed-english-v3.0`
- Use `cohere` SDK
- Read `COHERE_API_KEY` from env

---

### 1H: Cohere Rerank Provider
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/infrastructure/providers/rerank/cohere.py` (currently empty)

**Implementation**:
- Support model: `rerank-english-v3.0`
- Use `cohere` SDK

---

### 1I: InterlocutorChannelPresence Model
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/domain/interlocutor/channel_presence.py`

**Add to InterlocutorDataStore**:
```python
channel_presence: list[InterlocutorChannelPresence] = Field(default_factory=list)
```

---

### 1J: History Trimming
**Priority**: LOW
**Effort**: 0.25 day
**File**: `ruche/brains/focal/phases/interlocutor/updater.py:196-206`

**Add**:
```python
if self._config.max_history_entries and len(history) > self._config.max_history_entries:
    history = history[-self._config.max_history_entries:]
```

---

### 1K: Remove Duplicate ABCs
**Priority**: HIGH
**Effort**: 0.5 day

**Duplicates found**:

1. **MemoryStore** defined twice:
   - KEEP: `ruche/infrastructure/stores/memory/interface.py`
   - DELETE: `ruche/memory/store.py` (update all imports)

2. **InterlocutorDataStore** defined twice:
   - KEEP: `ruche/infrastructure/stores/interlocutor/interface.py`
   - DELETE: `ruche/interlocutor_data/store.py` (update all imports)

**Impact**: Causes confusion about which interface to implement against.

---

### 1L: Clean Up Empty Stub Files
**Priority**: MEDIUM
**Effort**: 0.5 day

**18 empty (0-byte) files** must be either implemented or deleted:

**Storage Implementations** (implement or document as future):
- `ruche/memory/stores/neo4j.py`
- `ruche/memory/stores/mongodb.py`
- `ruche/audit/stores/clickhouse.py`
- `ruche/audit/stores/timescale.py`
- `ruche/audit/stores/mongodb.py`
- `ruche/conversation/stores/dynamodb.py`
- `ruche/conversation/stores/mongodb.py`

**Provider Implementations** (implement priority ones):
- `ruche/infrastructure/providers/embedding/voyage.py`
- `ruche/infrastructure/providers/embedding/cohere.py` → See 1G
- `ruche/infrastructure/providers/embedding/openai.py` → See 1F
- `ruche/infrastructure/providers/rerank/voyage.py`
- `ruche/infrastructure/providers/rerank/cohere.py` → See 1H
- `ruche/infrastructure/providers/rerank/cross_encoder.py`

**Other** (delete if not planned):
- `ruche/api/grpc/server.py` → See 5B or delete
- `ruche/api/grpc/__init__.py`
- `ruche/api/routes/config.py`
- `ruche/observability/middleware.py` → See 1C
- `ruche/memory/ingestion/__init__.py`

---

### 1M: Document Client SDK
**Priority**: LOW
**Effort**: 0.5 day
**Files**:
- `ruche/client/client.py` (598 lines - COMPLETE but undocumented)
- Create `docs/development/client-sdk.md`

**The FocalClient is production-ready** with:
- `FocalClient.dev()` - Dev mode with JWT generation
- Full CRUD for agents, rules, scenarios, templates, variables
- Chat and streaming chat endpoints
- Depends on `httpx`, `python-jose`

**Currently only used in**: `notebooks/client_demo.py`

---

## Wave 2: Core Infrastructure

**Dependencies**: Wave 1 complete
**Can run in parallel**: All tasks are independent

### 2A: FabricTurnContext Protocol
**Priority**: CRITICAL
**Effort**: 1 day
**File**: `ruche/runtime/acf/models.py:215-241`

**Current** (WRONG):
```python
class FabricTurnContext(BaseModel):  # Pydantic model
    logical_turn_id: UUID
    # ... data fields
```

**Target** (CORRECT):
```python
from typing import Protocol

class FabricTurnContext(Protocol):
    """NOT serializable - rebuilt each Hatchet step."""
    logical_turn: LogicalTurn
    session_key: str
    channel: str

    async def has_pending_messages(self) -> bool: ...
    async def emit_event(self, event: ACFEvent) -> None: ...

@dataclass
class FabricTurnContextImpl:
    """Concrete implementation with live callbacks."""
    logical_turn: LogicalTurn
    session_key: str
    channel: str
    _check_pending: Callable[[], Awaitable[bool]]
    _route_event: Callable[[ACFEvent], Awaitable[None]]

    async def has_pending_messages(self) -> bool:
        return await self._check_pending()

    async def emit_event(self, event: ACFEvent) -> None:
        await self._route_event(event)
```

---

### 2B: AgentContext Rewrite
**Priority**: CRITICAL
**Effort**: 1 day
**File**: `ruche/runtime/agent/context.py`

**Current** (WRONG):
```python
@dataclass
class AgentContext:
    metadata: AgentMetadata
    capabilities: AgentCapabilities
    config_store: ConfigStore
    # ... stores
```

**Target** (per AGENT_RUNTIME_SPEC.md):
```python
@dataclass
class AgentContext:
    agent: Agent
    brain: Brain
    toolbox: Toolbox
    channel_bindings: dict[str, ChannelBinding]
    channel_policies: dict[str, ChannelPolicy]
    llm_executor: LLMExecutor | None = None
```

---

### 2C: AgentTurnContext
**Priority**: CRITICAL
**Effort**: 0.5 day
**File**: `ruche/runtime/agent/context.py` (add new class)

**Implementation**:
```python
@dataclass
class AgentTurnContext:
    """Per-turn context wrapping FabricTurnContext with AgentContext."""
    fabric: FabricTurnContext
    agent_context: AgentContext

    @property
    def toolbox(self) -> Toolbox:
        return self.agent_context.toolbox

    @property
    def logical_turn(self) -> LogicalTurn:
        return self.fabric.logical_turn

    async def has_pending_messages(self) -> bool:
        return await self.fabric.has_pending_messages()

    async def emit_event(self, event: ACFEvent) -> None:
        await self.fabric.emit_event(event)

    async def execute_tool(self, tool_name: str, args: dict) -> ToolResult:
        return await self.toolbox.execute(tool_name, args, self)
```

---

### 2D: Brain Protocol
**Priority**: HIGH
**Effort**: 0.5 day
**File**: Create `ruche/runtime/brain/protocol.py`

```python
from typing import Protocol

class Brain(Protocol):
    name: str

    async def think(self, ctx: AgentTurnContext) -> BrainResult: ...

class SupersedeCapable(Protocol):
    async def decide_supersede(
        self,
        current: LogicalTurn,
        new: RawMessage,
        interrupt_point: str,
    ) -> SupersedeDecision: ...
```

---

### 2E: Toolbox Implementation
**Priority**: CRITICAL
**Effort**: 2 days
**Directory**: Create `ruche/runtime/toolbox/`

**Files**:
- `__init__.py`
- `toolbox.py` - Main class with `execute()`, `execute_batch()`, `get_metadata()`, `is_available()`
- `gateway.py` - ToolGateway for actual execution
- `context.py` - ToolExecutionContext

**Key features**:
- Three-tier visibility (Catalog → Tenant-available → Agent-enabled)
- ACFEvent emission for side effects
- Side effect recording in LogicalTurn

---

### 2F: ChannelPolicy Model
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: Create `ruche/runtime/channels/models.py`

```python
class ChannelPolicy(BaseModel):
    channel: str
    aggregation_window_ms: int = 3000
    supersede_default: SupersedeMode = SupersedeMode.QUEUE
    supports_typing_indicator: bool = True
    supports_read_receipts: bool = True
    max_message_length: int | None = None
    supports_markdown: bool = True
    supports_rich_media: bool = True
    natural_response_delay_ms: int = 0
    max_messages_per_minute: int = 60
```

---

### 2G: Complete Template Model
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/domain/templates.py`

**Add missing fields**:
- `scope: Scope`
- `scope_id: UUID | None`
- `conditions: list[str]`
- `render(variables: dict) -> str` method
- `variables_used` property

---

### 2H: Type TurnContext
**Priority**: LOW
**Effort**: 0.5 day
**File**: `ruche/brains/focal/models/turn_context.py`

**Replace dict fields with proper types**:
```python
# Current
session: dict[str, Any]
customer_data: dict[str, Any]

# Target
session: Session
customer_data: InterlocutorDataStore
pipeline_config: PipelineConfig
```

---

### 2I: Turn Gateway (CRITICAL)
**Priority**: CRITICAL
**Effort**: 2 days
**Directory**: Create `ruche/runtime/acf/gateway.py`

**This is the #1 missing component** - No message ingress layer exists!

**Required Components** (per ACF Topic 07):
```python
class TurnGateway:
    """Message ingress layer that routes to ACF workflows."""

    async def receive_message(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
        channel_user_id: str,
        message: RawMessage,
    ) -> TurnDecision:
        """
        Entry point for all incoming messages.

        1. Check rate limits
        2. Lookup active workflow for session
        3. Decision: TRIGGER_NEW, SIGNAL_EXISTING, QUEUE, REJECT
        """
        ...

class ActiveTurnIndex:
    """O(1) lookup of running workflows by session key."""
    async def get_workflow_id(self, session_key: str) -> str | None: ...
    async def set_workflow_id(self, session_key: str, workflow_id: str) -> None: ...
    async def clear_workflow_id(self, session_key: str) -> None: ...

class TurnDecision(BaseModel):
    action: TurnAction  # TRIGGER_NEW, SIGNAL_EXISTING, QUEUE, REJECT
    workflow_id: str | None
    reason: str | None
```

**Integration Points**:
- Connect to API layer (`POST /v1/chat`)
- Connect to Hatchet workflow triggering
- Redis-backed `ActiveTurnIndex`

---

### 2J: Configuration Hierarchy
**Priority**: HIGH
**Effort**: 1.5 days
**Directory**: Create `ruche/runtime/config/resolver.py`

**Currently missing**: No per-tenant/agent/channel configuration loading.

**Required Components** (per ACF Topic 08):
```python
class ConfigResolver:
    """Multi-level configuration resolution."""

    async def resolve(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str | None = None,
        scenario_id: UUID | None = None,
        step_id: UUID | None = None,
    ) -> ResolvedConfig:
        """
        Resolution order (later overrides earlier):
        1. Platform defaults
        2. Tenant-level config
        3. Agent-level config
        4. Channel-level overrides
        5. Scenario-level overrides
        6. Step-level overrides
        """
        ...

class ResolvedConfig(BaseModel):
    accumulation_window_ms: int = 3000
    max_response_length: int = 4096
    channel_policy: ChannelPolicy
    brain_config: dict[str, Any]
    # ... other resolved values

class CachedConfigStore:
    """Config store wrapper with TTL-based caching."""
    cache_ttl_seconds: int = 300

    async def get_config(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AgentConfig: ...
```

**Usage in ACF Workflow**:
```python
# In workflow.accumulate()
config = await self._config_resolver.resolve(tenant_id, agent_id, channel)
wait_ms = config.accumulation_window_ms
```

---

## Wave 3: Integration

**Dependencies**: Wave 2 complete
**Can run in parallel**: All tasks are independent

### 3A: Workflow AgentRuntime Integration
**Priority**: CRITICAL
**Effort**: 1.5 days
**File**: `ruche/runtime/acf/workflow.py`

**Changes**:
1. Inject `AgentRuntime` dependency
2. In `run_agent` step:
   - Call `agent_runtime.get_context(tenant_id, agent_id)`
   - Build `FabricTurnContextImpl` with live callbacks
   - Wrap in `AgentTurnContext`
   - Call `agent_ctx.agent_context.brain.think(agent_ctx)`
3. Implement `_check_pending()` and `_route_event()` helpers

---

### 3B: Tool Execution Integration (P7.1-P7.7)
**Priority**: HIGH
**Effort**: 1 day
**Files**:
- `ruche/brains/focal/pipeline.py:957-998` (`_execute_tools`)
- Wire existing modules from `ruche/brains/focal/phases/execution/`:
  - `tool_binding_collector.py`
  - `variable_requirement_analyzer.py`
  - `variable_resolver.py`
  - `tool_scheduler.py`
  - `variable_merger.py`

**These modules exist but are NOT called from the pipeline!**

---

### 3C: Scenario Contributions (P6.4)
**Priority**: HIGH
**Effort**: 1 day
**Files**:
- `ruche/brains/focal/pipeline.py:1329-1381`
- `ruche/brains/focal/phases/orchestration/orchestrator.py`

**Current**: Creates empty `ScenarioContributionPlan`
**Target**: Extract actual contributions (ASK/INFORM/CONFIRM/ACTION_HINT) from active scenario steps

---

### 3D: LLM Semantic Categories (P9.4)
**Priority**: MEDIUM
**Effort**: 0.5 day
**Files**:
- `ruche/brains/focal/phases/generation/generator.py`
- `ruche/brains/focal/models/generation_result.py`

**Add**:
- Update generation prompt to request structured output with categories
- Add `categories: list[OutcomeCategory]` to `GenerationResult`
- Accumulate categories throughout brain phases

---

### 3E: Relationship Expansion (P5.3)
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/brains/focal/pipeline.py:1234-1279`

**Add call to**:
- `ruche/brains/focal/phases/filtering/relationship_expander.py` after P5.2

---

### 3F: Scope/Lifecycle Pre-Filter (P5.1)
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: `ruche/brains/focal/pipeline.py:1234-1279`

**Add before LLM filter**:
- Check `rule.enabled`
- Check `rule.scope` matches active scenario/step
- Check cooldown via `session.rule_last_fire_turn`
- Check `max_fires_per_session` via `session.rule_fires`

---

### 3G: Language Validation (P2.6)
**Priority**: LOW
**Effort**: 0.25 day
**File**: `ruche/brains/focal/phases/context/situation_sensor.py`

**Add**: Validate/fix `language` field from LLM output

---

## Wave 4: API & Runtime

**Dependencies**: Wave 3 complete
**Can run in parallel**: All tasks are independent

### 4A: Chat Endpoint
**Priority**: CRITICAL
**Effort**: 1.5 days
**File**: Create `ruche/api/routes/chat.py`

**Endpoints**:
- `POST /v1/chat` - Main message processing
- Wire to `FocalCognitivePipeline` via workflow

---

### 4B: Chat Streaming (SSE)
**Priority**: HIGH
**Effort**: 1 day
**File**: `ruche/api/routes/chat.py`

**Endpoint**: `POST /v1/chat/stream`
**Use**: `sse-starlette` for Server-Sent Events

---

### 4C: Memory Endpoints
**Priority**: MEDIUM
**Effort**: 1 day
**File**: Create `ruche/api/routes/memory.py`

**Endpoints**:
- `POST /v1/memory/episodes`
- `GET /v1/memory/search`
- `GET /v1/memory/entities/{id}`

---

### 4D: EventRouter
**Priority**: MEDIUM
**Effort**: 1 day
**File**: Create `ruche/runtime/acf/event_router.py`

**Implementation**:
- Route ACFEvents to appropriate listeners
- Record side effects in LogicalTurn
- Support external integrations

---

### 4E: IdempotencyCache
**Priority**: MEDIUM
**Effort**: 1 day
**Directory**: Create `ruche/runtime/idempotency/`

**Three layers** (per ACF Topic 12):
1. API layer (5min TTL) - Prevent duplicate HTTP requests
2. Beat layer (60s TTL) - Prevent duplicate turn processing
3. Tool layer (24hr TTL) - Prevent duplicate business actions

**Components**:
```python
class IdempotencyCache:
    """Redis-backed idempotency cache."""
    async def check(self, key: str, layer: str) -> IdempotencyCheckResult: ...
    async def mark_processing(self, key: str, layer: str) -> None: ...
    async def mark_complete(self, key: str, layer: str, result: Any) -> None: ...

class IdempotencyCheckResult(BaseModel):
    status: IdempotencyStatus  # NEW, PROCESSING, COMPLETE
    cached_result: Any | None
```

---

### 4F: Adaptive Accumulation
**Priority**: MEDIUM
**Effort**: 1 day
**File**: `ruche/runtime/acf/turn_manager.py`

**Current**: `suggest_wait_ms()` returns hardcoded value.
**Target**: Channel-aware, shape-aware, hint-aware timing.

**Required Changes** (per ACF Topic 03):
```python
class TurnManager:
    async def suggest_wait_ms(
        self,
        channel: str,
        message_shape: MessageShape,
        previous_hint: AccumulationHint | None,
        config: ResolvedConfig,
    ) -> int:
        """
        Adaptive wait time based on:
        1. Channel policy (WhatsApp vs Email vs Web)
        2. Message shape (GREETING_ONLY, FRAGMENT, COMPLETE)
        3. Previous turn hint (user typing cadence)
        """
        base_ms = config.accumulation_window_ms

        # Channel adjustment
        if channel == "email":
            base_ms = max(base_ms, 30000)  # Emails need longer
        elif channel == "whatsapp":
            base_ms = min(base_ms, 5000)  # WhatsApp is realtime

        # Shape adjustment
        if message_shape == MessageShape.FRAGMENT:
            base_ms *= 1.5  # Wait longer for fragments

        # Hint adjustment
        if previous_hint and previous_hint.expected_follow_up_ms:
            base_ms = int(base_ms * 0.5 + previous_hint.expected_follow_up_ms * 0.5)

        return base_ms
```

**Also add**: Persist `AccumulationHint` in `session.last_pipeline_result`.

---

### 4G: ACF Event Emission
**Priority**: MEDIUM
**Effort**: 0.5 day
**Files**:
- `ruche/runtime/acf/events.py` (models exist, emission doesn't)
- `ruche/runtime/acf/workflow.py`

**Current**: `FabricEvent` models defined but never emitted.
**Target**: Emit events during turn lifecycle.

**Events to emit**:
- `TurnStarted` - When turn processing begins
- `TurnCompleted` - When turn finishes
- `ToolExecuted` - When a tool runs
- `EnforcementViolation` - When constraint violated
- `SupersedeDecision` - When a turn supersedes another

**Integration**:
```python
# In workflow.run_agent()
await fabric_ctx.emit_event(FabricEvent(
    type=FabricEventType.TURN_STARTED,
    turn_id=logical_turn.id,
    timestamp=datetime.utcnow(),
))
```

---

## Wave 5: Advanced Features

**Dependencies**: Wave 4 complete
**Can run in parallel**: All tasks are independent

### 5A: Webhook System
**Priority**: MEDIUM
**Effort**: 2 days
**Directory**: Create `ruche/api/webhooks/`

**Components**:
- `WebhookSubscription` model
- `WebhookDelivery` model
- `WebhookDispatcher` with Hatchet workflow
- HMAC signature generation

**API**:
- `GET /v1/agents/{aid}/webhooks`
- `POST /v1/agents/{aid}/webhooks`

---

### 5B: gRPC Services
**Priority**: LOW
**Effort**: 3 days
**Directory**: `ruche/api/grpc/`

**Services**:
- `ChatService`
- `MemoryService`
- `ConfigService`

**Files**:
- Create `.proto` definitions
- Implement service handlers

---

### 5C: ChannelGateway
**Priority**: LOW
**Effort**: 2 days
**Directory**: Create `ruche/runtime/channels/`

**Components**:
- `ChannelGateway` class
- `ChannelAdapter` protocol
- At least one adapter (e.g., webchat)

---

### 5D: Row Level Security
**Priority**: MEDIUM
**Effort**: 0.5 day
**File**: Create `ruche/infrastructure/db/migrations/versions/016_enable_rls.py`

**Apply to**: All ConfigStore, MemoryStore, AuditStore tables

```sql
ALTER TABLE rules ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON rules
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

### 5E: PostgreSQL Session Persistence
**Priority**: MEDIUM
**Effort**: 1 day
**Files**:
- Create `ruche/infrastructure/db/migrations/versions/017_session_persistent.py`
- Update `ruche/conversation/stores/redis.py` to use PostgreSQL as fallback

**Rationale**: ADR-001 specifies PostgreSQL for long-term session storage. Current Redis-only approach loses sessions after 7 days.

---

### 5F: Regeneration Loop (P10.8)
**Priority**: LOW
**Effort**: 0.5 day
**File**: `ruche/brains/focal/pipeline.py:1440-1495`

**Add**: Retry generation before falling back to template on constraint violation

---

### 5G: Memory Ingestion (P11.5)
**Priority**: LOW
**Effort**: 1 day
**File**: `ruche/brains/focal/pipeline.py:759-873`

**Add**: Optional long-term memory storage for RAG (consider Zep/Graphiti integration)

---

### 5H: Migration Module Tests
**Priority**: HIGH
**Effort**: 2 days
**Directory**: `tests/unit/brains/focal/migration/`

**Critical Gap**: Migration module has **3,539 lines with 0 unit tests**.

**Files to test**:
- `ruche/brains/focal/migration/diff.py` - Content hashing, transformation computation
- `ruche/brains/focal/migration/planner.py` - Plan generation, deployment
- `ruche/brains/focal/migration/executor.py` - JIT migration execution
- `ruche/brains/focal/migration/composite.py` - Multi-version gap handling
- `ruche/brains/focal/migration/gap_fill.py` - Data retrieval service

**Test Categories**:
1. Unit tests for each class
2. Integration tests for migration flows
3. Edge cases (multi-version gaps, rollback scenarios)

---

### 5I: Test Coverage to 85%
**Priority**: HIGH
**Effort**: 3 days
**Current Coverage**: 59%
**Target Coverage**: 85% line, 80% branch

**Priority Areas** (sorted by impact):
1. `ruche/brains/focal/migration/` - 0% (3,539 lines) → See 5H
2. `ruche/brains/focal/phases/` - Partial coverage, critical path
3. `ruche/runtime/acf/` - ACF workflow tests
4. `ruche/infrastructure/stores/` - Store contract tests

**Strategy**:
1. Implement contract tests for all Store interfaces
2. Add unit tests for all phase classes
3. Add integration tests for workflow paths
4. Configure CI to enforce 85% threshold

**Contract Test Pattern**:
```python
# tests/unit/stores/test_config_store_contract.py
class ConfigStoreContract(ABC):
    @abstractmethod
    def store(self) -> ConfigStore: ...

    async def test_create_and_get_rule(self, store):
        rule = RuleFactory.create()
        await store.save_rule(rule)
        retrieved = await store.get_rule(rule.tenant_id, rule.id)
        assert retrieved == rule

    async def test_tenant_isolation(self, store):
        rule1 = RuleFactory.create(tenant_id=uuid4())
        rule2 = RuleFactory.create(tenant_id=uuid4())
        await store.save_rule(rule1)
        await store.save_rule(rule2)
        # Verify each tenant only sees their own rules
        ...

class TestInMemoryConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self):
        return InMemoryConfigStore()

class TestPostgresConfigStore(ConfigStoreContract):
    @pytest.fixture
    def store(self, postgres_connection):
        return PostgresConfigStore(postgres_connection)
```

---

## Summary

### Wave Parallelization

```
WAVE 1 (Foundation)     ─┬─ 1A (FOCAL consolidation)
                         ├─ 1B (DB tables)
                         ├─ 1C (Logging middleware)
                         ├─ 1D (Observability config)
                         ├─ 1E (Model consolidation)
                         ├─ 1F (OpenAI embedding)
                         ├─ 1G (Cohere embedding)
                         ├─ 1H (Cohere rerank)
                         ├─ 1I (ChannelPresence)
                         ├─ 1J (History trimming)
                         ├─ 1K (Remove duplicate ABCs)     ← NEW
                         ├─ 1L (Clean up empty stubs)      ← NEW
                         └─ 1M (Document client SDK)       ← NEW
                              │
                              ▼
WAVE 2 (Infrastructure) ─┬─ 2A (FabricTurnContext)
                         ├─ 2B (AgentContext)
                         ├─ 2C (AgentTurnContext)
                         ├─ 2D (Brain Protocol)
                         ├─ 2E (Toolbox)
                         ├─ 2F (ChannelPolicy)
                         ├─ 2G (Template)
                         ├─ 2H (TurnContext types)
                         ├─ 2I (Turn Gateway) ★ CRITICAL  ← NEW
                         └─ 2J (Config Hierarchy)          ← NEW
                              │
                              ▼
WAVE 3 (Integration)    ─┬─ 3A (Workflow integration)
                         ├─ 3B (Tool execution P7)
                         ├─ 3C (Scenario contributions P6.4)
                         ├─ 3D (LLM categories P9.4)
                         ├─ 3E (Relationship expansion P5.3)
                         ├─ 3F (Pre-filter P5.1)
                         └─ 3G (Language validation P2.6)
                              │
                              ▼
WAVE 4 (API)            ─┬─ 4A (Chat endpoint)
                         ├─ 4B (Chat streaming)
                         ├─ 4C (Memory endpoints)
                         ├─ 4D (EventRouter)
                         ├─ 4E (IdempotencyCache)
                         ├─ 4F (Adaptive accumulation)     ← NEW
                         └─ 4G (ACF event emission)        ← NEW
                              │
                              ▼
WAVE 5 (Advanced)       ─┬─ 5A (Webhooks)
                         ├─ 5B (gRPC)
                         ├─ 5C (ChannelGateway)
                         ├─ 5D (RLS)
                         ├─ 5E (Session PostgreSQL)
                         ├─ 5F (Regeneration loop)
                         ├─ 5G (Memory ingestion)
                         ├─ 5H (Migration module tests)    ← NEW
                         └─ 5I (Test coverage to 85%)      ← NEW
```

### Effort Estimates

| Wave | Tasks | Total Effort |
|------|-------|--------------|
| Wave 1 | 13 | ~7.5 days |
| Wave 2 | 10 | ~10.5 days |
| Wave 3 | 7 | ~5.75 days |
| Wave 4 | 7 | ~7 days |
| Wave 5 | 9 | ~15 days |
| **Total** | **46** | **~46 days** |

**With parallelization**: If you have 3-4 engineers working in parallel within each wave, total calendar time is approximately **12-18 days**.

---

## Critical Path

The minimum path to a working end-to-end system:

1. **1A** → Delete duplicate engine
2. **1B** → Add DB tables
3. **1K** → Remove duplicate ABCs
4. **2A, 2B, 2C, 2D** → Context layer rewrite
5. **2E** → Toolbox
6. **2I** → Turn Gateway ★ (NEW critical path item)
7. **3A** → Workflow integration
8. **4A** → Chat endpoint

This critical path is approximately **10-12 days** of focused work.

---

## Deep Analysis Compliance Summary

### FOCAL Brain Phase Compliance (74% overall)

| Phase | Compliance | Critical Gaps |
|-------|------------|---------------|
| Phase 1-3 (Context) | 100% | None |
| Phase 4 (Retrieval) | 78% | Lexical features not exposed separately |
| Phase 5 (Rule Selection) | 33% | P5.1 (scope filter), P5.3 (relationships) |
| Phase 6 (Scenario) | 38% | P6.4 (contributions) |
| Phase 7 (Tool Exec) | 29% | P7.2-P7.4 (scheduling), P7.7 (deferral) |
| Phase 8 (Planning) | 70% | P8.3 (contributions from P6) |
| Phase 9 (Generation) | 100% | None |
| Phase 10 (Enforcement) | 90% | P10.6 (relevance/grounding) |
| Phase 11 (Persistence) | 86% | P11.5 (memory ingestion) |

### ACF Topic Compliance

| Topic | Compliance | Priority |
|-------|------------|----------|
| 1. LogicalTurn | 75% | HIGH - Events missing |
| 2. Session Mutex | 85% | MEDIUM - Needs metrics |
| 3. Adaptive Accumulation | 45% | HIGH - Static timing |
| 4. Side-Effect Policy | 60% | HIGH - No Toolbox enforcement |
| 5. Checkpoint Reuse | 40% | MEDIUM - No reuse logic |
| 6. Hatchet Integration | 70% | HIGH - No AgentRuntime |
| 7. Turn Gateway | 15% | **CRITICAL** - No ingress layer |
| 8. Config Hierarchy | 20% | HIGH - Hardcoded configs |
| 9. Agenda & Goals | 0% | LOW - Future feature |
| 10. Channel Capabilities | 25% | HIGH - No adaptation |
| 11. Abuse Detection | 0% | LOW - Security feature |
| 12. Idempotency | 30% | HIGH - No cache |
| 13. ASA Validator | 0% | LOW - Design-time tooling |
