# Documentation Skeleton

This document provides a summary of all the documentation files in the `docs` directory.

---

### `/home/marvin/Projects/soldier/docs/design/scenario-update-methods.md`

This document tackles the problem of updating scenarios (conversation flows) while users are in the middle of them. The key solution is to pre-compute a "Migration Plan" whenever a scenario is updated. This plan defines exactly how to handle users at each step of the old scenario, specifying actions like continuing, collecting new data, or "teleporting" them to a different part of the flow. This approach is performant, reviewable by operators, and auditable. The document details the data models for migration plans, the workflow for generating and applying them, and how the system handles "gap fills" by trying to find required information from conversation history before asking the user. It also covers edge cases like very old sessions and provides a "Composite Migration" strategy to prevent a bad user experience when multiple updates happen in a row.

---

### `docs/design/domain-model.md`

This document defines the core data structures (the "domain model") for the Soldier application using Pydantic. It outlines the main entities, which are categorized into Configuration, Memory, and Session State.

*   **Configuration Entities:** These define the agent's behavior and include `Agent`, `Scenario`, `Rule`, `Template`, and `Variable`. They are versioned and cached.
*   **Memory Entities:** These represent the agent's knowledge and include `Episode` (a single unit of memory), `Entity` (a named thing), and `Relationship` (a connection between entities). These are stored in a graph-like structure.
*   **Session State Entities:** These track the runtime state of a conversation. Key models are `Session` (the overall state of a conversation) and `Turn` (a single user-agent exchange).

The document also defines various enums for state management, base models for tenancy and scoping, and request/response models for the API. It also touches on caching strategies and runtime models used by the `ScenarioFilter` and `RuleFilter`. The models for "Migration Plans" are also included, which are crucial for handling scenario updates.

---

### `docs/design/turn-pipeline.md`

This document describes the "Turn Pipeline", a 10-step process that handles a user's message from receipt to response. The pipeline is designed to be modular and configurable, allowing for different trade-offs between speed and quality.

The key steps are:
1.  **Receive & Reconcile:** Load the session and handle any scenario updates.
2.  **Extract Context:** Understand the user's intent using an LLM or embeddings.
3.  **Retrieve Candidates:** Find relevant rules, scenarios, and memories using vector search.
4.  **Rerank:** Improve the order of candidates using a reranking model.
5.  **Filter (Rules & Scenarios):** Use separate, dedicated filters to decide which rules apply (`RuleFilter`) and how to navigate within a scenario (`ScenarioFilter`).
6.  **Execute Tools:** Run any tools attached to the matched rules.
7.  **Generate Response:** Create the agent's response, potentially using an LLM.
8.  **Enforce Constraints:** Check the response against any hard rules.
9.  **Persist State:** Save the updated session, log the turn, and update memory.
10. **Respond:** Send the final response to the user.

The document also provides details on the configuration of each step, including which AI models to use, and gives examples of different pipeline configurations (e.g., "fastest", "balanced", "maximum quality").

---

### `docs/architecture/alignment-engine.md`

This document describes the "Alignment Engine," the core component of Soldier that ensures agent behavior follows predefined policies. It's a text-based pipeline that processes user messages through a series of steps to ensure predictable and controlled responses.

The pipeline includes:
*   **Input/Output Processing:** Handles multimodal data (audio, images) by converting it to text for the engine and back again for the response.
*   **Alignment Engine Pipeline:** A detailed, multi-stage process for text-based messages:
    1.  **Context Extraction:** Determines the user's true intent.
    2.  **Retrieval:** Fetches relevant rules, scenarios, and memories.
    3.  **Reranking:** Improves the order of the retrieved candidates.
    4.  **LLM Filtering:** A fast LLM decides which rules and scenario transitions are actually applicable.
    5.  **Tool Execution:** Runs tools attached to matched rules.
    6.  **Response Generation:** Creates the agent's response, using a high-quality LLM.
    7.  **Enforcement:** Validates the response against any hard constraints.

A key design principle is the separation of the **RuleFilter** (which rules apply?) from the **ScenarioFilter** (which step in a flow are we in?). The document also details the data models for Rules and Scenarios, the provider interfaces for plugging in different AI models (LLM, Embedding, Rerank), and the "Re-localization" mechanism for recovering from errors in scenario navigation.

