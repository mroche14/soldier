# Focal Implementation Plan

A comprehensive, phased implementation plan for building the Focal cognitive engine from the ground up.

> **Canonical architecture note (FOCAL 360):** This plan was originally written before `docs/focal_360/`. FOCAL 360 is now considered authoritative and introduces the **Agent Conversation Fabric (ACF)** (LogicalTurns, session mutex, supersede signals, Hatchet orchestration) as foundational conversation infrastructure. ACF work is captured in Phase **6.5** below.

---

## Phase 0: Project Skeleton & Foundation
**Goal**: Create the complete folder structure and base infrastructure

### 0.1 Create Folder Structure
> Reference: `docs/architecture/folder-structure.md`

- [x] Create top-level structure:
  ```
  focal/
  ├── config/                  # TOML configuration files
  ├── focal/                 # Main Python package
  ├── tests/                   # Test suite
  ├── docs/                    # Documentation (exists)
  └── deploy/                  # Kubernetes, Docker
  ```

- [x] Create `config/` directory with TOML files:
  - [x] `config/default.toml` - Base defaults
  - [x] `config/development.toml` - Local dev overrides
  - [x] `config/staging.toml` - Staging environment
  - [x] `config/production.toml` - Production environment
  - [x] `config/test.toml` - Test environment

- [x] Create `focal/` package structure:
  - [x] `focal/__init__.py`
  - [x] `focal/alignment/` - The brain
  - [x] `focal/memory/` - Long-term memory
  - [x] `focal/conversation/` - Live state
  - [x] `focal/audit/` - What happened
  - [x] `focal/observability/` - Logging, tracing, metrics
  - [x] `focal/providers/` - External services
  - [x] `focal/api/` - HTTP/gRPC interfaces
  - [x] `focal/config/` - Configuration loading
  - [x] `focal/customer_data/` - Customer data store

- [x] Create `tests/` structure mirroring `focal/`:
  - [x] `tests/unit/`
  - [x] `tests/integration/`
  - [x] `tests/e2e/`

- [x] Create `deploy/` structure:
  - [x] `deploy/docker/`
  - [x] `deploy/kubernetes/`

### 0.2 Project Configuration Files
- [x] `pyproject.toml` - Project metadata, dependencies
- [x] `.env.example` - Environment variable template
- [x] `Dockerfile` - Container build
- [x] `docker-compose.yml` - Local development stack
- [x] `Makefile` - Common commands

---

## Phase 1: Configuration System
**Goal**: Build the configuration loading system with Pydantic validation
> Reference: `docs/architecture/configuration-overview.md`, `docs/architecture/folder-structure.md` (config section)

### 1.1 Configuration Loader
- [x] `focal/config/__init__.py`
- [x] `focal/config/loader.py` - TOML loader with environment resolution
  - [x] Load TOML files by environment
  - [x] Resolve `${ENV_VAR}` placeholders
  - [x] Merge defaults → environment → env vars
- [x] `focal/config/settings.py` - Root Settings class
  - [x] `get_settings()` singleton function
  - [x] Environment-aware loading

### 1.2 Configuration Models (Pydantic)
> Reference: `docs/architecture/configuration-overview.md`

- [x] `focal/config/models/__init__.py`
- [x] `focal/config/models/api.py` - APIConfig
  - [x] Host, port, CORS settings
  - [x] Rate limit configuration
- [x] `focal/config/models/storage.py` - Storage backend configs
  - [x] ConfigStoreConfig
  - [x] MemoryStoreConfig
  - [x] SessionStoreConfig
  - [x] AuditStoreConfig
- [x] `focal/config/models/providers.py` - Provider configs
  - [x] LLMProviderConfig
  - [x] EmbeddingProviderConfig
  - [x] RerankProviderConfig
- [x] `focal/config/models/pipeline.py` - Pipeline step configs
  - [x] ContextExtractionConfig
  - [x] RetrievalConfig
  - [x] RerankingConfig
  - [x] LLMFilteringConfig
  - [x] GenerationConfig
  - [x] EnforcementConfig
- [x] `focal/config/models/selection.py` - Selection strategy configs
  - [x] ElbowSelectionConfig
  - [x] AdaptiveKSelectionConfig
  - [x] EntropySelectionConfig
  - [x] ClusterSelectionConfig
  - [x] FixedKSelectionConfig
- [x] `focal/config/models/observability.py` - Observability configs
  - [x] LoggingConfig
  - [x] TracingConfig
  - [x] MetricsConfig
- [x] `focal/config/models/agent.py` - Per-agent overrides

### 1.3 Default Configuration
- [x] Write `config/default.toml` with all sections
- [x] Write `config/development.toml` with dev overrides
- [x] Write `config/test.toml` with in-memory backends

### 1.4 Configuration Tests
- [x] `tests/unit/config/test_loader.py`
- [x] `tests/unit/config/test_settings.py`
- [x] `tests/unit/config/test_models.py`

---

## Phase 2: Observability Foundation
**Goal**: Set up structured logging, tracing, and metrics
> Reference: `docs/architecture/observability.md`

### 2.1 Logging
- [x] `focal/observability/__init__.py`
- [x] `focal/observability/logging.py`
  - [x] `setup_logging()` - Configure structlog
  - [x] `get_logger()` - Get bound logger
  - [x] JSON formatter for production
  - [x] Console formatter for development
  - [x] PII redaction processor

### 2.2 Tracing
- [x] `focal/observability/tracing.py`
  - [x] `setup_tracing()` - Configure OpenTelemetry
  - [x] OTLP exporter configuration
  - [x] Span helpers for pipeline steps

