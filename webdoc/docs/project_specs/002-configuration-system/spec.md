# Feature Specification: Configuration System

**Feature Branch**: `002-configuration-system`
**Created**: 2025-11-28
**Status**: Draft
**Input**: Build the configuration loading system with Pydantic validation for the Soldier cognitive engine.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load Configuration at Startup (Priority: P1)

As a developer deploying Soldier, I need the application to automatically load configuration from TOML files so that I can customize behavior without modifying code.

**Why this priority**: This is the foundational capability - without configuration loading, no other configuration features work. Every deployment needs this.

**Independent Test**: Can be fully tested by starting the application and verifying it reads `config/default.toml` values correctly.

**Acceptance Scenarios**:

1. **Given** a `config/default.toml` file exists with valid settings, **When** the application starts, **Then** all settings are loaded and accessible via `get_settings()`.
2. **Given** no configuration files exist, **When** the application starts, **Then** it uses Pydantic model defaults without crashing.
3. **Given** `config/default.toml` has a syntax error, **When** the application starts, **Then** it fails immediately with a clear error message indicating the file and line number.

---

### User Story 2 - Environment-Specific Overrides (Priority: P1)

As a DevOps engineer, I need to override base configuration per environment (development, staging, production) so that each deployment can have appropriate settings.

**Why this priority**: Critical for any real deployment - you cannot run the same configuration in dev and production.

**Independent Test**: Can be tested by setting `SOLDIER_ENV=staging` and verifying that `config/staging.toml` values override `config/default.toml`.

**Acceptance Scenarios**:

1. **Given** `SOLDIER_ENV=production` and both `default.toml` and `production.toml` exist, **When** the application loads configuration, **Then** values from `production.toml` override those in `default.toml`.
2. **Given** `SOLDIER_ENV=staging` but `staging.toml` does not exist, **When** the application loads configuration, **Then** it uses only `default.toml` values without error.
3. **Given** nested configuration in both files (e.g., `[api.rate_limit]`), **When** configuration is merged, **Then** only the specific nested keys in the environment file are overridden, not the entire section.

---

### User Story 3 - Environment Variable Overrides (Priority: P2)

As an operator, I need to override specific configuration values via environment variables so that I can adjust settings at runtime without modifying files.

**Why this priority**: Essential for container deployments and CI/CD pipelines where file modification is impractical.

**Independent Test**: Can be tested by setting `SOLDIER_API__PORT=9000` and verifying the port setting is overridden.

**Acceptance Scenarios**:

1. **Given** `SOLDIER_DEBUG=true` is set, **When** configuration loads, **Then** the `debug` setting is `True` regardless of TOML values.
2. **Given** `SOLDIER_API__PORT=9000` is set, **When** configuration loads, **Then** `settings.api.port` equals `9000`.
3. **Given** a TOML file sets `api.port = 8000` and `SOLDIER_API__PORT=9000` is set, **When** configuration loads, **Then** the environment variable wins (port is 9000).

---

### User Story 4 - Configuration Validation (Priority: P2)

As a developer, I need invalid configuration to be rejected at startup with clear error messages so that I can fix misconfigurations before they cause runtime failures.

**Why this priority**: Prevents silent failures and cryptic runtime errors. Fail-fast is essential for operability.

**Independent Test**: Can be tested by providing invalid configuration values and verifying descriptive error messages.

**Acceptance Scenarios**:

1. **Given** `api.port = "not-a-number"` in TOML, **When** configuration loads, **Then** validation fails with an error message mentioning "api.port" and "integer".
2. **Given** `api.port = -1` in TOML, **When** configuration loads, **Then** validation fails with an error message about valid port range.
3. **Given** a required nested section is completely missing, **When** configuration loads, **Then** Pydantic defaults are used (no error unless the default itself is invalid).

---

### User Story 5 - Access Configuration in Code (Priority: P2)

