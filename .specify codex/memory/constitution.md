# Project Constitution: Soldier

This document contains the hard rules the AI agent must follow. It is the absolute source of truth for all development. The AI cannot override these rules.

## 1. Core Principles

- **API-first**: All agent configuration and interaction must be exposed via REST/gRPC APIs. No SDK-only features.
- **Zero In-Memory State**: The application must be stateless. All state (configuration, session, memory, audit logs) must reside in external, persistent stores. Any pod must be able to serve any request for any tenant.
- **Multi-Tenant Native**: All data and operations must be isolated by `tenant_id` at every layer of the application (API, storage, cache, logs). There will be no data leakage between tenants.
- **Hot-Reload**: Changes to agent configuration (Rules, Scenarios, etc.) made via the API must take effect instantly without requiring a service restart.
- **Full Auditability**: Every significant decision made by the engine (e.g., rule matches, tool calls, memory retrievals) must be logged for traceability and debugging.

## 2. Technology Stack

- **Programming Language**: Python `3.11` or newer.
- **Package Management**: `uv` is the exclusive tool for managing dependencies and running scripts. `pip` or `poetry` are not to be used. Dependencies are added via `uv add <package>`.
- **Web Framework**: FastAPI is the required web framework for building REST APIs.
- **Core Libraries**:
    - `pydantic` and `pydantic-settings`: For all data modeling and configuration management.
    - `structlog`: For all application logging. Standard `logging` module usage is discouraged.
- **Banned Practices**:
    - Do not wrap imports in `try/except` blocks. Missing dependencies must cause an immediate `ModuleNotFoundError` at startup.

## 3. Architectural Patterns

- **The Four Stores**: The application's data persistence is strictly divided into four domain-aligned stores. Do not mix concerns between them.
    1.  **ConfigStore**: Handles "How should it behave?" (Rules, Scenarios, Templates).
    2.  **MemoryStore**: Handles "What does it remember?" (Episodic and semantic memory).
    3.  **SessionStore**: Handles "What's happening now?" (Active conversation state).
    4.  **AuditStore**: Handles "What happened?" (Immutable log of turns and events).
- **Interface-First Design**:
    - All Stores and Providers must be coded against an abstract interface (`abc.ABC`).
    - First, define the interface in a `base.py` or `store.py` file.
    - Second, create an `InMemory...` implementation for testing.
    - Third, create the production implementation (e.g., `Postgres...`, `Redis...`).
- **Provider Model for External Services**: All external AI services (LLMs, Embeddings, Rerankers, etc.) must be accessed through a `Provider` interface. Do not code directly against a specific service's SDK (e.g., `anthropic`, `openai`).
- **Dependency Injection**: Classes must receive their dependencies in the constructor (`__init__`). Do not instantiate dependencies inside a class.
- **Async Everywhere**: All I/O-bound operations (database calls, API requests, file access) must be `async`. Blocking I/O calls are forbidden in the main application logic.

## 4. Coding Standards

- **Linting & Formatting**: All code must be formatted with `ruff format` and pass `ruff check` using the rules defined in `pyproject.toml`.
- **Type Checking**: All code must pass `mypy` with `strict = true`. All functions and methods must have type annotations.
- **Naming Conventions**:
    - **Classes**: Domain-specific nouns describing what it *is* (e.g., `RuleRetriever`, `MemoryStore`). Avoid generic names like `Manager` or `Handler`.
    - **Methods**: Verb phrases describing the action (e.g., `extract_intent`, `filter_by_scope`).
    - **Clarity over Brevity**: Optimize for code that is easy to read and understand, not code that is fast to write.
- **Secrets Management**:
    - **NEVER** commit secrets to Git.
    - Secrets must not be stored in TOML files.
    - Use `pydantic.SecretStr` for any model field containing a secret.
    - Load secrets from environment variables or a secret manager, not from configuration files.

## 5. Testing Standards

- **Test Pyramid**: Adhere to the 80% Unit, 15% Integration, 5% E2E test ratio.
- **Code Coverage**:
    - Overall coverage must be at or above **85% line coverage** and **80% branch coverage**.
    - Core modules (`soldier/alignment`, `soldier/memory`) require a minimum of **85% line coverage**.
    - CI will fail any pull request that does not meet these coverage standards.
- **Unit Tests**:
    - Must be isolated and not perform any network or database I/O.
    - Must use in-memory implementations of stores (`InMemoryConfigStore`) and mock implementations of providers (`MockLLMProvider`).
- **Integration Tests**:
    - Must test the integration between components and real backends (e.g., PostgreSQL, Redis).
    - Backends must be run via Docker Compose for a consistent test environment.
    - External API calls (e.g., to Anthropic, OpenAI) **must** be recorded using `pytest-recording`. Live API calls are forbidden in CI.
- **Contract Testing**:
    - All implementations of a `Store` or `Provider` interface must be validated against a shared "contract test" class. For example, `PostgresConfigStore` and `InMemoryConfigStore` must both pass the `ConfigStoreContract` tests.
- **Test Data**: Use `Factory` classes (e.g., `RuleFactory`) to generate test data objects.

## 6. Folder Structure

- **Code Follows Concepts**: The folder structure must follow the domain concepts.
    - `soldier/alignment/`: The core cognitive pipeline.
    - `soldier/memory/`: The memory store and related logic.
    - `soldier/conversation/`: The session store and related logic.
    - `soldier/audit/`: The audit store and related logic.
    - `soldier/providers/`: Interfaces and implementations for all external services.
    - `soldier/config/`: Pydantic models for configuration.
    - `soldier/api/`: API routes, request/response models, and middleware.
    - `soldier/observability/`: Logging, tracing, and metrics setup.
- **Test Structure Mirrors Application**: The `tests/unit/` and `tests/integration/` directories must mirror the structure of the `soldier/` directory.

## 7. Observability

- **Structured Logging**: All logs must use `structlog`. Logs must be structured (JSON format in production) and include context (e.g., `tenant_id`, `trace_id`).
- **No PII in Logs**: Do not log Personally Identifiable Information (PII) or secrets at `INFO` level or above. Sensitive data may only be logged at `DEBUG` level.

## 8. Error Handling

- **No Swallowed Errors**: Do not use bare `except Exception: pass`. Errors should be caught specifically, logged with context, and either handled or re-raised.