### 2.3 Metrics
- [x] `focal/observability/metrics.py`
  - [x] Prometheus counters: requests, LLM calls, rule fires
  - [x] Histograms: latency per step, tokens used
  - [x] Gauges: active sessions

### 2.4 Middleware
- [x] `focal/observability/middleware.py`
  - [ ] Request context binding
  - [ ] tenant_id, agent_id, session_id extraction
  - [ ] Trace ID propagation

### 2.5 Tests
- [x] `tests/unit/observability/test_logging.py`
- [x] `tests/unit/observability/test_metrics.py`

---

## Phase 3: Domain Models
**Goal**: Define all core domain models with Pydantic
> Reference: `docs/design/domain-model.md`

### 3.1 Alignment Models
> Reference: `docs/architecture/alignment-engine.md`

- [x] `focal/alignment/models/__init__.py`
- [x] `focal/alignment/models/rule.py`
  - [x] Rule (condition, action, scope, priority)
  - [x] MatchedRule (with scores)
  - [x] RuleScope enum
- [x] `focal/alignment/models/scenario.py`
  - [x] Scenario
  - [x] ScenarioStep
  - [x] StepTransition
  - [x] ScenarioFilterResult
- [x] `focal/alignment/models/template.py`
  - [x] Template
  - [x] TemplateMode enum (SUGGEST, EXCLUSIVE, FALLBACK)
- [x] `focal/alignment/models/variable.py`
  - [x] Variable
  - [x] VariableUpdatePolicy enum
- [x] `focal/alignment/models/context.py`
  - [x] Context
  - [x] UserIntent
  - [x] ExtractedEntities

### 3.2 Memory Models
> Reference: `docs/architecture/memory-layer.md`

- [x] `focal/memory/models/__init__.py`
- [x] `focal/memory/models/episode.py`
  - [x] Episode (atomic memory unit)
  - [x] Bi-temporal attributes (valid_from, valid_to, recorded_at)
- [x] `focal/memory/models/entity.py`
  - [x] Entity (named thing in knowledge graph)
- [x] `focal/memory/models/relationship.py`
  - [x] Relationship (edge between entities)

### 3.3 Conversation Models
- [x] `focal/conversation/models/__init__.py`
- [x] `focal/conversation/models/session.py`
  - [x] Session (active conversation state)
  - [x] Link to CustomerDataStore (customer identity)
- [x] `focal/conversation/models/turn.py`
  - [x] Turn (single exchange)

### 3.4 Audit Models
- [x] `focal/audit/models/__init__.py`
- [x] `focal/audit/models/turn_record.py`
  - [x] TurnRecord (full turn with metadata)
- [x] `focal/audit/models/event.py`
  - [x] AuditEvent (tool calls, errors)

### 3.5 Customer Data Models
> Reference: `docs/design/customer-profile.md`

- [x] `focal/customer_data/__init__.py`
- [x] `focal/customer_data/enums.py`
  - [x] VariableSource enum
  - [x] VerificationLevel enum
  - [x] ItemStatus, SourceType, RequiredLevel, FallbackAction, ValidationMode
- [x] `focal/customer_data/models.py`
  - [x] CustomerDataStore
  - [x] ChannelIdentity
  - [x] VariableEntry
  - [x] CustomerDataField
  - [x] ProfileAsset
  - [x] Consent
  - [x] ScenarioFieldRequirement

### 3.6 Tests
- [x] `tests/unit/alignment/test_models.py`
- [x] `tests/unit/memory/test_models.py`
- [x] `tests/unit/conversation/test_models.py`
- [x] `tests/unit/customer_data/test_customer_data_models.py`

---

## Phase 4: Store Interfaces & In-Memory Implementations
**Goal**: Define all store interfaces and implement in-memory versions for testing
> Reference: `docs/design/decisions/001-storage-choice.md`

### 4.1 ConfigStore
- [x] `focal/alignment/stores/__init__.py`
- [x] `focal/alignment/stores/config_store.py` - Interface (ABC)
  - [x] `get_rules()`, `get_rule()`, `save_rule()`, `delete_rule()`
  - [x] `vector_search_rules()`
  - [x] `get_scenarios()`, `get_scenario()`, `save_scenario()`
  - [x] `get_templates()`, `save_template()`
  - [x] `get_variables()`
  - [x] `get_agent()`, `save_agent()`
- [x] `focal/alignment/stores/inmemory.py` - InMemoryConfigStore

### 4.2 MemoryStore
- [x] `focal/memory/store.py` - Interface (ABC)
  - [x] `add_episode()`, `get_episode()`
  - [x] `vector_search_episodes()`, `text_search_episodes()`
  - [x] `add_entity()`, `get_entities()`
  - [x] `add_relationship()`, `traverse_from_entities()`
  - [x] `delete_by_group()`
- [x] `focal/memory/stores/__init__.py`
- [x] `focal/memory/stores/inmemory.py` - InMemoryMemoryStore

### 4.3 SessionStore
- [x] `focal/conversation/store.py` - Interface (ABC)
  - [x] `get()`, `save()`, `delete()`
  - [x] `list_by_agent()`
- [x] `focal/conversation/stores/__init__.py`
- [x] `focal/conversation/stores/inmemory.py` - InMemorySessionStore

### 4.4 AuditStore
- [x] `focal/audit/store.py` - Interface (ABC)
  - [x] `save_turn()`, `get_turn()`
  - [x] `list_turns_by_session()`, `list_turns_by_tenant()`
  - [x] `save_event()`
- [x] `focal/audit/stores/__init__.py`
- [x] `focal/audit/stores/inmemory.py` - InMemoryAuditStore

