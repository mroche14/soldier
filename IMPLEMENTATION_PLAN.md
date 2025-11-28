# Soldier Implementation Plan

A comprehensive, phased implementation plan for building the Soldier cognitive engine from the ground up.

---

## Phase 0: Project Skeleton & Foundation
**Goal**: Create the complete folder structure and base infrastructure

### 0.1 Create Folder Structure
> Reference: `docs/architecture/folder-structure.md`

- [ ] Create top-level structure:
  ```
  soldier/
  ├── config/                  # TOML configuration files
  ├── soldier/                 # Main Python package
  ├── tests/                   # Test suite
  ├── docs/                    # Documentation (exists)
  └── deploy/                  # Kubernetes, Docker
  ```

- [ ] Create `config/` directory with TOML files:
  - [ ] `config/default.toml` - Base defaults
  - [ ] `config/development.toml` - Local dev overrides
  - [ ] `config/staging.toml` - Staging environment
  - [ ] `config/production.toml` - Production environment
  - [ ] `config/test.toml` - Test environment

- [ ] Create `soldier/` package structure:
  - [ ] `soldier/__init__.py`
  - [ ] `soldier/alignment/` - The brain
  - [ ] `soldier/memory/` - Long-term memory
  - [ ] `soldier/conversation/` - Live state
  - [ ] `soldier/audit/` - What happened
  - [ ] `soldier/observability/` - Logging, tracing, metrics
  - [ ] `soldier/providers/` - External services
  - [ ] `soldier/api/` - HTTP/gRPC interfaces
  - [ ] `soldier/config/` - Configuration loading
  - [ ] `soldier/profile/` - Customer profiles

- [ ] Create `tests/` structure mirroring `soldier/`:
  - [ ] `tests/unit/`
  - [ ] `tests/integration/`
  - [ ] `tests/e2e/`

- [ ] Create `deploy/` structure:
  - [ ] `deploy/docker/`
  - [ ] `deploy/kubernetes/`

### 0.2 Project Configuration Files
- [ ] `pyproject.toml` - Project metadata, dependencies
- [ ] `.env.example` - Environment variable template
- [ ] `Dockerfile` - Container build
- [ ] `docker-compose.yml` - Local development stack
- [ ] `Makefile` - Common commands

---

## Phase 1: Configuration System
**Goal**: Build the configuration loading system with Pydantic validation
> Reference: `docs/architecture/configuration-overview.md`, `docs/architecture/folder-structure.md` (config section)

### 1.1 Configuration Loader
- [ ] `soldier/config/__init__.py`
- [ ] `soldier/config/loader.py` - TOML loader with environment resolution
  - [ ] Load TOML files by environment
  - [ ] Resolve `${ENV_VAR}` placeholders
  - [ ] Merge defaults → environment → env vars
- [ ] `soldier/config/settings.py` - Root Settings class
  - [ ] `get_settings()` singleton function
  - [ ] Environment-aware loading

### 1.2 Configuration Models (Pydantic)
> Reference: `docs/architecture/configuration-overview.md`

- [ ] `soldier/config/models/__init__.py`
- [ ] `soldier/config/models/api.py` - APIConfig
  - [ ] Host, port, CORS settings
  - [ ] Rate limit configuration
- [ ] `soldier/config/models/storage.py` - Storage backend configs
  - [ ] ConfigStoreConfig
  - [ ] MemoryStoreConfig
  - [ ] SessionStoreConfig
  - [ ] AuditStoreConfig
- [ ] `soldier/config/models/providers.py` - Provider configs
  - [ ] LLMProviderConfig
  - [ ] EmbeddingProviderConfig
  - [ ] RerankProviderConfig
- [ ] `soldier/config/models/pipeline.py` - Pipeline step configs
  - [ ] ContextExtractionConfig
  - [ ] RetrievalConfig
  - [ ] RerankingConfig
  - [ ] LLMFilteringConfig
  - [ ] GenerationConfig
  - [ ] EnforcementConfig
