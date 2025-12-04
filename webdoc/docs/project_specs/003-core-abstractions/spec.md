# Feature Specification: Core Abstractions Layer

**Feature Branch**: `003-core-abstractions`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Core Abstractions Layer - Phases 2-5: Observability foundation, domain models, store interfaces with in-memory implementations, and provider interfaces with mock implementations"

## Overview

This specification covers the foundational abstractions that all other Soldier components build upon. It encompasses four implementation phases:

- **Phase 2**: Observability Foundation (logging, tracing, metrics)
- **Phase 3**: Domain Models (all Pydantic models for core entities)
- **Phase 4**: Store Interfaces & In-Memory Implementations
- **Phase 5**: Provider Interfaces & Mock Implementations

These phases are grouped because they form the complete "abstraction layer" - once complete, all interfaces are defined, all domain types exist, and testable in-memory/mock implementations are available for development.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Debugging with Structured Logs (Priority: P1)

A developer working on Soldier needs to debug issues in the turn processing pipeline. They require structured, consistent logging that includes all relevant context (tenant, agent, session, turn IDs) without manually passing this context everywhere.

**Why this priority**: Without observability, debugging any subsequent feature is extremely difficult. This is the first thing needed before building anything else.

**Independent Test**: Can be fully tested by initializing logging, processing a mock request, and verifying JSON log output contains all required context fields and proper formatting.

**Acceptance Scenarios**:

1. **Given** logging is configured for production (JSON format), **When** a log message is emitted with bound context, **Then** the output is valid JSON containing timestamp, level, event, and all bound context fields (tenant_id, agent_id, session_id, turn_id, trace_id).

2. **Given** logging is configured for development (console format), **When** a log message is emitted, **Then** the output is human-readable with colors and proper formatting.

3. **Given** a log message contains PII patterns (email, phone, SSN), **When** PII redaction is enabled, **Then** the sensitive values are masked in the output.

---

### User Story 2 - Operator Monitoring System Health (Priority: P1)

An operations engineer needs to monitor Soldier's health and performance through standard tooling (Prometheus/Grafana). They need metrics for request counts, latencies, error rates, and resource usage.

**Why this priority**: Metrics are essential for production operation and must be available from the start.

**Independent Test**: Can be fully tested by simulating various operations and verifying metrics are correctly incremented/recorded, then scraping the /metrics endpoint.

**Acceptance Scenarios**:

1. **Given** the metrics system is enabled, **When** a request is processed, **Then** request count, latency histogram, and status counters are updated with correct labels.

2. **Given** the metrics endpoint is exposed, **When** Prometheus scrapes /metrics, **Then** all defined metrics are returned in Prometheus text format.

---

### User Story 3 - Developer Creating and Validating Domain Entities (Priority: P1)

A developer building features needs to create and manipulate core domain objects (Rules, Scenarios, Sessions, Episodes) with proper validation, type safety, and serialization.

**Why this priority**: All business logic operates on domain models. Without them, no feature can be implemented.

**Independent Test**: Can be fully tested by instantiating each model with valid/invalid data and verifying validation behavior, serialization, and computed properties.

**Acceptance Scenarios**:

1. **Given** a Rule model definition, **When** a developer creates a Rule with valid data, **Then** the model is instantiated with all fields properly typed and defaults applied.

2. **Given** a Rule model with validation constraints, **When** invalid data is provided (e.g., priority > 100), **Then** a validation error is raised with a clear message.

3. **Given** a model with timestamps, **When** the model is created without explicit timestamps, **Then** created_at and updated_at are automatically set to the current time.

4. **Given** a model with soft delete support, **When** deleted_at is None, **Then** the entity is considered active; when set, it's considered deleted.

---

### User Story 4 - Developer Storing and Retrieving Configuration (Priority: P2)

A developer needs to store and retrieve agent configuration (rules, scenarios, templates, variables) through a consistent interface that supports different backends.

**Why this priority**: Configuration storage is required for the alignment pipeline but can use in-memory implementation initially.

**Independent Test**: Can be fully tested by performing CRUD operations on the in-memory implementation and verifying data persistence, queries, and tenant isolation.

**Acceptance Scenarios**:

1. **Given** an in-memory ConfigStore, **When** a rule is saved and then retrieved by ID, **Then** the retrieved rule matches the saved rule exactly.

2. **Given** rules with different tenant_ids, **When** querying rules for tenant A, **Then** only rules belonging to tenant A are returned.

3. **Given** rules with embeddings, **When** performing vector search, **Then** rules are returned ordered by similarity score (descending).

4. **Given** a rule with scope=STEP and scope_id set, **When** querying with scope filter, **Then** only matching scoped rules are returned.

