# Implementation Plan: Project Foundation & Configuration System

**Branch**: `001-project-foundation` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-project-foundation/spec.md`

## Summary

Implement the foundational project skeleton and configuration system for the Focal cognitive engine. This includes:
1. **Phase 0**: Complete folder structure with all domain packages, test directories, and deployment files
2. **Phase 1**: TOML-based configuration loading with Pydantic validation, including all configuration models for the system

## Technical Context

**Language/Version**: Python 3.11+ (required for `tomllib` built-in)
**Primary Dependencies**: pydantic, pydantic-settings, structlog
**Storage**: N/A (configuration phase - no database yet)
**Testing**: pytest, pytest-asyncio, pytest-cov
**Target Platform**: Linux server (Docker/Kubernetes deployment)
**Project Type**: Single Python package with domain subpackages
**Performance Goals**: Configuration loading < 100ms
**Constraints**: No secrets in TOML files; async-first patterns
**Scale/Scope**: 9 domain subpackages, 7 configuration model groups, 3 TOML environment files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution template is not filled in for this project. Using CLAUDE.md as the governing document:

| Principle | Status | Notes |
|-----------|--------|-------|
| Zero In-Memory State | ✅ Pass | Configuration is loaded once and cached via `@lru_cache` - acceptable for static config |
| Multi-Tenant by Design | ✅ Pass | N/A for configuration layer - tenant isolation applies to runtime data |
| Interface-First Design | ✅ Pass | All stores and providers will be abstract interfaces |
| Async-First | ✅ Pass | Configuration loading is sync (acceptable - happens once at startup) |
| Configuration in Files | ✅ Pass | This feature implements this principle |
| uv Package Manager | ✅ Pass | Will use uv for all dependency management |
| No try/except on imports | ✅ Pass | All dependencies will be required, not optional |

**Gate Result**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API contracts for config)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
focal/                        # Project root (already exists)
├── config/                     # TOML configuration files
│   ├── default.toml           # Base defaults
│   ├── development.toml       # Dev overrides
│   ├── staging.toml           # Staging overrides
│   ├── production.toml        # Production overrides
│   └── test.toml              # Test configuration
│
├── focal/                    # Main Python package
│   ├── __init__.py            # Package version, exports
│   ├── alignment/             # The brain
│   │   ├── __init__.py
│   │   ├── context/
│   │   ├── retrieval/
│   │   ├── filtering/
│   │   ├── execution/
│   │   ├── generation/
│   │   ├── enforcement/
│   │   └── models/
│   ├── memory/                # Long-term memory
│   │   ├── __init__.py
│   │   ├── models/
│   │   ├── stores/
│   │   ├── ingestion/
│   │   └── retrieval/
│   ├── conversation/          # Live session state
│   │   ├── __init__.py
│   │   ├── models/
│   │   └── stores/
│   ├── audit/                 # Immutable history
│   │   ├── __init__.py
│   │   ├── models/
│   │   └── stores/
│   ├── observability/         # Logging, tracing, metrics
│   │   └── __init__.py
│   ├── providers/             # External AI services
│   │   ├── __init__.py
│   │   ├── llm/
│   │   ├── embedding/
│   │   └── rerank/
│   ├── api/                   # HTTP/gRPC interfaces
│   │   ├── __init__.py
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── models/
│   ├── config/                # Configuration loading
│   │   ├── __init__.py
│   │   ├── loader.py          # TOML loading + merging
│   │   ├── settings.py        # Root Settings class
│   │   └── models/            # Pydantic config models
│   │       ├── __init__.py
│   │       ├── api.py
│   │       ├── storage.py
│   │       ├── providers.py
│   │       ├── pipeline.py
│   │       ├── selection.py
│   │       ├── observability.py
│   │       └── agent.py
│   └── profile/               # Customer profiles
│       └── __init__.py
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures
│   ├── unit/                  # Fast, isolated tests
│   │   ├── __init__.py
│   │   └── config/
│   │       ├── __init__.py
│   │       ├── test_loader.py
│   │       ├── test_settings.py
│   │       └── test_models.py
│   ├── integration/           # Tests with real backends
│   │   └── __init__.py
│   └── e2e/                   # Full pipeline tests
│       └── __init__.py
│
├── deploy/                     # Deployment configuration
│   ├── docker/
│   │   └── Dockerfile
│   └── kubernetes/
│       └── .gitkeep
│
├── pyproject.toml             # Project metadata, dependencies
├── .env.example               # Environment variable template
├── docker-compose.yml         # Local development stack
├── Makefile                   # Common commands
└── .gitignore                 # Git ignore patterns
```

**Structure Decision**: Single Python package with domain subpackages following the architecture documentation in `docs/architecture/folder-structure.md`.

## Complexity Tracking

> No violations requiring justification - structure follows documented architecture.
