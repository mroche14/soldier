# Tasks: Project Foundation & Configuration System

**Branch**: `001-project-foundation` | **Date**: 2025-11-28
**Generated from**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md)

## Task Format

```
- [ ] [TaskID] [Priority] [Story] Description
      └─ file: path/to/file.py (if applicable)
      └─ depends: TaskID (if blocked by another task)
```

---

## Phase 1: Setup (Blocking Prerequisites)

- [x] [T001] [P0] [Setup] Initialize pyproject.toml with project metadata and dependencies
      └─ file: pyproject.toml
      └─ deps: pydantic>=2.0, pydantic-settings>=2.0, structlog>=24.0
      └─ dev-deps: pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=4.0, ruff>=0.4, mypy>=1.10

- [x] [T002] [P0] [Setup] Create .gitignore with Python project patterns
      └─ file: .gitignore
      └─ depends: T001

- [x] [T003] [P0] [Setup] Create .env.example template file
      └─ file: .env.example
      └─ depends: T001

---

## Phase 2: US1 - Developer Initializes Project (P1)

### Directory Structure

- [x] [T004] [P1] [US1] Create soldier/ package root with __init__.py
      └─ file: soldier/__init__.py
      └─ depends: T001

- [x] [T005] [P1] [US1] Create soldier/alignment/ subpackage with nested directories
      └─ files: soldier/alignment/__init__.py, soldier/alignment/context/__init__.py, soldier/alignment/retrieval/__init__.py, soldier/alignment/filtering/__init__.py, soldier/alignment/execution/__init__.py, soldier/alignment/generation/__init__.py, soldier/alignment/enforcement/__init__.py, soldier/alignment/models/__init__.py
      └─ depends: T004

- [x] [T006] [P1] [US1] Create soldier/memory/ subpackage with nested directories
      └─ files: soldier/memory/__init__.py, soldier/memory/models/__init__.py, soldier/memory/stores/__init__.py, soldier/memory/ingestion/__init__.py, soldier/memory/retrieval/__init__.py
      └─ depends: T004

- [x] [T007] [P1] [US1] Create soldier/conversation/ subpackage with nested directories
      └─ files: soldier/conversation/__init__.py, soldier/conversation/models/__init__.py, soldier/conversation/stores/__init__.py
      └─ depends: T004

- [x] [T008] [P1] [US1] Create soldier/audit/ subpackage with nested directories
      └─ files: soldier/audit/__init__.py, soldier/audit/models/__init__.py, soldier/audit/stores/__init__.py
      └─ depends: T004

- [x] [T009] [P1] [US1] Create soldier/observability/ subpackage
      └─ file: soldier/observability/__init__.py
      └─ depends: T004

- [x] [T010] [P1] [US1] Create soldier/providers/ subpackage with nested directories
      └─ files: soldier/providers/__init__.py, soldier/providers/llm/__init__.py, soldier/providers/embedding/__init__.py, soldier/providers/rerank/__init__.py
      └─ depends: T004

- [x] [T011] [P1] [US1] Create soldier/api/ subpackage with nested directories
      └─ files: soldier/api/__init__.py, soldier/api/routes/__init__.py, soldier/api/middleware/__init__.py, soldier/api/models/__init__.py
      └─ depends: T004

- [x] [T012] [P1] [US1] Create soldier/config/ subpackage with models/ subdirectory
      └─ files: soldier/config/__init__.py, soldier/config/models/__init__.py
      └─ depends: T004

- [x] [T013] [P1] [US1] Create soldier/profile/ subpackage
      └─ file: soldier/profile/__init__.py
      └─ depends: T004

### Test Structure

- [x] [T014] [P1] [US1] Create tests/ root with conftest.py
      └─ files: tests/__init__.py, tests/conftest.py
      └─ depends: T001

- [x] [T015] [P1] [US1] Create tests/unit/ directory structure
      └─ files: tests/unit/__init__.py, tests/unit/config/__init__.py
      └─ depends: T014

- [x] [T016] [P1] [US1] Create tests/integration/ directory structure
      └─ file: tests/integration/__init__.py
      └─ depends: T014

- [x] [T017] [P1] [US1] Create tests/e2e/ directory structure
      └─ file: tests/e2e/__init__.py
      └─ depends: T014

### Deployment Structure

