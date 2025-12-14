# Wave Execution Guide

> **Purpose**: Step-by-step guide for launching subagents to implement the focal turn pipeline.
> **Strategy**: Wave-based execution with controlled parallelism (max 2 agents per wave).

---

## Execution Order Overview

```
WAVE 1: P1 (Foundation)           ← Must complete first
    ↓
WAVE 2: P2 ‖ P4 (Parallel)        ← 2 agents simultaneously
    ↓
WAVE 3: P3 ‖ P5 (Parallel)        ← 2 agents simultaneously
    ↓
WAVE 4: P6 (Scenario)             ← Sequential
    ↓
WAVE 5: P7 → P8 (Sequential)      ← Can be 1 or 2 agents
    ↓
WAVE 6: P9 → P10 → P11 (Final)    ← Can be 1 or 3 agents
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
4. **Ground themselves in the specs** - Read `docs/focal_turn_pipeline/spec/` folder

```bash
# Example exploration before implementing
mgrep "feature you're implementing"
grep -r "SimilarClassName" focal/
```

**The goal is NO duplicate/parallel implementations.** If something similar exists, extend it.

### Coordinator Checklist

Before launching each wave:

- [ ] Previous wave is 100% complete
- [ ] All blocked items from previous wave are resolved
- [ ] Integration tests pass for completed phases
- [ ] No merge conflicts in codebase
- [ ] All previous phase checklists are updated
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

## WAVE 1: Foundation (Sequential)

### Agent: P1 - Identification & Context Loading

**Prerequisites**: None (this is the first wave)

**Prompt**:

```markdown
# Task: Implement Phase 1 - Identification & Context Loading

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections (CRITICAL)
5. `docs/focal_turn_pipeline/implementation/phase-01-identification-checklist.md` - Your checklist

## Your Assignment
Execute ALL items in the Phase 1 checklist.

## Key Deliverables
1. Rename Profile models → InterlocutorData models (see CHECKLIST_CORRECTIONS.md)
2. Add `scope` and `persist` fields to InterlocutorDataField
3. Add `history` field to VariableEntry
4. Create TurnContext, GlossaryItem models
5. Create InterlocutorDataLoader, StaticConfigLoader
6. Update FocalCognitivePipeline to build TurnContext
7. Add ConfigStore methods for glossary and schema
8. Unit tests with 85%+ coverage

## Important Notes
- This phase RENAMES existing models, does NOT create duplicates
- Use `name` field (not `key`) per existing ProfileFieldDefinition convention
- All IDs must be UUID, not str
- Follow async patterns for all loaders

## CRITICAL: Checkbox Updates
As you complete EACH item:
1. Immediately edit the checklist file
2. Change `- [ ]` to `- [x]` for that item
3. Add brief implementation notes under the item
4. Do NOT wait until the end - update as you go

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/models/ -v
uv run pytest tests/unit/mechanics/focal/loaders/ -v
uv run pytest --cov=focal/mechanics/focal --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Expected Duration**: 4-6 hours

**Verification After Completion**:
- [ ] TurnContext model exists and is exported
- [ ] InterlocutorDataField has `scope` and `persist` fields
- [ ] VariableEntry has `history` field
- [ ] All renames complete (grep for old names returns nothing)
- [ ] Tests pass with 85%+ coverage
- [ ] No merge conflicts

---

## WAVE 2: Parallel Track A (2 Agents)

### Agent 2A: P2 - Situational Sensor

**Prerequisites**: Wave 1 (P1) complete

**Prompt**:

```markdown
# Task: Implement Phase 2 - Situational Sensor

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-02-situational-sensor-checklist.md` - Your checklist

## Prerequisites Completed (Phase 1)
- TurnContext model exists at `focal/mechanics/focal/models/turn_context.py`
- InterlocutorDataField (renamed from ProfileFieldDefinition) has `scope`, `persist`
- VariableEntry (renamed from ProfileField) has `history`
- GlossaryItem model exists at `focal/mechanics/focal/models/glossary.py`
- ConfigStore has glossary and schema methods