### 4.5 CustomerDataStore
- [x] `focal/customer_data/store.py` - CustomerDataStoreInterface (ABC)
  - [x] `get_by_customer_id()`, `get_by_channel_identity()`
  - [x] `get_or_create()`
  - [x] `update_field()`, `add_asset()`
  - [x] `merge_profiles()`, `link_channel()`
  - [x] Schema + requirements APIs (`get_field_definitions()`, `get_missing_fields()`, etc.)
- [x] `focal/customer_data/stores/__init__.py`
- [x] `focal/customer_data/stores/inmemory.py` - InMemoryCustomerDataStore

### 4.6 Tests
- [x] `tests/unit/alignment/stores/test_inmemory_config.py`
- [x] `tests/unit/memory/stores/test_inmemory_memory.py`
- [x] `tests/unit/conversation/stores/test_inmemory_session.py`
- [x] `tests/unit/audit/stores/test_inmemory_audit.py`
- [x] `tests/unit/customer_data/stores/test_inmemory_customer_data.py`

---

## Phase 5: Provider Interfaces & Mock Implementations
**Goal**: Define provider interfaces and mock implementations for testing
> Reference: `docs/design/decisions/001-storage-choice.md` (Provider section)

### 5.1 LLM Executor (Agno)
- [x] `focal/providers/__init__.py`
- [x] `focal/providers/llm/__init__.py`
- [x] `focal/providers/llm/base.py` - LLM data models + error types
  - [x] LLMMessage, LLMResponse, TokenUsage
  - [x] ProviderError subclasses (auth, rate-limit, model, content filter)
- [x] `focal/providers/llm/executor.py` - LLMExecutor (Agno-backed)
  - [x] Fallback chain on failure
  - [x] `create_executor()` / `create_executor_from_step_config()` / `create_executors_from_pipeline_config()`
  - [x] ExecutionContext helpers (`set_execution_context()`, `get_execution_context()`)
- [x] `focal/providers/llm/mock.py` - MockLLMProvider

### 5.2 Embedding Provider
- [x] `focal/providers/embedding/__init__.py`
- [x] `focal/providers/embedding/base.py` - EmbeddingProvider interface
  - [x] `dimensions` property
  - [x] `embed()` - Single text
  - [x] `embed_batch()` - Batch embedding
- [x] `focal/providers/embedding/mock.py` - MockEmbeddingProvider

### 5.3 Rerank Provider
- [x] `focal/providers/rerank/__init__.py`
- [x] `focal/providers/rerank/base.py` - RerankProvider interface
  - [x] `rerank()` - Rerank documents
  - [x] RerankResult model
- [x] `focal/providers/rerank/mock.py` - MockRerankProvider

### 5.4 Provider Wiring
- [x] LLM executor creation helpers live in `focal/providers/llm/executor.py`
- [x] Example end-to-end wiring in `focal/bootstrap.py`

### 5.5 Tests
- [x] `tests/unit/providers/test_llm_mock.py`
- [x] `tests/unit/providers/test_embedding_mock.py`
- [x] `tests/unit/providers/test_rerank_mock.py`

---

## Phase 6: Selection Strategies
**Goal**: Implement dynamic k-selection strategies for retrieval
> Reference: `docs/architecture/selection-strategies.md`

### 6.1 Selection Interface & Models
- [x] `focal/alignment/retrieval/__init__.py`
- [x] `focal/alignment/retrieval/selection.py`
  - [x] SelectionStrategy interface (ABC)
  - [x] ScoredItem generic model
  - [x] SelectionResult model
  - [x] `create_selection_strategy()` factory

### 6.2 Strategy Implementations
- [x] ElbowSelectionStrategy (relative score drop)
- [x] AdaptiveKSelectionStrategy (curvature analysis)
- [x] EntropySelectionStrategy (information method)
- [x] ClusterSelectionStrategy (topic clustering)
- [x] FixedKSelectionStrategy (baseline)

### 6.3 Tests
- [x] `tests/unit/alignment/retrieval/test_selection.py`
  - [x] Test each strategy with various score distributions
  - [x] Test edge cases (empty, single item, identical scores)

---

## Phase 6.5: Agent Conversation Fabric (ACF)
**Goal**: Implement ACF turn infrastructure (LogicalTurn, mutex, accumulation, supersede, Hatchet workflow)
> Reference: `docs/focal_360/architecture/ACF_ARCHITECTURE.md`, `docs/focal_360/architecture/ACF_SPEC.md`, `docs/focal_360/architecture/AGENT_RUNTIME_SPEC.md`, `docs/focal_360/architecture/TOOLBOX_SPEC.md`

### 6.5.1 Core ACF Models
- [ ] `LogicalTurn` model (includes `turn_group_id`, status, message list)
- [ ] `SupersedeDecision` / `SupersedeAction` types (facts vs decisions boundary)
- [ ] `FabricEvent` model (single event write path)

### 6.5.2 Concurrency + Accumulation
- [ ] Session mutex keyed by `{tenant}:{agent}:{customer}:{channel}`
- [ ] TurnGateway + message queue primitives
- [ ] Adaptive accumulation policy (channel-aware defaults)

### 6.5.3 ACF Runtime (Hatchet)
- [ ] `LogicalTurnWorkflow`: acquire_mutex → accumulate → run_pipeline → commit_and_respond
- [ ] `has_pending_messages()` signal (monotonic within a turn)
- [ ] Commit point tracking for irreversible side effects

### 6.5.4 Idempotency (Three-Layer)
- [ ] API-level idempotency (request retries)
- [ ] LogicalTurn/beat-level idempotency (`turn_group_id`)
- [ ] Tool-level idempotency keys (Toolbox/Gateway)