- [ ] `soldier/config/models/selection.py` - Selection strategy configs
  - [ ] ElbowSelectionConfig
  - [ ] AdaptiveKSelectionConfig
  - [ ] EntropySelectionConfig
  - [ ] ClusterSelectionConfig
  - [ ] FixedKSelectionConfig
- [ ] `soldier/config/models/observability.py` - Observability configs
  - [ ] LoggingConfig
  - [ ] TracingConfig
  - [ ] MetricsConfig
- [ ] `soldier/config/models/agent.py` - Per-agent overrides

### 1.3 Default Configuration
- [ ] Write `config/default.toml` with all sections
- [ ] Write `config/development.toml` with dev overrides
- [ ] Write `config/test.toml` with in-memory backends

### 1.4 Configuration Tests
- [ ] `tests/unit/config/test_loader.py`
- [ ] `tests/unit/config/test_settings.py`
- [ ] `tests/unit/config/test_models.py`

---

## Phase 2: Observability Foundation
**Goal**: Set up structured logging, tracing, and metrics
> Reference: `docs/architecture/observability.md`

### 2.1 Logging
- [ ] `soldier/observability/__init__.py`
- [ ] `soldier/observability/logging.py`
  - [ ] `setup_logging()` - Configure structlog
  - [ ] `get_logger()` - Get bound logger
  - [ ] JSON formatter for production
  - [ ] Console formatter for development
  - [ ] PII redaction processor

### 2.2 Tracing
- [ ] `soldier/observability/tracing.py`
  - [ ] `setup_tracing()` - Configure OpenTelemetry
  - [ ] OTLP exporter configuration
  - [ ] Span helpers for pipeline steps

### 2.3 Metrics
- [ ] `soldier/observability/metrics.py`
  - [ ] Prometheus counters: requests, LLM calls, rule fires
  - [ ] Histograms: latency per step, tokens used
  - [ ] Gauges: active sessions

### 2.4 Middleware
- [ ] `soldier/observability/middleware.py`
  - [ ] Request context binding
  - [ ] tenant_id, agent_id, session_id extraction
  - [ ] Trace ID propagation

### 2.5 Tests
- [ ] `tests/unit/observability/test_logging.py`
- [ ] `tests/unit/observability/test_metrics.py`

---

## Phase 3: Domain Models
**Goal**: Define all core domain models with Pydantic
> Reference: `docs/design/domain-model.md`

### 3.1 Alignment Models
> Reference: `docs/architecture/alignment-engine.md`

- [ ] `soldier/alignment/models/__init__.py`
- [ ] `soldier/alignment/models/rule.py`
  - [ ] Rule (condition, action, scope, priority)
  - [ ] MatchedRule (with scores)
  - [ ] RuleScope enum
- [ ] `soldier/alignment/models/scenario.py`
  - [ ] Scenario
  - [ ] ScenarioStep
  - [ ] StepTransition
  - [ ] ScenarioFilterResult
- [ ] `soldier/alignment/models/template.py`
  - [ ] Template
  - [ ] TemplateMode enum (SUGGEST, EXCLUSIVE, FALLBACK)
- [ ] `soldier/alignment/models/variable.py`
  - [ ] Variable
  - [ ] VariableUpdatePolicy enum
- [ ] `soldier/alignment/models/context.py`
  - [ ] Context
  - [ ] UserIntent
  - [ ] ExtractedEntities

### 3.2 Memory Models
> Reference: `docs/architecture/memory-layer.md`

- [ ] `soldier/memory/models/__init__.py`
- [ ] `soldier/memory/models/episode.py`
  - [ ] Episode (atomic memory unit)
  - [ ] Bi-temporal attributes (valid_from, valid_to, recorded_at)
- [ ] `soldier/memory/models/entity.py`
  - [ ] Entity (named thing in knowledge graph)