---

### User Story 5 - Developer Storing and Retrieving Memory (Priority: P2)

A developer needs to store conversation episodes and entities, then retrieve them through semantic search and graph traversal.

**Why this priority**: Memory storage enables the knowledge graph but can use in-memory implementation initially.

**Independent Test**: Can be fully tested by adding episodes/entities to the in-memory store and verifying retrieval via vector search, text search, and relationship traversal.

**Acceptance Scenarios**:

1. **Given** an in-memory MemoryStore with episodes, **When** vector search is performed, **Then** episodes are returned ordered by embedding similarity.

2. **Given** an in-memory MemoryStore with entities and relationships, **When** traversing from an entity, **Then** related entities within the specified depth are returned.

3. **Given** episodes with a specific group_id, **When** delete_by_group is called, **Then** all episodes, entities, and relationships for that group are removed.

---

### User Story 6 - Developer Managing Session State (Priority: P2)

A developer needs to store and retrieve active session state with fast access patterns suitable for real-time conversation processing.

**Why this priority**: Session management is required for conversation tracking but can use in-memory implementation initially.

**Independent Test**: Can be fully tested by performing session CRUD operations and verifying state persistence, retrieval, and listing.

**Acceptance Scenarios**:

1. **Given** an in-memory SessionStore, **When** a session is saved and retrieved, **Then** the complete session state including scenario tracking, rule fires, and variables is preserved.

2. **Given** multiple sessions for different agents, **When** listing sessions by agent, **Then** only sessions for the specified agent are returned.

---

### User Story 7 - Developer Recording Audit Events (Priority: P2)

A developer needs to record turn records and audit events for compliance and debugging purposes.

**Why this priority**: Audit logging is required for compliance but can use in-memory implementation initially.

**Independent Test**: Can be fully tested by saving turn records and events, then querying them by session, tenant, and time range.

**Acceptance Scenarios**:

1. **Given** an in-memory AuditStore, **When** a turn record is saved, **Then** it can be retrieved by turn_id and includes all processing metadata.

2. **Given** multiple turns for a session, **When** listing turns by session, **Then** turns are returned in chronological order with pagination support.

---

### User Story 8 - Developer Managing Customer Profiles (Priority: P2)

A developer needs to store and retrieve persistent customer profile data that spans across sessions.

**Why this priority**: Profile management enables cross-session data but can use in-memory implementation initially.

**Independent Test**: Can be fully tested by performing profile CRUD operations and verifying field updates, asset attachments, and channel identity lookups.

**Acceptance Scenarios**:

1. **Given** an in-memory ProfileStore, **When** a profile is retrieved by channel identity (e.g., phone number), **Then** the correct profile with all fields and assets is returned.

2. **Given** an existing profile, **When** a field is updated with provenance information, **Then** the field value, source, and timestamps are correctly recorded.

---

### User Story 9 - Developer Using LLM for Text Generation (Priority: P2)

A developer needs to call LLMs for text generation and structured output without coupling to a specific provider.

**Why this priority**: LLM providers are needed for the alignment pipeline but mock implementation enables testing.

**Independent Test**: Can be fully tested by calling the mock LLM provider and verifying it returns configurable responses with proper token usage tracking.

**Acceptance Scenarios**:

1. **Given** a mock LLM provider configured with a default response, **When** generate() is called, **Then** the configured response is returned with simulated token usage.

2. **Given** a mock LLM provider, **When** generate_structured() is called with a Pydantic schema, **Then** a valid instance of that schema is returned.

3. **Given** a mock LLM provider configured with `fail_after_n=3`, **When** generate() is called 4 times, **Then** the first 3 calls succeed and the 4th raises a ProviderError.

---

### User Story 10 - Developer Using Embeddings for Semantic Search (Priority: P2)

A developer needs to generate vector embeddings for text to enable semantic search functionality.

**Why this priority**: Embedding providers are needed for retrieval but mock implementation enables testing.

**Independent Test**: Can be fully tested by calling the mock embedding provider and verifying consistent vector output with correct dimensions.

**Acceptance Scenarios**:

1. **Given** a mock embedding provider with 384 dimensions, **When** embed() is called, **Then** a vector of exactly 384 floats is returned.

2. **Given** multiple texts to embed, **When** embed_batch() is called, **Then** vectors are returned for all texts efficiently.

---

### User Story 11 - Developer Reranking Search Results (Priority: P3)

A developer needs to rerank search results by relevance to improve retrieval quality.

**Why this priority**: Reranking is an optional enhancement that can be added after basic retrieval works.

