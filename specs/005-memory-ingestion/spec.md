# Feature Specification: Memory Ingestion System

**Feature Branch**: `005-memory-ingestion`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Implement Phase 12: Memory Layer - Complete the memory ingestion system including MemoryIngestor for episode creation, EntityExtractor for LLM-based entity extraction, and ConversationSummarizer for hierarchical summarization. This builds on existing memory models and store interfaces to enable automatic memory capture from conversations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Episode Creation (Priority: P1)

When a conversation turn completes, the system automatically captures it as a memory episode without requiring manual intervention. This enables the agent to recall past interactions in future conversations.

**Why this priority**: This is the foundation of the memory system. Without episode creation, no other memory features can function. It delivers immediate value by enabling basic conversation history recall.

**Independent Test**: Can be fully tested by processing a single conversation turn and verifying an episode is created in the memory store with correct content, timestamps, and metadata. Delivers value by enabling conversation continuity.

**Acceptance Scenarios**:

1. **Given** a completed conversation turn with user message and agent response, **When** the ingestion system processes it, **Then** an episode is created with the turn content, correct timestamps, tenant/session group_id, and a generated embedding
2. **Given** multiple conversation turns in sequence, **When** each is processed, **Then** each creates a separate episode with sequential timestamps and all are retrievable by group_id
3. **Given** a conversation turn with no content, **When** processing is attempted, **Then** the system skips episode creation and logs the event without failing

---

### User Story 2 - Entity and Relationship Extraction (Priority: P2)

As conversations occur, the system automatically identifies important entities (people, products, orders, concepts) and their relationships, building a knowledge graph that enables contextual understanding in future interactions.

**Why this priority**: This enables the agent to understand factual relationships and answer questions about past interactions. It builds on P1 (episodes must exist first) and significantly enhances memory quality.

**Independent Test**: Can be fully tested by providing sample conversation text, verifying entities are extracted, and confirming relationships are created in the knowledge graph. Delivers value by enabling fact-based queries like "what products did this customer order?"

**Acceptance Scenarios**:

1. **Given** an episode containing "I ordered a laptop last week but it arrived damaged", **When** entity extraction runs, **Then** entities are created for Order, Laptop, and DamageIssue with appropriate relationships
2. **Given** an episode with no recognizable entities, **When** extraction runs, **Then** no entities are created but the episode is still stored
3. **Given** an episode mentioning an existing entity, **When** extraction runs, **Then** the system links to the existing entity rather than creating a duplicate
4. **Given** a conversation that updates a fact (e.g., "my address changed"), **When** extraction runs, **Then** old relationships are invalidated with valid_to timestamp and new ones created with valid_from

---

### User Story 3 - Hierarchical Conversation Summarization (Priority: P3)

For long-running conversations exceeding a configurable turn threshold, the system automatically generates summaries of older conversation segments, enabling efficient retrieval without loading hundreds of individual turns.

**Why this priority**: This is an optimization that becomes important only for long conversations. The system works without it (using raw episodes), but performance degrades for sessions with many turns. Can be implemented after basic ingestion is working.

**Independent Test**: Can be fully tested by creating a session with more turns than the summary threshold, verifying a summary episode is created, and confirming retrieval prefers the summary for old turns. Delivers value by maintaining performance for long-running conversations.

**Acceptance Scenarios**:

1. **Given** a conversation with turns exceeding the summary threshold (e.g., 20 turns), **When** the threshold is crossed, **Then** a summary episode is generated covering the oldest N turns
2. **Given** multiple summaries exist for a very long conversation, **When** hierarchical summarization triggers, **Then** a meta-summary is created covering previous summaries
3. **Given** a summary episode exists, **When** retrieving memory for context, **Then** the summary is used for old turns instead of loading all raw episodes
4. **Given** summarization is disabled in configuration, **When** turns exceed typical thresholds, **Then** no summarization occurs and all episodes remain individually accessible

---

### Edge Cases

- What happens when entity extraction fails due to LLM provider timeout or error?
- How does the system handle extremely large conversation turns (e.g., pasted documents)?
- What happens if embedding generation fails partway through processing?
- How does the system handle concurrent ingestion of the same conversation from multiple requests?
- What happens when the memory store is unavailable during ingestion?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create an Episode from each completed conversation turn containing user message, agent response, timestamp, group_id (tenant:session), and source metadata
- **FR-002**: System MUST generate embeddings for each episode using the configured embedding provider immediately upon creation
- **FR-003**: System MUST extract entities from episode content using LLM-based analysis identifying people, products, orders, concepts, and other domain-specific nouns
- **FR-004**: System MUST extract relationships between identified entities with relationship types (contains, has_issue, related_to, owns, etc.)
- **FR-005**: System MUST handle temporal updates by setting valid_to timestamps on invalidated relationships and creating new relationships with valid_from timestamps
- **FR-006**: System MUST merge extracted entities with existing knowledge graph nodes when the same entity is mentioned again
- **FR-007**: System MUST generate conversation summaries asynchronously when turn count exceeds configured threshold (default 20 turns)
- **FR-008**: System MUST create hierarchical summaries (summary of summaries) for conversations exceeding the second-level threshold (default 100 turns)
- **FR-009**: System MUST isolate all memory operations by group_id to prevent cross-tenant or cross-session data leakage
- **FR-010**: System MUST handle ingestion failures gracefully by logging errors and continuing without blocking conversation flow
- **FR-011**: System MUST support configurable enable/disable flags for entity extraction and summarization features
- **FR-012**: System MUST store embedding model name with each episode to track which model generated the embedding
- **FR-013**: System MUST complete episode creation and embedding generation within 500ms for synchronous operations
- **FR-014**: System MUST complete full ingestion including entity extraction within 2 seconds for asynchronous operations
- **FR-015**: System MUST validate that episodes contain required fields (content, group_id, timestamps) before storage

### Key Entities *(include if feature involves data)*

- **Episode**: Atomic memory unit representing a conversation turn, system event, or external data, containing text content, timestamps (occurred_at, recorded_at), group_id, source metadata, and embedding vector
- **Entity**: Named thing extracted from episodes (person, product, order, concept) with attributes, valid_from/valid_to temporal markers, and recorded_at timestamp
- **Relationship**: Directed edge between two entities with relationship type, optional properties, and bi-temporal attributes (valid_from, valid_to, recorded_at)
- **MemoryIngestor**: Service responsible for orchestrating episode creation, embedding generation, and triggering extraction and summarization
- **EntityExtractor**: Component using LLM provider to identify entities and relationships from episode text using structured output
- **ConversationSummarizer**: Component generating compressed summaries of conversation segments when thresholds are exceeded

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Episode creation and embedding generation completes within 500 milliseconds for 95% of conversation turns
- **SC-002**: Entity extraction identifies at least 80% of factual entities (people, products, orders) mentioned in test conversation sets
- **SC-003**: System correctly handles conversations up to 200 turns without performance degradation in retrieval speed
- **SC-004**: Memory ingestion failures (LLM timeout, provider errors) do not block conversation responses - the system gracefully degrades
- **SC-005**: Hierarchical summaries reduce retrieval context size by at least 70% for conversations exceeding 50 turns
- **SC-006**: Entity merge logic correctly identifies duplicate entities with 90% accuracy on test data (avoiding both duplicate creation and incorrect merging)
- **SC-007**: All memory operations maintain complete tenant isolation with zero data leakage in multi-tenant testing scenarios