### 6.5.5 Tests
- [ ] Unit tests for LogicalTurn + supersede decisions
- [ ] Unit/integration tests for session mutex and accumulation
- [ ] Workflow tests for LogicalTurnWorkflow happy path + supersede scenarios

---

## Phase 7: Alignment Pipeline - Context Extraction
**Goal**: Implement context extraction (understanding user messages)
> Reference: `docs/architecture/alignment-engine.md`, `docs/focal_turn_pipeline/spec/pipeline.md`

### 7.1 Context Extractor
- [x] `focal/alignment/context/__init__.py`
- [x] `focal/alignment/context/extractor.py`
  - [x] ContextExtractor interface
  - [x] LLMContextExtractor implementation
  - [ ] RuleBasedContextExtractor (simple patterns)
- [x] `focal/alignment/context/models.py`
  - [x] Context model
  - [x] UserIntent model
  - [x] ExtractedEntities model
- [x] `focal/alignment/context/prompts/`
  - [x] `extract_intent.txt` - Intent extraction prompt

### 7.2 Tests
- [x] `tests/unit/alignment/context/test_extractor.py`

---

## Phase 8: Alignment Pipeline - Retrieval
**Goal**: Implement rule, scenario, and memory retrieval
> Reference: `docs/design/decisions/002-rule-matching-strategy.md`

### 8.1 Rule Retrieval
- [x] `focal/alignment/retrieval/rule_retriever.py`
  - [x] RuleRetriever class
  - [x] Vector similarity search
  - [ ] BM25 hybrid search
  - [x] Scope filtering (GLOBAL → SCENARIO → STEP)
  - [x] Selection strategy application

### 8.2 Scenario Retrieval
- [x] `focal/alignment/retrieval/scenario_retriever.py`
  - [x] ScenarioRetriever class
  - [x] Entry condition matching
  - [x] Active scenario continuation

### 8.3 Memory Retrieval
- [x] `focal/memory/retrieval/__init__.py`
- [x] `focal/memory/retrieval/retriever.py`
  - [x] MemoryRetriever class
  - [ ] Hybrid retrieval (vector + BM25 + graph)

### 8.4 Reranker
- [x] `focal/alignment/retrieval/reranker.py`
  - [x] ResultReranker class
  - [x] Provider-agnostic reranking

### 8.5 Tests
- [x] `tests/unit/alignment/retrieval/test_rule_retriever.py`
- [x] `tests/unit/alignment/retrieval/test_scenario_retriever.py`
- [x] `tests/unit/memory/retrieval/test_retriever.py`

---

## Phase 9: Alignment Pipeline - Filtering
**Goal**: Implement LLM-based filtering (judging relevance)
> Reference: `docs/architecture/alignment-engine.md`

### 9.1 Rule Filter
- [x] `focal/alignment/filtering/__init__.py`
- [x] `focal/alignment/filtering/rule_filter.py`
  - [x] RuleFilter class
  - [x] LLM-based condition evaluation
  - [x] Batch filtering for efficiency
- [x] `focal/alignment/filtering/prompts/filter_rules.txt`

### 9.2 Scenario Filter
- [x] `focal/alignment/filtering/scenario_filter.py`
  - [x] ScenarioFilter class
  - [x] Start/continue/exit decisions
  - [x] Step transition evaluation
- [x] `focal/alignment/filtering/prompts/evaluate_scenario.txt`

### 9.3 Tests
- [x] `tests/unit/alignment/filtering/test_rule_filter.py`
- [x] `tests/unit/alignment/filtering/test_scenario_filter.py`

---

## Phase 10: Alignment Pipeline - Execution & Generation
**Goal**: Implement tool execution and response generation
> Reference: `docs/focal_turn_pipeline/spec/pipeline.md`

### 10.1 Tool Execution
- [x] `focal/alignment/execution/__init__.py`
- [x] `focal/alignment/execution/tool_executor.py`
  - [x] ToolExecutor class
  - [x] Execute tools from matched rules
  - [x] Timeout handling
  - [x] Result aggregation
- [x] `focal/alignment/execution/variable_resolver.py`
  - [x] VariableResolver class
  - [x] Resolve variables from customer_data/session

### 10.2 Response Generation
- [x] `focal/alignment/generation/__init__.py`
- [x] `focal/alignment/generation/prompt_builder.py`
  - [x] PromptBuilder class
  - [x] Assemble system prompt with rules, memory, context
- [x] `focal/alignment/generation/generator.py`
  - [x] ResponseGenerator class
  - [x] LLM-based response generation
  - [x] Template interpolation
- [x] `focal/alignment/generation/prompts/system_prompt.txt`

### 10.3 Enforcement
- [x] `focal/alignment/enforcement/__init__.py`
- [x] `focal/alignment/enforcement/validator.py`
  - [x] EnforcementValidator class
  - [x] Check response against hard constraints
  - [ ] Self-critique (optional)
- [x] `focal/alignment/enforcement/fallback.py`
  - [x] FallbackHandler class
  - [x] Template fallback logic

### 10.4 Tests
- [x] `tests/unit/alignment/execution/test_tool_executor.py`
- [x] `tests/unit/alignment/generation/test_generator.py`
- [x] `tests/unit/alignment/enforcement/test_validator.py`

---

## Phase 11: Alignment Engine Integration
**Goal**: Wire together all pipeline components
> Reference: `docs/architecture/alignment-engine.md`

### 11.1 Alignment Engine
- [x] `focal/alignment/__init__.py`
- [x] `focal/alignment/engine.py`
  - [x] AlignmentEngine class
  - [x] `process_turn()` - Full pipeline orchestration
  - [x] Step timing and logging
  - [x] Error handling and fallbacks