- [ ] `soldier/memory/models/relationship.py`
  - [ ] Relationship (edge between entities)

### 3.3 Conversation Models
- [ ] `soldier/conversation/models/__init__.py`
- [ ] `soldier/conversation/models/session.py`
  - [ ] Session (active conversation state)
  - [ ] Link to CustomerProfile
- [ ] `soldier/conversation/models/turn.py`
  - [ ] Turn (single exchange)

### 3.4 Audit Models
- [ ] `soldier/audit/models/__init__.py`
- [ ] `soldier/audit/models/turn_record.py`
  - [ ] TurnRecord (full turn with metadata)
- [ ] `soldier/audit/models/event.py`
  - [ ] AuditEvent (tool calls, errors)

### 3.5 Profile Models
> Reference: `docs/design/customer-profile.md`

- [ ] `soldier/profile/__init__.py`
- [ ] `soldier/profile/models.py`
  - [ ] CustomerProfile
  - [ ] ChannelIdentity
  - [ ] ProfileField
  - [ ] ProfileFieldSource enum
  - [ ] ProfileAsset
  - [ ] VerificationLevel enum
  - [ ] Consent
  - [ ] ProfileFieldDefinition

### 3.6 Tests
- [ ] `tests/unit/alignment/test_models.py`
- [ ] `tests/unit/memory/test_models.py`
- [ ] `tests/unit/conversation/test_models.py`
- [ ] `tests/unit/profile/test_models.py`

---

## Phase 4: Store Interfaces & In-Memory Implementations
**Goal**: Define all store interfaces and implement in-memory versions for testing
> Reference: `docs/design/decisions/001-storage-choice.md`

### 4.1 ConfigStore
- [ ] `soldier/alignment/stores/__init__.py`
- [ ] `soldier/alignment/stores/config_store.py` - Interface (ABC)
  - [ ] `get_rules()`, `get_rule()`, `save_rule()`, `delete_rule()`
  - [ ] `vector_search_rules()`
  - [ ] `get_scenarios()`, `get_scenario()`, `save_scenario()`
  - [ ] `get_templates()`, `save_template()`
  - [ ] `get_variables()`
  - [ ] `get_agent()`, `save_agent()`
- [ ] `soldier/alignment/stores/inmemory.py` - InMemoryConfigStore

### 4.2 MemoryStore
- [ ] `soldier/memory/store.py` - Interface (ABC)
  - [ ] `add_episode()`, `get_episode()`
  - [ ] `vector_search_episodes()`, `text_search_episodes()`
  - [ ] `add_entity()`, `get_entities()`
  - [ ] `add_relationship()`, `traverse_from_entities()`
  - [ ] `delete_by_group()`
- [ ] `soldier/memory/stores/__init__.py`
- [ ] `soldier/memory/stores/inmemory.py` - InMemoryMemoryStore

### 4.3 SessionStore
- [ ] `soldier/conversation/store.py` - Interface (ABC)
  - [ ] `get()`, `save()`, `delete()`
  - [ ] `list_by_agent()`
- [ ] `soldier/conversation/stores/__init__.py`
- [ ] `soldier/conversation/stores/inmemory.py` - InMemorySessionStore

### 4.4 AuditStore
- [ ] `soldier/audit/store.py` - Interface (ABC)
  - [ ] `save_turn()`, `get_turn()`
  - [ ] `list_turns_by_session()`, `list_turns_by_tenant()`
  - [ ] `save_event()`
- [ ] `soldier/audit/stores/__init__.py`
- [ ] `soldier/audit/stores/inmemory.py` - InMemoryAuditStore

### 4.5 ProfileStore
- [ ] `soldier/profile/store.py` - Interface (ABC)
  - [ ] `get_by_customer_id()`, `get_by_channel_identity()`
  - [ ] `get_or_create()`
  - [ ] `update_field()`, `add_asset()`
  - [ ] `merge_profiles()`, `link_channel()`