---

### `docs/design/customer-profile.md`

This document introduces the "Customer Profile," a persistent, cross-session data store for verified facts about a customer. It addresses the need for a storage layer that sits between temporary session variables and unstructured conversation memory.

Key aspects of the Customer Profile include:

*   **Persistence:** It stores verified customer data (like email, KYC status, or preferences) that persists across multiple conversations and scenarios.
*   **Data Models:** It defines Pydantic models for `CustomerProfile`, `ProfileField` (a single fact), `ProfileAsset` (like an uploaded ID), and `Consent`. Each field tracks its value, source, verification status, and confidence.
*   **Schema Definition:** "Profile Field Definitions" allow developers to define the schema of expected customer data, including validation rules, privacy settings, and extraction hints for LLMs.
*   **Integration:** The profile is tightly integrated with sessions and scenarios. Scenarios can declare required fields, and the `ScenarioFilter` can check the profile before allowing a user to enter a scenario or transition to a new step.
*   **Scenario Migration:** The profile simplifies scenario migrations by providing a reliable source for "gap filling" when new data is required by an updated scenario flow.
*   **Privacy:** The design includes considerations for privacy and compliance (GDPR/CCPA), with features for data export, deletion, and a detailed audit trail.

---

### `docs/architecture/overview.md`

This document provides a high-level overview of the Soldier system's architecture. Soldier is designed as an **API-first, multi-tenant cognitive engine** with a focus on horizontal scalability and pluggability.

Key architectural points include:
*   **Design Principles:** The system is built to be API-first, stateless (no in-memory state), and multi-tenant. Every component, from AI models to storage backends, is designed to be pluggable.
*   **Deployment Modes:** It supports two modes: **Standalone**, where Soldier is the source of truth for configuration, and **External Platform Integration**, where it consumes configuration from an external control plane.
*   **Core Components:**
    *   **API Layer:** Handles external communication, authentication, and validation.
    *   **Alignment Engine:** The central processing pipeline that ensures agent behavior follows defined rules and scenarios.
    *   **Providers:** Abstract interfaces for external AI services (LLMs, Embeddings, Rerankers, etc.).
    *   **Stores:** Abstract interfaces for data persistence, categorized into `ConfigStore`, `MemoryStore`, `SessionStore`, and `AuditStore`.
*   **Request Flow:** The document outlines the detailed, step-by-step process of a conversation turn, from receiving the request to persisting the state and sending a response.
*   **Configuration:** The system uses TOML files for configuration, with validation provided by Pydantic. This allows for different deployment profiles (e.g., minimal, balanced, max quality) and environment variable overrides.
*   **Extensibility:** The architecture is designed to be extensible, allowing new providers and storage backends to be added by implementing the defined interfaces.

---

### `docs/design/api-crud.md`

This document details the RESTful API for performing CRUD (Create, Read, Update, Delete) operations on Soldier's core configuration entities. These endpoints are primarily for "standalone mode," where Soldier manages its own configuration.

Key features of the API include:
*   **Standard RESTful Design:** Uses standard HTTP verbs and resource-based URLs (e.g., `/v1/agents`, `/v1/rules`).
*   **Authentication:** All endpoints are protected and require a JWT containing the `tenant_id`.
*   **Core Resources:** The API provides full CRUD functionality for `Agents`, `Scenarios` (including steps), `Rules`, and `Templates`.
*   **Tool and Variable Management:** It allows for listing available tools and managing which tools and `Variables` are active for a given agent.
*   **Publishing Workflow:** Includes endpoints for managing the lifecycle of agent configurations, such as checking for unpublished changes, publishing a new version, and rolling back to a previous version.
*   **Session Management:** Provides endpoints to list, get, update, and delete conversation sessions, as well as retrieve the turn-by-turn history of a session.
*   **Webhooks:** Supports creating webhooks to receive notifications for various system events like `session.created` or `scenario.completed`.
*   **Common Patterns:** The API uses consistent patterns for pagination, filtering, and error responses across all resources.

---

### `docs/architecture/configuration-toml.md`

This document provides a set of example TOML configuration files that demonstrate how the Soldier application is configured for different environments. It showcases the hierarchical and override-based nature of the configuration system.