- [x] `focal/alignment/result.py`
  - [x] AlignmentResult model
  - [x] TurnMetadata model

### 11.2 Pipeline Configuration
- [x] Pipeline step enable/disable
- [x] Per-step provider selection
- [ ] Timeout configuration

### 11.3 Integration Tests
- [x] `tests/integration/test_alignment_engine.py`
  - [x] Full pipeline with mock providers
  - [x] Rule matching → filtering → generation

---

## Phase 12: Memory Layer
**Goal**: Implement memory ingestion and retrieval
> Reference: `docs/architecture/memory-layer.md`

### 12.1 Memory Ingestion
- [x] `focal/memory/ingestion/__init__.py`
- [x] `focal/memory/ingestion/ingestor.py`
  - [x] MemoryIngestor class
  - [x] Episode creation from turns
  - [x] Embedding generation with fallback
  - [x] Async task queuing
- [x] `focal/memory/ingestion/entity_extractor.py`
  - [x] EntityExtractor class
  - [x] LLM-based entity extraction
  - [x] EntityDeduplicator class (4-stage pipeline)
  - [x] Temporal relationship updates
- [x] `focal/memory/ingestion/summarizer.py`
  - [x] ConversationSummarizer class
  - [x] Hierarchical summarization (window + meta)
- [x] `focal/memory/ingestion/models.py`
  - [x] Structured output models (ExtractedEntity, ExtractedRelationship)
- [x] `focal/memory/ingestion/errors.py`
  - [x] Error classes (IngestionError, ExtractionError, SummarizationError)
- [x] `focal/memory/ingestion/queue.py`
  - [x] TaskQueue interface
  - [x] InMemoryTaskQueue implementation
  - [x] RedisTaskQueue implementation
- [x] `focal/memory/ingestion/tasks.py`
  - [x] Background task handlers
- [x] `focal/config/models/pipeline.py`
  - [x] MemoryIngestionConfig and related config models
- [x] `focal/providers/embedding/sentence_transformers.py`
  - [x] SentenceTransformersProvider implementation
- [x] `config/default.toml`
  - [x] Memory ingestion configuration section

### 12.2 Tests
- [x] `tests/unit/memory/ingestion/test_ingestor.py`
- [x] `tests/unit/memory/ingestion/test_entity_extractor.py`
- [x] `tests/unit/memory/ingestion/test_summarizer.py`
- [x] `tests/integration/memory/test_ingestion_flow.py`

---

## Phase 13: API Layer - Core
**Goal**: Implement HTTP API endpoints
> Reference: `docs/architecture/api-layer.md`, `docs/design/api-crud.md`

### 13.1 FastAPI Application
- [x] `focal/api/__init__.py`
- [x] `focal/api/app.py` - FastAPI app factory
  - [x] Middleware setup
  - [x] Route registration
  - [x] Exception handlers

### 13.2 API Models
- [x] `focal/api/models/__init__.py`
- [x] `focal/api/models/chat.py`
  - [x] ChatRequest
  - [x] ChatResponse
- [x] `focal/api/models/errors.py`
  - [x] ErrorResponse
  - [x] Error codes enum

### 13.3 Core Routes
- [x] `focal/api/routes/__init__.py`
- [x] `focal/api/routes/chat.py`
  - [x] `POST /v1/chat` - Process message
  - [x] `POST /v1/chat/stream` - SSE streaming
- [x] `focal/api/routes/sessions.py`
  - [x] `GET /v1/sessions/{id}` - Get session
  - [x] `DELETE /v1/sessions/{id}` - End session
  - [x] `GET /v1/sessions/{id}/turns` - Session history
- [x] `focal/api/routes/health.py`
  - [x] `GET /health` - Health check
  - [x] `GET /metrics` - Prometheus metrics

### 13.4 Middleware
- [x] `focal/api/middleware/__init__.py`
- [x] `focal/api/middleware/auth.py`
  - [x] JWT validation
  - [x] Tenant extraction
- [x] `focal/api/middleware/rate_limit.py`
  - [x] Per-tenant rate limiting

### 13.5 Tests
- [x] `tests/unit/api/test_chat.py`
- [x] `tests/unit/api/test_sessions.py`
- [x] `tests/integration/api/test_chat_flow.py`

---

## Phase 14: API Layer - CRUD Operations ✅
**Goal**: Implement configuration CRUD endpoints
> Reference: `docs/design/api-crud.md`, `specs/001-api-crud/`

### 14.1 Agent Routes
- [x] `focal/api/routes/agents.py`
  - [x] `GET /v1/agents` - List agents
  - [x] `GET /v1/agents/{id}` - Get agent
  - [x] `POST /v1/agents` - Create agent
  - [x] `PUT /v1/agents/{id}` - Update agent
  - [x] `DELETE /v1/agents/{id}` - Delete agent

### 14.2 Rules Routes
- [x] `focal/api/routes/rules.py`
  - [x] `GET /v1/agents/{id}/rules` - List rules
  - [x] `GET /v1/agents/{id}/rules/{rule_id}` - Get rule
  - [x] `POST /v1/agents/{id}/rules` - Create rule
  - [x] `PUT /v1/agents/{id}/rules/{rule_id}` - Update rule
  - [x] `DELETE /v1/agents/{id}/rules/{rule_id}` - Delete rule
  - [x] `POST /v1/agents/{id}/rules/bulk` - Bulk operations

### 14.3 Scenarios Routes
- [x] `focal/api/routes/scenarios.py`
  - [x] Scenario CRUD
  - [x] Step CRUD

### 14.4 Templates Routes
- [x] `focal/api/routes/templates.py`
  - [x] Template CRUD
  - [x] `POST /preview` - Template preview