- [ ] `soldier/profile/stores/__init__.py`
- [ ] `soldier/profile/stores/inmemory.py` - InMemoryProfileStore

### 4.6 Tests
- [ ] `tests/unit/alignment/stores/test_inmemory_config.py`
- [ ] `tests/unit/memory/stores/test_inmemory_memory.py`
- [ ] `tests/unit/conversation/stores/test_inmemory_session.py`
- [ ] `tests/unit/audit/stores/test_inmemory_audit.py`
- [ ] `tests/unit/profile/stores/test_inmemory_profile.py`

---

## Phase 5: Provider Interfaces & Mock Implementations
**Goal**: Define provider interfaces and mock implementations for testing
> Reference: `docs/design/decisions/001-storage-choice.md` (Provider section)

### 5.1 LLM Provider
- [ ] `soldier/providers/__init__.py`
- [ ] `soldier/providers/llm/__init__.py`
- [ ] `soldier/providers/llm/base.py` - LLMProvider interface
  - [ ] `generate()` - Text completion
  - [ ] `generate_structured()` - Structured output
  - [ ] LLMResponse model
  - [ ] TokenUsage model
- [ ] `soldier/providers/llm/mock.py` - MockLLMProvider

### 5.2 Embedding Provider
- [ ] `soldier/providers/embedding/__init__.py`
- [ ] `soldier/providers/embedding/base.py` - EmbeddingProvider interface
  - [ ] `dimensions` property
  - [ ] `embed()` - Single text
  - [ ] `embed_batch()` - Batch embedding
- [ ] `soldier/providers/embedding/mock.py` - MockEmbeddingProvider

### 5.3 Rerank Provider
- [ ] `soldier/providers/rerank/__init__.py`
- [ ] `soldier/providers/rerank/base.py` - RerankProvider interface
  - [ ] `rerank()` - Rerank documents
  - [ ] RerankResult model
- [ ] `soldier/providers/rerank/mock.py` - MockRerankProvider

### 5.4 Provider Factory
- [ ] `soldier/providers/factory.py`
  - [ ] `create_llm_provider(config)`
  - [ ] `create_embedding_provider(config)`
  - [ ] `create_rerank_provider(config)`

### 5.5 Tests
- [ ] `tests/unit/providers/test_llm_mock.py`
- [ ] `tests/unit/providers/test_embedding_mock.py`
- [ ] `tests/unit/providers/test_rerank_mock.py`

---

## Phase 6: Selection Strategies
**Goal**: Implement dynamic k-selection strategies for retrieval
> Reference: `docs/architecture/selection-strategies.md`

### 6.1 Selection Interface & Models
- [ ] `soldier/alignment/retrieval/__init__.py`
- [ ] `soldier/alignment/retrieval/selection.py`
  - [ ] SelectionStrategy interface (ABC)
  - [ ] ScoredItem generic model
  - [ ] SelectionResult model
  - [ ] `create_selection_strategy()` factory

### 6.2 Strategy Implementations
- [ ] ElbowSelectionStrategy (relative score drop)
- [ ] AdaptiveKSelectionStrategy (curvature analysis)
- [ ] EntropySelectionStrategy (information method)
- [ ] ClusterSelectionStrategy (topic clustering)
- [ ] FixedKSelectionStrategy (baseline)

### 6.3 Tests
- [ ] `tests/unit/alignment/retrieval/test_selection.py`
  - [ ] Test each strategy with various score distributions
  - [ ] Test edge cases (empty, single item, identical scores)

---

## Phase 7: Alignment Pipeline - Context Extraction
**Goal**: Implement context extraction (understanding user messages)
> Reference: `docs/architecture/alignment-engine.md`, `docs/design/turn-pipeline.md`

### 7.1 Context Extractor
- [ ] `soldier/alignment/context/__init__.py`
- [ ] `soldier/alignment/context/extractor.py`
  - [ ] ContextExtractor interface
  - [ ] LLMContextExtractor implementation
  - [ ] RuleBasedContextExtractor (simple patterns)