## Your Assignment
Execute ALL items in the Phase 2 checklist.

## Key Deliverables
1. Create SituationalSnapshot, CandidateVariableInfo models
2. Create InterlocutorSchemaMask model and builder
3. Create Jinja2 TemplateLoader utility
4. Create situational_sensor.jinja2 template
5. Implement SituationalSensor class with all P2.x substeps
6. Add [pipeline.situational_sensor] config section
7. Integrate with FocalCognitivePipeline (replace ContextExtractor)
8. Unit tests with 85%+ coverage

## Important Notes
- InterlocutorDataField, VariableEntry, InterlocutorDataStore already exist (renamed in P1)
- Do NOT create duplicate models - use the renamed Profile models
- Template path: `focal/mechanics/focal/context/prompts/situational_sensor.jinja2`
- Config model: SituationalSensorConfig in `focal/config/models/pipeline.py`

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/context/ -v
uv run pytest tests/unit/mechanics/focal/models/test_situational_snapshot.py -v
uv run pytest --cov=focal/mechanics/focal/context --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 2B: P4 - Retrieval & Selection

**Prerequisites**: Wave 1 (P1) complete

**Prompt**:

```markdown
# Task: Implement Phase 4 - Retrieval & Selection

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-04-retrieval-selection-checklist.md` - Your checklist

## Prerequisites Completed (Phase 1)
- TurnContext model exists
- ConfigStore interface defined
- Selection strategies exist (fixed_k, elbow, adaptive_k, entropy, clustering)

## Your Assignment
Execute ALL items in the Phase 4 checklist.

## Key Deliverables
1. Implement hybrid retrieval (vector + BM25/lexical)
2. Parallelize rule/scenario/memory retrieval with asyncio.gather
3. Add reranking configuration per object type
4. Implement intent retrieval (if in scope, otherwise mark blocked)
5. Update config for hybrid search parameters
6. Unit tests with 85%+ coverage

## Important Notes
- Intent catalog (P4.2-P4.3) may be out of scope per CHECKLIST_CORRECTIONS - mark as blocked if so
- Focus on parallelization using asyncio.gather
- BM25 implementation can use rank-bm25 library: `uv add rank-bm25`

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/retrieval/ -v
uv run pytest --cov=focal/mechanics/focal/retrieval --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 2**:
- [ ] SituationalSnapshot model exists with candidate_variables
- [ ] InterlocutorSchemaMask builds correctly
- [ ] TemplateLoader works with Jinja2 templates
- [ ] Retrieval is parallelized (asyncio.gather)
- [ ] Both agents' tests pass
- [ ] No conflicts between P2 and P4 changes

---

## WAVE 3: Parallel Track B (2 Agents)

### Agent 3A: P3 - Customer Data Update

**Prerequisites**: Wave 2 (P2) complete

**Prompt**:

```markdown
# Task: Implement Phase 3 - Customer Data Update

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-03-customer-data-update-checklist.md` - Your checklist

## Prerequisites Completed
- SituationalSnapshot model exists with candidate_variables (P2)
- InterlocutorDataField has scope and persist fields (P1)
- VariableEntry has history field (P1)
- InterlocutorDataStore (renamed CustomerProfile) exists (P1)

## Your Assignment
Execute ALL items in the Phase 3 checklist.

## Key Deliverables
1. Implement candidate variable → InterlocutorDataStore matching
2. Implement type coercion and validation
3. Implement in-memory update with history tracking
4. Mark variables for persistence based on persist flag
5. Implement SESSION scope cleanup at session end
6. Unit tests with 85%+ coverage

## Important Notes
- Use existing validation in `focal/domain/interlocutor/validation.py` if available
- candidate_variables comes from SituationalSnapshot (P2 output)
- Only variables with persist=True should be saved to database
- History should track: {value, timestamp, source, confidence}

