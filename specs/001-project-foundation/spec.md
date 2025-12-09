# Feature Specification: Project Foundation & Configuration System

**Feature Branch**: `001-project-foundation`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Implement Phase 0 (Project Skeleton & Foundation) and Phase 1 (Configuration System) - Create complete folder structure, project configuration files, TOML configuration loader with Pydantic validation, and all configuration models"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Initializes Project (Priority: P1)

A developer clones the repository and wants to start developing. They need a properly organized project structure with all necessary directories, package configuration, and development tooling in place so they can immediately begin writing code.

**Why this priority**: Without the foundational project structure, no other development work can proceed. This is the prerequisite for all other features.

**Independent Test**: Can be tested by cloning the repository, running `uv sync` to install dependencies, and verifying all package directories exist with proper `__init__.py` files.

**Acceptance Scenarios**:

1. **Given** a fresh clone of the repository, **When** I run `uv sync`, **Then** all dependencies are installed and the `focal` package is importable
2. **Given** the project structure exists, **When** I look for a specific domain (e.g., alignment, memory), **Then** I find a corresponding directory with `__init__.py`
3. **Given** the test structure exists, **When** I run `uv run pytest`, **Then** the test framework initializes successfully (even with no tests yet)

---

### User Story 2 - Developer Configures Application for Local Development (Priority: P2)

A developer wants to configure the Focal application for local development. They need to set environment-specific configuration values (database URLs, log levels, feature flags) through TOML files, with sensible defaults for development.

**Why this priority**: Configuration loading is required before any runtime component can work. It enables per-environment customization essential for development workflow.

**Independent Test**: Can be tested by setting `FOCAL_ENV=development`, calling `get_settings()`, and verifying returned values match development TOML overrides.

**Acceptance Scenarios**:

1. **Given** default.toml and development.toml exist, **When** I load settings with `FOCAL_ENV=development`, **Then** development values override defaults
2. **Given** a Pydantic model with defaults, **When** no TOML file specifies that value, **Then** the Pydantic default is used
3. **Given** an environment variable `FOCAL_API__PORT=9000`, **When** I load settings, **Then** the API port is 9000 (overriding TOML)

---

### User Story 3 - Developer Adds New Configuration Section (Priority: P3)

A developer needs to add a new configurable component to Focal. They want a consistent pattern for defining configuration models with validation, defaults, and environment override support.

**Why this priority**: Extensibility of configuration is important but not blocking. Once the base system works, new sections can be added incrementally.

**Independent Test**: Can be tested by creating a new Pydantic model, adding it to Settings class, writing values to TOML, and verifying they load correctly.

**Acceptance Scenarios**:

1. **Given** I create a new Pydantic model for configuration, **When** I add it to the Settings class, **Then** it integrates with the loading system automatically
2. **Given** I define validation rules in my model (e.g., port > 0), **When** invalid TOML values are provided, **Then** a validation error is raised at startup
3. **Given** I nest configuration sections, **When** I use `FOCAL_SECTION__SUBSECTION__KEY=value`, **Then** the nested value is overridden

---

### User Story 4 - Developer Runs Tests Locally (Priority: P3)

A developer wants to run tests in isolation with a test-specific configuration (in-memory backends, lower timeouts). They need a test.toml that configures all stores to use in-memory implementations.

**Why this priority**: Test isolation is important for reliable development but can use defaults initially. This story ensures proper test configuration.

**Independent Test**: Can be tested by setting `FOCAL_ENV=test`, loading settings, and verifying storage backends are configured as "inmemory".

**Acceptance Scenarios**:

1. **Given** test.toml exists, **When** I set `FOCAL_ENV=test` and load settings, **Then** storage backends use in-memory implementations
2. **Given** test environment is active, **When** I import configuration, **Then** debug mode is enabled and log level is DEBUG

---

### Edge Cases

- What happens when config/default.toml is missing? System raises clear error at startup.
- What happens when TOML syntax is invalid? System raises descriptive parse error with file location.
- What happens when environment variable format is wrong (missing `__` delimiter)? System ignores malformed variables and logs warning.
- What happens when required configuration value has no default and is not provided? Pydantic validation fails with clear field error.
- What happens when FOCAL_CONFIG_DIR points to non-existent directory? System raises clear error indicating directory not found.

## Requirements *(mandatory)*

### Functional Requirements

**Project Structure (Phase 0)**