- [ ] `soldier/alignment/context/models.py`
  - [ ] Context model
  - [ ] UserIntent model
  - [ ] ExtractedEntities model
- [ ] `soldier/alignment/context/prompts/`
  - [ ] `extract_intent.txt` - Intent extraction prompt

### 7.2 Tests
- [ ] `tests/unit/alignment/context/test_extractor.py`

---

## Phase 8: Alignment Pipeline - Retrieval
**Goal**: Implement rule, scenario, and memory retrieval
> Reference: `docs/design/decisions/002-rule-matching-strategy.md`

### 8.1 Rule Retrieval
- [ ] `soldier/alignment/retrieval/rule_retriever.py`
  - [ ] RuleRetriever class
  - [ ] Vector similarity search
  - [ ] BM25 hybrid search
  - [ ] Scope filtering (GLOBAL → SCENARIO → STEP)
  - [ ] Selection strategy application

### 8.2 Scenario Retrieval
- [ ] `soldier/alignment/retrieval/scenario_retriever.py`
  - [ ] ScenarioRetriever class
  - [ ] Entry condition matching
  - [ ] Active scenario continuation

### 8.3 Memory Retrieval
- [ ] `soldier/memory/retrieval/__init__.py`
- [ ] `soldier/memory/retrieval/retriever.py`
  - [ ] MemoryRetriever class
  - [ ] Hybrid retrieval (vector + BM25 + graph)

### 8.4 Reranker
- [ ] `soldier/alignment/retrieval/reranker.py`
  - [ ] ResultReranker class
  - [ ] Provider-agnostic reranking

### 8.5 Tests
- [ ] `tests/unit/alignment/retrieval/test_rule_retriever.py`
- [ ] `tests/unit/alignment/retrieval/test_scenario_retriever.py`
- [ ] `tests/unit/memory/retrieval/test_retriever.py`

---

## Phase 9: Alignment Pipeline - Filtering
**Goal**: Implement LLM-based filtering (judging relevance)
> Reference: `docs/architecture/alignment-engine.md`

### 9.1 Rule Filter
- [ ] `soldier/alignment/filtering/__init__.py`
- [ ] `soldier/alignment/filtering/rule_filter.py`
  - [ ] RuleFilter class
  - [ ] LLM-based condition evaluation
  - [ ] Batch filtering for efficiency
- [ ] `soldier/alignment/filtering/prompts/filter_rules.txt`

### 9.2 Scenario Filter
- [ ] `soldier/alignment/filtering/scenario_filter.py`
  - [ ] ScenarioFilter class
  - [ ] Start/continue/exit decisions
  - [ ] Step transition evaluation
- [ ] `soldier/alignment/filtering/prompts/evaluate_scenario.txt`

### 9.3 Tests
- [ ] `tests/unit/alignment/filtering/test_rule_filter.py`
- [ ] `tests/unit/alignment/filtering/test_scenario_filter.py`

---

## Phase 10: Alignment Pipeline - Execution & Generation
**Goal**: Implement tool execution and response generation
> Reference: `docs/design/turn-pipeline.md`

### 10.1 Tool Execution
- [ ] `soldier/alignment/execution/__init__.py`
- [ ] `soldier/alignment/execution/tool_executor.py`
  - [ ] ToolExecutor class
  - [ ] Execute tools from matched rules
  - [ ] Timeout handling
  - [ ] Result aggregation
- [ ] `soldier/alignment/execution/variable_resolver.py`
  - [ ] VariableResolver class
  - [ ] Resolve variables from profile/session

### 10.2 Response Generation
- [ ] `soldier/alignment/generation/__init__.py`
- [ ] `soldier/alignment/generation/prompt_builder.py`
  - [ ] PromptBuilder class
  - [ ] Assemble system prompt with rules, memory, context
- [ ] `soldier/alignment/generation/generator.py`
  - [ ] ResponseGenerator class
  - [ ] LLM-based response generation
  - [ ] Template interpolation
