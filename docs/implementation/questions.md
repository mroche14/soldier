# Implementation Questions

> **Status**: AWAITING USER DECISIONS
> **Date**: 2025-12-15
> **Purpose**: Ambiguities that need human decision before implementation planning proceeds

---

## Critical Questions (Blocking)

### Q1: FOCAL Code Duplication Resolution

**Context**: I found two large files that appear to contain the same or similar FOCAL brain logic:
- `ruche/brains/focal/pipeline.py` (2097 lines)
- `ruche/alignment/engine.py` (2078 lines)

**Question**: Are these:
- (A) **The same code** - One should be deleted
- (B) **Different implementations** - Both are needed
- (C) **Evolution** - One is the old version, one is new

**My assumption if no answer**: They are duplicates; keep `brains/focal/pipeline.py`, migrate any unique logic from `alignment/engine.py`, then delete `alignment/engine.py`.


My take : Put them in Brain/focal for now I will review them.

---

### Q2: Folder Structure Refactoring Scope

**Context**: The documented target structure (docs/architecture/folder-structure.md) differs significantly from current code organization.

**Question**: Do you want:
- (A) **Full restructure** - Move all files to match documented structure exactly
- (B) **Incremental alignment** - Fix critical issues only, defer full restructure
- (C) **Update documentation** - Accept current structure as canonical, update docs to match

**Trade-offs**:
- (A) breaks all imports, requires massive refactor, but achieves ideal structure
- (B) leaves technical debt but minimizes disruption
- (C) accepts reality, updates docs, avoids code changes

**My assumption if no answer**: (B) Incremental alignment - fix critical duplications and ACF, defer full restructure.

My take : A. so test should be planned after to make sure everything works

---

### Q3: ConfigStore Location

**Context - DUPLICATION FOUND**: There are TWO nearly-identical ConfigStore interfaces:
- `ruche/infrastructure/stores/config/interface.py` → `ConfigStore` (401 lines)
- `ruche/alignment/stores/agent_config_store.py` → `AgentConfigStore` (408 lines)

Both have identical methods except `AgentConfigStore` has one extra: `get_all_tool_activations()`.

**What ConfigStore manages**:

| Entity | Purpose | FOCAL-Specific? |
|--------|---------|-----------------|
| **Rules** | Behavioral rules for agent responses (with vector search) | ✅ Yes - FOCAL concept |
| **Scenarios** | Conversation flow graphs (nodes, edges, conditions) | ✅ Yes - FOCAL concept |
| **MigrationPlans** | Scenario version migration plans | ✅ Yes - FOCAL concept |
| **Templates** | Response templates for generation | ⚠️ Maybe - other brains could use |
| **Variables** | Agent-level variable definitions | ❌ No - platform level |
| **Agents** | Agent definitions (per tenant) | ❌ No - platform level |
| **ToolActivations** | Which tools are enabled per agent | ❌ No - platform level |
| **GlossaryItems** | Domain terminology | ❌ No - platform level |
| **CustomerDataFields** | Schema for interlocutor data fields | ❌ No - platform level |
| **Intents** | Intent definitions for classification | ⚠️ Maybe - depends on brain |

**Role**: ConfigStore = "brain configuration" - everything an agent needs to know HOW to behave. Tenant+agent scoped. NOT runtime state (SessionStore), NOT memory (MemoryStore).

**Options**:
- (A) `ruche/brains/focal/stores/` - FOCAL-specific (brain owns its config)
- (B) `ruche/infrastructure/stores/config/` - Platform-level (all brains share)
- (C) **Split** - Platform-level base + Brain-specific extension

**Implication of (A) - Brain-specific**:
- Each brain type defines its own config schema
- **Pro**: Clean - LangGraph doesn't need "Rules"/"Scenarios"
- **Con**: Shared concepts (Agents, Tools, Glossary) would be duplicated

**Implication of (B) - Platform-level**:
- One ConfigStore shared by all brains, injected by AgentRuntime
- **Pro**: Single source of truth
- **Con**: Contains FOCAL-specific concepts other brains don't use

**Implication of (C) - Split** (my recommendation):
```
ruche/infrastructure/stores/config/
├── interface.py    # BaseConfigStore (Agents, Tools, Glossary, Variables, Intents)
└── ...

ruche/brains/focal/stores/
├── interface.py    # FocalConfigStore(BaseConfigStore) + Rules, Scenarios, Migrations
└── ...
```
- **Pro**: Clean separation platform vs brain-specific
- **Pro**: Other brains only see what they need
- **Con**: More complex initially

**My assumption if no answer**: (B) - Keep in infrastructure, defer split to later.

My take : OK for C but I think the base should be very limited. Agents and Tools maybe

---

### Q4: `customer_data` → `interlocutor` Renaming

**Context**: V6 standardized terminology to use "interlocutor" (more general than "customer"). Current code uses `customer_data/` folder and `CustomerDataStore` class names.