- **FR-001**: System MUST have a `focal/` Python package with proper `__init__.py` at each level
- **FR-002**: System MUST have domain-specific subpackages: `alignment/`, `memory/`, `conversation/`, `audit/`, `observability/`, `providers/`, `api/`, `config/`, `profile/`
- **FR-003**: System MUST have a `tests/` directory mirroring the `focal/` structure with `unit/`, `integration/`, and `e2e/` subdirectories
- **FR-004**: System MUST have a `config/` directory at project root for TOML configuration files
- **FR-005**: System MUST have a `deploy/` directory with `docker/` and `kubernetes/` subdirectories
- **FR-006**: System MUST have a `pyproject.toml` with project metadata and dependencies
- **FR-007**: System MUST have a `.env.example` template file for environment variables
- **FR-008**: System MUST have a `Dockerfile` for container builds
- **FR-009**: System MUST have a `docker-compose.yml` for local development stack
- **FR-010**: System MUST have a `Makefile` with common development commands

**Configuration Loading (Phase 1)**

- **FR-011**: System MUST load TOML configuration from `config/` directory
- **FR-012**: System MUST support environment-specific TOML files (default.toml, development.toml, staging.toml, production.toml, test.toml)
- **FR-013**: System MUST determine environment from `FOCAL_ENV` variable, defaulting to "development"
- **FR-014**: System MUST deep-merge configuration: defaults -> environment-specific -> environment variables
- **FR-015**: System MUST support environment variable overrides with `FOCAL_` prefix and `__` as nested delimiter
- **FR-016**: System MUST provide a `get_settings()` function returning cached Settings instance
- **FR-017**: System MUST validate all configuration through Pydantic models at load time

**Configuration Models (Phase 1)**

- **FR-018**: System MUST have APIConfig model with host, port, CORS, and rate limit settings
- **FR-019**: System MUST have StorageConfig models for ConfigStore, MemoryStore, SessionStore, and AuditStore backends
- **FR-020**: System MUST have ProviderConfig models for LLM, Embedding, and Rerank providers
- **FR-021**: System MUST have PipelineConfig models for each pipeline step (context extraction, retrieval, reranking, LLM filtering, generation, enforcement)
- **FR-022**: System MUST have SelectionConfig models for selection strategies (elbow, adaptive_k, entropy, clustering, fixed_k)
- **FR-023**: System MUST have ObservabilityConfig model for logging, tracing, and metrics settings
- **FR-024**: System MUST have AgentConfig model for per-agent configuration overrides

**Default TOML Configuration (Phase 1)**

- **FR-025**: System MUST provide `config/default.toml` with sensible defaults for all configuration sections
- **FR-026**: System MUST provide `config/development.toml` with development-appropriate overrides (debug enabled, verbose logging)
- **FR-027**: System MUST provide `config/test.toml` with test-appropriate configuration (in-memory backends)

**Configuration Tests (Phase 1)**

- **FR-028**: System MUST have unit tests for TOML loader functionality
- **FR-029**: System MUST have unit tests for Settings class and `get_settings()` function
- **FR-030**: System MUST have unit tests for all configuration Pydantic models

### Key Entities

- **Settings**: Root configuration object containing all nested configuration sections. Provides access to application-wide settings.
- **APIConfig**: Configuration for the HTTP API server including bind address, CORS policies, and rate limits.
- **StorageConfig**: Configuration for each of the four stores (Config, Memory, Session, Audit) specifying backend type and connection details.
- **ProviderConfig**: Configuration for AI providers (LLM, Embedding, Rerank) specifying provider type, model, and credentials reference.
- **PipelineConfig**: Configuration for each step in the alignment pipeline specifying whether enabled and which providers to use.
- **SelectionConfig**: Configuration for retrieval selection strategies specifying algorithm and parameters.
- **ObservabilityConfig**: Configuration for logging level, tracing endpoints, and metrics collection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can clone the repository and run `uv sync && uv run pytest` within 60 seconds without errors
- **SC-002**: All 9 domain subpackages are importable as Python modules (e.g., `from focal.alignment import ...`)
- **SC-003**: Configuration loading completes in under 100 milliseconds
- **SC-004**: 100% of configuration values have either Pydantic defaults or TOML defaults
- **SC-005**: Invalid configuration (missing required fields, wrong types) is detected at application startup, not at runtime
- **SC-006**: Unit test coverage for configuration modules reaches 85% line coverage
- **SC-007**: A developer can override any configuration value via environment variable without modifying files

## Assumptions

- Python 3.11+ is the minimum supported version (for `tomllib` built-in)
- `uv` is used as the package manager (as specified in CLAUDE.md)
- The project follows async-first patterns (as specified in architecture docs)
- Secrets are stored in `.env` files or environment variables, never in TOML files
- The configuration system is loaded once at startup and cached (not hot-reloadable)
