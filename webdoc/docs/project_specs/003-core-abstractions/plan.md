# Implementation Plan: Core Abstractions Layer

**Branch**: `003-core-abstractions` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-core-abstractions/spec.md`

## Summary

Implement the foundational abstraction layer for Soldier including:
- **Phase 2**: Observability foundation (structlog logging, Prometheus metrics, OpenTelemetry tracing)
- **Phase 3**: Domain models (all Pydantic models for core entities)
- **Phase 4**: Store interfaces & in-memory implementations (ConfigStore, MemoryStore, SessionStore, AuditStore, ProfileStore)
- **Phase 5**: Provider interfaces & mock implementations (LLM, Embedding, Rerank)

This layer provides all interfaces, models, and testable implementations for development before production backends are connected.

## Technical Context

**Language/Version**: Python 3.11+ (required for built-in `tomllib`)
**Primary Dependencies**: pydantic, pydantic-settings, structlog, prometheus_client, opentelemetry-sdk, opentelemetry-exporter-otlp
**Storage**: In-memory only (dict-based implementations for testing/development)
**Testing**: pytest, pytest-asyncio, pytest-cov
**Target Platform**: Linux server (containerized)
**Project Type**: Single Python package
**Performance Goals**: 10K entities per store, 1K req/s for mock providers (SC-007, SC-008)
**Constraints**: All I/O async, multi-tenant (tenant_id everywhere), zero in-memory state
**Scale/Scope**: Foundation layer - no external dependencies yet

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution violations detected. The project constitution is a template awaiting customization. Proceeding with standard best practices:

| Gate | Status | Notes |
|------|--------|-------|
| Library-First | PASS | All code organized as soldier/ package |
| Interface-First | PASS | ABCs before implementations |
| Test-First | PASS | TDD approach mandated |
| No Hardcoded Values | PASS | Configuration via TOML + Pydantic |
| Async Everything | PASS | All I/O operations async |
| Multi-Tenant | PASS | tenant_id on every entity/query |

## Project Structure

### Documentation (this feature)

```text
specs/003-core-abstractions/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
soldier/
├── observability/           # Phase 2: Logging, tracing, metrics
│   ├── __init__.py
│   ├── logging.py           # structlog setup, PII redaction
│   ├── tracing.py           # OpenTelemetry setup
│   ├── metrics.py           # Prometheus metrics
│   └── middleware.py        # Request context binding
│
├── alignment/
│   ├── models/              # Phase 3: Alignment domain models
│   │   ├── __init__.py
│   │   ├── rule.py
│   │   ├── scenario.py
│   │   ├── template.py
│   │   ├── variable.py
│   │   └── context.py
│   └── stores/              # Phase 4: ConfigStore
│       ├── __init__.py
│       ├── config_store.py  # ABC interface
│       └── inmemory.py      # InMemoryConfigStore
│
├── memory/
│   ├── models/              # Phase 3: Memory domain models
│   │   ├── __init__.py
│   │   ├── episode.py
│   │   ├── entity.py
│   │   └── relationship.py
│   ├── store.py             # Phase 4: MemoryStore ABC
│   └── stores/
│       ├── __init__.py
│       └── inmemory.py      # InMemoryMemoryStore
│
├── conversation/
│   ├── models/              # Phase 3: Conversation domain models
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── turn.py
│   ├── store.py             # Phase 4: SessionStore ABC
│   └── stores/
│       ├── __init__.py
│       └── inmemory.py      # InMemorySessionStore
│
├── audit/
│   ├── models/              # Phase 3: Audit domain models
│   │   ├── __init__.py
│   │   ├── turn_record.py
│   │   └── event.py
│   ├── store.py             # Phase 4: AuditStore ABC
│   └── stores/
│       ├── __init__.py
│       └── inmemory.py      # InMemoryAuditStore
│
├── profile/
│   ├── __init__.py
│   ├── models.py            # Phase 3: Profile domain models
│   ├── store.py             # Phase 4: ProfileStore ABC
│   └── stores/
│       ├── __init__.py
│       └── inmemory.py      # InMemoryProfileStore
│
└── providers/
    ├── __init__.py
    ├── llm/                 # Phase 5: LLM providers
    │   ├── __init__.py
    │   ├── base.py          # LLMProvider ABC
    │   └── mock.py          # MockLLMProvider
    ├── embedding/           # Phase 5: Embedding providers
    │   ├── __init__.py
    │   ├── base.py          # EmbeddingProvider ABC
    │   └── mock.py          # MockEmbeddingProvider
    ├── rerank/              # Phase 5: Rerank providers
    │   ├── __init__.py
    │   ├── base.py          # RerankProvider ABC
    │   └── mock.py          # MockRerankProvider
    └── factory.py           # Phase 5: Provider factory functions