### 14.5 Variables Routes
- [x] `focal/api/routes/variables.py`
  - [x] Variable CRUD with resolver tool references

### 14.6 Tools Routes
- [x] `focal/api/routes/tools.py`
  - [x] Tool activation/deactivation with policy overrides

### 14.7 Publish Routes
- [x] `focal/api/routes/publish.py`
  - [x] Publish status and initiation
  - [x] Rollback to previous version

### 14.8 Tests
- [x] `tests/unit/api/test_agents.py`
- [x] `tests/unit/api/test_rules.py` (via existing test infrastructure)
- [x] `tests/unit/api/test_scenarios.py` (via existing test infrastructure)
- [x] `tests/unit/api/test_templates.py` (via existing test infrastructure)

---

## Phase 15: Scenario Migration System ✅
**Goal**: Implement scenario update handling for active sessions
> Reference: `docs/design/scenario-update-methods.md`, `specs/008-scenario-migration/`

### 15.1 Migration Plan Generation (User Story 1) ✅
- [x] `focal/alignment/migration/__init__.py`
- [x] `focal/alignment/migration/models.py`
  - [x] MigrationPlan, MigrationPlanStatus, MigrationScenario
  - [x] TransformationMap, AnchorTransformation
  - [x] UpstreamChanges, DownstreamChanges, InsertedNode, DeletedNode
  - [x] MigrationSummary, MigrationWarning, FieldCollectionInfo
  - [x] AnchorMigrationPolicy, ScopeFilter
- [x] `focal/alignment/migration/diff.py`
  - [x] `compute_node_content_hash()` - SHA-256 anchor identification
  - [x] `find_anchor_nodes()` - Content hash matching between versions
  - [x] `compute_upstream_changes()` - Reverse BFS analysis
  - [x] `compute_downstream_changes()` - Forward BFS analysis
  - [x] `determine_migration_scenario()` - clean_graft/gap_fill/re_route
  - [x] `compute_transformation_map()` - Complete diff between versions
- [x] `focal/alignment/migration/planner.py`
  - [x] MigrationPlanner - generate_plan(), approve_plan(), reject_plan()
  - [x] MigrationDeployer - deploy(), get_deployment_status()
- [x] `focal/api/routes/migrations.py` - Full migration API
- [x] `focal/config/models/migration.py` - Migration configuration
- [x] Store extensions (ConfigStore, SessionStore) for migration

### 15.2 Migration Application (User Story 2) ✅
- [x] `focal/alignment/migration/executor.py`
  - [x] MigrationExecutor class with reconcile() method
  - [x] `_execute_clean_graft()` - Silent teleport to V2 anchor
  - [x] `_execute_gap_fill()` - Collect fields or teleport
  - [x] `_execute_re_route()` - Evaluate fork, check checkpoint, teleport
  - [x] `_fallback_reconciliation()` - Content hash matching fallback
  - [x] `_is_upstream_of_checkpoint()` - Block teleport past checkpoints
- [x] AlignmentEngine integration
  - [x] `_pre_turn_reconciliation()` - Check for updates before turn
  - [x] ReconciliationResult field added to AlignmentResult

### 15.3 Per-Anchor Policies & Checkpoint Blocking (User Stories 3-4) ✅
- [x] Scope filter matching (channel, age, node filtering)
- [x] `update_downstream=false` behavior
- [x] `force_scenario` policy override
- [x] Checkpoint blocking with `_find_last_checkpoint()`, `_is_upstream_of_checkpoint()`
- [x] `checkpoint_warning` field in ReconciliationResult

### 15.4 Multi-Version Gaps (User Story 5) ✅
- [x] `focal/alignment/migration/composite.py`
  - [x] CompositeMapper class
  - [x] `get_plan_chain()` - Load V1→V2→...→Vn plans
  - [x] `accumulate_requirements()` - Collect all fields across chain
  - [x] `prune_requirements()` - Keep only final version fields
  - [x] `execute_composite_migration()` - Net effect computation

### 15.5 Gap Fill (User Story 6) ✅
- [x] `focal/alignment/migration/field_resolver.py`
  - [x] MissingFieldResolver class
  - [x] `try_profile_fill()` - Check CustomerDataStore
  - [x] `try_session_fill()` - Check session variables
  - [x] `try_conversation_extraction()` - LLM extraction
  - [x] `persist_extracted_values()` - Save to CustomerDataStore
  - [x] Confidence thresholds (0.85/0.95)
- [x] Integration into `_execute_gap_fill()` in executor

### 15.6 Polish ✅
- [x] Migration metrics in `focal/observability/metrics.py`
- [x] Plan retention cleanup (`cleanup_old_plans()`)
- [x] CLAUDE.md migration module documentation

### 15.7 Tests ✅
- [x] `tests/unit/alignment/migration/test_diff.py` - 12 tests
- [x] `tests/unit/alignment/migration/test_planner.py` - 28 tests
- [x] `tests/unit/alignment/migration/test_executor.py` - 16 tests
- [x] `tests/unit/alignment/migration/test_composite.py` - 12 tests
- [x] `tests/unit/alignment/migration/test_gap_fill.py` - 15 tests
- [x] `tests/integration/alignment/migration/test_migration_flow.py` - 3 tests
- [x] `tests/contract/test_config_store_migration.py` - 10 tests

---

## Phase 16: Production Store Implementations
**Goal**: Implement real database backends

### 16.1 PostgreSQL Stores
> Reference: `docs/design/decisions/001-storage-choice.md`

