# Tasks: Memory Ingestion System

**Input**: Design documents from `/specs/005-memory-ingestion/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Unit tests included as per Focal testing requirements (85% coverage target). Integration tests included for full ingestion flow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dependencies and configuration structure for memory ingestion

- [x] T001 Add sentence-transformers dependency via uv
- [x] T002 Add python-Levenshtein dependency for fuzzy matching via uv
- [x] T003 [P] Add rq (optional) dependency for Redis task queue via uv
- [x] T004 [P] Create focal/memory/ingestion/ module with __init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration models and base infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 [P] Create MemoryIngestionConfig in focal/config/models/pipeline.py
- [x] T006 [P] Create EntityExtractionConfig in focal/config/models/pipeline.py
- [x] T007 [P] Create EntityDeduplicationConfig in focal/config/models/pipeline.py
- [x] T008 [P] Create SummarizationConfig in focal/config/models/pipeline.py
- [x] T009 [P] Create ExtractedEntity structured output model in focal/memory/ingestion/models.py
- [x] T010 [P] Create ExtractedRelationship structured output model in focal/memory/ingestion/models.py
- [x] T011 [P] Create EntityExtractionResult structured output model in focal/memory/ingestion/models.py
- [x] T012 [P] Create IngestionError exception in focal/memory/ingestion/errors.py
- [x] T013 [P] Create ExtractionError exception in focal/memory/ingestion/errors.py
- [x] T014 [P] Create SummarizationError exception in focal/memory/ingestion/errors.py
- [x] T015 [P] Add memory ingestion configuration section to config/default.toml
- [x] T016 [P] Create SentenceTransformersProvider in focal/providers/embedding/sentence_transformers.py
- [x] T017 [P] Create TaskQueue interface in focal/memory/ingestion/queue.py
- [x] T018 [P] Create InMemoryTaskQueue implementation in focal/memory/ingestion/queue.py
- [x] T019 [P] Create RedisTaskQueue implementation (optional) in focal/memory/ingestion/queue.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Automatic Episode Creation (Priority: P1) 🎯 MVP

**Goal**: When a conversation turn completes, the system automatically captures it as a memory episode without requiring manual intervention

**Independent Test**: Process a single conversation turn and verify an episode is created in the memory store with correct content, timestamps, and metadata. Delivers value by enabling conversation continuity.

### Unit Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [P] [US1] Unit test for MemoryIngestor.ingest_turn() - episode creation in tests/unit/memory/ingestion/test_ingestor.py
- [x] T021 [P] [US1] Unit test for MemoryIngestor.ingest_turn() - embedding generation in tests/unit/memory/ingestion/test_ingestor.py
- [x] T022 [P] [US1] Unit test for MemoryIngestor.ingest_turn() - embedding fallback on timeout in tests/unit/memory/ingestion/test_ingestor.py
- [x] T023 [P] [US1] Unit test for MemoryIngestor.ingest_event() - system event creation in tests/unit/memory/ingestion/test_ingestor.py
- [x] T024 [P] [US1] Unit test for MemoryIngestor - async task queuing in tests/unit/memory/ingestion/test_ingestor.py
- [x] T025 [P] [US1] Unit test for MemoryIngestor - graceful degradation on storage failure in tests/unit/memory/ingestion/test_ingestor.py
- [x] T026 [P] [US1] Unit test for MemoryIngestor - latency target validation (<500ms) in tests/unit/memory/ingestion/test_ingestor.py

### Implementation for User Story 1

- [x] T027 [US1] Implement MemoryIngestor class skeleton in focal/memory/ingestion/ingestor.py
- [x] T028 [US1] Implement MemoryIngestor.__init__() with dependency injection in focal/memory/ingestion/ingestor.py
- [x] T029 [US1] Implement MemoryIngestor.ingest_turn() - episode creation logic in focal/memory/ingestion/ingestor.py
- [x] T030 [US1] Implement MemoryIngestor.ingest_turn() - embedding generation with fallback in focal/memory/ingestion/ingestor.py
- [x] T031 [US1] Implement MemoryIngestor.ingest_turn() - episode storage in focal/memory/ingestion/ingestor.py
- [x] T032 [US1] Implement MemoryIngestor.ingest_event() for system events in focal/memory/ingestion/ingestor.py
- [x] T033 [US1] Implement MemoryIngestor._queue_async_task() helper for task queuing in focal/memory/ingestion/ingestor.py
- [x] T034 [US1] Add structured logging for episode creation in focal/memory/ingestion/ingestor.py
- [x] T035 [US1] Add OpenTelemetry span for memory.ingest_turn in focal/memory/ingestion/ingestor.py
- [x] T036 [US1] Add Prometheus metrics for episode creation in focal/memory/ingestion/ingestor.py
- [x] T037 [US1] Implement error handling and graceful degradation in focal/memory/ingestion/ingestor.py

**Checkpoint**: At this point, User Story 1 should be fully functional - episodes are created from conversation turns with embeddings, async tasks are queued, and the system handles failures gracefully

---

## Phase 4: User Story 2 - Entity and Relationship Extraction (Priority: P2)

**Goal**: As conversations occur, the system automatically identifies important entities (people, products, orders, concepts) and their relationships, building a knowledge graph that enables contextual understanding

**Independent Test**: Provide sample conversation text, verify entities are extracted, and confirm relationships are created in the knowledge graph. Delivers value by enabling fact-based queries.

### Unit Tests for User Story 2

- [x] T038 [P] [US2] Unit test for EntityExtractor.extract() - LLM structured output parsing in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T039 [P] [US2] Unit test for EntityExtractor.extract() - confidence filtering in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T040 [P] [US2] Unit test for EntityExtractor.extract_batch() - parallel processing in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T041 [P] [US2] Unit test for EntityExtractor - LLM provider timeout handling in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T042 [P] [US2] Unit test for EntityDeduplicator.find_duplicate() - exact match stage in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T043 [P] [US2] Unit test for EntityDeduplicator.find_duplicate() - fuzzy match stage in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T044 [P] [US2] Unit test for EntityDeduplicator.find_duplicate() - embedding similarity stage in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T045 [P] [US2] Unit test for EntityDeduplicator.find_duplicate() - rule-based stage in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T046 [P] [US2] Unit test for EntityDeduplicator.merge_entities() - attribute merging in tests/unit/memory/ingestion/test_entity_extractor.py
- [x] T047 [P] [US2] Unit test for temporal relationship updates - invalidation and creation in tests/unit/memory/ingestion/test_entity_extractor.py

### Implementation for User Story 2

- [x] T048 [P] [US2] Implement EntityExtractor class skeleton in focal/memory/ingestion/entity_extractor.py
- [x] T049 [US2] Implement EntityExtractor.__init__() with LLM provider dependency in focal/memory/ingestion/entity_extractor.py
- [x] T050 [US2] Implement EntityExtractor._build_extraction_prompt() for LLM in focal/memory/ingestion/entity_extractor.py
- [x] T051 [US2] Implement EntityExtractor.extract() - LLM call with structured output in focal/memory/ingestion/entity_extractor.py
- [x] T052 [US2] Implement EntityExtractor.extract() - confidence filtering logic in focal/memory/ingestion/entity_extractor.py
- [x] T053 [US2] Implement EntityExtractor.extract_batch() for parallel extraction in focal/memory/ingestion/entity_extractor.py
- [x] T054 [US2] Implement EntityExtractor error handling and timeout logic in focal/memory/ingestion/entity_extractor.py
- [x] T055 [P] [US2] Implement EntityDeduplicator class skeleton in focal/memory/ingestion/entity_extractor.py
- [x] T056 [US2] Implement EntityDeduplicator.find_duplicate() - exact match stage in focal/memory/ingestion/entity_extractor.py
- [x] T057 [US2] Implement EntityDeduplicator.find_duplicate() - fuzzy match stage with Levenshtein in focal/memory/ingestion/entity_extractor.py
- [x] T058 [US2] Implement EntityDeduplicator.find_duplicate() - embedding similarity stage in focal/memory/ingestion/entity_extractor.py
- [x] T059 [US2] Implement EntityDeduplicator.find_duplicate() - rule-based matching stage in focal/memory/ingestion/entity_extractor.py
- [x] T060 [US2] Implement EntityDeduplicator.merge_entities() for attribute merging in focal/memory/ingestion/entity_extractor.py
- [x] T061 [US2] Implement entity storage with deduplication in focal/memory/ingestion/entity_extractor.py
- [x] T062 [US2] Implement temporal relationship update logic (valid_from/valid_to) in focal/memory/ingestion/entity_extractor.py
- [x] T063 [US2] Implement relationship storage with temporal versioning in focal/memory/ingestion/entity_extractor.py
- [x] T064 [US2] Add structured logging for entity extraction in focal/memory/ingestion/entity_extractor.py
- [x] T065 [US2] Add OpenTelemetry spans for extraction and deduplication in focal/memory/ingestion/entity_extractor.py
- [x] T066 [US2] Add Prometheus metrics for entities and relationships in focal/memory/ingestion/entity_extractor.py
- [x] T067 [US2] Integrate EntityExtractor with MemoryIngestor async task queue in focal/memory/ingestion/ingestor.py
- [x] T068 [US2] Create background task handler for entity extraction in focal/memory/ingestion/tasks.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - episodes are created with entities and relationships automatically extracted asynchronously, building a knowledge graph

---

## Phase 5: User Story 3 - Hierarchical Conversation Summarization (Priority: P3)

**Goal**: For long-running conversations exceeding a configurable turn threshold, the system automatically generates summaries of older conversation segments, enabling efficient retrieval

**Independent Test**: Create a session with more turns than the summary threshold, verify a summary episode is created, and confirm retrieval prefers the summary for old turns. Delivers value by maintaining performance for long conversations.

### Unit Tests for User Story 3

- [x] T069 [P] [US3] Unit test for ConversationSummarizer.summarize_window() - summary generation in tests/unit/memory/ingestion/test_summarizer.py
- [x] T070 [P] [US3] Unit test for ConversationSummarizer.summarize_window() - summary metadata in tests/unit/memory/ingestion/test_summarizer.py
- [x] T071 [P] [US3] Unit test for ConversationSummarizer.create_meta_summary() - meta-summary generation in tests/unit/memory/ingestion/test_summarizer.py
- [x] T072 [P] [US3] Unit test for ConversationSummarizer.check_and_summarize_if_needed() - threshold checking in tests/unit/memory/ingestion/test_summarizer.py
- [x] T073 [P] [US3] Unit test for ConversationSummarizer.check_and_summarize_if_needed() - automatic triggering in tests/unit/memory/ingestion/test_summarizer.py
- [x] T074 [P] [US3] Unit test for ConversationSummarizer - compression ratio validation in tests/unit/memory/ingestion/test_summarizer.py
- [x] T075 [P] [US3] Unit test for ConversationSummarizer - LLM provider timeout handling in tests/unit/memory/ingestion/test_summarizer.py

### Implementation for User Story 3

- [x] T076 [P] [US3] Implement ConversationSummarizer class skeleton in focal/memory/ingestion/summarizer.py
- [x] T077 [US3] Implement ConversationSummarizer.__init__() with dependencies in focal/memory/ingestion/summarizer.py
- [x] T078 [US3] Implement ConversationSummarizer._format_episodes_for_summary() helper in focal/memory/ingestion/summarizer.py
- [x] T079 [US3] Implement ConversationSummarizer.summarize_window() - LLM call for window summary in focal/memory/ingestion/summarizer.py
- [x] T080 [US3] Implement ConversationSummarizer.summarize_window() - summary episode creation in focal/memory/ingestion/summarizer.py
- [x] T081 [US3] Implement ConversationSummarizer.create_meta_summary() for hierarchical summaries in focal/memory/ingestion/summarizer.py
- [x] T082 [US3] Implement ConversationSummarizer.check_and_summarize_if_needed() - threshold checking in focal/memory/ingestion/summarizer.py
- [x] T083 [US3] Implement ConversationSummarizer.check_and_summarize_if_needed() - automatic trigger logic in focal/memory/ingestion/summarizer.py
- [x] T084 [US3] Implement ConversationSummarizer.check_and_summarize_if_needed() - summary persistence in focal/memory/ingestion/summarizer.py
- [x] T085 [US3] Add structured logging for summarization in focal/memory/ingestion/summarizer.py
- [x] T086 [US3] Add OpenTelemetry spans for summarization operations in focal/memory/ingestion/summarizer.py
- [x] T087 [US3] Add Prometheus metrics for summaries in focal/memory/ingestion/summarizer.py
- [x] T088 [US3] Integrate ConversationSummarizer with MemoryIngestor async queue in focal/memory/ingestion/ingestor.py
- [x] T089 [US3] Create background task handler for summarization in focal/memory/ingestion/tasks.py

**Checkpoint**: All user stories should now be independently functional - episodes are created, entities extracted, and summaries generated for long conversations

---

## Phase 6: Integration & Quality Assurance

**Purpose**: Integration tests and cross-story validation

- [x] T090 [P] Integration test for full ingestion flow (Turn → Episode → Entities → Relationships) in tests/integration/memory/test_ingestion_flow.py
- [x] T091 [P] Integration test for temporal relationship updates in tests/integration/memory/test_ingestion_flow.py
- [x] T092 [P] Integration test for deduplication accuracy on test dataset in tests/integration/memory/test_ingestion_flow.py
- [x] T093 [P] Integration test for summarization quality and compression ratio in tests/integration/memory/test_ingestion_flow.py
- [x] T094 [P] Integration test for tenant isolation (no data leakage) in tests/integration/memory/test_ingestion_flow.py
- [x] T095 [P] Integration test for graceful degradation on LLM failures in tests/integration/memory/test_ingestion_flow.py
- [x] T096 [P] Integration test for end-to-end latency targets (<500ms episode, <2s extraction) in tests/integration/memory/test_ingestion_flow.py

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T097 [P] Add docstrings to all public methods in focal/memory/ingestion/
- [x] T098 [P] Verify test coverage meets 85% threshold for ingestion module
- [x] T099 [P] Update IMPLEMENTATION_PLAN.md Phase 12 checkboxes as complete
- [ ] T100 [P] Performance profiling and optimization if latency targets not met
- [ ] T101 [P] Validate quickstart.md examples work end-to-end
- [ ] T102 [P] Code review and cleanup (remove debug logging, optimize imports)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Integration & QA (Phase 6)**: Depends on desired user stories being complete
- **Polish (Phase 7)**: Depends on all user stories and integration tests

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 (MemoryIngestor) but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1 (MemoryIngestor) but independently testable

### Within Each User Story

- Unit tests MUST be written and FAIL before implementation
- Models/structured output before services
- Services before integration with ingestor
- Core implementation before observability (logging, spans, metrics)
- Story complete and tested before moving to next priority

### Parallel Opportunities

- All Setup tasks (T001-T004) can run in parallel
- All Foundational config models (T005-T014) can run in parallel
- All Foundational config sections (T015-T019) can run in parallel
- Once Foundational phase completes, all three user stories can start in parallel (if team capacity allows)
- All unit tests within a user story marked [P] can be written in parallel
- Models/classes within different modules can be worked on in parallel (e.g., EntityExtractor and ConversationSummarizer)
- All integration tests (T090-T096) can run in parallel
- All polish tasks (T097-T102) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all unit tests for User Story 1 together:
Task T020: "Unit test for MemoryIngestor.ingest_turn() - episode creation in tests/unit/memory/ingestion/test_ingestor.py"
Task T021: "Unit test for MemoryIngestor.ingest_turn() - embedding generation in tests/unit/memory/ingestion/test_ingestor.py"
Task T022: "Unit test for MemoryIngestor.ingest_turn() - embedding fallback on timeout in tests/unit/memory/ingestion/test_ingestor.py"
Task T023: "Unit test for MemoryIngestor.ingest_event() - system event creation in tests/unit/memory/ingestion/test_ingestor.py"
Task T024: "Unit test for MemoryIngestor - async task queuing in tests/unit/memory/ingestion/test_ingestor.py"
Task T025: "Unit test for MemoryIngestor - graceful degradation on storage failure in tests/unit/memory/ingestion/test_ingestor.py"
Task T026: "Unit test for MemoryIngestor - latency target validation (<500ms) in tests/unit/memory/ingestion/test_ingestor.py"
```