tests/
├── unit/
│   ├── observability/
│   │   ├── test_logging.py
│   │   └── test_metrics.py
│   ├── alignment/
│   │   ├── test_models.py
│   │   └── stores/
│   │       └── test_inmemory_config.py
│   ├── memory/
│   │   ├── test_models.py
│   │   └── stores/
│   │       └── test_inmemory_memory.py
│   ├── conversation/
│   │   ├── test_models.py
│   │   └── stores/
│   │       └── test_inmemory_session.py
│   ├── audit/
│   │   ├── test_models.py
│   │   └── stores/
│   │       └── test_inmemory_audit.py
│   ├── profile/
│   │   ├── test_models.py
│   │   └── stores/
│   │       └── test_inmemory_profile.py
│   └── providers/
│       ├── test_llm_mock.py
│       ├── test_embedding_mock.py
│       └── test_rerank_mock.py
└── conftest.py              # Shared fixtures
```

**Structure Decision**: Single Python package with domain-aligned modules following existing `soldier/` structure. Tests mirror source structure.

## Complexity Tracking

No constitution violations to justify.

## Implementation Phases

### Phase 2: Observability Foundation

| Component | Files | Key Decisions |
|-----------|-------|---------------|
| Logging | `observability/logging.py` | structlog, JSON/console format, PII redaction via two-tier approach (key-name lookup + regex fallback), contextvars for context propagation |
| Metrics | `observability/metrics.py` | prometheus_client, counters/histograms/gauges as defined in observability.md |
| Tracing | `observability/tracing.py` | OpenTelemetry SDK, OTLP export, span helpers |
| Middleware | `observability/middleware.py` | Context binding for tenant_id, agent_id, session_id, turn_id, trace_id |

### Phase 3: Domain Models

| Domain | Files | Models |
|--------|-------|--------|
| Alignment | `alignment/models/*.py` | Rule, MatchedRule, RuleScope, Scenario, ScenarioStep, StepTransition, Template, TemplateMode, Variable, VariableUpdatePolicy, Context, UserIntent |
| Memory | `memory/models/*.py` | Episode, Entity, Relationship |
| Conversation | `conversation/models/*.py` | Session, Turn, ToolCall, StepVisit, SessionStatus |
| Audit | `audit/models/*.py` | TurnRecord, AuditEvent |
| Profile | `profile/models.py` | CustomerProfile, ChannelIdentity, ProfileField, ProfileFieldSource, ProfileAsset, VerificationLevel, Consent |

### Phase 4: Store Interfaces & In-Memory Implementations

| Store | Interface | In-Memory | Key Methods |
|-------|-----------|-----------|-------------|
| ConfigStore | `alignment/stores/config_store.py` | `alignment/stores/inmemory.py` | CRUD for rules/scenarios/templates/variables, vector_search_rules (cosine similarity) |
| MemoryStore | `memory/store.py` | `memory/stores/inmemory.py` | CRUD for episodes/entities/relationships, vector_search, text_search, traverse_from_entities |
| SessionStore | `conversation/store.py` | `conversation/stores/inmemory.py` | get/save/delete session, list_by_agent |
| AuditStore | `audit/store.py` | `audit/stores/inmemory.py` | save_turn, get_turn, list_turns_by_session, save_event |
| ProfileStore | `profile/store.py` | `profile/stores/inmemory.py` | get_by_customer_id, get_by_channel_identity, update_field, add_asset |

### Phase 5: Provider Interfaces & Mock Implementations

| Provider | Interface | Mock | Key Methods |
|----------|-----------|------|-------------|
| LLMProvider | `providers/llm/base.py` | `providers/llm/mock.py` | generate(), generate_structured(), with fail_after_n/error_rate for failure injection |
| EmbeddingProvider | `providers/embedding/base.py` | `providers/embedding/mock.py` | embed(), embed_batch(), dimensions property, with failure injection |
| RerankProvider | `providers/rerank/base.py` | `providers/rerank/mock.py` | rerank(), with failure injection |
| Factory | `providers/factory.py` | N/A | create_llm_provider(), create_embedding_provider(), create_rerank_provider() |

## Key Implementation Decisions

### From Clarifications (spec.md)

1. **Mock Provider Failure Injection**: All mock providers support `fail_after_n` and `error_rate` configuration for testing error handling paths
2. **Vector Search Similarity**: Cosine similarity for all in-memory vector search operations
3. **Context Propagation**: Python contextvars for async-safe request context binding
4. **PII Redaction**: Two-tier approach - (1) key-name lookup via frozenset (O(1)), (2) regex patterns on string values as fallback

### From Documentation

1. **Multi-Tenant**: All entities have `tenant_id`, all queries filter by tenant
2. **Soft Delete**: `deleted_at` instead of hard deletes
3. **Precomputed Embeddings**: `embedding` and `embedding_model` fields on searchable entities
4. **Async-First**: All store/provider methods are async

## Dependencies to Add

```bash
# Core (already present from Phase 1)
# pydantic, pydantic-settings

# Observability
uv add structlog
uv add prometheus_client
uv add opentelemetry-sdk
uv add opentelemetry-exporter-otlp

# Testing (dev dependencies)
uv add --dev pytest-asyncio
uv add --dev pytest-cov
```

## Success Criteria Mapping

| Criterion | How Verified |
|-----------|--------------|
| SC-001: Models pass validation | Unit tests with valid/invalid data |
| SC-002: Stores pass contract tests | CRUD + tenant isolation tests |
| SC-003: Mock providers valid responses | Unit tests with various inputs |
| SC-004: Valid JSON logging | Test log output parsing |
| SC-005: Metrics endpoint | Test Prometheus format |
| SC-006: 85% line coverage | pytest-cov enforcement |
| SC-007: 10K entities | Performance tests (optional) |
| SC-008: 1K req/s mocks | Performance tests (optional) |