- [x] `focal/alignment/stores/postgres.py` - PostgresConfigStore
- [x] `focal/memory/stores/postgres.py` - PostgresMemoryStore (pgvector)
- [x] `focal/audit/stores/postgres.py` - PostgresAuditStore
- [x] `focal/customer_data/stores/postgres.py` - PostgresCustomerDataStore

### 16.2 Redis Session Store
- [x] `focal/conversation/stores/redis.py` - RedisSessionStore
  - [x] Two-tier (cache + persistent)
  - [x] TTL management

### 16.3 Additional Backends (Optional)
- [ ] MongoDB stores
- [ ] Neo4j memory store
- [ ] DynamoDB session store

### 16.4 Database Migrations
- [x] Alembic setup for PostgreSQL
- [x] Migration scripts (001-007)

### 16.5 Integration Tests
- [x] `tests/integration/stores/test_postgres_config.py`
- [x] `tests/integration/stores/test_postgres_memory.py`
- [x] `tests/integration/stores/test_postgres_audit.py`
- [x] `tests/integration/stores/test_postgres_customer_data.py`
- [x] `tests/integration/stores/test_redis_session.py`

---

## Phase 17: Production Provider Implementations
**Goal**: Implement real AI provider integrations

### 17.1 LLM Execution (Agno-backed)
- [x] `focal/providers/llm/executor.py` - LLMExecutor routes to providers via model string
- [x] `focal/config/models/providers.py` - LLMProviderConfig (model string + API key config)

### 17.2 Embedding Providers
- [x] `focal/providers/embedding/openai.py` - OpenAIEmbeddings
- [x] `focal/providers/embedding/cohere.py` - CohereEmbeddings
- [x] `focal/providers/embedding/sentence_transformers.py` - Local

### 17.3 Rerank Providers
- [x] `focal/providers/rerank/cohere.py` - CohereRerank
- [x] `focal/providers/rerank/cross_encoder.py` - Local CrossEncoder

### 17.4 Integration Tests
- [ ] Provider integration tests (optional) in `tests/integration/providers/`

---

## Phase 17.5: Customer Data Store Enhancement ✅
**Goal**: Evolve CustomerDataStore into a comprehensive Customer Context Vault with lineage tracking, explicit status management, schema-driven field definitions, and Redis caching.
> Reference: `specs/010-customer-context-vault/spec.md`

### 17.5.1 Model Enhancements ✅
- [x] Add `ItemStatus` enum (active, superseded, expired, orphaned) to `focal/customer_data/enums.py`
- [x] Add `SourceType` enum (profile_field, profile_asset, session, tool, external)
- [x] Add `RequiredLevel` enum (hard, soft)
- [x] Add `FallbackAction` enum (ask, skip, block, extract)
- [x] Add `ValidationMode` enum (strict, warn, disabled)
- [x] Enhance `VariableEntry` with:
  - [x] `id: UUID` field for lineage tracking
  - [x] `source_item_id`, `source_item_type`, `source_metadata` fields
  - [x] `status`, `superseded_by_id`, `superseded_at` fields
  - [x] `field_definition_id` field
- [x] Enhance `ProfileAsset` with lineage and status fields
- [x] Create `CustomerDataField` model (schema)
- [x] Create `ScenarioFieldRequirement` model (bindings)
- [x] Update `CustomerDataStore` with lineage helpers (`get_derived_fields()`)

### 17.5.2 Store Interface Updates ✅
- [x] Extend `CustomerDataStoreInterface` with:
  - [x] Status-aware queries: `get_field()`, `get_field_history()`, `expire_stale_fields()`
  - [x] Lineage operations: `get_derivation_chain()`, `get_derived_items()`, `check_has_dependents()`
  - [x] Schema operations: `get_field_definitions()`, `save_field_definition()`
  - [x] Requirements operations: `get_scenario_requirements()`, `get_missing_fields()`
- [x] Update `InMemoryCustomerDataStore` with all new methods
- [x] Create contract test suite for CustomerDataStore (`tests/contract/test_customer_data_store_contract.py`)

### 17.5.3 Database Schema (Alembic Migrations) ✅
- [x] `008_profile_fields_enhancement.py` - Add lineage + status columns
- [x] `009_profile_assets_enhancement.py` - Add lineage + status columns
- [x] `010_profile_field_definitions.py` - New table
- [x] `011_scenario_field_requirements.py` - New table
- [x] Update `PostgresCustomerDataStore` with all new methods

### 17.5.4 Redis Caching Layer ✅
- [x] Create `focal/customer_data/stores/cached.py` - `CustomerDataStoreCacheLayer` wrapper
- [x] Implement two-tier caching (Redis + PostgreSQL)
- [x] Cache invalidation on mutations
- [x] Fallback logic for Redis failures
- [x] Add Redis cache config to `focal/config/models/storage.py`
- [x] Update `config/default.toml` with `[customer_data]` section

### 17.5.5 Schema Validation Service ✅
- [x] Create `focal/customer_data/validation.py` - `CustomerDataFieldValidator`
- [x] Type validators for: string, number, boolean, date, email, phone, json
- [x] Regex and allowed values validation
- [x] Validation mode support (strict, warn, disabled)

### 17.5.6 MissingFieldResolver Integration ✅
- [x] `GapFillResult` with `field_definition`, confidence, source tracking
- [x] `MissingFieldResolver` class with:
  - [x] `try_profile_fill()` - Check CustomerDataStore
  - [x] `try_session_fill()` - Check session variables
  - [x] `try_conversation_extraction()` - LLM extraction