**Question**: Should the renaming happen now or later?
- (A) **Now** - Rename folder to `interlocutor_data/`, classes to `InterlocutorDataStore`, etc.
- (B) **Later** - Keep current names, add renaming to future backlog
- (C) **Alias only** - Keep files, add type aliases for new names

**Impact of (A)**: ~50+ files need import updates, all references change
**Impact of (B)**: Terminology drift continues
**Impact of (C)**: Minimal code change, gradual migration

**My assumption if no answer**: (C) - Add aliases now, full rename in dedicated refactor sprint.

My take :  Now (A). 

---

### Q5: IMPLEMENTATION_PLAN.md Disposition

**Context**: The root `IMPLEMENTATION_PLAN.md` is:
- Focused on FOCAL Brain (Phases 7-11)
- Uses old naming (`focal/` instead of `ruche/`)
- References deleted doc paths (`docs/focal_360/`, `docs/focal_turn_pipeline/`)
- Phase 6.5 (ACF) is mostly unchecked

**Question**: What should happen to this file?
- (A) **Move to `docs/focal_brain/`** - It's brain-specific, move it there
- (B) **Supersede with new plan** - Create `docs/implementation/plan.md` as new master, archive old
- (C) **Update in place** - Fix paths, update checkboxes, keep at root

**My assumption if no answer**: (B) - Create new comprehensive plan in `docs/implementation/`, move old to `docs/implementation/archive/`.

My take : A then create new implementation plan no ? I think subagents will need them no ?

---

## Architecture Questions

### Q6: ACF Implementation Status

**Context**: Phase 6.5 in IMPLEMENTATION_PLAN shows ACF as mostly unchecked, but `ruche/runtime/acf/` has 8 Python files.

**Question**: Is ACF:
- (A) **Implemented but unchecked** - Just need to verify and update checkboxes
- (B) **Partially implemented** - Core exists, some features missing
- (C) **Stub only** - Files exist but not functional

My take : you should check that

---

## 🔍 AUDIT COMPLETE - Answer is (B) Partially Implemented

**Files audited** (8 files, ~700 lines total):

| File | Status | Summary |
|------|--------|---------|
| `models.py` | ✅ COMPLETE | LogicalTurn, FabricTurnContext, SupersedeAction, etc. - all models implemented |
| `mutex.py` | ✅ COMPLETE | SessionMutex with Redis - acquire, release, extend, is_locked all work |
| `turn_manager.py` | ✅ COMPLETE | Adaptive accumulation - message shape analysis, user cadence, channel defaults |
| `supersede.py` | ✅ COMPLETE | SupersedeCoordinator - can_supersede, enforce_decision, handle_absorb/supersede |
| `commit_point.py` | ✅ COMPLETE | CommitPointTracker - side effect recording, commit point detection |
| `events.py` | ✅ COMPLETE | ACFEvent with all event types defined |
| `workflow.py` | ⚠️ STUB | LogicalTurnWorkflow is a placeholder - raises NotImplementedError |
| `__init__.py` | ✅ COMPLETE | Clean exports of all components |

**What's implemented**:
- ✅ LogicalTurn model with full lifecycle (ACCUMULATING → PROCESSING → COMPLETE/SUPERSEDED)
- ✅ SessionMutex (Redis-backed distributed lock)
- ✅ TurnManager with adaptive accumulation (channel-aware, user cadence)
- ✅ SupersedeCoordinator with 4-state model (SUPERSEDE/ABSORB/QUEUE/FORCE_COMPLETE)
- ✅ CommitPointTracker with side effect policy classification
- ✅ ACFEvent model with all event types

**What's NOT implemented** (workflow.py stub):
- ❌ Hatchet workflow integration (LogicalTurnWorkflow)
- ❌ Workflow steps: acquire_mutex → accumulate → run_pipeline → commit_and_respond → release_mutex
- ❌ Connection to actual pipeline execution

**Verdict**: ACF core components are COMPLETE and functional. Only the Hatchet workflow integration is missing. WP-002 should focus on:
1. Implementing LogicalTurnWorkflow with Hatchet
2. Wiring ACF to the actual pipeline execution
3. Adding integration tests

My take : You should check that
---

### Q7: Hatchet Workflow Integration

**Context**: Documentation describes Hatchet-native concurrency for session mutex and LogicalTurnWorkflow. I see `ruche/jobs/` folder with workflows.

**Question**: Is Hatchet:
- (A) **Fully integrated** - LogicalTurnWorkflow runs via Hatchet
- (B) **Partially integrated** - Background jobs use Hatchet, but not ACF
- (C) **Not yet integrated** - Code is prepared but Hatchet not wired

---

## 🔍 AUDIT COMPLETE - Answer is (B) Partially Integrated

**Hatchet infrastructure**:
| Component | Status |
|-----------|--------|
| `HatchetClient` wrapper | ✅ COMPLETE - Lazy init, health check, graceful degradation |
| `HatchetConfig` | ✅ COMPLETE - Server URL, API key, enabled flag |
| Background workflows | ✅ COMPLETE - 3 workflows implemented |