## Testing Commands
```bash
uv run pytest tests/unit/domain/interlocutor/ -v
uv run pytest --cov=focal/domain/interlocutor --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 3B: P5 - Rule Selection & Filtering

**Prerequisites**: Wave 2 (P4) complete

**Prompt**:

```markdown
# Task: Implement Phase 5 - Rule Selection & Filtering

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-05-rule-selection-checklist.md` - Your checklist

## Prerequisites Completed
- Rule retrieval parallelized (P4)
- Selection strategies exist (P4)
- RuleFilter exists with LLM filtering

## Your Assignment
Execute ALL items in the Phase 5 checklist.

## Key Deliverables
1. Add rule relationship expansion (depends_on, entails, excludes)
2. Update Rule model with relationship fields if needed
3. Create scenario_filter.jinja2 template (per CHECKLIST_CORRECTIONS)
4. Implement ternary LLM filter output (applies/not/maybe)
5. Unit tests with 85%+ coverage

## Important Notes
- scenario_filter.jinja2 is noted as missing in CHECKLIST_CORRECTIONS
- Rule relationships may require Rule model updates
- Coordinate with P6 (Scenario Orchestration) on interfaces

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/filtering/ -v
uv run pytest --cov=focal/mechanics/focal/filtering --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 3**:
- [ ] Customer data updates work with candidate_variables
- [ ] History tracking works for VariableEntry
- [ ] SESSION scope variables cleaned up correctly
- [ ] Rule relationships implemented
- [ ] scenario_filter.jinja2 template created
- [ ] No conflicts between P3 and P5 changes

---

## WAVE 4: Scenario Orchestration (Sequential)

### Agent: P6 - Scenario Orchestration

**Prerequisites**: Wave 3 (P3, P5) complete

**Prompt**:

```markdown
# Task: Implement Phase 6 - Scenario Orchestration

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-06-scenario-orchestration-checklist.md` - Your checklist

## Prerequisites Completed
- Rule filtering complete with relationships (P5)
- Scenario retrieval parallelized (P4)
- Customer data available for condition evaluation (P3)

## Your Assignment
Execute ALL items in the Phase 6 checklist.

## Key Deliverables
1. Add missing ScenarioAction values: PAUSE, COMPLETE, CANCEL
2. Implement step skipping logic (jump to furthest reachable)
3. Create ScenarioContribution, ScenarioContributionPlan models
4. Create ScenarioSelectionContext model
5. Implement multi-scenario coordination
6. Unit tests with 85%+ coverage

## Important Notes
- ScenarioContribution and ScenarioContributionPlan are new models
- Step skipping requires evaluating all downstream conditions
- Multi-scenario coordination determines priority/ordering

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/filtering/test_scenario_filter.py -v
uv run pytest tests/unit/mechanics/focal/models/test_scenario_*.py -v
uv run pytest --cov=focal/mechanics/focal/filtering --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 4**:
- [ ] ScenarioAction has PAUSE, COMPLETE, CANCEL
- [ ] Step skipping works correctly
- [ ] ScenarioContributionPlan model exists
- [ ] Multi-scenario coordination implemented
- [ ] Tests pass

---

## WAVE 5: Tool & Planning (Sequential)

### Agent 5A: P7 - Tool Execution

**Prerequisites**: Wave 4 (P6) complete

**Prompt**:

```markdown
# Task: Implement Phase 7 - Tool Execution

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-07-tool-execution-checklist.md` - Your checklist

## Prerequisites Completed
- ScenarioFilterResult with contributions (P6)
- InterlocutorDataStore with variables (P3)
- Rule.attached_tool_ids exists

## Your Assignment
Execute ALL items in the Phase 7 checklist.

## Key Deliverables
1. Create ToolBinding model
2. Implement variable resolution from profile/session
3. Implement tool scheduling: BEFORE_STEP, DURING_STEP, AFTER_STEP
4. Implement future tool queue for AFTER_STEP tools
5. Collect tool bindings from matched rules and scenarios
6. Unit tests with 85%+ coverage

## Important Notes
- Tool execution (P7.5) is already implemented - don't duplicate
- Focus on scheduling and variable resolution
- AFTER_STEP tools should queue for next phase

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/execution/ -v
uv run pytest --cov=focal/mechanics/focal/execution --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

---

### Agent 5B: P8 - Response Planning

**Prerequisites**: P7 complete

**Prompt**:

```markdown
# Task: Implement Phase 8 - Response Planning

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-08-response-planning-checklist.md` - Your checklist

## Prerequisites Completed
- ScenarioContributionPlan from P6
- MatchedRules from P5
- ToolResults from P7

## Your Assignment
Execute ALL items in the Phase 8 checklist.

## Key Deliverables
1. Create ResponseType enum (ASK, ANSWER, MIXED, ESCALATE, HANDOFF)
2. Create ResponsePlan, RuleConstraint models
3. Implement ResponsePlanner class with all P8.x substeps
4. Determine global response type from scenarios/rules
5. Extract must_include/must_avoid constraints from rules
6. Integrate with AlignmentEngine between P7 and P9
7. Unit tests with 85%+ coverage

## Important Notes
- Phase 8 is currently SKIPPED in pipeline - this is the gap to fill
- ResponsePlan goes to `focal/mechanics/focal/planning/models.py`
- ResponsePlanner goes to `focal/mechanics/focal/planning/planner.py`

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/planning/ -v
uv run pytest --cov=focal/mechanics/focal/planning --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

**Verification After Wave 5**:
- [ ] ToolBinding model exists
- [ ] Tool scheduling works (BEFORE/DURING/AFTER)
- [ ] ResponseType enum exists
- [ ] ResponsePlan model exists
- [ ] ResponsePlanner integrated into engine
- [ ] Pipeline now executes P7 → P8 → P9

---

## WAVE 6: Generation → Enforcement → Persistence

### Option A: Single Agent for All Three

**Prompt**:

```markdown
# Task: Implement Phases 9, 10, 11 - Generation, Enforcement, Persistence