- [ ] `soldier/alignment/generation/prompts/system_prompt.txt`

### 10.3 Enforcement
- [ ] `soldier/alignment/enforcement/__init__.py`
- [ ] `soldier/alignment/enforcement/validator.py`
  - [ ] EnforcementValidator class
  - [ ] Check response against hard constraints
  - [ ] Self-critique (optional)
- [ ] `soldier/alignment/enforcement/fallback.py`
  - [ ] FallbackHandler class
  - [ ] Template fallback logic

### 10.4 Tests
- [ ] `tests/unit/alignment/execution/test_tool_executor.py`
- [ ] `tests/unit/alignment/generation/test_generator.py`
- [ ] `tests/unit/alignment/enforcement/test_validator.py`

---

## Phase 11: Alignment Engine Integration
**Goal**: Wire together all pipeline components
> Reference: `docs/architecture/alignment-engine.md`

### 11.1 Alignment Engine
- [ ] `soldier/alignment/__init__.py`
- [ ] `soldier/alignment/engine.py`
  - [ ] AlignmentEngine class
  - [ ] `process_turn()` - Full pipeline orchestration
  - [ ] Step timing and logging
  - [ ] Error handling and fallbacks
- [ ] `soldier/alignment/result.py`
  - [ ] AlignmentResult model
  - [ ] TurnMetadata model

### 11.2 Pipeline Configuration
- [ ] Pipeline step enable/disable
- [ ] Per-step provider selection
- [ ] Timeout configuration

### 11.3 Integration Tests
- [ ] `tests/integration/test_alignment_engine.py`
  - [ ] Full pipeline with mock providers
  - [ ] Rule matching → filtering → generation

---

## Phase 12: Memory Layer
**Goal**: Implement memory ingestion and retrieval
> Reference: `docs/architecture/memory-layer.md`

### 12.1 Memory Ingestion
- [ ] `soldier/memory/ingestion/__init__.py`
- [ ] `soldier/memory/ingestion/ingestor.py`
  - [ ] MemoryIngestor class
  - [ ] Episode creation from turns
  - [ ] Embedding generation
- [ ] `soldier/memory/ingestion/entity_extractor.py`
  - [ ] EntityExtractor class
  - [ ] LLM-based entity extraction
- [ ] `soldier/memory/ingestion/summarizer.py`
  - [ ] ConversationSummarizer class
  - [ ] Hierarchical summarization

### 12.2 Tests
- [ ] `tests/unit/memory/ingestion/test_ingestor.py`
- [ ] `tests/unit/memory/ingestion/test_entity_extractor.py`

---

## Phase 13: API Layer - Core
**Goal**: Implement HTTP API endpoints
> Reference: `docs/architecture/api-layer.md`, `docs/design/api-crud.md`

### 13.1 FastAPI Application
- [ ] `soldier/api/__init__.py`
- [ ] `soldier/api/app.py` - FastAPI app factory
  - [ ] Middleware setup
  - [ ] Route registration
  - [ ] Exception handlers

### 13.2 API Models
- [ ] `soldier/api/models/__init__.py`
- [ ] `soldier/api/models/chat.py`
  - [ ] ChatRequest
  - [ ] ChatResponse
- [ ] `soldier/api/models/errors.py`
  - [ ] ErrorResponse
  - [ ] Error codes enum

### 13.3 Core Routes
- [ ] `soldier/api/routes/__init__.py`
- [ ] `soldier/api/routes/chat.py`
  - [ ] `POST /v1/chat` - Process message
  - [ ] `POST /v1/chat/stream` - SSE streaming
- [ ] `soldier/api/routes/sessions.py`
  - [ ] `GET /v1/sessions/{id}` - Get session
  - [ ] `DELETE /v1/sessions/{id}` - End session
  - [ ] `GET /v1/sessions/{id}/turns` - Session history