- [x] [T018] [P1] [US1] Create deploy/ directory with docker/ and kubernetes/ subdirectories
      └─ files: deploy/docker/Dockerfile, deploy/kubernetes/.gitkeep
      └─ depends: T001

- [x] [T019] [P1] [US1] Create docker-compose.yml for local development
      └─ file: docker-compose.yml
      └─ depends: T018

- [x] [T020] [P1] [US1] Create Makefile with common development commands
      └─ file: Makefile
      └─ depends: T001

### Config Directory

- [x] [T021] [P1] [US1] Create config/ directory at project root
      └─ file: config/.gitkeep
      └─ depends: T001

---

## Phase 3: US2 - Developer Configures for Local Development (P2)

### Configuration Models

- [x] [T022] [P2] [US2] Implement RateLimitConfig Pydantic model
      └─ file: soldier/config/models/api.py
      └─ depends: T012
      └─ fields: enabled (bool), requests_per_minute (int), burst_size (int)
      └─ validation: requests_per_minute > 0, burst_size >= 0

- [x] [T023] [P2] [US2] Implement APIConfig Pydantic model
      └─ file: soldier/config/models/api.py
      └─ depends: T022
      └─ fields: host (str), port (int), workers (int), cors_origins (list[str]), cors_allow_credentials (bool), rate_limit (RateLimitConfig)
      └─ validation: port 1-65535, workers >= 1

- [x] [T024] [P2] [US2] Implement StoreBackendConfig Pydantic model
      └─ file: soldier/config/models/storage.py
      └─ depends: T012
      └─ fields: backend (str), connection_url (str|None), pool_size (int), pool_timeout (int)
      └─ validation: backend in [inmemory, postgres, redis, mongodb, neo4j, dynamodb]

- [x] [T025] [P2] [US2] Implement StorageConfig Pydantic model
      └─ file: soldier/config/models/storage.py
      └─ depends: T024
      └─ fields: config (StoreBackendConfig), memory (StoreBackendConfig), session (StoreBackendConfig), audit (StoreBackendConfig)

- [x] [T026] [P2] [US2] Implement LLMProviderConfig Pydantic model
      └─ file: soldier/config/models/providers.py
      └─ depends: T012
      └─ fields: provider (str), model (str), api_key (SecretStr|None), base_url (str|None), max_tokens (int), temperature (float), timeout (int)
      └─ validation: provider in [anthropic, openai, bedrock, vertex, ollama, mock], temperature 0.0-2.0

- [x] [T027] [P2] [US2] Implement EmbeddingProviderConfig Pydantic model
      └─ file: soldier/config/models/providers.py
      └─ depends: T012
      └─ fields: provider (str), model (str), api_key (SecretStr|None), dimensions (int), batch_size (int)
      └─ validation: provider in [openai, cohere, voyage, sentence_transformers, mock]

- [x] [T028] [P2] [US2] Implement RerankProviderConfig Pydantic model
      └─ file: soldier/config/models/providers.py
      └─ depends: T012
      └─ fields: provider (str), model (str), api_key (SecretStr|None), top_k (int)
      └─ validation: provider in [cohere, voyage, cross_encoder, mock]

- [x] [T029] [P2] [US2] Implement ProvidersConfig Pydantic model
      └─ file: soldier/config/models/providers.py
      └─ depends: T026, T027, T028
      └─ fields: default_llm (str), default_embedding (str), default_rerank (str), llm (dict), embedding (dict), rerank (dict)

- [x] [T030] [P2] [US2] Implement SelectionConfig Pydantic model
      └─ file: soldier/config/models/selection.py
      └─ depends: T012
      └─ fields: strategy (str), min_score (float), max_k (int), params (dict)
      └─ validation: strategy in [elbow, adaptive_k, entropy, clustering, fixed_k], min_score 0.0-1.0

- [x] [T031] [P2] [US2] Implement SelectionStrategiesConfig Pydantic model
      └─ file: soldier/config/models/selection.py
      └─ depends: T030
      └─ fields: rule (SelectionConfig), scenario (SelectionConfig), memory (SelectionConfig)

- [x] [T032] [P2] [US2] Implement ContextExtractionConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T012
      └─ fields: enabled (bool), mode (str), llm_provider (str), history_turns (int)
      └─ validation: mode in [llm, embedding, hybrid]

