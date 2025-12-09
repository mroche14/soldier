# FOCAL 360 Wave Execution Guide

> **Purpose**: Step-by-step guide for launching subagents to implement FOCAL 360 platform features.
> **Strategy**: Wave-based execution with controlled parallelism (max 2 agents per wave).

---

## Execution Order Overview

Based on the gap analysis, features are ordered by dependencies:

```
WAVE 1: Foundation (Quick Wins)          ← Wire existing infrastructure
    ↓
WAVE 2: Ingress & Safety                 ← Pre-pipeline layer (parallel)
    ↓
WAVE 3: Config & Channels                ← Pipeline extensions (parallel)
    ↓
WAVE 4: Side-Effects & Tools             ← P7 enhancements (sequential)
    ↓
WAVE 5: Lifecycle & Proactive            ← New systems (parallel)
    ↓
WAVE 6: Meta-Agents (Future)             ← ASA, Reporter (sequential)
```

---

## Before Starting Any Wave

### CRITICAL: Checkbox Rule for All Agents

Every agent MUST:
1. **Check boxes `[x]` immediately after completing each item** - not at the end
2. Edit the checklist file directly using the Edit tool
3. Add implementation notes under checked items
4. Mark blocked items with `⏸️ BLOCKED:` and continue

**DO NOT** just write a summary at the end. The checklist file itself must be updated.

### CRITICAL: Codebase Exploration Rule

**Before implementing ANYTHING**, every agent MUST:

1. **Search the existing codebase** to see if similar functionality exists
2. **Modify existing code** instead of creating parallel implementations
3. **Remove obsolete code** when replacing/renaming
4. **Ground themselves in the gap analysis** - Read `docs/focal_360/gap_analysis.md`

```bash
# Example exploration before implementing
mgrep "feature you're implementing"
grep -r "SimilarClassName" soldier/
```

**The goal is NO duplicate/parallel implementations.** If something similar exists, extend it.

### CRITICAL: Consult Gap Analysis

Every agent MUST read `docs/focal_360/gap_analysis.md` before implementing anything.