**Independent Test**: Can be fully tested by calling the mock rerank provider and verifying result ordering and score assignment.

**Acceptance Scenarios**:

1. **Given** a mock rerank provider and a list of documents, **When** rerank() is called with a query, **Then** documents are returned with relevance scores in descending order.

---

### User Story 12 - SRE Tracing Request Flow (Priority: P3)

An SRE needs to trace requests through the system to diagnose latency issues and understand request flow across components.

**Why this priority**: Tracing is valuable for debugging but can be added after basic logging works.

**Independent Test**: Can be fully tested by configuring tracing, processing a request, and verifying spans are created with correct parent-child relationships and attributes.

**Acceptance Scenarios**:

1. **Given** tracing is enabled with OTLP export, **When** a request is processed, **Then** spans are created for each pipeline step with correct timing and attributes.

2. **Given** a distributed trace context (W3C traceparent header), **When** a request arrives, **Then** the trace ID is propagated to all logs and child spans.

---

### Edge Cases

- What happens when a model is created with an unknown field? (Ignored by default in Pydantic v2)
- How does the system handle empty collections? (Stores return empty lists, not None)
- What happens when tenant_id is missing from a query? (Raises an error - never query without tenant isolation)
- How does vector search behave with no matching results? (Returns empty list)
- What happens when a mock provider is called with unexpected parameters? (Uses sensible defaults)
- How does the system handle concurrent writes to the same session? (In-memory stores use simple dict storage; production stores handle this)

---

## Requirements *(mandatory)*

### Functional Requirements

#### Observability (Phase 2)

- **FR-001**: System MUST provide structured JSON logging with configurable output format (JSON for production, console for development)
- **FR-002**: System MUST automatically bind context (tenant_id, agent_id, session_id, turn_id, trace_id) to all log messages within a request scope using contextvars
- **FR-003**: System MUST support log levels (DEBUG, INFO, WARNING, ERROR) with configurable minimum level
- **FR-004**: System MUST redact PII from logs when redaction is enabled using two-tier approach: (1) key-name lookup via frozenset for sensitive keys (email, password, token, ssn, etc.), (2) regex patterns on string values for accidental PII (email, phone formats)
- **FR-005**: System MUST expose Prometheus-compatible metrics at a configurable endpoint
- **FR-006**: System MUST track request counts, latencies, and error rates with tenant/agent labels
- **FR-007**: System MUST support OpenTelemetry tracing with OTLP export when configured
- **FR-008**: System MUST propagate W3C trace context headers for distributed tracing

#### Domain Models (Phase 3)

- **FR-009**: System MUST define Pydantic models for all alignment entities (Rule, Scenario, ScenarioStep, StepTransition, Template, Variable, Context)
- **FR-010**: System MUST define Pydantic models for all memory entities (Episode, Entity, Relationship)
- **FR-011**: System MUST define Pydantic models for conversation state (Session, Turn, StepVisit)
- **FR-012**: System MUST define Pydantic models for audit records (TurnRecord, AuditEvent)
- **FR-013**: System MUST define Pydantic models for customer profiles (CustomerProfile, ProfileField, ProfileAsset, ChannelIdentity, Consent)
- **FR-014**: All models MUST include tenant_id for multi-tenant isolation
- **FR-015**: All mutable models MUST include created_at, updated_at timestamps with automatic defaults
- **FR-016**: Models supporting soft delete MUST include nullable deleted_at timestamp
- **FR-017**: Models with embeddings MUST include optional embedding field with embedding_model tracking

#### Store Interfaces (Phase 4)

- **FR-018**: System MUST define abstract ConfigStore interface for rules, scenarios, templates, variables, and agent configuration
- **FR-019**: System MUST define abstract MemoryStore interface for episodes, entities, and relationships with vector/text search
- **FR-020**: System MUST define abstract SessionStore interface for session state with cache semantics
- **FR-021**: System MUST define abstract AuditStore interface for turn records and events with time-series queries
- **FR-022**: System MUST define abstract ProfileStore interface for customer profiles with channel identity lookup
- **FR-023**: System MUST provide InMemoryConfigStore implementation with linear scan vector search using cosine similarity
- **FR-024**: System MUST provide InMemoryMemoryStore implementation with dict-based graph traversal and cosine similarity for vector search
- **FR-025**: System MUST provide InMemorySessionStore implementation
- **FR-026**: System MUST provide InMemoryAuditStore implementation
- **FR-027**: System MUST provide InMemoryProfileStore implementation

#### Provider Interfaces (Phase 5)