- [x] [T033] [P2] [US2] Implement RetrievalConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T030
      └─ fields: enabled (bool), embedding_provider (str), max_k (int), rule_selection (SelectionConfig), scenario_selection (SelectionConfig), memory_selection (SelectionConfig)

- [x] [T034] [P2] [US2] Implement RerankingConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T012
      └─ fields: enabled (bool), rerank_provider (str), top_k (int)

- [x] [T035] [P2] [US2] Implement LLMFilteringConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T012
      └─ fields: enabled (bool), llm_provider (str), batch_size (int)

- [x] [T036] [P2] [US2] Implement GenerationConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T012
      └─ fields: enabled (bool), llm_provider (str), temperature (float), max_tokens (int)

- [x] [T037] [P2] [US2] Implement EnforcementConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T012
      └─ fields: enabled (bool), self_critique_enabled (bool), max_retries (int)

- [x] [T038] [P2] [US2] Implement PipelineConfig Pydantic model
      └─ file: soldier/config/models/pipeline.py
      └─ depends: T032, T033, T034, T035, T036, T037
      └─ fields: context_extraction, retrieval, reranking, llm_filtering, generation, enforcement

- [x] [T039] [P2] [US2] Implement LoggingConfig Pydantic model
      └─ file: soldier/config/models/observability.py
      └─ depends: T012
      └─ fields: level (str), format (str), include_trace_id (bool)
      └─ validation: level in [DEBUG, INFO, WARNING, ERROR, CRITICAL], format in [json, console]

- [x] [T040] [P2] [US2] Implement TracingConfig Pydantic model
      └─ file: soldier/config/models/observability.py
      └─ depends: T012
      └─ fields: enabled (bool), service_name (str), otlp_endpoint (str|None), sample_rate (float)
      └─ validation: sample_rate 0.0-1.0

- [x] [T041] [P2] [US2] Implement MetricsConfig Pydantic model
      └─ file: soldier/config/models/observability.py
      └─ depends: T012
      └─ fields: enabled (bool), port (int), path (str)
      └─ validation: port 1-65535

- [x] [T042] [P2] [US2] Implement ObservabilityConfig Pydantic model
      └─ file: soldier/config/models/observability.py
      └─ depends: T039, T040, T041
      └─ fields: logging (LoggingConfig), tracing (TracingConfig), metrics (MetricsConfig)

- [x] [T043] [P2] [US2] Implement AgentConfig Pydantic model
      └─ file: soldier/config/models/agent.py
      └─ depends: T012
      └─ fields: Agent-level configuration overrides

### Root Settings Model

- [x] [T044] [P2] [US2] Implement Settings root Pydantic model
      └─ file: soldier/config/settings.py
      └─ depends: T023, T025, T029, T031, T038, T042
      └─ fields: app_name (str), debug (bool), log_level (str), api, storage, providers, pipeline, selection, observability

### Configuration Loader

- [x] [T045] [P2] [US2] Implement TOML loader with deep merge functionality
      └─ file: soldier/config/loader.py
      └─ depends: T044
      └─ functions: load_toml(), deep_merge(), get_config_dir()

- [x] [T046] [P2] [US2] Implement get_settings() function with @lru_cache
      └─ file: soldier/config/__init__.py
      └─ depends: T045
      └─ exports: get_settings, Settings

### TOML Configuration Files

- [x] [T047] [P2] [US2] Create config/default.toml with base defaults
      └─ file: config/default.toml
      └─ depends: T021
      └─ sections: api, storage, providers, pipeline, selection, observability

- [x] [T048] [P2] [US2] Create config/development.toml with dev overrides
      └─ file: config/development.toml
      └─ depends: T047
      └─ overrides: debug=true, log_level=DEBUG

- [x] [T049] [P2] [US2] Create config/staging.toml with staging overrides
      └─ file: config/staging.toml
      └─ depends: T047

- [x] [T050] [P2] [US2] Create config/production.toml with production overrides
      └─ file: config/production.toml
      └─ depends: T047

---

## Phase 4: US3 - Developer Adds Config Section (P3)

- [x] [T051] [P3] [US3] Export all config models from soldier/config/models/__init__.py
      └─ file: soldier/config/models/__init__.py
      └─ depends: T042, T043
      └─ exports: All *Config classes

