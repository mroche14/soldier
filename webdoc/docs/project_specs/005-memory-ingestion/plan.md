# Implementation Plan: Memory Ingestion System

**Branch**: `005-memory-ingestion` | **Date**: 2025-11-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-memory-ingestion/spec.md`

## Summary

Implement the Memory Ingestion System to automatically capture conversation turns as episodes, extract entities and relationships using LLM-based analysis, and generate hierarchical summaries for long conversations. This system builds on existing Episode, Entity, and Relationship models defined in the domain layer, adding the orchestration logic (MemoryIngestor), extraction intelligence (EntityExtractor), and compression capability (ConversationSummarizer).

**Primary requirement**: Process conversation turns into structured memory with <500ms latency for episode creation and <2s for full entity extraction (async).

**Technical approach**:
- LLM-based entity extraction via existing LLMProvider interface
- Multi-stage entity deduplication (exact → fuzzy → embedding → rule-based)
- Bi-temporal graph updates for relationship versioning
- Async task queue (Redis or in-memory) for extraction and summarization
- Sentence-transformers for local embeddings with OpenAI fallback
- Hierarchical abstractive summarization (window + meta-summaries)

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- pydantic (existing) - Data validation and structured output
- sentence-transformers - Local embedding generation
- fuzzywuzzy - Fuzzy string matching for deduplication
- rq (optional) - Redis task queue for production
- All existing Focal dependencies (LLMProvider, EmbeddingProvider, MemoryStore)

**Storage**: MemoryStore interface (InMemory for dev, PostgreSQL/Neo4j/MongoDB for production)
**Testing**: pytest, existing test infrastructure (unit, integration, e2e)
**Target Platform**: Linux server, async Python runtime
**Project Type**: Single (backend service, no frontend)

**Performance Goals**:
- Episode creation: <500ms p95
- Entity extraction: <2s p95 (async)
- Entity deduplication: <100ms p95
- Summarization: <2s per window (async)
- Memory growth: <1MB per 100 turns

**Constraints**:
- Must not block conversation flow (async extraction/summarization)
- Must maintain tenant isolation (all queries filtered by group_id)
- Must handle LLM provider failures gracefully (no crashes)
- Must be configuration-driven (enable/disable features per agent)

**Scale/Scope**:
- Support 1000+ concurrent sessions
- Handle conversations up to 200+ turns efficiently
- Process 100 episodes/second ingestion rate
- 85%+ entity extraction accuracy

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: ✅ PASSED

No constitution file present - skipping formal gate checks.

**Informal architectural alignment**:
- ✅ Uses existing provider interfaces (LLMProvider, EmbeddingProvider)
- ✅ Configuration-driven via TOML
- ✅ Multi-tenant by design (group_id on all entities)
- ✅ Async-first architecture
- ✅ Observable (structured logging, spans, metrics)
- ✅ No in-memory state (uses external stores)

---

## Project Structure

### Documentation (this feature)

```text
specs/005-memory-ingestion/
├── spec.md              # Feature specification
├── plan.md              # This file (implementation plan)
├── research.md          # Technical research and decisions
├── data-model.md        # Data models and relationships
├── quickstart.md        # Usage guide
├── contracts/           # Service interface contracts
│   └── service-interfaces.md
└── tasks.md             # (Created by /speckit.tasks command - NOT created yet)
```

### Source Code (repository root)

```text
focal/
├── memory/
│   ├── __init__.py
│   ├── models/                 # (existing)
│   │   ├── episode.py
│   │   ├── entity.py
│   │   └── relationship.py
│   ├── store.py                # (existing interface)
│   ├── stores/                 # (existing implementations)
│   │   ├── inmemory.py
│   │   ├── postgres.py
│   │   ├── neo4j.py
│   │   └── mongodb.py
│   ├── ingestion/              # (NEW - this feature)
│   │   ├── __init__.py
│   │   ├── ingestor.py         # MemoryIngestor orchestrator
│   │   ├── entity_extractor.py # EntityExtractor + deduplication
│   │   └── summarizer.py       # ConversationSummarizer
│   └── retrieval/              # (existing)
│       ├── retriever.py
│       └── reranker.py
├── config/
│   └── models/
│       └── pipeline.py         # Add MemoryIngestionConfig
├── providers/
│   └── embedding/              # Add SentenceTransformersProvider
│       └── sentence_transformers.py

tests/
├── unit/
│   └── memory/
│       └── ingestion/          # (NEW)
│           ├── test_ingestor.py
│           ├── test_entity_extractor.py
│           └── test_summarizer.py
└── integration/
    └── memory/
        └── test_ingestion_flow.py  # (NEW)
