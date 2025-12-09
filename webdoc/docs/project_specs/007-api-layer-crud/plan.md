# Implementation Plan: API CRUD Operations

**Branch**: `001-api-crud` | **Date**: 2025-11-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-api-crud/spec.md`

## Summary

Implement RESTful CRUD endpoints for managing agent configuration entities (Agents, Rules, Scenarios, Templates, Variables, Tools) and publishing workflows. Builds on existing FastAPI infrastructure (Phase 13), domain models (Phase 3), and ConfigStore interface (Phase 4) to expose configuration management via HTTP API.

## Technical Context

**Language/Version**: Python 3.11+ (existing)
**Primary Dependencies**: FastAPI, uvicorn, pydantic, python-jose (JWT) - all existing from Phase 13
**Storage**: ConfigStore interface with InMemoryConfigStore (Phase 4), existing embedding providers (Phase 5)
**Testing**: pytest with pytest-asyncio, httpx for API testing (existing)
**Target Platform**: Linux server (containerized)
**Project Type**: Single Python package (focal/)
**Performance Goals**: 500ms p95 for CRUD operations, 100 concurrent requests (from SC-001, SC-002)
**Constraints**: <500ms for sync operations, async embedding computation, zero cross-tenant leakage
**Scale/Scope**: Multi-tenant, 100 rules per agent typical, 50 rules per bulk operation

## Constitution Check

*No constitution file found - proceeding without gates.*

## Project Structure

### Documentation (this feature)

```text
specs/001-api-crud/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
focal/
├── api/
│   ├── routes/
│   │   ├── agents.py        # NEW: Agent CRUD endpoints
│   │   ├── rules.py         # NEW: Rule CRUD + bulk operations
│   │   ├── scenarios.py     # NEW: Scenario + step CRUD
│   │   ├── templates.py     # NEW: Template CRUD + preview
│   │   ├── variables.py     # NEW: Variable CRUD
│   │   ├── tools.py         # NEW: Tool activation management
│   │   ├── publish.py       # NEW: Publishing and versioning
│   │   └── (existing)       # chat.py, sessions.py, health.py
│   ├── models/
│   │   ├── crud.py          # NEW: Request/response models for CRUD
│   │   ├── pagination.py    # NEW: Pagination models
│   │   ├── bulk.py          # NEW: Bulk operation models
│   │   └── (existing)       # chat.py, errors.py, session.py
│   └── services/
│       ├── embedding.py     # NEW: Async embedding service
│       └── publish.py       # NEW: Publish job orchestration
└── alignment/
    ├── models/              # Existing: Rule, Scenario, Template, Variable
    └── stores/              # Existing: ConfigStore interface

tests/
├── unit/
│   └── api/
│       ├── test_agents.py       # NEW
│       ├── test_rules.py        # NEW
│       ├── test_scenarios.py    # NEW
│       ├── test_templates.py    # NEW
│       └── (existing)
└── integration/
    └── api/
        └── test_crud_flow.py    # NEW: Full CRUD integration tests
```

**Structure Decision**: Extends existing `focal/api/routes/` structure with new route modules per entity type. API models go in `focal/api/models/` following existing patterns. Services layer added for cross-cutting concerns (embedding computation, publish orchestration).