- **FR-028**: System MUST define abstract LLMProvider interface with generate() and generate_structured() methods
- **FR-029**: System MUST define abstract EmbeddingProvider interface with dimensions property and embed/embed_batch methods
- **FR-030**: System MUST define abstract RerankProvider interface with rerank() method
- **FR-031**: System MUST provide MockLLMProvider with configurable responses, token usage simulation, and failure injection (`fail_after_n`, `error_rate`)
- **FR-032**: System MUST provide MockEmbeddingProvider with configurable dimensions, deterministic output, and failure injection (`fail_after_n`, `error_rate`)
- **FR-033**: System MUST provide MockRerankProvider with score simulation and failure injection (`fail_after_n`, `error_rate`)
- **FR-034**: System MUST provide factory functions to create providers from configuration

### Key Entities

#### Alignment Domain

- **Rule**: Behavioral policy with condition, action, scope, priority, and optional embedding for semantic matching
- **Scenario**: Multi-step conversational flow with entry conditions, steps, and version tracking
- **ScenarioStep**: Single step within a scenario with transitions, attachments, and data collection markers
- **StepTransition**: Possible transition between steps with condition and priority
- **Template**: Pre-written response text with variable placeholders and usage mode (suggest, exclusive, fallback)
- **Variable**: Dynamic context value resolved at runtime via tools

#### Memory Domain

- **Episode**: Atomic memory unit with content, embedding, bi-temporal attributes, and group isolation
- **Entity**: Named thing (person, order, product) with attributes and temporal validity
- **Relationship**: Connection between entities with type and temporal validity

#### Conversation Domain

- **Session**: Runtime state including scenario tracking, rule fires, variables, and customer profile link
- **Turn**: Single conversation exchange with processing metadata
- **StepVisit**: Record of visiting a step for loop detection and audit

#### Profile Domain

- **CustomerProfile**: Persistent cross-session customer data with fields, assets, and verification status
- **ProfileField**: Single customer fact with provenance, verification, and confidence
- **ChannelIdentity**: Customer identity on a specific channel (phone, email, etc.)

#### Provider Domain

- **LLMResponse**: Response from LLM generation with text, usage, and finish reason
- **TokenUsage**: Token counts for prompt and completion
- **RerankResult**: Reranked document with index and relevance score

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All domain models pass validation for 100% of valid test cases and reject 100% of invalid test cases
- **SC-002**: In-memory store implementations pass all contract tests for CRUD operations, queries, and tenant isolation
- **SC-003**: Mock provider implementations return valid responses for all standard usage patterns
- **SC-004**: Logging system produces valid JSON output that can be parsed by standard log aggregators
- **SC-005**: Metrics endpoint returns all defined metrics in Prometheus text format
- **SC-006**: Unit test coverage for all new code exceeds 85% line coverage and 80% branch coverage
- **SC-007**: All in-memory implementations can handle at least 10,000 entities with p99 query latency < 50ms and throughput > 100 queries/second on standard development hardware
- **SC-008**: Each mock provider can process at least 1,000 generate/embed/rerank calls per second (single-threaded, measured via pytest-benchmark) to ensure tests run quickly

---

## Assumptions

1. **Python 3.11+**: The implementation requires Python 3.11 or later for built-in `tomllib` support
2. **Pydantic v2**: All models use Pydantic v2 with modern validation patterns
3. **Structlog for logging**: Structured logging uses structlog library
4. **Prometheus client**: Metrics use the prometheus_client library
5. **OpenTelemetry**: Tracing uses OpenTelemetry SDK with OTLP export
6. **UUID for IDs**: All entity IDs use UUID4 for global uniqueness
7. **UTC timestamps**: All timestamps are in UTC
8. **In-memory for testing**: In-memory implementations are for testing and development only, not production

---

## Out of Scope

- Production database implementations (PostgreSQL, Redis, Neo4j) - covered in Phase 16
- Production AI provider implementations (Anthropic, OpenAI, Cohere) - covered in Phase 17
- API endpoints and HTTP layer - covered in Phases 13-14
- Pipeline step implementations - covered in Phases 7-11
- gRPC interfaces - covered in Phase 18

---

## Clarifications

### Session 2025-11-28

- Q: What error handling behavior should mock providers implement for testing? → A: Configurable failure injection (providers accept `fail_after_n` or `error_rate` config for testing)
- Q: What similarity metric should in-memory vector search use? → A: Cosine similarity (normalized dot product, range -1 to 1)
- Q: How should request context be propagated for automatic log binding? → A: contextvars (Python's built-in async-safe context propagation)
- Q: How should PII redaction be implemented in logs? → A: Two-tier approach: (1) key-name lookup via frozenset for known sensitive keys (O(1)), (2) regex patterns on string values as fallback