The gap analysis identifies:
- What already exists (don't recreate)
- Partial implementations to extend
- Vocabulary mappings (use correct terms)

### Coordinator Checklist

Before launching each wave:

- [ ] Previous wave is 100% complete
- [ ] All blocked items from previous wave are resolved
- [ ] Integration tests pass for completed features
- [ ] No merge conflicts in codebase
- [ ] All previous feature checklists are updated
- [ ] **Code quality checks pass** (ruff, mypy)

### Launch Command Pattern

```
/task Plan subagent_type=Plan prompt="[WAVE PROMPT BELOW]"
```

Or for implementation:

```
/task subagent_type=general-purpose prompt="[WAVE PROMPT BELOW]"
```

---

## WAVE 1: Foundation (Parallel - 2 Agents)

These wire existing infrastructure that the gap analysis identified as "partial":

### Agent 1A: Integrate Idempotency

**Prerequisites**: None (this is the first wave)

**Prompt**:

```markdown
# Task: Integrate Idempotency into Chat Endpoint

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Idempotency" section
5. `docs/focal_360/implementation/idempotency-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- `IdempotencyCache` exists at `soldier/api/middleware/idempotency.py`
- Chat route has TODOs at lines 189-193 and 232-234
- Infrastructure is ready, just NOT CONNECTED

## Your Assignment
Execute ALL items related to idempotency integration.

## Key Deliverables
1. Connect `IdempotencyCache` to the chat endpoint
2. Implement the TODO at lines 189-193 (check cache before processing)
3. Implement the TODO at lines 232-234 (cache response after processing)
4. Add Redis backend option for production (extend existing cache)
5. Add tests for idempotent chat requests
6. Update `config/default.toml` with idempotency settings

## Important Notes
- Use existing IdempotencyCache - do NOT create a new class
- Key format: `idempotency:{tenant_id}:{idempotency_key}`
- TTL should be configurable (default 24 hours)
- Follow async patterns for all cache operations

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/api/middleware/test_idempotency.py -v
uv run pytest tests/unit/api/routes/test_chat.py -v
uv run pytest --cov=soldier/api --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Completion**:
- [ ] IdempotencyCache connected to chat endpoint
- [ ] Duplicate requests return cached response
- [ ] Redis backend option available
- [ ] Tests pass with 85%+ coverage
- [ ] No merge conflicts

---

### Agent 1B: Wire AgentConfig into Pipeline

**Prerequisites**: None (can run parallel with 1A)

**Prompt**:

```markdown
# Task: Integrate AgentConfig into Pipeline Config Resolution

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Config Hierarchy" section
5. `docs/focal_360/implementation/agent-config-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- `AgentConfig` model exists at `soldier/config/models/agent.py`
- Config loading is at `soldier/config/loader.py`
- P1.6 loads static config but doesn't merge agent overrides
- Model is defined but NOT integrated into pipeline

## Your Assignment
Execute ALL items related to AgentConfig integration.

## Key Deliverables
1. Extend P1.6 to load agent-specific config from ConfigStore
2. Merge agent overrides onto pipeline defaults
3. Add `get_agent_config(tenant_id, agent_id)` method to ConfigStore
4. Update AlignmentEngine to use merged config
5. Add tests for config merging
6. Document the config resolution order

## Important Notes
- Use existing AgentConfig model - do NOT create duplicates
- Merge order: tenant defaults → agent overrides
- All IDs must be UUID, not str
- Follow async patterns for all loaders

## Files to Modify
- `soldier/config/loader.py` - Add merge logic
- `soldier/alignment/engine.py` - Use merged config in P1.6
- `soldier/alignment/stores/agent_config_store.py` - Add method if needed

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/config/ -v
uv run pytest tests/unit/alignment/test_engine.py -v
uv run pytest --cov=soldier/config --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 1**:
- [ ] Idempotency works for chat requests (test with same key)
- [ ] Agent-specific config overrides pipeline defaults
- [ ] Both agents' tests pass
- [ ] No conflicts between changes

---

## WAVE 2: Ingress & Safety (Parallel - 2 Agents)

### Agent 2A: Implement Debouncing

**Prerequisites**: Wave 1 complete

**Prompt**:

```markdown
# Task: Implement Message Debouncing

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Ingress Control" section
5. `docs/focal_360/README.md` - Section 3 (Ingress Control concept)
6. `docs/focal_360/implementation/debouncing-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- `burst_size` config exists but is UNUSED
- Rate limiting exists at `soldier/api/middleware/rate_limit.py`
- No debouncing/coalescing logic exists

## Your Assignment
Execute ALL items related to message debouncing.

## Key Deliverables
1. Create `IngressConfig` model with debounce settings
2. Implement `BurstCoalescer` class (or extend RateLimiter)
3. Add debounce window detection by (tenant_id, customer_key, channel)
4. Implement message coalescing within window
5. Add `[api.ingress]` config section
6. Add comprehensive tests
7. Document the debouncing behavior

## Important Notes
- Debounce window: configurable (default 2000ms)
- Coalescing: concatenate messages with newline separator
- Key: (tenant_id, agent_id, customer_id, channel)
- Do NOT duplicate existing rate limiting - extend or work alongside it

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/api/middleware/test_ingress.py -v
uv run pytest --cov=soldier/api/middleware --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 2B: Abuse Detection Foundation

**Prerequisites**: Wave 1 complete (can run parallel with 2A)

**Prompt**:

```markdown
# Task: Implement Abuse Detection Foundation

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Ingress Control" section
5. `docs/focal_360/README.md` - Section 5 (Abuse firewall)
6. `docs/focal_360/implementation/abuse-detection-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- Rate limiting exists
- `OutcomeCategory` includes `SAFETY_REFUSAL`
- No abuse detection or flagging exists

## Your Assignment
Execute ALL items related to abuse detection.

## Key Deliverables
1. Create `AbuseDetector` class
2. Track abuse signals per (tenant_id, customer_id):
   - Repeated rate limit hits
   - Repeated SAFETY_REFUSAL outcomes
   - Rapid-fire message patterns
3. Add `ABUSE_SUSPECTED` to `OutcomeCategory` enum
4. Log abuse flags to AuditStore via TurnRecord
5. Add configurable thresholds
6. Add tests for abuse detection

## Important Notes
- Integration points:
  - Called from rate limit middleware (pre-P1)
  - Consults TurnRecord history (post-P10)
  - Writes to AuditStore
- Use existing OutcomeCategory enum - extend it, don't create new

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/api/middleware/test_abuse.py -v
uv run pytest --cov=soldier/api/middleware --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 2**:
- [ ] Rapid messages within window are coalesced
- [ ] Abuse patterns are detected and flagged
- [ ] ABUSE_SUSPECTED added to OutcomeCategory
- [ ] Both integrate with existing rate limiting
- [ ] No conflicts between changes

---

## WAVE 3: Config & Channels (Parallel - 2 Agents)

### Agent 3A: Channel Capabilities

**Prerequisites**: Wave 2 complete

**Prompt**:

```markdown
# Task: Implement Channel Capabilities Model

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Channel System" section
5. `docs/focal_360/README.md` - Section 7 (Channels)
6. `docs/focal_360/implementation/channel-capabilities-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- `Channel` enum exists (6 channels)
- `ChannelIdentity` exists for multi-channel customer linking
- Channel formatters exist (WhatsApp, Email, SMS, Default)
- MISSING: `ChannelCapability` metadata model

## Your Assignment
Execute ALL items related to channel capabilities.

## Key Deliverables
1. Create `ChannelCapability` model:
   - `max_message_length: int`
   - `supports_rich_media: bool`
   - `supports_delivery_receipts: bool`
   - `supports_read_receipts: bool`
   - `fallback_channel: Channel | None`
2. Create `ChannelProfile` registry (static config)
3. Load in P1.6 and attach to TurnContext
4. Update formatters to use capabilities
5. Add `[channels]` config section
6. Add tests

## Important Notes
- Use existing Channel enum - do NOT create duplicates
- Extend existing formatters rather than replacing them
- Follow the pattern in `soldier/alignment/generation/formatters/`

## Files to Create/Modify
- `soldier/alignment/models/channel.py` (new)
- `soldier/alignment/context/` (extend TurnContext)
- `soldier/alignment/generation/formatters/` (use capabilities)
- `config/default.toml` (add section)

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/alignment/models/test_channel.py -v
uv run pytest tests/unit/alignment/generation/formatters/ -v
uv run pytest --cov=soldier/alignment/models --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 3B: Scenario Config Overrides

**Prerequisites**: Wave 1 (AgentConfig integration) complete

**Prompt**:

```markdown
# Task: Implement Scenario-Level Config Overrides

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Config Hierarchy" section
5. `docs/focal_360/implementation/scenario-config-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- AgentConfig should now be integrated (Wave 1)
- No ScenarioConfig model exists
- Config hierarchy should be: tenant → agent → scenario → step

## Your Assignment
Execute ALL items related to scenario config overrides.

## Key Deliverables
1. Create `ScenarioConfig` model (similar to AgentConfig)
2. Add `config_overrides` field to Scenario model
3. Extend config resolution to include scenario overrides
4. Update engine to use scenario config when in scenario
5. Add tests for the full hierarchy
6. Document config precedence

## Important Notes
- Config Resolution Order (final):
  1. Pydantic defaults
  2. `default.toml`
  3. `{env}.toml`
  4. Environment variables
  5. Agent overrides (from Wave 1)
  6. Scenario overrides (this task)

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/config/ -v
uv run pytest tests/unit/alignment/test_engine.py -v
uv run pytest --cov=soldier/config --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 3**:
- [ ] ChannelCapability available in TurnContext
- [ ] Formatters respect channel capabilities
- [ ] Scenario config overrides work
- [ ] Full hierarchy: tenant → agent → scenario → step

---

## WAVE 4: Side-Effects & Tools (Sequential - 2 Agents)

### Agent 4A: Side-Effect Registry

**Prerequisites**: Wave 3 complete

**Prompt**:

```markdown
# Task: Implement Tool Side-Effect Registry

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Side-Effect Registry" section
5. `docs/focal_360/README.md` - Section 4 (Side-Effect Registry)
6. `docs/focal_360/implementation/side-effect-registry-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- Tool scheduling (BEFORE/DURING/AFTER) exists
- `ScenarioStep.is_checkpoint` marks irreversible steps
- MISSING: ToolSideEffectPolicy, central registry

## Your Assignment
Execute ALL items related to the side-effect registry.

## Key Deliverables
1. Create `ToolSideEffectPolicy` enum:
   - `REVERSIBLE` - Safe to cancel/replay
   - `COMPENSATABLE` - Can undo via compensation tool
   - `IRREVERSIBLE` - Commit point reached
2. Create `ToolEffectRegistry` class
3. Add `side_effect_policy` field to ToolBinding
4. P7 consults registry before execution
5. Registry used by Ingress Control for cancel decisions
6. Add configuration for default policies
7. Add tests

## Important Notes
- Integration points:
  - P7 (tool execution) - Check before execute
  - Ingress Control (Wave 2) - Cancel decision
  - TurnRecord - Log commit points
- Use existing ToolBinding model - extend it, don't create new

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/alignment/execution/test_side_effect.py -v
uv run pytest --cov=soldier/alignment/execution --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 4B: Turn Cancellation

**Prerequisites**: Agent 4A (Side-Effect Registry) complete

**Prompt**:

```markdown
# Task: Implement Turn Cancellation

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Turn Cancellation" section
5. `docs/focal_360/README.md` - Section 3.4 (Irreversible checkpoints)
6. `docs/focal_360/implementation/turn-cancellation-checklist.md` - Your checklist (if exists)

## Prerequisites Completed (Wave 4A)
- Side-Effect Registry exists
- ToolSideEffectPolicy enum defined
- ToolBinding has side_effect_policy field

## Your Assignment
Execute ALL items related to turn cancellation.

## Key Deliverables
1. Add cancellation token to `AlignmentEngine.process_turn()`
2. Check token at phase boundaries
3. Consult SideEffectRegistry for safe cancel points
4. Implement cancel logic before irreversible tools
5. Integrate with BurstCoalescer (cancel in-flight if new message)
6. Add `TurnCancelled` outcome
7. Log cancellations to AuditStore
8. Add tests

## Important Notes
- Key design decisions:
  - Cancel is safe only before IRREVERSIBLE tools
  - COMPENSATABLE tools trigger compensation on cancel
  - Cancellation logged with reason
- Coordinate with Debouncing (Wave 2) for integration

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/alignment/test_cancellation.py -v
uv run pytest --cov=soldier/alignment --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 4**:
- [ ] Tools have side-effect policies
- [ ] Registry consulted before tool execution
- [ ] Turns can be cancelled before commit points
- [ ] Cancellation integrates with debouncing
- [ ] TurnCancelled outcome logged to AuditStore

---

## WAVE 5: Lifecycle & Proactive (Parallel - 2 Agents)

### Agent 5A: Agenda & Goals

**Prerequisites**: Wave 4 complete

**Prompt**:

```markdown
# Task: Implement Agenda and Goal System

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Agenda/Goals" section
5. `docs/focal_360/README.md` - Section 9 (Agenda, goals)
6. `docs/focal_360/implementation/agenda-goals-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- Hatchet job framework exists
- Session model tracks scenario state
- OutcomeCategory exists
- MISSING: AgendaTask, Goal models

## Your Assignment
Execute ALL items related to agenda and goals.

## Key Deliverables
1. Create `AgendaTask` model:
   - `task_type`, `scheduled_at`, `customer_id`, `context`
2. Create `Goal` model:
   - `expected_response`, `completion_criteria`, `timeout`
3. Create `AgendaStore` interface + InMemory impl
4. Attach Goal to ResponsePlan (P8)
5. Persist to SessionState (P11)
6. Create Hatchet workflow for follow-up checks
7. Add tests

## Important Notes
- Files to create:
  - `soldier/agenda/models.py`
  - `soldier/agenda/store.py`
  - `soldier/agenda/stores/inmemory.py`
  - `soldier/jobs/workflows/follow_up.py`
- Use existing Hatchet patterns from `soldier/jobs/`

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/agenda/ -v
uv run pytest --cov=soldier/agenda --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 5B: Hot Reload Config Watcher

**Prerequisites**: Wave 3 (Config hierarchy) complete

**Prompt**:

```markdown
# Task: Implement Hot Reload Config Watcher

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Config Hierarchy" section
5. `docs/architecture/kernel-agent-integration.md` - Hot reload design
6. `docs/focal_360/implementation/hot-reload-checklist.md` - Your checklist (if exists)

## Context from Gap Analysis
- Hot reload architecture is DOCUMENTED but not implemented
- Redis pub/sub channel: `cfg-updated`
- TTL-based cache invalidation mentioned

## Your Assignment
Execute ALL items related to config hot reload.

## Key Deliverables
1. Create `ConfigWatcher` service
2. Subscribe to Redis pub/sub `cfg-updated` channel
3. On event: reload agent/scenario config from ConfigStore
4. Invalidate cached configs with TTL
5. Graceful degradation if Redis unavailable
6. Add health check for watcher
7. Add tests

## Important Notes
- Integration points:
  - Startup: Start watcher as background task
  - Publisher: Emit `cfg-updated` after publish
  - Engine: Use cached config with invalidation
- Follow existing Redis patterns from codebase

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/config/test_watcher.py -v
uv run pytest tests/integration/config/test_hot_reload.py -v
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 5**:
- [ ] Agenda tasks can be created and scheduled
- [ ] Goals attached to responses and tracked
- [ ] Follow-up workflow triggers on timeout
- [ ] Config hot reload works via Redis pub/sub
- [ ] Graceful degradation when Redis unavailable

---

## WAVE 6: Meta-Agents (Sequential - Future)

> **Note**: This wave requires a stable foundation. Only proceed after Waves 1-5 are complete and battle-tested.

### Agent 6A: Reporter Agent

**Prerequisites**: All previous waves complete

**Prompt**:

```markdown
# Task: Implement Reporter Agent

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Meta-Agents" section
5. `docs/focal_360/README.md` - Section 13 (Reporter agent)
6. `docs/focal_360/implementation/reporter-agent-checklist.md` - Your checklist (if exists)

## Prerequisites Completed
- All Waves 1-5 complete
- AuditStore with rich turn data
- Abuse detection flags in place

## Your Assignment
Execute ALL items related to the Reporter agent.

## Key Deliverables
1. Create `ReporterAgent` persona
2. Read-only access to AuditStore
3. Natural language summarization tools
4. Intent distribution, outcome rates, abuse flags
5. Trend analysis capabilities
6. Add tests

## Important Notes
- Reporter is a READ-ONLY persona over AuditStore
- Use existing observability infrastructure
- Output format should be tenant-friendly

## Testing Commands
```bash
uv run pytest tests/unit/agents/test_reporter.py -v
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 6B: ASA Meta-Agent

**Prerequisites**: Reporter Agent (6A) complete

**Prompt**:

```markdown
# Task: Implement Agent Setter Agent (ASA)

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_360/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_360/gap_analysis.md` - See "Meta-Agents" section
5. `docs/focal_360/README.md` - Section 12 (ASA)
6. `docs/focal_360/implementation/asa-checklist.md` - Your checklist (if exists)

## Prerequisites Completed
- All previous waves complete
- Stable admin API surface
- Simulation sandbox (if implemented)

## Your Assignment
Execute ALL items related to the ASA meta-agent.

## Key Deliverables
1. Create `ASAAgent` persona
2. Access to admin APIs as tools
3. Edge-case generation capabilities
4. Side-effect policy recommendations
5. Stress-testing workflows
6. Add tests

## Important Notes
- ASA scope (from README.md):
  - Build/update rules, scenarios, glossary, customer data schema
  - Recommend safe side-effect policies
  - Stress-test agent behavior with edge cases
  - Propose migration-safe edits

## Testing Commands
```bash
uv run pytest tests/unit/agents/test_asa.py -v
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 6**:
- [ ] Reporter Agent can summarize tenant activity
- [ ] ASA can propose rule/scenario updates
- [ ] Edge-case generation works
- [ ] Both agents have comprehensive tests

---

## Post-Wave Quality Checks (MANDATORY)

**Every wave must pass these checks before proceeding to next wave:**

### Code Quality (Run After Each Wave)

```bash
# 1. Ruff linting
uv run ruff check soldier/
uv run ruff check --fix soldier/  # Auto-fix issues

# 2. Ruff formatting
uv run ruff format soldier/

# 3. Mypy type checking
uv run mypy soldier/ --ignore-missing-imports

# 4. Tests
uv run pytest tests/unit/ -v --tb=short
```

### Quick All-in-One Check

```bash
echo "=== WAVE QUALITY CHECK ===" && \
uv run ruff check soldier/ && \
uv run ruff format --check soldier/ && \
uv run mypy soldier/ --ignore-missing-imports && \
uv run pytest tests/unit/ -v --tb=short && \
echo "=== ALL CHECKS PASSED ==="
```

**DO NOT proceed to next wave if quality checks fail.**

---

## Post-Implementation Verification

After all waves complete:

### Integration Test

```bash
# Run full integration tests
uv run pytest tests/integration/ -v

# Run E2E test if available
uv run pytest tests/e2e/ -v
```

### Coverage Check

```bash
uv run pytest --cov=soldier --cov-report=html
# Open htmlcov/index.html to verify 85%+ coverage
```

### Final Quality Gate

```bash
# Full quality check on entire soldier module
uv run ruff check soldier/ && \
uv run ruff format --check soldier/ && \
uv run mypy soldier/ --ignore-missing-imports && \
uv run pytest tests/unit/ --cov=soldier --cov-fail-under=85
```

### Checklist Audit

- [ ] All feature checklists have no unmarked `- [ ]` items
- [ ] All blocked items documented with reasons
- [ ] All implementation notes added to checklists
- [ ] Gap analysis updated with completion status

### Documentation Update

- [ ] Update `docs/doc_skeleton.md` if new docs created
- [ ] Update `CLAUDE.md` if new patterns established
- [ ] Update `IMPLEMENTATION_PLAN.md` if it exists
- [ ] Update `docs/focal_360/gap_analysis.md` with completion notes

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Import error after new model | Run `uv sync`, check all imports updated |
| Test discovery fails | Ensure `__init__.py` exists in test directories |
| Coverage below threshold | Add edge case tests, check untested branches |
| Merge conflict | Coordinate with other agent, resolve manually |
| Model validation error | Check field types match spec |
| Redis connection fails | Check Redis is running, use graceful fallback |
| Config not reloading | Check pub/sub channel name, verify TTL |

### Emergency Rollback

If a wave causes critical issues:

```bash
# Check what changed
git diff HEAD~N  # N = number of commits in wave

# Revert if needed
git revert HEAD~N..HEAD
```

---

## Summary

| Wave | Features | Agents | Parallel? |
|------|----------|--------|-----------|
| 1 | Idempotency, AgentConfig | 2 | Yes |
| 2 | Debouncing, Abuse Detection | 2 | Yes |
| 3 | ChannelCapability, ScenarioConfig | 2 | Yes |
| 4 | Side-Effect Registry, Turn Cancellation | 2 | Sequential |
| 5 | Agenda/Goals, Hot Reload | 2 | Yes |
| 6 | Reporter, ASA | 2 | Sequential |

**Total minimum agents**: 6 (if single-agent waves)
**Total with parallelism**: 12 agent invocations

---

## Related Documents

- [FOCAL 360 Overview](README.md) - Full platform proposal
- [Gap Analysis](gap_analysis.md) - Existing implementations mapping
- [Subagent Protocol](SUBAGENT_PROTOCOL.md) - Execution rules for agents
- [Focal Turn Pipeline](../focal_turn_pipeline/README.md) - The 11-phase pipeline this platform wraps
