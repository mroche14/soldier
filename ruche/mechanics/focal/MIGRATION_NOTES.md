# FOCAL Pipeline Migration Notes

This document tracks the migration of the alignment engine to the new mechanics/focal/ architecture.

## Migration Summary

**Date**: 2025-12-14
**Source**: `focal_backup_20251214/alignment/`
**Target**: `focal/mechanics/focal/`

## What Was Migrated

### 1. Core Pipeline File

- **Source**: `focal_backup_20251214/alignment/engine.py` (2078 lines)
- **Target**: `focal/mechanics/focal/pipeline.py`
- **Changes**:
  - Renamed `AlignmentEngine` → `FocalCognitivePipeline`
  - Updated module docstring to reflect 12-phase architecture
  - Updated class docstring with phase breakdown
  - All imports and logic preserved as-is

### 2. Models

Copied to `focal/mechanics/focal/models/`:

- `turn_context.py` - TurnContext model (Phase 1 output)
- `situational_snapshot.py` - SituationSnapshot (Phase 2 output)
- `response_plan.py` - ResponsePlan models (Phase 8 output)
- `enforcement_result.py` - EnforcementResult (Phase 11 output)
- `pipeline_result.py` - AlignmentResult and PipelineStepTiming

### 3. Migration Module

- **Source**: `focal_backup_20251214/alignment/migration/`
- **Target**: `focal/mechanics/focal/migration/`
- **Files copied**:
  - `executor.py` - MigrationExecutor for JIT migrations
  - `planner.py` - MigrationPlanner and MigrationDeployer
  - `field_resolver.py` - MissingFieldResolver for gap filling
  - `models.py` - ReconciliationResult, MigrationPlan, etc.
  - `diff.py` - Content hashing and diff utilities
  - `composite.py` - CompositeMapper for multi-version gaps

### 4. Prompts

Copied to `focal/mechanics/focal/prompts/`:

- `situation_sensor.jinja2` - Phase 2 prompt template
- `filter_rules.jinja2` - Phase 6 rule filtering prompt
- `scenario_filter.jinja2` - Phase 7 scenario filtering prompt

## New Protocol Architecture

Created `focal/mechanics/protocol.py` with:

- `CognitivePipeline` Protocol - Abstract interface for all mechanics
- `PipelineResult` - Standardized output format
- `ResponseSegment` - Response component model

The FOCAL pipeline implements this protocol but currently returns `AlignmentResult`
instead of `PipelineResult`. Future work will add a wrapper method.

## Directory Structure

```
focal/mechanics/
├── __init__.py                 # Exports protocol and implementations
├── protocol.py                 # CognitivePipeline protocol
└── focal/
    ├── __init__.py             # Exports FocalCognitivePipeline
    ├── pipeline.py             # Main orchestrator (2078 lines)
    ├── MIGRATION_NOTES.md      # This file
    ├── models/
    │   ├── __init__.py
    │   ├── turn_context.py
    │   ├── situational_snapshot.py
    │   ├── response_plan.py
    │   ├── enforcement_result.py
    │   └── pipeline_result.py
    ├── phases/
    │   ├── __init__.py
    │   └── README.md           # Future phase extraction plan
    ├── migration/
    │   ├── __init__.py
    │   ├── executor.py
    │   ├── planner.py
    │   ├── field_resolver.py
    │   ├── models.py
    │   ├── diff.py
    │   └── composite.py
    └── prompts/
        ├── situation_sensor.jinja2
        ├── filter_rules.jinja2
        └── scenario_filter.jinja2
```

## What Was NOT Migrated

The following remain in their original locations and are imported by the pipeline:

### Alignment Components (Still in `focal/alignment/`)

- `context/` - SituationSensor, ContextExtractor, customer schema mask
- `customer/` - CustomerDataUpdater
- `enforcement/` - EnforcementValidator, FallbackHandler
- `execution/` - ToolExecutor
- `filtering/` - RuleFilter, ScenarioFilter
- `generation/` - ResponseGenerator, PromptBuilder
- `loaders/` - CustomerDataLoader, StaticConfigLoader
- `planning/` - ResponsePlanner
- `retrieval/` - All retrievers (rule, scenario, intent, memory)
- `stores/` - AgentConfigStore