*   **`default.toml`:** This file contains the base configuration with sensible defaults for all settings, including API settings, provider configurations, and the full turn pipeline (from input processing to output processing). It defines fallback chains for AI models for each step of the pipeline.
*   **`development.toml`:** This file overrides the default settings for a local development environment. It enables debug mode, disables rate limiting, uses in-memory storage for speed, and selects cheaper, faster AI models for generation.
*   **`production.toml`:** This file configures the system for a production environment. It uses more workers, enables rate limiting, selects the highest quality models, and points to robust, external storage backends like PostgreSQL and Neo4j, with credentials typically loaded from environment variables.
*   **`test.toml`:** This file sets up the configuration for running automated tests. It uses in-memory storage and points all pipeline steps to mock models to ensure fast, isolated, and predictable test execution.

---

### `docs/design/decisions/001-storage-choice.md`

This document is an Architectural Decision Record (ADR) that defines the core architecture for data persistence (Storage) and AI capabilities (Providers).

The key decisions are:

*   **Storage Architecture:** The system's storage is divided into four distinct, domain-aligned interfaces:
    *   **`ConfigStore`:** For agent configuration (rules, scenarios). Read-heavy.
    *   **`MemoryStore`:** For the agent's knowledge graph (episodes, entities). Append-heavy with semantic search needs.
    *   **`SessionStore`:** For runtime conversation state. Uses a two-tier system with a Redis cache for speed and a persistent backend (like PostgreSQL) for durability.
    *   **`AuditStore`:** For immutable, append-only logs of all actions for compliance and debugging.

*   **Provider Architecture:** AI capabilities are abstracted into three provider interfaces:
    *   **`LLMProvider`:** For text generation and understanding.
    *   **`EmbeddingProvider`:** For converting text into vector embeddings for search.
    *   **`RerankProvider`:** For improving the relevance of search results.

This decoupled design allows for pluggable backends. For example, `MemoryStore` could be implemented with Neo4j or PostgreSQL (with pgvector), and `LLMProvider` can be switched between Anthropic, OpenAI, or a local model, all without changing the core application logic. The ADR includes the Python interface definitions for each store and provider, and discusses the pros and cons of this approach.

---

### `docs/architecture/configuration-models.md`

This document defines the Pydantic models that represent Soldier's configuration structure. These models are used to validate the TOML configuration files and provide a typed interface to the settings throughout the application.

The key configuration models defined are:

*   **`DeploymentConfig`:** Specifies the deployment mode (`standalone` or `external`) and its associated settings.
*   **`APIConfig`:** Configures the API server, including host, port, workers, CORS, and rate limiting.
*   **Provider Configurations:** A comprehensive set of models for all AI providers, categorized by modality (LLM, Vision, Embedding, STT, TTS, etc.). A key feature is the use of **fallback chains**, where each pipeline step can specify a list of models to try in order. This provides resilience against provider outages or performance issues. The configuration leverages **LiteLLM** for a unified interface.
*   **`PipelineConfig`:** This is the master model for the turn pipeline. It composes configurations for each step (`InputProcessing`, `ContextExtraction`, `Retrieval`, `Generation`, etc.), allowing for fine-grained control over which models and settings are used at each stage of processing.
*   **`StorageConfig`:** Defines the configuration for all storage backends. It includes separate configurations for `ConfigStore`, `MemoryStore`, `SessionStore`, and `AuditStore`, each allowing a different backend to be selected (e.g., `postgres`, `redis`, `neo4j`, `inmemory`).
*   **Selection Strategy Configurations:** Defines models for various strategies (`Elbow`, `AdaptiveK`, `Entropy`, `Clustering`) used in the retrieval step to dynamically select the best number of results.

---

### `docs/architecture/folder-structure.md`

This document outlines the folder structure of the Soldier codebase, which is organized by conceptual domains rather than technical layers.

The main directories within the `soldier/` package are:

*   **`alignment/`**: The "brain" of the agent, containing the logic for the entire turn pipeline, from context extraction to response generation and enforcement. It's further subdivided by pipeline stage.
*   **`memory/`**: Manages the agent's long-term memory, including the `MemoryStore` interface and its various database implementations (e.g., Neo4j, PostgreSQL).
*   **`conversation/`**: Handles the live state of conversations, primarily through the `SessionStore` interface and its implementations (e.g., Redis).
*   **`audit/`**: Manages the immutable audit trail of all interactions, using the `AuditStore` interface.
*   **`providers/`**: Contains the interfaces and implementations for all external AI services, such as LLMs, embedding models, and rerankers.
*   **`config/`**: Manages the loading and validation of TOML configuration files using Pydantic models.
*   **`api/`**: Defines the external-facing REST and gRPC APIs, including routes, middleware, and request/response models.

The document emphasizes the philosophy of "code follows concepts" and provides a quick reference guide for finding specific parts of the codebase. It also briefly touches on the testing structure, which mirrors the application's layout.

---

### `docs/architecture/configuration.md`

This file acts as a hub, directing to more specific documents about Soldier's configuration architecture. It links to pages covering:
*   An overview of configuration and loading.
*   The Pydantic models used for validation.
*   Examples of TOML configuration files.
*   Secrets management.
*   Usage, validation, and best practices.

---

### `docs/architecture/configuration-overview.md`

This document provides an overview of Soldier's configuration architecture, which is built on TOML files and validated by Pydantic models. The core philosophy is to keep configuration out of the code.

Key aspects of the architecture are:

*   **Folder Structure:** Configuration is split between `config/` for TOML files and `soldier/config/` for the Python code that loads and models the configuration. Secrets are handled separately in a `.env` file at the project root.
*   **Loading Mechanism:** The system uses a hierarchical loading mechanism. It starts with `default.toml`, overrides it with an environment-specific file (e.g., `development.toml`), and finally applies any environment variables (prefixed with `SOLDIER_`). This provides a clear and flexible way to manage settings across different environments.
*   **`Settings` Class:** A central Pydantic `Settings` class serves as the root of the configuration structure. It composes other Pydantic models for different parts of the system (API, pipeline, storage, etc.) and provides a single, type-safe entry point for accessing all configuration values.
*   **Best Practice:** The document reinforces the principle of separating configuration from code and managing secrets securely outside of version control.

---

### `docs/architecture/configuration-usage-validation.md`

This document provides guidance on how to use, validate, and manage the configuration within the Soldier application code.

Key points include:

*   **Accessing Configuration:** It shows how to access the globally loaded and cached settings object (`get_settings()`) to retrieve configuration values in a type-safe manner.
*   **Dependency Injection:** It recommends using a dependency injection pattern (e.g., with FastAPI's `Depends`) to provide specific configuration sections (like `GenerationConfig`) to the components that need them.
*   **Factory Functions:** It demonstrates using factory functions to create objects (like `SelectionStrategy`) based on the loaded configuration, decoupling the object's creation from its usage.
*   **Validation:** Pydantic is used for automatic validation of the configuration at application startup. The document shows how to catch `ValidationError` to provide clear error messages and fail fast if the configuration is invalid.
*   **Best Practices:** It outlines several best practices:
    1.  Avoid hardcoding values; define them in configuration with defaults in the Pydantic models.
    2.  Manage all secrets through environment variables, never in configuration files.
    3.  Use environment-specific files (`development.toml`, `production.toml`) only for overrides, keeping the base configuration in `default.toml`.
    4.  Validate the entire configuration early at application startup.

---

### `docs/architecture/configuration-secrets.md`

This document details the architecture for managing secrets like API keys and database credentials within the Soldier application, emphasizing that **secrets should never be committed to configuration files**.

The key principles and mechanisms are:

*   **Secret Resolution Order:** Secrets are resolved in a specific order of precedence:
    1.  A dedicated secret manager (like AWS Secrets Manager or HashiCorp Vault) in production.
    2.  Standard environment variables (e.g., `ANTHROPIC_API_KEY`).
    3.  Soldier-prefixed environment variables (e.g., `SOLDIER_PIPELINE__GENERATION__MODELS`).
    4.  A local `.env` file for development (which is gitignored).

*   **Development Workflow:** For local development, a `.env` file at the project root is used to store secrets. An `.env.example` file is committed as a template for other developers.

*   **Pydantic Integration:** The Pydantic models use the `SecretStr` type to ensure that secret values are never accidentally logged or exposed in error messages.

*   **Production Environment:** In production, secrets are expected to be injected via environment variables (e.g., in a Docker or Kubernetes environment) or fetched from a dedicated secret manager.

*   **Best Practices:** The document concludes with a summary of best practices, including using standard environment variable names, keeping TOML files secret-free, and using a secret manager in production.

---

### `docs/architecture/api-layer.md`

This document describes the API Layer of the Soldier application, which is the primary entry point for all external interactions. Soldier is positioned as a message processing engine that receives requests from upstream services.

Key aspects of the API layer include:

*   **Multiple Interfaces:** Soldier supports several API interfaces to cater to different use cases:
    *   **REST API (FastAPI):** The primary interface for web applications, offering standard CRUD endpoints, chat processing (including streaming via SSE), and session management.
    *   **gRPC API:** A high-performance interface for service-to-service communication, offering unary, server-streaming, and bi-directional streaming methods.
    *   **MCP (Model Context Protocol) Server:** Allows LLMs (like Claude or Copilot) to use Soldier as a tool provider, exposing its capabilities through a standardized tool schema.

*   **Request/Response Structure:** The document defines the JSON structure for chat requests and responses, which include essential context like `tenant_id`, `agent_id`, and `session_id`.

*   **Idempotency:** The API supports idempotency for safe retries on mutating endpoints (like creating rules or processing messages) via an `Idempotency-Key` header.

*   **Async Operations:** For long-running operations, the API supports webhook callbacks, where Soldier can post the final result to a specified URL.

*   **Rate Limiting and Error Handling:** The API includes per-tenant rate limiting and provides standardized error responses with clear error codes.

*   **Versioning:** The API is versioned through the URL path (e.g., `/v1/`), and deprecation is communicated via response headers.

---

### `docs/architecture/kernel-agent-integration.md`

This document explains how Soldier integrates into the broader External Platform architecture, positioning itself as the core **Cognitive Layer**. It is designed to replace the previous `legacy-adapter` and `legacy-server` components.

Key points of the integration are:

*   **Role in Architecture:** Soldier acts as the "brain," receiving messages from the `Message-Router` and processing them through its turn pipeline. It sits between the channel/routing layers and the tool execution layer.
*   **Configuration Source:** In this integration mode, Soldier is not the source of truth for configuration. Instead, it consumes configuration "bundles" (for agents, rules, scenarios, etc.) that are compiled by a `Publisher` service and stored in Redis.
*   **Hot-Reloading:** Soldier's `Config Watcher` subscribes to a Redis pub/sub channel (`cfg-updated`). When a new configuration is published, the watcher loads the new bundle from Redis into its cache, allowing for configuration updates without a service restart.
*   **Data Flow:** The document details the flow of inbound messages from the `Channel-Gateway` to Soldier and the flow of configuration updates from the `Control Plane` to Soldier via the Publisher and Redis.
*   **Tenant Isolation:** Tenant isolation is maintained at every layer, from Redis key prefixes to `tenant_id` columns in the databases.
*   **Migration Path:** A phased migration path is outlined, starting with deploying Soldier in a shadow mode alongside the old system, followed by a gradual cutover, and finally the complete removal of the legacy components.
*   **Key Differences:** The document concludes by highlighting the major architectural improvements over the previous system (legacy framework), such as being stateless, supporting hot-reloading, native multi-tenancy, and having a more advanced rule and memory system.

---

### `docs/architecture/selection-strategies.md`

This document addresses the "k-selection" problem: how to dynamically decide the optimal number of results to keep from a semantic search instead of using a naive, fixed `top_k`. It introduces the `SelectionStrategy` interface and several implementations to analyze score distributions and find a natural cutoff point.

The implemented strategies are:

*   **Elbow Method:** A simple strategy that cuts off results when there is a significant relative drop in score between consecutive items. Best for queries with a clear separation between relevant and irrelevant results.
*   **Adaptive-K Method:** A more robust, general-purpose strategy that analyzes the "curvature" of the score curve to find where the rate of score drop accelerates, indicating the start of the "noise floor."
*   **Entropy-Based Selection:** Measures the uncertainty (Shannon Entropy) of the score distribution. If scores are tightly clustered (high entropy), it keeps more results because the relevance is ambiguous. If there's a clear winner (low entropy), it keeps fewer.
*   **Clustering-Based Selection:** Groups results into clusters based on their scores (using DBSCAN) and selects the top items from each cluster. This is useful for broad queries that may match multiple distinct topics.
*   **Fixed-K Selection:** The baseline strategy that returns a fixed number of items, used for comparison and as a fallback.

The document also details how these strategies are configured in the TOML files for different retrieval types (rules, scenarios, memory), how they are implemented using Pydantic models, and how they are used within the retrieval pipeline.

---

### `docs/architecture/memory-layer.md`

This document details Soldier's Memory Layer, which provides agents with long-term context and factual grounding. The core of this layer is a **temporal knowledge graph**.

Key concepts include:

*   **Episodes, Entities, and Relationships:** The memory is built from `Episodes` (atomic units of experience like a user message). From these, `Entities` (named things) and `Relationships` (connections between them) are extracted to form the knowledge graph.
*   **Temporal Modeling:** All data in the graph is "bi-temporal," tracking both when a fact became true (`valid_from`/`valid_to`) and when it was recorded (`recorded_at`). This allows for point-in-time queries and handling of contradictions without deleting data.
*   **`MemoryStore` Interface:** The memory layer is accessed through a `MemoryStore` interface, allowing for different pluggable backends like Neo4j, PostgreSQL with pgvector, or MongoDB.
*   **Hybrid Retrieval:** To find relevant context, Soldier uses a hybrid retrieval strategy that combines three methods:
    1.  **Semantic Vector Search:** For finding conceptually similar information.
    2.  **Keyword/BM25 Search:** For precise matching of exact terms.
    3.  **Graph Traversal:** For expanding context by following relationships from known-relevant entities.
*   **Ingestion Pipeline:** A pipeline processes new information by extracting entities and relationships, generating embeddings, updating the graph, and asynchronously creating summaries of long conversations.
*   **Multi-Tenancy:** Memory is strictly isolated between tenants using a `group_id` (a combination of `tenant_id` and `session_id`) on all data.

---

### `docs/vision.md`

This document lays out the vision for Soldier, positioning it as a **production-grade cognitive engine** designed to overcome the limitations of existing conversational AI frameworks.

The core problems it aims to solve are:
1.  **The "Prompt Trap":** Relying solely on large system prompts, which becomes unmanageable and unpredictable at scale.
2.  **The "Code Trap":** Requiring developers to define agent behavior in code (like the previous legacy framework system), which prevents hot-reloading, horizontal scaling, and non-developer access.

Soldier's solution is an **API-first, multi-tenant, and fully persistent architecture**. Its key principles include having zero in-memory state, hot-reloading for all configurations, and native multi-tenancy.

The document highlights the key components Soldier provides, such as API-driven **Scenarios** and **Rules**, an advanced **Memory** system (a feature the previous system lacked), and a post-generation **Enforcement** step to validate responses against hard constraints.

It also clarifies Soldier's role within the broader External Platform ecosystem as the **cognitive layer**, replacing the legacy legacy framework components. The vision is not to build another general-purpose LLM framework but a specialized, scalable, and observable engine for building reliable conversational agents.

---

### `docs/design/decisions/002-rule-matching-strategy.md`

This Architectural Decision Record (ADR) outlines the strategy for matching user messages to the most relevant `Rules`.

The decided approach is a **hybrid strategy** combining the strengths of different search methods:

1.  **Candidate Retrieval:** First, a set of candidate rules is retrieved. This is done by scope (Global, Scenario, Step).
2.  **Hybrid Scoring:** Each candidate is scored using a weighted combination of:
    *   **Vector Similarity (70%):** For semantic understanding (e.g., "money back" matches "refund").
    *   **BM25 Keyword Search (30%):** For precision on exact terms (e.g., product SKUs, error codes).
3.  **Final Ranking:** The hybrid score is then combined with the rule's `priority` and `scope` to produce a final score for ranking.
4.  **Filtering:** Business logic filters are applied (e.g., `enabled` status, `cooldown`, `max_fires`).

This approach provides a balance of semantic relevance and keyword precision, while also respecting the configured business logic of the rules. The ADR also notes that this could be enhanced in the future with LLM-generated patterns for even higher accuracy.

---

### `docs/architecture/observability.md`

This document defines Soldier's logging, tracing, and metrics strategy, designed to integrate seamlessly into the External Platform (kernel_agent) observability stack.

Key aspects include:

*   **Three Pillars:** The observability architecture is built on three pillars:
    *   **Logs:** Structured JSON logs via `structlog` to stdout, with automatic context binding (`tenant_id`, `agent_id`, `session_id`, `turn_id`, `trace_id`).
    *   **Traces:** OpenTelemetry spans for each pipeline step, exported via OTLP to a collector (Jaeger/Tempo).
    *   **Metrics:** Prometheus-compatible `/metrics` endpoint with counters, histograms, and gauges for requests, pipeline latency, LLM calls, rule matches, and errors.

*   **Audit vs. Operational Separation:** Domain events (turn records, rule fires, scenario transitions) are persisted in the `AuditStore` for compliance and long-term analysis. Operational debugging data (provider errors, latency, fallbacks) goes to ephemeral logs.

*   **kernel_agent Integration:** Soldier reuses the `libs/observability` tracing setup from kernel_agent and is configured via the same environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `LOG_LEVEL`).

