# Data Model: API CRUD Operations

**Date**: 2025-11-29
**Feature**: 001-api-crud

## Overview

This document defines the data models for API CRUD operations. Most domain models already exist (Phase 3); this focuses on new models needed for API layer and extensions to existing models.

---

## New Models

### Agent

Top-level container for conversational AI configuration.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Unique identifier |
| `tenant_id` | UUID | FK, required | Tenant ownership |
| `name` | string | 1-100 chars, required | Agent display name |
| `description` | string | optional | Human description |
| `enabled` | boolean | default: true | Is agent active |
| `current_version` | int | default: 1, >=1 | Published version number |
| `settings` | AgentSettings | embedded | Provider and model config |
| `created_at` | datetime | auto | Creation timestamp |
| `updated_at` | datetime | auto | Last modification |
| `deleted_at` | datetime | nullable | Soft delete marker |

**AgentSettings (embedded)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `llm_provider` | string | optional | e.g., "anthropic", "openai" |
| `llm_model` | string | optional | e.g., "claude-3-5-sonnet" |
| `temperature` | float | 0.0-2.0, default: 0.7 | Generation temperature |
| `max_tokens` | int | default: 1024, >=1 | Max response tokens |

**Relationships**:
- Has many Rules (via `agent_id`)
- Has many Scenarios (via `agent_id`)
- Has many Templates (via `agent_id`)
- Has many Variables (via `agent_id`)
- Has many ToolActivations (via `agent_id`)

---

### ToolActivation

Per-agent tool enablement status.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Unique identifier |
| `tenant_id` | UUID | FK, required | Tenant ownership |
| `agent_id` | UUID | FK, required | Parent agent |
| `tool_id` | string | required | External tool reference |
| `status` | enum | enabled/disabled | Current state |
| `policy_override` | dict | optional | Custom timeout, etc. |
| `enabled_at` | datetime | nullable | Last enable time |
| `disabled_at` | datetime | nullable | Last disable time |
| `created_at` | datetime | auto | Creation timestamp |
| `updated_at` | datetime | auto | Last modification |

**Unique Constraint**: `(tenant_id, agent_id, tool_id)`

---

### PublishJob

Tracks publish operation progress.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, auto-generated | Job identifier |
| `tenant_id` | UUID | FK, required | Tenant ownership |
| `agent_id` | UUID | FK, required | Target agent |
| `version` | int | required | Target version number |
| `status` | enum | pending/running/completed/failed | Job status |
| `stages` | list[PublishStage] | embedded | Stage progress |
| `description` | string | optional | User-provided description |
| `started_at` | datetime | required | Job start time |
| `completed_at` | datetime | nullable | Job completion time |
| `error` | string | nullable | Failure message if failed |

**PublishStage (embedded)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | required | validate/compile/write_bundles/swap_pointer/invalidate_cache |
| `status` | enum | pending/running/completed/failed | Stage status |
| `duration_ms` | int | nullable | Execution time |
| `error` | string | nullable | Stage-specific error |

---

## Existing Models (Reference)

These models are already implemented in Phase 3. Listed here for reference with CRUD-relevant notes.

### Rule (`soldier/alignment/models/rule.py`)

| Key Fields | CRUD Notes |
|------------|------------|
| `id`, `tenant_id`, `agent_id` | Standard scoping |
| `name`, `condition_text`, `action_text` | Create/update payload |
| `scope`, `scope_id` | Filtering parameters |
| `priority` | Range filtering (-100 to 100) |
| `enabled` | Filter parameter |
| `embedding`, `embedding_model` | Auto-computed on create/update |
| `max_fires_per_session`, `cooldown_turns` | Behavior controls |
| `attached_tool_ids`, `attached_template_ids` | Reference lists |

**Validation**:
- `scope_id` required when `scope` is SCENARIO or STEP
- `name` length 1-100
- `condition_text` and `action_text` non-empty

---

### Scenario (`soldier/alignment/models/scenario.py`)

| Key Fields | CRUD Notes |
|------------|------------|
| `id`, `tenant_id`, `agent_id` | Standard scoping |
| `name`, `description` | Create/update payload |
| `entry_step_id` | Must reference valid step |
| `steps` | Nested step management |
| `version` | Incremented on edit |
| `tags` | Array for filtering |
| `enabled` | Filter parameter |