- [ ] `soldier/api/routes/health.py`
  - [ ] `GET /health` - Health check
  - [ ] `GET /metrics` - Prometheus metrics

### 13.4 Middleware
- [ ] `soldier/api/middleware/__init__.py`
- [ ] `soldier/api/middleware/auth.py`
  - [ ] JWT validation
  - [ ] Tenant extraction
- [ ] `soldier/api/middleware/rate_limit.py`
  - [ ] Per-tenant rate limiting

### 13.5 Tests
- [ ] `tests/unit/api/test_chat.py`
- [ ] `tests/unit/api/test_sessions.py`
- [ ] `tests/integration/api/test_chat_flow.py`

---

## Phase 14: API Layer - CRUD Operations
**Goal**: Implement configuration CRUD endpoints
> Reference: `docs/design/api-crud.md`

### 14.1 Agent Routes
- [ ] `soldier/api/routes/agents.py`
  - [ ] `GET /v1/agents` - List agents
  - [ ] `GET /v1/agents/{id}` - Get agent
  - [ ] `POST /v1/agents` - Create agent
  - [ ] `PUT /v1/agents/{id}` - Update agent
  - [ ] `DELETE /v1/agents/{id}` - Delete agent

### 14.2 Rules Routes
- [ ] `soldier/api/routes/rules.py`
  - [ ] `GET /v1/agents/{id}/rules` - List rules
  - [ ] `GET /v1/agents/{id}/rules/{rule_id}` - Get rule
  - [ ] `POST /v1/agents/{id}/rules` - Create rule
  - [ ] `PUT /v1/agents/{id}/rules/{rule_id}` - Update rule
  - [ ] `DELETE /v1/agents/{id}/rules/{rule_id}` - Delete rule
  - [ ] `POST /v1/agents/{id}/rules/bulk` - Bulk operations

### 14.3 Scenarios Routes
- [ ] `soldier/api/routes/scenarios.py`
  - [ ] Scenario CRUD
  - [ ] Step CRUD

### 14.4 Templates Routes
- [ ] `soldier/api/routes/templates.py`
  - [ ] Template CRUD
  - [ ] `POST /preview` - Template preview

### 14.5 Tests
- [ ] `tests/unit/api/test_rules.py`
- [ ] `tests/unit/api/test_scenarios.py`
- [ ] `tests/unit/api/test_templates.py`

---

## Phase 15: Scenario Migration System
**Goal**: Implement scenario update handling for active sessions
> Reference: `docs/design/scenario-update-methods.md`

### 15.1 Migration Plan Generation
- [ ] `soldier/alignment/migration/__init__.py`
- [ ] `soldier/alignment/migration/models.py`
  - [ ] MigrationPlan
  - [ ] StepMigrationAction
  - [ ] MigrationSummary
  - [ ] MigrationWarning
- [ ] `soldier/alignment/migration/generator.py`
  - [ ] `generate_migration_plan()` - Compute plan on scenario update
  - [ ] `compute_step_action()` - Per-step action determination

### 15.2 Migration Application
- [ ] `soldier/alignment/migration/applicator.py`
  - [ ] `pre_turn_reconciliation()` - Check for updates before turn
  - [ ] `apply_migration_plan()` - Apply plan to session
  - [ ] `execute_composite_migration()` - Handle version gaps

### 15.3 Gap Fill
- [ ] `soldier/alignment/migration/gap_fill.py`
  - [ ] `fill_gap()` - Profile → session → extraction → ask
  - [ ] Conversation extraction via LLM

### 15.4 Tests
- [ ] `tests/unit/alignment/migration/test_generator.py`
- [ ] `tests/unit/alignment/migration/test_applicator.py`
- [ ] `tests/integration/test_scenario_migration.py`

---

## Phase 16: Production Store Implementations
**Goal**: Implement real database backends

### 16.1 PostgreSQL Stores
> Reference: `docs/design/decisions/001-storage-choice.md`