### Other Modules

- `focal/audit/` - AuditStore, TurnRecord
- `focal/conversation/` - SessionStore, Session
- `focal/customer_data/` - CustomerDataStore, field validation
- `focal/memory/` - MemoryStore, MemoryRetriever
- `focal/providers/` - LLMExecutor, EmbeddingProvider, RerankProvider
- `focal/config/` - PipelineConfig, ScenarioMigrationConfig
- `focal/observability/` - Logging, metrics

## Import Dependencies

The `FocalCognitivePipeline` class currently imports from:

- `focal.alignment.*` - Most pipeline components
- `focal.audit.*` - Turn record persistence
- `focal.conversation.*` - Session management
- `focal.customer_data.*` - Customer profile management
- `focal.memory.*` - Memory retrieval
- `focal.providers.*` - LLM/embedding/rerank providers
- `focal.config.*` - Configuration models
- `focal.observability.*` - Logging and metrics

## Future Refactoring Tasks

### Phase 1: Extract Phase Logic

Each private method in `pipeline.py` should be extracted to its own phase module:

- `_resolve_customer()` → `phases/p01_identification.py`
- `_sense_situation()` → `phases/p02_situational.py`
- Customer data update code → `phases/p03_data_update.py`
- `_retrieve_rules()` → `phases/p04_retrieval.py`
- Reranking logic → `phases/p05_reranking.py`
- `_filter_rules()`, `_filter_scenarios()` → `phases/p06_filtering.py`
- Scenario orchestration → `phases/p07_orchestration.py`
- `_build_response_plan()` → `phases/p08_planning.py`
- `_execute_tools()` → `phases/p09_execution.py`
- `_generate_response()` → `phases/p10_generation.py`
- `_enforce_response()` → `phases/p11_enforcement.py`
- Persistence methods → `phases/p12_persistence.py`

### Phase 2: Protocol Adapter

Add a wrapper method to `FocalCognitivePipeline` that:

1. Calls `process_turn()` to get `AlignmentResult`
2. Converts `AlignmentResult` → `PipelineResult`
3. Implements the `CognitivePipeline` protocol fully

### Phase 3: Migrate Supporting Modules

Gradually move alignment components into mechanics/focal/:

- Context extraction → `focal/mechanics/focal/context/`
- Retrieval → `focal/mechanics/focal/retrieval/`
- Filtering → `focal/mechanics/focal/filtering/`
- Generation → `focal/mechanics/focal/generation/`
- Enforcement → `focal/mechanics/focal/enforcement/`

## Testing Considerations

### What Needs Testing

1. **Import Resolution**: Verify all imports work from new location
2. **Class Rename**: Ensure `FocalCognitivePipeline` can replace `AlignmentEngine`
3. **Model Imports**: Check that models are importable from `mechanics.focal.models`
4. **Migration Module**: Verify migration executor works from new location
5. **Prompts**: Ensure Jinja2 templates load correctly

### Test Migration Strategy

1. Update imports in test files to use `FocalCognitivePipeline`
2. Copy alignment tests to `tests/mechanics/focal/`
3. Verify all existing tests pass with renamed class
4. Add protocol compliance tests

## Known Issues

1. **AlignmentResult vs PipelineResult**: The pipeline returns `AlignmentResult`
   but should return `PipelineResult` to match protocol. Needs adapter.

2. **Circular Imports**: May need to refactor imports when extracting phases
   to avoid circular dependencies.

3. **Path Dependencies**: Template loading uses `Path(__file__).parent` which
   may break if not carefully handled during phase extraction.

## Rollback Plan

If issues arise, the original code is preserved in `focal_backup_20251214/alignment/`.

To rollback:
1. Delete `focal/mechanics/focal/`
2. Restore from `focal_backup_20251214/alignment/` to `focal/alignment/`
3. Revert class name from `FocalCognitivePipeline` to `AlignmentEngine`

## Related Documentation

- `focal/mechanics/protocol.py` - Protocol definitions
- `focal/mechanics/focal/phases/README.md` - Phase extraction plan
- `IMPLEMENTATION_PLAN.md` - Overall project implementation tracking