```

**Structure Decision**: Single project with new `focal/memory/ingestion/` module. Builds on existing memory infrastructure without modifying existing code. All new functionality is opt-in via configuration.

---

## Complexity Tracking

No complexity violations - feature aligns with existing architecture:
- Uses existing provider interfaces
- Follows configuration-driven pattern
- Extends existing memory models
- No new architectural patterns introduced

---

## Phase 0: Research ✅ COMPLETE

All technical research completed and documented in [`research.md`](./research.md).

**Deliverables**:
- ✅ Entity Extraction Approach: LLM-based with structured output
- ✅ Entity Deduplication Strategy: Multi-stage hybrid (exact/fuzzy/embedding/rule)
- ✅ Temporal Graph Update Pattern: Bi-temporal versioning (valid_from/valid_to)
- ✅ Async Task Pattern: Fire-and-forget with fallback queue
- ✅ Embedding Model Selection: Sentence-transformers with OpenAI fallback
- ✅ Summarization Strategy: Hierarchical abstractive (window + meta)

---

## Phase 1: Design & Contracts ✅ COMPLETE

**Deliverables**:
- ✅ Data Model [`data-model.md`](./data-model.md)
  - Episode, Entity, Relationship models (extended existing)
  - MemoryIngestor, EntityExtractor, ConversationSummarizer service models
  - Configuration models (MemoryIngestionConfig, EntityExtractionConfig, etc.)
  - Structured output models (ExtractedEntity, ExtractedRelationship)

- ✅ Service Contracts [`contracts/service-interfaces.md`](./contracts/service-interfaces.md)
  - MemoryIngestor interface (ingest_turn, ingest_event)
  - EntityExtractor interface (extract, extract_batch)
  - EntityDeduplicator interface (find_duplicate, merge_entities)
  - ConversationSummarizer interface (summarize_window, create_meta_summary)
  - Error handling contracts (IngestionError, ExtractionError, SummarizationError)
  - Observability contracts (logging, spans, metrics)

- ✅ Quickstart Guide [`quickstart.md`](./quickstart.md)
  - Configuration setup
  - Basic usage examples (ingest turn, extract entities, create summaries)
  - Advanced patterns (batch extraction, per-agent config)
  - Integration with alignment engine
  - Monitoring and debugging
  - Troubleshooting guide

---

## Phase 2: Implementation Tasks

**Status**: Ready for `/speckit.tasks`

Use `/speckit.tasks` command to generate actionable, dependency-ordered task list from this plan.

**Expected task categories**:
1. **Configuration & Models** (foundation)
   - Add MemoryIngestionConfig to pipeline.py
   - Add structured output models (ExtractedEntity, etc.)
   - Add sentence-transformers dependency

2. **Core Services** (P1 - episode creation)
   - Implement MemoryIngestor class
   - Implement embedding generation with fallback
   - Add async task queue abstraction

3. **Entity Extraction** (P2 - knowledge graph building)
   - Implement EntityExtractor with LLM structured output
   - Implement EntityDeduplicator (4-stage pipeline)
   - Implement temporal relationship updates

4. **Summarization** (P3 - long conversation handling)
   - Implement ConversationSummarizer
   - Implement window summarization
   - Implement meta-summarization

5. **Testing**
   - Unit tests for each component
   - Integration test for full ingestion flow
   - Contract tests for deduplication accuracy

6. **Observability**
   - Add structured logging to all components
   - Add OpenTelemetry spans
   - Add Prometheus metrics

---

## Implementation Phases (High-Level)

### Phase 2.1: Foundation (Configuration & Dependencies)
- Add configuration models
- Add sentence-transformers provider
- Add structured output models
- Update TOML files with defaults

### Phase 2.2: Core Ingestion (P1)
- Implement MemoryIngestor orchestrator
- Implement embedding generation
- Implement async task queue (in-memory version)
- Basic episode creation flow

### Phase 2.3: Entity Extraction (P2)
- Implement EntityExtractor with LLM calls
- Implement multi-stage deduplication
- Implement temporal relationship updates
- Entity and relationship storage

### Phase 2.4: Summarization (P3)
- Implement ConversationSummarizer
- Implement window summarization logic
- Implement meta-summary logic
- Threshold-based triggering

### Phase 2.5: Observability & Polish
- Add structured logging throughout
- Add OpenTelemetry spans
- Add Prometheus metrics
- Performance profiling and optimization

### Phase 2.6: Testing & Documentation
- Unit tests (85%+ coverage)
- Integration tests
- Update IMPLEMENTATION_PLAN.md checkboxes
- Code review and refinement

---

## Success Criteria

From [`spec.md`](./spec.md#success-criteria):

- ✅ **SC-001**: Episode creation completes within 500ms for 95% of turns
- ✅ **SC-002**: Entity extraction identifies 80%+ of factual entities
- ✅ **SC-003**: System handles 200+ turn conversations without degradation
- ✅ **SC-004**: Ingestion failures don't block conversation flow (graceful degradation)
- ✅ **SC-005**: Summaries reduce context size by 70%+ for 50+ turn conversations
- ✅ **SC-006**: Entity deduplication achieves 90%+ accuracy
- ✅ **SC-007**: Complete tenant isolation with zero data leakage

---

## Testing Strategy

### Unit Tests (Target: 85% coverage)

**MemoryIngestor**:
- Episode creation from turn
- Embedding generation and fallback
- Async task queuing
- Error handling (graceful degradation)

**EntityExtractor**:
- LLM structured output parsing
- Confidence filtering
- Batch extraction
- Provider timeout handling

**EntityDeduplicator**:
- Each deduplication stage independently
- Multi-stage pipeline (early exit)
- Entity merging logic

**ConversationSummarizer**:
- Window summarization
- Meta-summarization
- Threshold checking
- Summary storage

### Integration Tests

**Full Ingestion Flow**:
- Turn → Episode → Entities → Relationships → Summary
- End-to-end verification
- Use mock providers for determinism

**Temporal Updates**:
- Relationship invalidation (valid_to)
- New relationship creation (valid_from)
- Point-in-time queries

**Deduplication Accuracy**:
- Known duplicates correctly merged
- Non-duplicates remain separate
- Precision/recall measurement

**Summarization Quality**:
- Key facts preserved in summaries
- Compression ratio validation
- Meta-summary coverage

---

## Configuration Reference

**Full TOML configuration** (from [`research.md`](./research.md)):

```toml
[memory.ingestion]
enabled = true
embedding_enabled = true
entity_extraction_enabled = true
summarization_enabled = true
async_extraction = true
async_summarization = true
queue_backend = "inmemory"
max_ingestion_latency_ms = 500