*   **Privacy:** The document emphasizes never logging secrets or raw PII at INFO level, using `SecretStr` in Pydantic models, and auto-redacting sensitive patterns (email, SSN).

*   **Configuration:** Observability settings are defined in TOML under `[observability.logging]`, `[observability.tracing]`, and `[observability.metrics]`, with environment variable overrides.

---

### `docs/development/testing-strategy.md`

This document defines Soldier's overall testing approach, covering the test pyramid, CI/CD pipeline, coverage requirements, and environment configurations.

Key aspects include:

*   **Test Pyramid:** Defines three layers of tests - Unit (80%, fast, isolated), Integration (15%, with real backends), and E2E (5%, full system validation).
*   **Coverage Requirements:** Sets minimum coverage targets per module (85% line coverage overall, with specific targets for alignment, memory, providers, etc.).
*   **CI/CD Pipeline:** Defines what tests run at each stage - lint/unit on every PR, integration on merge, E2E on release. Includes GitHub Actions workflow configuration.
*   **Integration Test Environment:** Docker Compose setup for PostgreSQL (pgvector), Redis, and Neo4j. Covers database isolation strategies (transaction rollback, truncation, separate databases).
*   **Performance Testing:** Codifies latency targets from architecture docs (e.g., full turn < 1000ms P50) with benchmark test structure.
*   **Contract Testing:** Pattern for verifying that all Store and Provider implementations fulfill their interface contracts.
*   **Test Data Management:** Fixture factory pattern and seed data approach for realistic test scenarios.