**Implemented workflows** (in `ruche/jobs/workflows/`):
1. `ExpireStaleFieldsWorkflow` - Profile field expiry (cron: hourly)
2. `DetectOrphanedItemsWorkflow` - Orphan detection
3. `ExtractSchemaRequirementsWorkflow` - Schema extraction from scenarios

**NOT implemented**:
- ❌ `LogicalTurnWorkflow` - The ACF workflow is a stub in `ruche/runtime/acf/workflow.py`
- ❌ ACF-Hatchet wiring for turn processing

**Pattern established**: The existing workflows show the pattern:
```python
@hatchet.workflow(name="...", on_crons=["..."])
class HatchetWorkflow:
    @hatchet.step(retries=3, retry_delay="60s")
    async def step_name(self, context):
        ...
```

**WP-002 should**:
1. Follow the same pattern for LogicalTurnWorkflow
2. Wire ACF mutex acquisition as first step
3. Add brain.think() execution step
4. Add commit/respond step with mutex release

My take : You should check that

---

### Q8: Provider Backward Compatibility

**Context**: I found providers in two locations:
- `ruche/providers/` (18 files) - Appears to be for backward compatibility
- `ruche/infrastructure/providers/` (16 files) - Actual implementations

**Question**: Can we:
- (A) **Delete `ruche/providers/`** - No external code depends on it
- (B) **Keep as re-exports** - `ruche/providers/` just re-exports from `infrastructure/`
- (C) **Merge carefully** - Some unique code exists in root providers/

**My assumption if no answer**: (B) - Keep `ruche/providers/__init__.py` as re-exports for any external consumers.

My take : You should check that but I would say A
---

## Process Questions

### Q9: Subagent Work Split Strategy

**Context**: You mentioned subagents should have a protocol and work should be split into independent shares.

**Question**: Preferred parallelization strategy:
- (A) **By layer** - One agent per layer (API, Brain, Infrastructure, Runtime)
- (B) **By feature** - One agent per work package (ACF, Enforcement, Refactoring)
- (C) **By phase** - One agent per IMPLEMENTATION_PLAN phase
- (D) **Hybrid** - Layer for structure, feature for implementation

**My assumption if no answer**: (B) - Feature-based allows true independence.

My take : The best as soon as the final work is checck and working with tests

---

### Q10: Testing During Refactor

**Context**: Folder restructuring will break imports. Tests need to pass throughout.

**Question**: Testing strategy during refactor:
- (A) **All tests pass after each move** - Slow but safe
- (B) **Batch moves, then fix tests** - Faster but riskier
- (C) **Skip tests during structure phase** - Fix all at end

**My assumption if no answer**: (A) - Tests must pass after each atomic change.
My take : B
---

### Q11: Git Strategy

**Question**: How should structural changes be committed?
- (A) **One PR per work package** - Easier to review
- (B) **One massive PR** - Avoids intermediate broken states
- (C) **One commit per file move** - Maximum granularity

**My assumption if no answer**: (A) - One PR per work package.

My take : we will push once everything is ready

---

## Nice-to-Have Clarifications

### Q12: gRPC Priority

**Context**: IMPLEMENTATION_PLAN Phase 18 shows gRPC as optional. Current code has `ruche/api/grpc/` with proto definitions.

**Question**: Is gRPC:
- (A) **Priority** - Needed for production
- (B) **Deferred** - Nice to have, not blocking
- (C) **Removed** - Not needed, can delete

My take : B
---

### Q13: MCP Server Priority

**Context**: `ruche/api/mcp/` has MCP (Model Context Protocol) server code.

**Question**: Is MCP:
- (A) **Priority** - Needed for LLM tool discovery
- (B) **Deferred** - Future feature
- (C) **Removed** - Not needed

My take : B
---

### Q14: MongoDB/Neo4j/DynamoDB Stores

**Context**: Multiple alternative store implementations exist (MongoDB for memory, Neo4j for memory, DynamoDB for sessions).

**Question**: Should these be:
- (A) **Kept** - Future flexibility
- (B) **Removed** - PostgreSQL + Redis is the decision per ADR-003
- (C) **Deprecated** - Keep code but mark as unsupported

My take : B for now
---

## Summary

**Blocking questions** (need answer before I can create detailed plan):
- Q1: FOCAL duplication
- Q2: Refactoring scope
- Q5: IMPLEMENTATION_PLAN disposition

**Important questions** (affect plan quality):
- Q3: ConfigStore location
- Q4: Interlocutor renaming
- Q9: Subagent strategy

**Can proceed with assumptions** (nice to clarify):
- Q6-Q8, Q10-Q14

---

Please respond with your decisions. Format:
```
Q1: A/B/C
Q2: A/B/C
...
```

Or provide additional context if the options don't fit.