[memory.ingestion.extraction]
enabled = true
llm_provider = "anthropic"
model = "haiku"
max_tokens = 1024
temperature = 0.3
batch_size = 10
timeout_ms = 2000
min_confidence = "medium"

[memory.ingestion.deduplication]
exact_match_enabled = true
fuzzy_match_enabled = true
fuzzy_threshold = 0.85
embedding_match_enabled = true
embedding_threshold = 0.80
rule_based_enabled = true

[memory.ingestion.embedding]
provider = "sentence_transformers"
model = "all-mpnet-base-v2"
batch_size = 32
max_latency_ms = 500

[memory.ingestion.embedding.fallback]
enabled = true
provider = "openai"
model = "text-embedding-3-small"

[memory.ingestion.summarization.window]
turns_per_summary = 20
llm_provider = "anthropic"
model = "haiku"
max_tokens = 256
temperature = 0.5

[memory.ingestion.summarization.meta]
summaries_per_meta = 5
enabled_at_turn_count = 100
llm_provider = "anthropic"
model = "haiku"
max_tokens = 512
temperature = 0.5

[memory.ingestion.queue]
redis_url = "redis://localhost:6379"
worker_count = 4
retry_attempts = 3
retry_backoff_seconds = 5
```

---

## Dependencies

**New**:
- `sentence-transformers` - Local embedding generation
- `python-Levenshtein` or `fuzzywuzzy` - Fuzzy string matching
- `rq` (optional, production) - Redis task queue

**Existing**:
- pydantic - Data models and validation
- structlog - Structured logging
- opentelemetry - Tracing
- prometheus-client - Metrics
- All existing Focal provider interfaces

**Installation**:
```bash
uv add sentence-transformers
uv add python-Levenshtein
uv add rq  # optional for production
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM provider timeout during extraction | High | Retry logic, fallback providers, graceful degradation |
| Embedding model too slow | Medium | Use faster model, fallback to API, async processing |
| Deduplication false positives | Medium | Tunable thresholds, manual review queue, accuracy metrics |
| Summary quality degradation | Low | Regular quality checks, human-in-loop validation |
| Queue overload | Medium | Auto-scaling workers, monitoring, backpressure handling |

---

## Next Steps

1. Run `/speckit.tasks` to generate detailed task list
2. Review and prioritize tasks
3. Begin implementation with Phase 2.1 (Foundation)
4. Iterate through P1 → P2 → P3 user stories
5. Mark IMPLEMENTATION_PLAN.md checkboxes as complete
6. Integration test and performance validation
7. Deploy and monitor

---

## References

- **Feature Spec**: [`spec.md`](./spec.md)
- **Research**: [`research.md`](./research.md)
- **Data Model**: [`data-model.md`](./data-model.md)
- **Service Contracts**: [`contracts/service-interfaces.md`](./contracts/service-interfaces.md)
- **Quickstart**: [`quickstart.md`](./quickstart.md)
- **Architecture**: `/docs/architecture/memory-layer.md`
- **Implementation Plan**: `/IMPLEMENTATION_PLAN.md` (Phase 12)