**ScenarioStep (nested)**:
- `id` auto-generated if not provided
- `scenario_id` set automatically
- `transitions` reference other steps by ID
- `is_entry` / `is_terminal` for flow control

**Validation**:
- `entry_step_id` must point to existing step
- Step IDs must be unique within scenario
- Transition `to_step_id` must reference existing step

---

### Template (`soldier/alignment/models/template.py`)

| Key Fields | CRUD Notes |
|------------|------------|
| `id`, `tenant_id`, `agent_id` | Standard scoping |
| `name`, `text` | Create/update payload |
| `mode` | SUGGEST/EXCLUSIVE/FALLBACK filter |
| `scope`, `scope_id` | Scoping and filtering |
| `conditions` | Optional expression |

**Derived Fields** (computed on save):
- `variables_used`: Extracted from `{placeholder}` patterns in `text`

---

### Variable (`soldier/alignment/models/variable.py`)

| Key Fields | CRUD Notes |
|------------|------------|
| `id`, `tenant_id`, `agent_id` | Standard scoping |
| `name` | Unique per agent, lowercase with underscores |
| `description` | Optional |
| `resolver_tool_id` | External tool reference |
| `update_policy` | ON_SESSION_START/ON_DEMAND/PERIODIC |
| `cache_ttl_seconds` | 0 = no cache |

**Validation**:
- `name` pattern: `^[a-z_][a-z0-9_]*$`
- `name` unique within agent

---

## API Request/Response Models

### Pagination

```
PaginatedRequest:
  limit: int (default: 20, max: 100)
  offset: int (default: 0)
  sort: string (optional, format: "field:asc|desc")

PaginatedResponse<T>:
  items: list[T]
  total: int
  limit: int
  offset: int
  has_more: bool
```

### Bulk Operations

```
BulkOperationRequest:
  operations: list[BulkOperation]

BulkOperation:
  action: "create" | "update" | "delete"
  id: UUID (required for update/delete)
  data: dict (required for create/update)

BulkOperationResponse:
  results: list[BulkResult]

BulkResult:
  action: string
  success: bool
  id: UUID | null
  error: string | null
```

### Error Response (existing, extended)

```
ErrorResponse:
  error:
    code: ErrorCode
    message: string
    details: list[ErrorDetail] | null

New ErrorCodes:
  - RULE_NOT_FOUND
  - SCENARIO_NOT_FOUND
  - TEMPLATE_NOT_FOUND
  - VARIABLE_NOT_FOUND
  - ENTRY_STEP_DELETION
  - PUBLISH_IN_PROGRESS
  - PUBLISH_FAILED
  - INVALID_TRANSITION
```

---

## State Transitions

### Agent Lifecycle

```
Created → Enabled → Disabled → Deleted (soft)
                 ↑__________↓
```

### Publish Job Lifecycle

```
pending → running → completed
              ↓
           failed
```

### PublishStage Lifecycle

```
pending → running → completed
              ↓
           failed (stops job)
```

---

## Indexes and Queries

### Primary Queries

| Entity | Common Query | Index Suggestion |
|--------|-------------|------------------|
| Agent | By tenant_id, list all | `(tenant_id, deleted_at)` |
| Rule | By agent_id with scope filter | `(tenant_id, agent_id, scope, enabled)` |
| Rule | Vector search | Vector index on `embedding` |
| Scenario | By agent_id, enabled | `(tenant_id, agent_id, enabled)` |
| Template | By agent_id with mode/scope filter | `(tenant_id, agent_id, mode, scope)` |
| Variable | By agent_id | `(tenant_id, agent_id)` |
| ToolActivation | By agent_id | `(tenant_id, agent_id)` |

### Tenant Isolation

All queries MUST filter by `tenant_id` to prevent cross-tenant data leakage.

```python
# Correct
await store.get_rules(tenant_id=current_tenant, agent_id=agent_id)

# WRONG - Missing tenant filter
await store.get_rules(agent_id=agent_id)  # Security violation
```
