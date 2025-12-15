# Refactoring Plan: Target Folder Structure

> **Status**: DRAFT - Pending user decisions
> **Purpose**: Define the target codebase structure and migration path

---

## Current vs. Target Structure

### Legend
- 🟢 **KEEP** - Already correct
- 🟡 **MOVE** - Relocate to new path
- 🔴 **MERGE** - Consolidate with another module
- ⚪ **NEW** - Create new (doesn't exist)

---

## Target Structure

```
ruche/
├── api/                                    # 🟢 KEEP
│   ├── routes/                             # 🟢 KEEP
│   ├── models/                             # 🟢 KEEP
│   ├── middleware/                         # 🟢 KEEP
│   ├── grpc/                               # 🟢 KEEP (optional)
│   └── mcp/                                # 🟢 KEEP (optional)
│
├── brains/                                 # 🟢 KEEP (expand)
│   ├── protocol.py                         # 🟢 KEEP - Brain ABC
│   └── focal/                              # 🔴 MERGE alignment/ into here
│       ├── engine.py                       # 🔴 MERGE from alignment/engine.py
│       ├── pipeline.py                     # 🟢 KEEP (or merge with engine)
│       ├── phases/                         # 🟡 MOVE from alignment/
│       │   ├── p01_identification/         # 🟡 MOVE from alignment/loaders/
│       │   ├── p02_situational_sensor/     # 🟡 MOVE from alignment/context/
│       │   ├── p03_interlocutor_update/    # 🟡 MOVE from alignment/customer/
│       │   ├── p04_retrieval/              # 🟡 MOVE from alignment/retrieval/
│       │   ├── p05_rule_selection/         # 🟡 MOVE from alignment/filtering/
│       │   ├── p06_scenario_orchestration/ # 🟡 MOVE from alignment/orchestration/
│       │   ├── p07_tool_execution/         # 🟡 MOVE from alignment/execution/
│       │   ├── p08_response_planning/      # 🟡 MOVE from alignment/planning/
│       │   ├── p09_generation/             # 🟡 MOVE from alignment/generation/
│       │   ├── p10_enforcement/            # 🟡 MOVE from alignment/enforcement/
│       │   └── p11_persistence/            # ⚪ NEW (or part of engine)
│       ├── models/                         # 🟡 MOVE from alignment/models/
│       ├── migration/                      # 🟡 MOVE from alignment/migration/
│       ├── prompts/                        # 🟡 CONSOLIDATE from various prompts/
│       └── stores/                         # 🟡 MOVE from alignment/stores/ (ConfigStore)
│
├── runtime/                                # 🟢 KEEP
│   ├── acf/                                # 🟢 KEEP (verify completeness)
│   ├── agent/                              # 🟢 KEEP
│   └── agenda/                             # 🟢 KEEP
│
├── domain/                                 # 🟢 KEEP (expand)
│   ├── interlocutor/                       # 🟢 KEEP (+ merge from customer_data/)
│   ├── rules/                              # 🟢 KEEP
│   ├── scenarios/                          # 🟢 KEEP
│   ├── memory/                             # 🟢 KEEP (+ merge from memory/models/)
│   ├── glossary.py                         # 🟢 KEEP
│   └── templates.py                        # 🟢 KEEP
│
├── infrastructure/                         # 🟢 KEEP (consolidate)
│   ├── stores/                             # 🟢 KEEP (expand)
│   │   ├── config/                         # 🟢 KEEP
│   │   ├── session/                        # 🟡 MOVE from conversation/stores/
│   │   ├── memory/                         # 🟢 KEEP
│   │   ├── audit/                          # 🟡 MOVE from audit/stores/
│   │   ├── interlocutor/                   # 🟡 MOVE from customer_data/stores/
│   │   └── vector/                         # 🟡 MOVE from vector/stores/
│   ├── providers/                          # 🟢 KEEP
│   │   ├── llm/                            # 🟢 KEEP
│   │   ├── embedding/                      # 🟢 KEEP
│   │   └── rerank/                         # 🟢 KEEP
│   ├── toolbox/                            # 🟢 KEEP
│   ├── channels/                           # 🟢 KEEP
│   ├── db/                                 # 🟡 MOVE from db/
│   └── jobs/                               # 🟡 MOVE from jobs/
│
├── asa/                                    # 🟢 KEEP
├── config/                                 # 🟢 KEEP
├── observability/                          # 🟢 KEEP
├── client/                                 # 🟢 KEEP
├── utils/                                  # 🟢 KEEP
│
├── providers/                              # 🔴 CONVERT to re-exports only
│   └── __init__.py                         # Re-export from infrastructure/providers/
│
└── [DELETED after migration]
    ├── alignment/                          # 🔴 DELETE (merged into brains/focal/)
    ├── audit/                              # 🔴 DELETE (merged into infrastructure/)
    ├── conversation/                       # 🔴 DELETE (merged into infrastructure/)
    ├── customer_data/                      # 🔴 DELETE (merged into domain/ + infrastructure/)
    ├── memory/                             # 🔴 DELETE (split to domain/ + infrastructure/)
    ├── db/                                 # 🔴 DELETE (moved to infrastructure/)
    ├── jobs/                               # 🔴 DELETE (moved to infrastructure/)
    └── vector/                             # 🔴 DELETE (moved to infrastructure/)
```

---

## Migration Steps

### Phase 1: FOCAL Consolidation (WP-001)

**Goal**: Merge `alignment/` into `brains/focal/`

```bash
# Step 1: Analyze duplication
diff ruche/brains/focal/pipeline.py ruche/alignment/engine.py

# Step 2: Move phase implementations
mv ruche/alignment/context/ ruche/brains/focal/phases/p02_situational_sensor/
mv ruche/alignment/filtering/ ruche/brains/focal/phases/p05_rule_selection/
mv ruche/alignment/generation/ ruche/brains/focal/phases/p09_generation/
mv ruche/alignment/enforcement/ ruche/brains/focal/phases/p10_enforcement/
mv ruche/alignment/execution/ ruche/brains/focal/phases/p07_tool_execution/
mv ruche/alignment/loaders/ ruche/brains/focal/phases/p01_identification/
mv ruche/alignment/orchestration/ ruche/brains/focal/phases/p06_scenario_orchestration/
mv ruche/alignment/planning/ ruche/brains/focal/phases/p08_response_planning/
mv ruche/alignment/retrieval/ ruche/brains/focal/retrieval/
mv ruche/alignment/migration/ ruche/brains/focal/migration/
mv ruche/alignment/models/ ruche/brains/focal/models/
mv ruche/alignment/stores/ ruche/brains/focal/stores/

# Step 3: Consolidate engine
# Merge unique logic from alignment/engine.py into brains/focal/engine.py
# Delete alignment/engine.py

# Step 4: Update imports
# Use IDE refactoring or automated scripts
```

### Phase 2: Infrastructure Consolidation (WP-004)

**Goal**: Move stores and support modules under infrastructure/

```bash
# Move session stores
mv ruche/conversation/stores/ ruche/infrastructure/stores/session/
# Keep conversation/models/ for now or move to domain/

# Move audit stores
mv ruche/audit/stores/ ruche/infrastructure/stores/audit/
mv ruche/audit/models/ ruche/domain/audit/

# Move customer data
mv ruche/customer_data/stores/ ruche/infrastructure/stores/interlocutor/
# Merge customer_data/models.py into domain/interlocutor/

# Move vector stores
mv ruche/vector/stores/ ruche/infrastructure/stores/vector/

# Move supporting infrastructure
mv ruche/db/ ruche/infrastructure/db/
mv ruche/jobs/ ruche/infrastructure/jobs/
```

### Phase 3: Provider Cleanup (WP-006)

**Goal**: Single provider location with backward-compatible re-exports

```python
# ruche/providers/__init__.py (after cleanup)
"""
Backward-compatible re-exports.
Use ruche.infrastructure.providers directly for new code.
"""
from ruche.infrastructure.providers.llm import LLMExecutor
from ruche.infrastructure.providers.embedding import EmbeddingProvider
from ruche.infrastructure.providers.rerank import RerankProvider

__all__ = ["LLMExecutor", "EmbeddingProvider", "RerankProvider"]
```

---

## Import Update Strategy

### Automated Updates

Use `refactoring-script.py` (to be created):

```python
import_mappings = {
    "ruche.alignment.engine": "ruche.brains.focal.engine",
    "ruche.alignment.context": "ruche.brains.focal.phases.p02_situational_sensor",
    "ruche.alignment.filtering": "ruche.brains.focal.phases.p05_rule_selection",
    # ... etc
}
```

### Manual Verification

After automated updates:
1. Run `ruff check ruche/`
2. Run `mypy ruche/`
3. Run `pytest tests/`

---

## Rollback Plan

Each migration phase creates a commit. If issues arise:

```bash
# Revert to pre-migration state
git revert --no-commit HEAD~N  # N = number of migration commits
git commit -m "Revert migration attempt"
```

---

## Testing Strategy During Migration

### Per-Move Testing

After each `mv` command:
1. Update imports in moved files
2. Run tests for that module: `pytest tests/unit/{module}/`
3. Commit if passing

### Integration Testing

After each phase:
1. Run full test suite: `pytest`
2. Run type checking: `mypy ruche/`
3. Run linting: `ruff check ruche/`

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Broken imports | HIGH | HIGH | Automated refactoring, incremental commits |
| Test failures | MEDIUM | MEDIUM | Run tests after each move |
| Circular imports | LOW | HIGH | Careful dependency analysis |
| Performance regression | LOW | LOW | Benchmarks before/after |

---

## Decision Points

### If Q2 = (A) Full Restructure
- Execute all phases as described
- Estimated: 3-5 days

### If Q2 = (B) Incremental Alignment
- Phase 1 only (FOCAL consolidation)
- Defer Phase 2-3 to future
- Estimated: 2-3 days

### If Q2 = (C) Update Documentation
- No code changes
- Update `folder-structure.md` to match current code
- Estimated: 0.5 days

---

*This plan will be finalized after user decisions.*