As a developer writing Soldier code, I need a simple, type-safe way to access configuration values so that I can use settings throughout the codebase.

**Why this priority**: This is how all other code will interact with configuration - it must be ergonomic and safe.

**Independent Test**: Can be tested by calling `get_settings()` from multiple modules and verifying consistent, typed access.

**Acceptance Scenarios**:

1. **Given** the application has started, **When** any module calls `get_settings()`, **Then** it receives the same cached Settings instance.
2. **Given** settings are loaded, **When** accessing `settings.api.port`, **Then** the value is an integer (not a string).
3. **Given** settings are loaded, **When** accessing `settings.providers.llm`, **Then** I get a properly typed `LLMProviderConfig` object.

---

### Edge Cases

- What happens when TOML contains unknown keys not defined in Pydantic models? (Should be ignored, not cause errors)
- What happens when environment variable format is wrong (e.g., `SOLDIER_API_PORT` instead of `SOLDIER_API__PORT`)? (Should be ignored)
- What happens when configuration directory doesn't exist? (Should use defaults only)
- What happens when `SOLDIER_CONFIG_DIR` points to a non-existent path? (Should fail with clear error)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load configuration from `config/default.toml` as the base configuration.
- **FR-002**: System MUST merge environment-specific TOML files (`config/{SOLDIER_ENV}.toml`) on top of defaults.
- **FR-003**: System MUST support environment variable overrides with `SOLDIER_` prefix and `__` as nested delimiter.
- **FR-004**: System MUST validate all configuration values using Pydantic models at load time.
- **FR-005**: System MUST provide a `get_settings()` function that returns a cached, singleton Settings instance.
- **FR-006**: System MUST fail immediately with descriptive errors when configuration is invalid.
- **FR-007**: System MUST ignore unknown keys in TOML files (forward compatibility).
- **FR-008**: System MUST perform deep merging of nested configuration sections.
- **FR-009**: System MUST provide typed Pydantic models for all configuration sections: API, Pipeline, Providers, Storage, Selection Strategies, and Observability.
- **FR-010**: System MUST support `SOLDIER_ENV` environment variable to select environment (default: "development").
- **FR-011**: System MUST support `SOLDIER_CONFIG_DIR` environment variable to override config directory location.

### Key Entities

- **Settings**: Root configuration object containing all nested configuration sections. Singleton, cached.
- **APIConfig**: API server settings (host, port, CORS, rate limits).
- **PipelineConfig**: Turn pipeline step configurations (context extraction, retrieval, reranking, filtering, generation, enforcement).
- **ProvidersConfig**: AI provider configurations (LLM, embedding, rerank) with named provider instances.
- **StorageConfig**: Storage backend configurations for ConfigStore, MemoryStore, SessionStore, AuditStore.
- **SelectionConfig**: Dynamic k-selection strategy configurations (elbow, adaptive-k, entropy, clustering, fixed-k).
- **ObservabilityConfig**: Logging, tracing, and metrics configurations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Application starts successfully with only `config/default.toml` present within 2 seconds.
- **SC-002**: Application starts successfully with no configuration files present (using Pydantic defaults) within 2 seconds.
- **SC-003**: Invalid configuration causes startup failure with error message that identifies the problematic field within 1 second.
- **SC-004**: All configuration values are accessible via typed Python attributes (no dictionary key access required).
- **SC-005**: Configuration loading and validation completes in under 100ms.
- **SC-006**: 100% of configuration models have complete type annotations.
- **SC-007**: Unit tests cover all configuration loading paths with at least 90% code coverage.

## Assumptions

- TOML is the chosen configuration format (industry standard, human-readable).
- Pydantic v2 is used for validation (modern, fast, good error messages).
- The `tomllib` standard library module (Python 3.11+) is used for TOML parsing.
- Configuration is loaded once at startup and cached (no hot-reload requirement for this phase).
- Secrets are handled separately via `.env` files and environment variables (not in TOML).