---

## Phase 5: US4 - Developer Runs Tests Locally (P3)

### Test Configuration

- [x] [T052] [P3] [US4] Create config/test.toml with test-appropriate config
      └─ file: config/test.toml
      └─ depends: T047
      └─ overrides: all storage backends="inmemory", all providers="mock", debug=true

### Unit Tests

- [x] [T053] [P3] [US4] Write unit tests for TOML loader
      └─ file: tests/unit/config/test_loader.py
      └─ depends: T045
      └─ tests: load_toml(), deep_merge(), environment selection, missing file handling

- [x] [T054] [P3] [US4] Write unit tests for Settings class
      └─ file: tests/unit/config/test_settings.py
      └─ depends: T046
      └─ tests: get_settings(), caching, env var overrides, SOLDIER_ prefix handling

- [x] [T055] [P3] [US4] Write unit tests for API config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T023
      └─ tests: APIConfig validation, RateLimitConfig validation, port range, defaults

- [x] [T056] [P3] [US4] Write unit tests for Storage config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T025
      └─ tests: StorageConfig validation, backend enum, pool settings

- [x] [T057] [P3] [US4] Write unit tests for Provider config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T029
      └─ tests: LLMProviderConfig validation, temperature range, SecretStr handling

- [x] [T058] [P3] [US4] Write unit tests for Pipeline config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T038
      └─ tests: PipelineConfig defaults, step enabling/disabling

- [x] [T059] [P3] [US4] Write unit tests for Selection config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T031
      └─ tests: SelectionConfig validation, strategy enum, min_score range

- [x] [T060] [P3] [US4] Write unit tests for Observability config models
      └─ file: tests/unit/config/test_models.py
      └─ depends: T042
      └─ tests: ObservabilityConfig defaults, log level enum, sample_rate range

### Test Fixtures

- [x] [T061] [P3] [US4] Add configuration test fixtures to conftest.py
      └─ file: tests/conftest.py
      └─ depends: T014
      └─ fixtures: tmp_config_dir, mock_toml_files, env_override

---

## Phase 6: Polish & Cross-cutting

- [ ] [T062] [P3] [Polish] Verify all 9 domain packages are importable
      └─ depends: T004-T013
      └─ test: `from soldier.{domain} import ...` for all 9 domains

- [ ] [T063] [P3] [Polish] Verify configuration loads in under 100ms
      └─ depends: T046
      └─ test: Benchmark get_settings() call time

- [ ] [T064] [P3] [Polish] Verify 85% test coverage for config modules
      └─ depends: T053-T060
      └─ command: `uv run pytest --cov=soldier/config --cov-report=term-missing`

- [ ] [T065] [P3] [Polish] Run ruff linting and fix any issues
      └─ depends: T004-T060
      └─ command: `uv run ruff check soldier/ tests/`

- [ ] [T066] [P3] [Polish] Run mypy type checking and fix any issues
      └─ depends: T004-T060
      └─ command: `uv run mypy soldier/`

---

## Summary

| Phase | Tasks | Priority | Description |
|-------|-------|----------|-------------|
| 1 | T001-T003 | P0 | Setup: pyproject.toml, .gitignore, .env.example |
| 2 | T004-T021 | P1 | US1: Project structure (directories, tests, deploy) |
| 3 | T022-T050 | P2 | US2: Config models, loader, TOML files |
| 4 | T051 | P3 | US3: Config extensibility (exports) |
| 5 | T052-T061 | P3 | US4: Test config and unit tests |
| 6 | T062-T066 | P3 | Polish: Verification and quality |

**Total Tasks**: 66
**Critical Path**: T001 → T004 → T012 → T044 → T046 → T053-T060

---

## Acceptance Criteria Mapping

| Criteria | Tasks |
|----------|-------|
| SC-001: Clone + test in 60s | T001, T014, T020 |
| SC-002: 9 packages importable | T004-T013, T062 |
| SC-003: Config load < 100ms | T045, T046, T063 |
| SC-004: 100% values have defaults | T022-T044, T047 |
| SC-005: Invalid config detected at startup | T017 (validation), T053-T060 |
| SC-006: 85% test coverage | T053-T060, T064 |
| SC-007: Env var override support | T045, T054 |