---

## Parallel Example: User Story 2

```bash
# After Foundational phase, can work on US2 in parallel with US1:
Task T048: "Implement EntityExtractor class skeleton in focal/memory/ingestion/entity_extractor.py"
Task T055: "Implement EntityDeduplicator class skeleton in focal/memory/ingestion/entity_extractor.py"

# Different team members can work on different modules:
Developer A: EntityExtractor implementation (T048-T054)
Developer B: EntityDeduplicator implementation (T055-T063)
Developer C: ConversationSummarizer implementation (T076-T089) for US3
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T019) - CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T020-T037)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo basic episode creation with embeddings

**Value delivered**: Conversation turns are automatically captured as memory episodes, enabling basic conversation history and continuity.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
   - **Value**: Episodes created from turns, enabling conversation recall
3. Add User Story 2 → Test independently → Deploy/Demo
   - **Value**: Knowledge graph built from conversations, enabling fact-based queries
4. Add User Story 3 → Test independently → Deploy/Demo
   - **Value**: Long conversations efficiently summarized, maintaining performance
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T019)
2. Once Foundational is done:
   - Developer A: User Story 1 (Episode Creation) - T020-T037
   - Developer B: User Story 2 (Entity Extraction) - T038-T068
   - Developer C: User Story 3 (Summarization) - T069-T089
3. Stories complete and integrate independently via MemoryIngestor
4. Team collaborates on integration tests (T090-T096)
5. Team completes polish tasks in parallel (T097-T102)

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- All unit tests should FAIL before implementation begins
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Follow Focal coding standards: async-first, dependency injection, structured logging, provider interfaces
- Do NOT skip temporal update logic - critical for relationship versioning
- Do NOT skip observability (logging, spans, metrics) - required for production monitoring
- Do NOT hardcode configuration - all settings via TOML with Pydantic defaults
- Maintain 85% test coverage threshold for memory ingestion module
