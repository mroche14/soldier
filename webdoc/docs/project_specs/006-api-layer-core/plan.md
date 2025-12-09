# Implementation Plan: API Layer - Core

**Branch**: `006-api-layer-core` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-api-layer-core/spec.md`

## Summary

Implement the HTTP API layer for Focal including a FastAPI application factory, middleware for authentication and rate limiting, core endpoints for chat processing (sync and streaming), session management, and health/metrics. The API integrates with the existing AlignmentEngine, SessionStore, and AuditStore to process messages and manage conversation state.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, uvicorn, python-jose (JWT), sse-starlette (SSE streaming)
**Storage**: In-memory stores (existing), Redis for idempotency cache and rate limiting
**Testing**: pytest, pytest-asyncio, httpx (async test client)
**Target Platform**: Linux server (containerized)
**Project Type**: Single Python package (existing structure)
**Performance Goals**: <100ms p95 for API overhead (excluding LLM time), support SSE streaming
**Constraints**: Multi-tenant isolation, stateless API pods, async-first
**Scale/Scope**: Per-tenant rate limits (60-600 req/min by tier), concurrent sessions per tenant

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution file found - proceeding with standard software engineering best practices:
- [x] Single responsibility per module
- [x] Dependency injection for testability
- [x] Interface-first design (existing pattern in codebase)
- [x] Async-first (existing pattern)
- [x] Structured logging (existing observability)

## Project Structure

### Documentation (this feature)

```text
specs/006-api-layer-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI spec)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
focal/
├── api/
│   ├── __init__.py
│   ├── app.py                 # FastAPI application factory
│   ├── dependencies.py        # Dependency injection (stores, providers)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── chat.py            # ChatRequest, ChatResponse, StreamEvent
│   │   └── errors.py          # ErrorResponse, ErrorCode enum
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py            # POST /v1/chat, POST /v1/chat/stream
│   │   ├── sessions.py        # GET/DELETE /v1/sessions/{id}, turns
│   │   └── health.py          # GET /health, GET /metrics
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py            # JWT validation, tenant extraction
│       ├── rate_limit.py      # Per-tenant rate limiting
│       ├── context.py         # Request context binding (trace_id, etc.)
│       └── idempotency.py     # Idempotency-Key handling

tests/
├── unit/
│   └── api/
│       ├── test_chat.py
│       ├── test_sessions.py
│       ├── test_auth.py
│       └── test_rate_limit.py
└── integration/
    └── api/
        └── test_chat_flow.py
```

**Structure Decision**: Extends existing `focal/api/` structure with stub files already in place. Uses existing test layout under `tests/unit/` and `tests/integration/`.

## Complexity Tracking

No constitution violations - design follows existing codebase patterns.