- [x] Confidence thresholds (0.85/0.95)
- [x] Track lineage when persisting extracted values
- [x] Add `fill_scenario_requirements()` method (batch fill)
- [x] Add `get_unfilled_hard_requirements()` and `get_fields_to_ask()` helpers
- [x] Update `AlignmentEngine` to check missing fields before scenario entry
  - [x] `_check_scenario_requirements()` method
  - [x] `missing_requirements` and `scenario_blocked` fields in `AlignmentResult`

### 17.5.7 Observability ✅
- [x] Add cache hit/miss/invalidation/error metrics
- [x] Add derivation chain depth histogram
- [x] Add schema validation error counter
- [x] Add gap fill attempts/count metrics
- [x] Structured logging for validation failures and lineage operations

### 17.5.8 Tests ✅
- [x] `tests/unit/customer_data/test_customer_data_models.py` - Model enhancements
- [x] `tests/unit/customer_data/test_validation.py` - Schema validation
- [x] `tests/unit/customer_data/stores/test_cached_customer_data.py` - Cache wrapper
- [x] `tests/unit/customer_data/stores/test_inmemory_customer_data.py` - InMemory store
- [x] `tests/unit/customer_data/test_extraction.py` - Field extraction
- [x] `tests/contract/test_customer_data_store_contract.py` - Contract tests
- [x] `tests/integration/stores/test_postgres_customer_data.py` - PostgreSQL integration
- [ ] `tests/integration/stores/test_cached_customer_data.py` - Redis integration
- [ ] `tests/integration/alignment/test_customer_data_requirements.py` - Scenario requirements

---

## Phase 18: gRPC API (Optional)
**Goal**: Add gRPC interface for service-to-service communication
> Reference: `docs/architecture/api-layer.md` (gRPC section)

### 18.1 Proto Definitions
- [ ] `focal/api/grpc/protos/focal.proto`
  - [ ] ChatService
  - [ ] MemoryService
  - [ ] ConfigService

### 18.2 gRPC Server
- [ ] `focal/api/grpc/__init__.py`
- [ ] `focal/api/grpc/server.py`
- [ ] `focal/api/grpc/servicers/chat.py`

### 18.3 Generated Code
- [ ] Proto compilation setup
- [ ] Python stubs generation

---

## Phase 19: Deployment & DevOps
**Goal**: Production-ready deployment configuration

### 19.1 Docker
- [ ] `Dockerfile` - Multi-stage build
- [ ] `docker-compose.yml` - Full stack for local dev
- [ ] `docker-compose.test.yml` - Test environment

### 19.2 Kubernetes
- [ ] `deploy/kubernetes/deployment.yaml`
- [ ] `deploy/kubernetes/service.yaml`
- [ ] `deploy/kubernetes/configmap.yaml`
- [ ] `deploy/kubernetes/hpa.yaml` - Horizontal Pod Autoscaler

### 19.3 CI/CD
- [ ] GitHub Actions workflow
- [ ] Test automation
- [ ] Docker image build
- [ ] Deployment automation

---

## Phase 20: End-to-End Testing & Documentation
**Goal**: Full system validation and documentation

### 20.1 E2E Tests
- [ ] `tests/e2e/test_chat_flow.py` - Complete chat interaction
- [ ] `tests/e2e/test_scenario_flow.py` - Scenario navigation
- [ ] `tests/e2e/test_memory_flow.py` - Memory persistence

### 20.2 Performance Tests
- [ ] Latency benchmarks
- [ ] Load testing setup
- [ ] Stress testing

### 20.3 Documentation
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Deployment guide
- [ ] Operations runbook

---

## Document Reference Index

| Phase | Primary Documents |
|-------|-------------------|
| 0-1 | `docs/architecture/folder-structure.md`, `docs/architecture/configuration-overview.md` |
| 2 | `docs/architecture/observability.md` |
| 3 | `docs/design/domain-model.md`, `docs/design/customer-profile.md` |
| 4 | `docs/design/decisions/001-storage-choice.md` |
| 5 | `docs/design/decisions/001-storage-choice.md` (Provider section) |
| 6 | `docs/architecture/selection-strategies.md` |
| 6.5 | `docs/focal_360/architecture/ACF_ARCHITECTURE.md`, `docs/focal_360/architecture/ACF_SPEC.md`, `docs/focal_360/architecture/AGENT_RUNTIME_SPEC.md` |
| 7-11 | `docs/architecture/alignment-engine.md`, `docs/focal_turn_pipeline/spec/pipeline.md` |
| 8 | `docs/design/decisions/002-rule-matching-strategy.md` |
| 12 | `docs/architecture/memory-layer.md` |
| 13-14 | `docs/architecture/api-layer.md`, `docs/design/api-crud.md` |
| 15 | `docs/design/scenario-update-methods.md` |
| 17.5 | `specs/010-customer-context-vault/spec.md`, `docs/design/customer-profile.md` |
| All | `docs/vision.md`, `docs/architecture/overview.md` |

---

## Implementation Order Rationale

1. **Phases 0-2**: Foundation - Can't build anything without folder structure, configuration, and logging
2. **Phases 3-5**: Core abstractions - Define interfaces before implementations
3. **Phase 6**: Selection strategies - Needed for retrieval
4. **Phase 6.5**: ACF - Foundation for concurrency/turn orchestration
5. **Phases 7-11**: Pipeline - Build each step, then integrate
6. **Phase 12**: Memory - Enhances alignment but not strictly required
7. **Phases 13-14**: API - Expose the engine externally
8. **Phase 15**: Migration - Advanced scenario handling
9. **Phases 16-17**: Production backends - Replace mocks with real implementations
10. **Phase 17.5**: Customer Data Store Enhancement - Lineage, status, schema, caching
11. **Phases 18-20**: Polish - Optional features and deployment

Each phase should be completable independently, with tests passing at each stage.