- [ ] `soldier/alignment/stores/postgres.py` - PostgresConfigStore
- [ ] `soldier/memory/stores/postgres.py` - PostgresMemoryStore (pgvector)
- [ ] `soldier/audit/stores/postgres.py` - PostgresAuditStore
- [ ] `soldier/profile/stores/postgres.py` - PostgresProfileStore

### 16.2 Redis Session Store
- [ ] `soldier/conversation/stores/redis.py` - RedisSessionStore
  - [ ] Two-tier (cache + persistent)
  - [ ] TTL management

### 16.3 Additional Backends (Optional)
- [ ] MongoDB stores
- [ ] Neo4j memory store
- [ ] DynamoDB session store

### 16.4 Database Migrations
- [ ] Alembic setup for PostgreSQL
- [ ] Migration scripts

### 16.5 Integration Tests
- [ ] `tests/integration/stores/test_postgres_config.py`
- [ ] `tests/integration/stores/test_postgres_memory.py`
- [ ] `tests/integration/stores/test_redis_session.py`

---

## Phase 17: Production Provider Implementations
**Goal**: Implement real AI provider integrations

### 17.1 LLM Providers
- [ ] `soldier/providers/llm/anthropic.py` - AnthropicProvider
- [ ] `soldier/providers/llm/openai.py` - OpenAIProvider
- [ ] `soldier/providers/llm/bedrock.py` - BedrockProvider (optional)
- [ ] `soldier/providers/llm/ollama.py` - OllamaProvider (optional)

### 17.2 Embedding Providers
- [ ] `soldier/providers/embedding/openai.py` - OpenAIEmbeddings
- [ ] `soldier/providers/embedding/cohere.py` - CohereEmbeddings
- [ ] `soldier/providers/embedding/sentence_transformers.py` - Local

### 17.3 Rerank Providers
- [ ] `soldier/providers/rerank/cohere.py` - CohereRerank
- [ ] `soldier/providers/rerank/cross_encoder.py` - Local CrossEncoder

### 17.4 Integration Tests
- [ ] `tests/integration/providers/test_anthropic.py`
- [ ] `tests/integration/providers/test_openai.py`

---

## Phase 18: gRPC API (Optional)
**Goal**: Add gRPC interface for service-to-service communication
> Reference: `docs/architecture/api-layer.md` (gRPC section)

### 18.1 Proto Definitions
- [ ] `soldier/api/grpc/protos/soldier.proto`
  - [ ] ChatService
  - [ ] MemoryService
  - [ ] ConfigService

### 18.2 gRPC Server
- [ ] `soldier/api/grpc/__init__.py`
- [ ] `soldier/api/grpc/server.py`
- [ ] `soldier/api/grpc/servicers/chat.py`

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
| 7-11 | `docs/architecture/alignment-engine.md`, `docs/design/turn-pipeline.md` |
| 8 | `docs/design/decisions/002-rule-matching-strategy.md` |
| 12 | `docs/architecture/memory-layer.md` |
| 13-14 | `docs/architecture/api-layer.md`, `docs/design/api-crud.md` |
| 15 | `docs/design/scenario-update-methods.md` |
| All | `docs/vision.md`, `docs/architecture/overview.md` |

---

## Implementation Order Rationale

1. **Phases 0-2**: Foundation - Can't build anything without folder structure, configuration, and logging
2. **Phases 3-5**: Core abstractions - Define interfaces before implementations
3. **Phase 6**: Selection strategies - Needed for retrieval
4. **Phases 7-11**: Pipeline - Build each step, then integrate
5. **Phase 12**: Memory - Enhances alignment but not strictly required
6. **Phases 13-14**: API - Expose the engine externally
7. **Phase 15**: Migration - Advanced scenario handling
8. **Phases 16-17**: Production backends - Replace mocks with real implementations
9. **Phases 18-20**: Polish - Optional features and deployment

Each phase should be completable independently, with tests passing at each stage.