## CRITICAL: Read These Files FIRST (in order)
1. `docs/focal_turn_pipeline/implementation/SUBAGENT_PROTOCOL.md` - Execution rules
2. `CLAUDE.md` - Project conventions
3. `.specify/memory/constitution.md` - Hard rules
4. `docs/focal_turn_pipeline/implementation/CHECKLIST_CORRECTIONS.md` - Naming corrections
5. `docs/focal_turn_pipeline/implementation/phase-09-generation-checklist.md`
6. `docs/focal_turn_pipeline/implementation/phase-10-enforcement-checklist.md`
7. `docs/focal_turn_pipeline/implementation/phase-11-persistence-checklist.md`

## Prerequisites Completed
- ResponsePlan from P8
- All models from P1-P8

## Your Assignment
Execute ALL items in Phases 9, 10, and 11 checklists.

## Key Deliverables

### Phase 9: Generation
1. Update PromptBuilder to accept ResponsePlan
2. Add glossary to generation prompt
3. Implement channel formatting (placeholder for now)
4. Create TurnOutcome, OutcomeCategory models
5. Update generation.jinja2 template

### Phase 10: Enforcement
1. FIX CRITICAL: Always enforce GLOBAL hard constraints
2. Add simpleeval for deterministic enforcement (uv add simpleeval)
3. Implement LLM-as-Judge for subjective constraints
4. Create llm_judge.jinja2 template
5. Implement variable extraction from response
6. Add enforcement_expression field to Rule model

### Phase 11: Persistence
1. Implement persistent_updates batching for InterlocutorDataStore
2. Add entity_extraction.jinja2 template (from CHECKLIST_CORRECTIONS)
3. Add summarization templates (window_summary.jinja2, meta_summary.jinja2)

## Testing Commands
```bash
uv run pytest tests/unit/mechanics/focal/generation/ -v
uv run pytest tests/unit/mechanics/focal/enforcement/ -v
uv run pytest tests/unit/mechanics/focal/persistence/ -v
uv run pytest --cov=focal/mechanics/focal --cov-report=term-missing
```

