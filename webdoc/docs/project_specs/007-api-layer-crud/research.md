# Research: API CRUD Operations

**Date**: 2025-11-29
**Feature**: 001-api-crud

## Overview

This document captures research findings for implementing CRUD API endpoints. Since this feature builds on existing infrastructure (Phase 13 API Layer, Phase 4 ConfigStore, Phase 3 Domain Models), the research focuses on patterns for extending these foundations.

---

## 1. Agent Model Extension

### Decision
Use an `Agent` model as a lightweight container with settings, extending existing `AgentScopedModel` base.

### Rationale
- The codebase already uses `AgentScopedModel` as a base for entities (Rule, Scenario, Template, Variable)
- Agents don't currently exist as explicit models - they're implicit containers referenced by `agent_id`
- Need a concrete model for versioning, settings storage, and stats tracking

### Alternatives Considered
1. **Config-only approach**: Store agent settings in TOML - rejected because multi-tenant dynamic configuration requires database storage
2. **Extend Session**: Make agents a property of sessions - rejected because agents are configuration, sessions are runtime state

### Implementation Notes
```python
class Agent(TenantScopedModel):
    id: UUID
    name: str
    description: str | None
    enabled: bool
    current_version: int
    settings: AgentSettings  # LLM provider, model, temperature, etc.
```

---

## 2. Bulk Operations Pattern

### Decision
Use a transactional bulk operation endpoint with individual result reporting.

### Rationale
- Spec requires bulk operations for rules (FR-011)
- Need to handle partial failures gracefully
- Each operation result must be reported individually

### Alternatives Considered
1. **All-or-nothing transactions**: Fail entire batch on any error - rejected because one invalid rule shouldn't block 49 valid ones
2. **Fire-and-forget async**: Queue all operations - rejected because caller needs immediate feedback on success/failure

### Implementation Pattern
```python
class BulkOperation(BaseModel):
    action: Literal["create", "update", "delete"]
    id: UUID | None = None  # Required for update/delete
    data: dict | None = None  # Required for create/update

class BulkResult(BaseModel):
    action: str
    success: bool
    id: UUID | None
    error: str | None

# Response: {"results": [BulkResult, ...]}
```

---

## 3. Async Embedding Computation

### Decision
Trigger embedding computation asynchronously on rule create/update, don't block API response.

### Rationale
- SC-001 requires <500ms response times
- Embedding computation can take 100-500ms depending on provider
- SC-010 explicitly requires async embedding recomputation

### Alternatives Considered
1. **Synchronous**: Block until embedding complete - rejected due to latency impact
2. **Client-triggered**: Require separate embedding endpoint - rejected because it's error-prone and adds complexity

### Implementation Pattern
```python
# On rule save:
await config_store.save_rule(rule)  # Immediate
background_tasks.add_task(compute_and_update_embedding, rule.id)  # Async

# Use FastAPI BackgroundTasks for simplicity
# Consider task queue (Redis) for production scale
```

---

## 4. Template Variable Extraction

### Decision
Use regex pattern matching to extract `{variable_name}` placeholders from template text.

### Rationale
- FR-020 requires identifying variables used in templates
- Simple pattern: `{word_characters}` is sufficient
- No need for complex parsing - templates are simple substitution

### Pattern
```python
import re
VARIABLE_PATTERN = re.compile(r'\{([a-z_][a-z0-9_]*)\}')

def extract_variables(text: str) -> list[str]:
    return list(set(VARIABLE_PATTERN.findall(text)))
```

---

## 5. Pagination Pattern

### Decision
Use offset-based pagination with consistent response structure.

### Rationale
- Simple to implement and understand
- Works well for configuration data (not high-velocity)
- Matches api-crud.md specification

### Alternatives Considered
1. **Cursor-based**: Better for real-time data - overkill for config management
2. **Page-number**: Less flexible than offset - offset is more RESTful

### Response Structure
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool = False
```

---

## 6. Scenario Step ID Auto-Generation

### Decision
Auto-generate UUID step IDs on scenario creation when not provided.

### Rationale
- FR-014 requires auto-generation
- Simplifies client experience - can create scenarios without managing IDs
- UUIDs avoid collision issues

### Implementation
```python
for step in scenario.steps:
    if step.id is None:
        step.id = uuid4()
    step.scenario_id = scenario.id
```

---

## 7. Publishing Workflow

### Decision
Implement as async job with stage tracking, stored in memory/Redis.

### Rationale
- FR-033 requires progress reporting through stages
- Publishing involves multiple steps (validate, compile, deploy)
- Need job status lookup

### Stages
1. `validate` - Check configuration consistency
2. `compile` - Compute embeddings, validate references
3. `write_bundles` - Serialize configuration
4. `swap_pointer` - Atomic version switch
5. `invalidate_cache` - Clear any cached config

### Implementation
```python
class PublishJob(BaseModel):
    id: UUID
    agent_id: UUID
    version: int
    status: Literal["pending", "running", "completed", "failed"]
    stages: list[PublishStage]
    started_at: datetime
    completed_at: datetime | None
```

---

## 8. Circular Transition Detection

### Decision
Validate scenario transitions on save to detect unreachable steps, warn on potential infinite loops.

### Rationale
- Edge case from spec: "How does the system handle circular transitions?"
- Circular transitions aren't always invalid (loops are sometimes intentional)
- Detect unreachable steps (orphaned from entry) as errors

### Implementation
```python
def validate_scenario_graph(scenario: Scenario) -> list[str]:
    warnings = []
    reachable = compute_reachable_steps(scenario.entry_step_id, scenario.steps)
    for step in scenario.steps:
        if step.id not in reachable:
            warnings.append(f"Step {step.name} is unreachable from entry")
    return warnings
```

---

## 9. Error Codes Extension

### Decision
Extend existing `ErrorCode` enum with CRUD-specific codes.

### Rationale
- Existing error handling in `focal/api/models/errors.py`
- Need codes for: rule/scenario/template not found, validation failures, publish failures

### New Codes
```python
RULE_NOT_FOUND = "RULE_NOT_FOUND"
SCENARIO_NOT_FOUND = "SCENARIO_NOT_FOUND"
TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
VARIABLE_NOT_FOUND = "VARIABLE_NOT_FOUND"
ENTRY_STEP_DELETION = "ENTRY_STEP_DELETION"
PUBLISH_IN_PROGRESS = "PUBLISH_IN_PROGRESS"
PUBLISH_FAILED = "PUBLISH_FAILED"
INVALID_TRANSITION = "INVALID_TRANSITION"
```

---

## 10. Tool Activation Storage

### Decision
Store tool activations as a separate entity linking agents to tools.

### Rationale
- Tools are defined externally (FR-027)
- Activation state is per-agent
- Need to track enable/disable timestamps and policy overrides

### Model
```python
class ToolActivation(AgentScopedModel):
    tool_id: str
    status: Literal["enabled", "disabled"]
    policy_override: dict | None
    enabled_at: datetime | None
    disabled_at: datetime | None
```

---

## Summary

All technical decisions are resolved. No NEEDS CLARIFICATION items remain. The implementation can proceed with:

1. **Existing infrastructure**: FastAPI app, ConfigStore, domain models, error handling
2. **New patterns**: Bulk operations, async embedding, pagination, publish jobs
3. **Extensions**: Agent model, ToolActivation model, new error codes