---

### `docs/development/unit-testing.md`

This document provides concrete guidance for writing unit tests in the Soldier codebase, including naming conventions, patterns, fixture composition, and templates for testing different component types.

Key aspects include:

*   **Core Principles:** One test = one behavior, fast execution, isolation, determinism, readability.
*   **Naming Conventions:** `test_<method>_<scenario>_<expected_behavior>` pattern for test functions, `Test<MethodOrBehavior>` for test classes.
*   **Arrange-Act-Assert Pattern:** Standard structure for all tests with clear separation of setup, execution, and verification.
*   **Async Testing:** Configuration for `pytest-asyncio`, patterns for async tests, generators, and timeouts.
*   **Fixture Composition:** Building complex test objects through fixture dependencies (tenant → agent → scenario → session → context).
*   **Factory Pattern:** `RuleFactory`, `SessionFactory`, etc. for creating test objects with sensible defaults and overrides.
*   **Mocking Guidelines:** When to mock (external APIs, time) vs. when to use real implementations (stores via in-memory).
*   **Component-Specific Templates:** Detailed examples for testing Stores, Selection Strategies, Pipeline Steps, and Domain Models.
*   **Parametrized Tests:** Using `@pytest.mark.parametrize` for testing multiple input combinations.
*   **Error Testing:** Patterns for testing expected exceptions and error messages.
*   **Coverage:** What to cover, what to skip, and how to use coverage exclusions.
