# Research: Project Foundation & Configuration System

**Date**: 2025-11-28
**Feature**: 001-project-foundation

## Overview

This document captures research findings and decisions for implementing the project foundation and configuration system.

---

## 1. Python Package Structure

### Decision
Use a flat package structure with domain-aligned subpackages under `focal/`.

### Rationale
- Follows the documented architecture in `docs/architecture/folder-structure.md`
- "Code follows concepts, not technical layers" philosophy
- Each subpackage is self-contained and independently testable
- Clear mental model: "Where would I look for X? In the folder named after X."

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| src/ layout | Project is a single package, not a monorepo |
| Feature-based modules | Domain alignment is clearer for this architecture |
| Flat modules (no subpackages) | Too many files at one level, harder to navigate |

---

## 2. Configuration Loading Strategy

### Decision
Use `tomllib` (Python 3.11+ built-in) for TOML parsing with `pydantic-settings` for validation and environment variable support.

### Rationale
- `tomllib` is in the standard library (Python 3.11+) - no external dependency for parsing
- `pydantic-settings` provides automatic environment variable binding with `FOCAL_` prefix
- Deep merge strategy allows environment-specific files to override only changed values
- `@lru_cache` on `get_settings()` ensures single load and consistent access

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| YAML configuration | TOML is more explicit, less error-prone (no implicit type coercion) |
| JSON configuration | No comments support, less human-readable |
| Python config files | Security risk, not hot-reloadable |
| dynaconf | Additional dependency when pydantic-settings suffices |
| python-dotenv only | No structured configuration, only flat key-value |

### Implementation Pattern
```
Loading Order:
1. Pydantic model defaults (in code)
2. config/default.toml (base configuration)
3. config/{FOCAL_ENV}.toml (environment overrides)
4. FOCAL_* environment variables (runtime overrides)
```

---

## 3. Pydantic Configuration Models

### Decision
Create separate Pydantic models for each configuration domain, composed into a root `Settings` class.

### Rationale
- Separation of concerns - each domain's config is self-contained
- Type safety - IDE autocomplete and type checking
- Validation at load time - fail fast on invalid configuration
- Documentation - field descriptions serve as inline docs

### Configuration Model Hierarchy
```
Settings (root)
├── api: APIConfig
│   └── rate_limit: RateLimitConfig
├── storage: StorageConfig
│   ├── config: StoreBackendConfig
│   ├── memory: StoreBackendConfig
│   ├── session: StoreBackendConfig
│   └── audit: StoreBackendConfig
├── providers: ProvidersConfig
│   ├── llm: dict[str, LLMProviderConfig]
│   ├── embedding: dict[str, EmbeddingProviderConfig]
│   └── rerank: dict[str, RerankProviderConfig]
├── pipeline: PipelineConfig
│   ├── context_extraction: ContextExtractionConfig
│   ├── retrieval: RetrievalConfig
│   ├── reranking: RerankingConfig
│   ├── llm_filtering: LLMFilteringConfig
│   ├── generation: GenerationConfig
│   └── enforcement: EnforcementConfig
├── selection: SelectionStrategiesConfig
│   ├── rule: SelectionConfig
│   ├── scenario: SelectionConfig
│   └── memory: SelectionConfig
└── observability: ObservabilityConfig
    ├── logging: LoggingConfig
    ├── tracing: TracingConfig
    └── metrics: MetricsConfig
```

---

## 4. Environment Variable Override Pattern

### Decision
Use `FOCAL_` prefix with `__` as nested delimiter for environment variable overrides.

### Rationale
- Standard pydantic-settings pattern
- Clear namespace prevents conflicts with other applications
- Double underscore clearly indicates nesting (single underscore may be in key names)

### Examples
```bash
FOCAL_DEBUG=true                    # settings.debug
FOCAL_API__PORT=9000                # settings.api.port
FOCAL_API__RATE_LIMIT__ENABLED=true # settings.api.rate_limit.enabled
FOCAL_STORAGE__SESSION__BACKEND=redis # settings.storage.session.backend
```

---

## 5. Test Configuration Strategy

### Decision
Use `config/test.toml` with in-memory backends and mock providers for isolated testing.

### Rationale
- Tests should be fast and not require external services
- In-memory implementations provide deterministic behavior
- Same configuration system tests itself (dogfooding)

### Test Configuration Principles
- All storage backends: `inmemory`
- All providers: `mock`
- Debug mode: enabled
- Log level: DEBUG
- Timeouts: shortened for faster test feedback

---

## 6. Project Configuration Files

### Decision
Include standard Python project files with uv as the package manager.

### Files and Purpose
| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool config |
| `.env.example` | Template for environment variables (secrets) |
| `Dockerfile` | Container build for deployment |
| `docker-compose.yml` | Local development stack |
| `Makefile` | Common commands (lint, test, run) |
| `.gitignore` | Exclude build artifacts, .env, __pycache__ |

### pyproject.toml Structure
```toml
[project]
name = "focal"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

---

## 7. Directory Initialization Pattern

### Decision
Create minimal `__init__.py` files that establish the package structure without implementation.

### Rationale
- Allows immediate import verification (`from focal.alignment import ...`)
- Implementation comes in later phases
- Clear separation between structure (this phase) and behavior (later phases)

### Pattern
```python
# focal/alignment/__init__.py
"""Alignment engine: rules, scenarios, context extraction, response generation."""
```

Each `__init__.py` contains only a docstring describing the package's purpose. Exports are added when implementations exist.

---

## Resolved Clarifications

All technical decisions were made based on:
1. Existing architecture documentation (`docs/architecture/`)
2. CLAUDE.md development guidelines
3. Python/Pydantic best practices

No external research or clarifications were needed - the documentation provides sufficient guidance.