## Report Format
Provide a final report following the template in SUBAGENT_PROTOCOL.md.
```

### Option B: Three Separate Agents (Sequential)

Use the individual phase prompts, running P9 → P10 → P11 in sequence.

**Verification After Wave 6**:
- [ ] PromptBuilder uses ResponsePlan
- [ ] GLOBAL constraints always enforced (CRITICAL FIX)
- [ ] simpleeval integrated for deterministic enforcement
- [ ] LLM-as-Judge implemented
- [ ] TurnOutcome model exists
- [ ] All templates migrated to Jinja2
- [ ] Full pipeline executes P1 → P11

---

## Post-Wave Quality Checks (MANDATORY)

**Every wave must pass these checks before proceeding to next wave:**

### Code Quality (Run After Each Wave)

```bash
# 1. Ruff linting
uv run ruff check focal/mechanics/focal/
uv run ruff check --fix focal/mechanics/focal/  # Auto-fix issues

# 2. Ruff formatting
uv run ruff format focal/mechanics/focal/

# 3. Mypy type checking
uv run mypy focal/mechanics/focal/ --ignore-missing-imports

# 4. Tests
uv run pytest tests/unit/mechanics/focal/ -v --tb=short
```

### Quick All-in-One Check

```bash
echo "=== WAVE QUALITY CHECK ===" && \
uv run ruff check focal/mechanics/focal/ && \
uv run ruff format --check focal/mechanics/focal/ && \
uv run mypy focal/mechanics/focal/ --ignore-missing-imports && \
uv run pytest tests/unit/mechanics/focal/ -v --tb=short && \
echo "=== ALL CHECKS PASSED ==="
```

**DO NOT proceed to next wave if quality checks fail.**

---

## Post-Implementation Verification

After all waves complete:

### Integration Test

```bash
# Run full pipeline test
uv run pytest tests/integration/mechanics/focal/ -v

# Run E2E test if available
uv run pytest tests/e2e/ -v
```

### Coverage Check

```bash
uv run pytest --cov=focal/mechanics/focal --cov-report=html
# Open htmlcov/index.html to verify 85%+ coverage
```

### Final Quality Gate

```bash
# Full quality check on entire mechanics/focal module
uv run ruff check focal/mechanics/focal/ && \
uv run ruff format --check focal/mechanics/focal/ && \
uv run mypy focal/mechanics/focal/ --ignore-missing-imports && \
uv run pytest tests/unit/mechanics/focal/ --cov=focal/mechanics/focal --cov-fail-under=85
```

### Checklist Audit

- [ ] All 11 phase checklists have no unmarked `- [ ]` items
- [ ] All blocked items documented with reasons
- [ ] All implementation notes added to checklists
- [ ] CHECKLIST_CORRECTIONS.md items addressed

### Documentation Update

- [ ] Update `docs/doc_skeleton.md` if new docs created
- [ ] Update `CLAUDE.md` if new patterns established
- [ ] Update `IMPLEMENTATION_PLAN.md` if it exists

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Import error after P1 renames | Run `uv sync`, check all imports updated |
| Test discovery fails | Ensure `__init__.py` exists in test directories |
| Coverage below threshold | Add edge case tests, check untested branches |
| Merge conflict | Coordinate with other agent, resolve manually |
| Model validation error | Check field types match spec |

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

| Wave | Phases | Agents | Parallel? |
|------|--------|--------|-----------|
| 1 | P1 | 1 | No |
| 2 | P2, P4 | 2 | Yes |
| 3 | P3, P5 | 2 | Yes |
| 4 | P6 | 1 | No |
| 5 | P7, P8 | 2 | Sequential |
| 6 | P9, P10, P11 | 1-3 | Sequential |

**Total minimum agents**: 6 (if single-agent waves)
**Total with parallelism**: 10 agent invocations
**Estimated total time**: 30-40 hours of agent work
