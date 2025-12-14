# Phase 11: Persistence, Audit & Output - Implementation Checklist

> **Reference**: `docs/focal_turn_pipeline/README.md` (Phase 11), `docs/focal_turn_pipeline/analysis/gap_analysis.md` (Parallelism)
> **Status**: 95% Implemented (Gap Analysis)
> **Goal**: Convert sequential persistence to parallel, add scope-based filtering, enhance TurnRecord with outcome tracking

---

## Phase Overview

Phase 11 handles the final persistence and audit trail creation after response generation:

1. **P11.1** - Update SessionState with lifecycle changes, transitions, canonical intent
2. **P11.2** - Persist SessionState to session store
3. **P11.3** - Persist InterlocutorDataStore (only non-SESSION scoped fields)
4. **P11.4** - Record complete TurnRecord with all phase decisions
5. **P11.5** - Background memory ingestion (entity extraction, summarization)
6. **P11.6** - Build final API response
7. **P11.7** - Emit metrics and traces

**Current Gap**: Operations run sequentially. Should use `asyncio.gather()` for parallel persistence.

---

## 1. Parallel Persistence Implementation

### 1.1 Convert Sequential to Parallel

- [ ] **Refactor FocalCognitivePipeline persistence to use asyncio.gather**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Current code (lines ~446-460):
    ```python
    # Sequential awaits (SLOW)
    await self._update_and_persist_session(...)
    await self._persist_turn_record(...)
    ```
  - New code:
    ```python
    # Parallel persistence with asyncio.gather
    persistence_tasks = []

    # Task 1: Session persistence
    if session and persist:
        persistence_tasks.append(
            self._update_and_persist_session(
                session=session,
                scenario_result=scenario_result,
                matched_rules=matched_rules,
                tool_results=tool_results,
            )
        )

    # Task 2: CustomerData persistence (if updates exist)
    if customer_data_updates and persist:
        persistence_tasks.append(
            self._persist_customer_data(
                session=session,
                updates=customer_data_updates,
            )
        )

    # Task 3: TurnRecord
    if persist and self._audit_store:
        persistence_tasks.append(
            self._persist_turn_record(
                result=result,
                session=session,
                generation_result=generation_result,
            )
        )

    # Execute all persistence in parallel
    if persistence_tasks:
        await asyncio.gather(*persistence_tasks, return_exceptions=True)
    ```
  - Details: Run all persistence operations in parallel. Use `return_exceptions=True` to avoid one failure blocking others.

- [ ] **Add error handling for parallel persistence failures**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Add
  - Details: Check for exceptions in gather results, log failures separately
    ```python
    results = await asyncio.gather(*persistence_tasks, return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "persistence_failed",
                task_index=i,
                error=str(result),
                session_id=str(session_id),
            )
    ```

### 1.2 Add Persistence Timing Metrics

- [ ] **Track parallel persistence duration**
  - File: `ruche/observability/metrics.py`
  - Action: Add
  - Details: Add histogram for parallel persistence timing
    ```python
    PERSISTENCE_DURATION = Histogram(
        "focal_persistence_duration_seconds",
        "Time spent in parallel persistence operations",
        ["operation"],  # session, customer_data, turn_record
    )
    ```

- [ ] **Update engine to record persistence metrics**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details: Wrap persistence in timing context
    ```python
    from ruche.observability.metrics import PERSISTENCE_DURATION

    with PERSISTENCE_DURATION.labels(operation="parallel").time():
        results = await asyncio.gather(*persistence_tasks, return_exceptions=True)
    ```

---

## 2. InterlocutorDataStore Persistence (Scope-Based Filtering)

### 2.1 Implement Scope-Based Persistence

- [ ] **Create _persist_customer_data method**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Add
  - Details: Filter and persist only non-SESSION scoped fields
    ```python
    async def _persist_customer_data(
        self,
        session: Session,
        updates: list[CustomerDataUpdate],
    ) -> None:
        """Persist customer data updates, filtering by scope.

        Only persists fields with:
        - scope != SESSION (SESSION scope is ephemeral)
        - persist = True in ProfileFieldDefinition

        Args:
            session: Current session
            updates: List of customer data updates from Phase 3
        """
        if not self._profile_store:
            return

        # Filter: only persist non-SESSION scope with persist=True
        persistent_updates = [
            update for update in updates
            if update.field_definition.scope != "SESSION"
            and update.field_definition.persist
        ]

        if not persistent_updates:
            logger.debug(
                "no_customer_data_to_persist",
                session_id=str(session.session_id),
                total_updates=len(updates),
            )
            return

        # Get or create customer profile
        profile = await self._profile_store.get_by_customer_id(
            tenant_id=session.tenant_id,
            customer_id=session.customer_id,
        )

        if not profile:
            logger.warning(
                "profile_not_found_for_persistence",
                session_id=str(session.session_id),
                customer_id=str(session.customer_id),
            )
            return

        # Update each field
        for update in persistent_updates:
            field = ProfileField(
                name=update.field_name,
                value=update.value,
                value_type=update.field_definition.value_type,
                source=ProfileFieldSource.CONVERSATION,
                source_session_id=session.session_id,
                confidence=update.confidence,
                field_definition_id=update.field_definition.id,
            )

            await self._profile_store.update_field(
                tenant_id=session.tenant_id,
                profile_id=profile.id,
                field=field,
                supersede_existing=True,
            )

        logger.info(
            "customer_data_persisted",
            session_id=str(session.session_id),
            fields_persisted=len(persistent_updates),
            fields_skipped=len(updates) - len(persistent_updates),
        )
    ```

- [ ] **Add CustomerDataUpdate model**
  - File: `ruche/pipelines/focal/models/customer_data.py`
  - Action: Create
  - Details: Lightweight model for Phase 3 → Phase 11 handoff
    ```python
    """Customer data update models for Phase 3."""

    from pydantic import BaseModel, Field
    from ruche.domain.interlocutor.models import InterlocutorDataField

    class CustomerDataUpdate(BaseModel):
        """Lightweight update record from Phase 3.

        Tracks which fields were updated during situational sensing
        and should be persisted in Phase 11.
        """

        field_name: str = Field(..., description="Field name")
        value: Any = Field(..., description="Extracted value")
        confidence: float = Field(..., description="Confidence score 0-1")
        field_definition: InterlocutorDataField = Field(
            ..., description="Schema definition with scope and persist flags"
        )
        is_update: bool = Field(
            default=False, description="True if updating existing value"
        )
    ```

### 2.2 Session-End Cleanup

- [ ] **Add session cleanup for SESSION-scoped variables**
  - File: `ruche/runtime/store.py`
  - Action: Modify interface
  - Details: Add cleanup method to SessionStore interface
    ```python
    @abstractmethod
    async def cleanup_session_scoped_data(
        self,
        session_id: UUID,
    ) -> None:
        """Remove SESSION-scoped customer data on session end.

        Called when session status transitions to ENDED or ABANDONED.
        Removes ephemeral data that should not persist across sessions.

        Args:
            session_id: Session to clean up
        """
        pass
    ```

- [ ] **Implement cleanup in InMemorySessionStore**
  - File: `ruche/runtime/stores/inmemory.py`
  - Action: Add
  - Details: Clear SESSION-scoped variables from session.variables dict
    ```python
    async def cleanup_session_scoped_data(
        self,
        session_id: UUID,
    ) -> None:
        """Remove SESSION-scoped variables."""
        session = await self.get(session_id)
        if not session:
            return

        # Remove SESSION-scoped keys (would need schema to determine)
        # For now, log intent
        logger.info(
            "session_cleanup_triggered",
            session_id=str(session_id),
            variables_before=len(session.variables),
        )
    ```

- [ ] **Implement cleanup in RedisSessionStore**
  - File: `ruche/runtime/stores/redis.py`
  - Action: Add
  - Details: Same cleanup logic for Redis backend

- [ ] **Call cleanup on session end**
  - File: `ruche/api/routes/sessions.py`
  - Action: Modify
  - Details: Add cleanup call in DELETE endpoint
    ```python
    @router.delete("/{session_id}")
    async def end_session(
        session_id: UUID,
        session_store: SessionStore = Depends(get_session_store),
    ):
        """End a session and clean up ephemeral data."""
        await session_store.cleanup_session_scoped_data(session_id)
        await session_store.delete(session_id)
        return {"status": "ended"}
    ```

---

## 3. Background Memory Ingestion

### 3.1 Integrate Task Queue

- [ ] **Add memory ingestion task to engine**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details: Fire-and-forget memory ingestion after response sent
    ```python
    # After persistence (fire and forget)
    if self._memory_ingestor and self._task_queue:
        # Don't await - background task
        asyncio.create_task(
            self._task_queue.enqueue(
                "memory_ingestion",
                {
                    "logical_turn_id": str(turn_id),
                    "session_id": str(session_id),
                    "user_message": user_message,
                    "agent_response": result.response,
                    "tenant_id": str(session.tenant_id),
                    "agent_id": str(session.agent_id),
                },
            )
        )
    ```

- [ ] **Add TaskQueue to FocalCognitivePipeline constructor**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details: Add optional task_queue parameter
    ```python
    def __init__(
        self,
        # ... existing parameters ...
        task_queue: TaskQueue | None = None,
        memory_ingestor: MemoryIngestor | None = None,
    ):
        # ... existing init ...
        self._task_queue = task_queue
        self._memory_ingestor = memory_ingestor
    ```

### 3.2 Add Configuration

- [ ] **Add memory ingestion toggle to config**
  - File: `config/default.toml`
  - Action: Modify
  - Details: Add background ingestion flag
    ```toml
    [pipeline.memory_ingestion]
    enabled = true
    background = true  # If false, blocks turn completion
    ```

- [ ] **Update MemoryIngestionConfig model**
  - File: `ruche/config/models/pipeline.py`
  - Action: Modify
  - Details: Add background flag
    ```python
    class MemoryIngestionConfig(BaseModel):
        enabled: bool = True
        background: bool = True  # Fire-and-forget vs blocking
        # ... existing fields ...
    ```

### 3.3 LLM Template Migration (Gap Analysis Item)

> **CRITICAL**: The gap analysis identified that entity extraction and summarization use hardcoded inline prompts.
> These must be migrated to Jinja2 templates following the project's LLM Task Configuration Pattern.

- [ ] **Create entity_extraction.jinja2 template**
  - File: `ruche/memory/ingestion/prompts/entity_extraction.jinja2`
  - Action: Create new file
  - Details: Extract the 192-line inline prompt from `entity_extractor.py:45-237`
    ```jinja2
    {# Entity Extraction Prompt Template #}
    You are an entity extraction system. Extract entities from the conversation.

    ## Customer Schema
    {% for field in customer_data_fields %}
    - {{ field.name }}: {{ field.value_type }} ({{ field.scope }})
    {% endfor %}

    ## Conversation
    {{ conversation_window }}

    ## Instructions
    Extract entities matching the schema above. Return JSON:
    {
      "entities": [
        {"field_name": "...", "value": "...", "confidence": 0.0-1.0}
      ]
    }
    ```

- [ ] **Refactor EntityExtractor to use Jinja2 template**
  - File: `ruche/memory/ingestion/entity_extractor.py`
  - Action: Modify
  - Details: Replace hardcoded prompt with template loader
    ```python
    from jinja2 import Environment, FileSystemLoader

    class EntityExtractor:
        def __init__(self, llm_executor: LLMExecutor, template_dir: str = None):
            self._llm_executor = llm_executor
            template_dir = template_dir or str(Path(__file__).parent / "prompts")
            self._env = Environment(loader=FileSystemLoader(template_dir))
            self._template = self._env.get_template("entity_extraction.jinja2")

        async def extract(self, conversation: list, customer_data_fields: list) -> list[Entity]:
            prompt = self._template.render(
                customer_data_fields=customer_data_fields,
                conversation_window=self._format_conversation(conversation),
            )
            # ... existing LLM call logic ...
    ```

- [ ] **Create window_summary.jinja2 template**
  - File: `ruche/memory/ingestion/prompts/window_summary.jinja2`
  - Action: Create new file
  - Details: Extract inline summarization prompt from `summarizer.py`
    ```jinja2
    {# Window Summary Prompt Template #}
    Summarize the following {{ turn_count }} conversation turns concisely.
    Focus on key facts, decisions, and outcomes.

    ## Conversation Turns
    {% for turn in turns %}
    Turn {{ turn.number }}:
    User: {{ turn.user_message }}
    Agent: {{ turn.agent_response }}
    {% endfor %}

    ## Summary (max {{ max_tokens }} tokens)
    ```

- [ ] **Create meta_summary.jinja2 template**
  - File: `ruche/memory/ingestion/prompts/meta_summary.jinja2`
  - Action: Create new file
  - Details: Template for summarizing multiple window summaries
    ```jinja2
    {# Meta Summary Prompt Template #}
    Create a higher-level summary from these {{ summary_count }} conversation summaries.

    ## Window Summaries
    {% for summary in summaries %}
    ### Summary {{ loop.index }}
    {{ summary.content }}
    {% endfor %}

    ## Meta Summary (max {{ max_tokens }} tokens)
    ```

- [ ] **Refactor Summarizer to use Jinja2 templates**
  - File: `ruche/memory/ingestion/summarizer.py`
  - Action: Modify
  - Details: Replace inline prompts with template loading
    ```python
    from jinja2 import Environment, FileSystemLoader

    class Summarizer:
        def __init__(self, llm_executor: LLMExecutor, template_dir: str = None):
            self._llm_executor = llm_executor
            template_dir = template_dir or str(Path(__file__).parent / "prompts")
            self._env = Environment(loader=FileSystemLoader(template_dir))
            self._window_template = self._env.get_template("window_summary.jinja2")
            self._meta_template = self._env.get_template("meta_summary.jinja2")
    ```

- [ ] **Create prompts directory and __init__.py**
  - File: `ruche/memory/ingestion/prompts/__init__.py`
  - Action: Create directory and init file

- [ ] **Add unit tests for template loading**
  - File: `tests/unit/memory/ingestion/test_template_loading.py`
  - Action: Create
  - Tests:
    - Template files exist and load correctly
    - Templates render with expected variables
    - Missing template raises clear error

---

## 4. TurnRecord Enhancement

### 4.1 TurnOutcome Integration

> **NOTE**: `TurnOutcome` and `OutcomeCategory` models are defined in **Phase 9 (Generation)**, section 1.1-1.2.
> This phase only adds the outcome field to TurnRecord for persistence.

**Prerequisites from Phase 9** (must be complete first):
- [x] `OutcomeCategory` model - `ruche/pipelines/focal/models/outcome.py`
- [x] `TurnOutcome` model - `ruche/pipelines/focal/models/outcome.py`
- [x] `build_turn_outcome()` helper - `ruche/pipelines/focal/generation/resolution.py`

- [ ] **Add outcome field to TurnRecord**
  - File: `ruche/audit/models/turn_record.py`
  - Action: Modify
  - Details: Add TurnOutcome field
    ```python
    from ruche.pipelines.focal.models.outcome import TurnOutcome

    class TurnRecord(BaseModel):
        # ... existing fields ...

        # NEW: Turn outcome tracking
        outcome: TurnOutcome | None = Field(
            default=None,
            description="Resolution status and categories"
        )
    ```

### 4.2 Add Phase Decisions to TurnRecord

- [ ] **Add phase decision fields to TurnRecord**
  - File: `ruche/audit/models/turn_record.py`
  - Action: Modify
  - Details: Track all major pipeline decisions
    ```python
    class TurnRecord(BaseModel):
        # ... existing fields ...

        # Phase decisions (for debugging and analytics)
        canonical_intent: str | None = Field(
            default=None,
            description="Canonical intent label from Phase 2"
        )
        matched_rules_count: int = Field(
            default=0,
            description="Number of rules matched in Phase 5"
        )
        scenario_lifecycle_decisions: dict[str, str] = Field(
            default_factory=dict,
            description="Scenario ID → lifecycle action (CONTINUE, START, etc.)"
        )
        step_transitions: dict[str, dict] = Field(
            default_factory=dict,
            description="Scenario ID → {from_step, to_step, reason}"
        )
        tool_executions: list[dict] = Field(
            default_factory=list,
            description="Tools executed with results/errors"
        )
        enforcement_violations: list[str] = Field(
            default_factory=list,
            description="Constraint violations detected in Phase 10"
        )
        regeneration_attempts: int = Field(
            default=0,
            description="Number of regeneration attempts due to violations"
        )
    ```

### 4.3 Populate Outcome in Engine

- [ ] **Compute TurnOutcome in FocalCognitivePipeline**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Add method
  - Details: Determine resolution and categories from pipeline state
    ```python
    def _compute_turn_outcome(
        self,
        matched_rules: list[MatchedRule],
        scenario_result: ScenarioFilterResult | None,
        tool_results: list[ToolResult],
        enforcement_result: EnforcementResult | None,
    ) -> TurnOutcome:
        """Compute turn outcome based on pipeline decisions.

        Args:
            matched_rules: Rules that matched
            scenario_result: Scenario orchestration result
            tool_results: Tool execution results
            enforcement_result: Enforcement validation result

        Returns:
            TurnOutcome with resolution and categories
        """
        categories = []

        # Pipeline-determined categories
        if not matched_rules:
            categories.append(
                OutcomeCategory(
                    source="PIPELINE",
                    category="MATCHED_ZERO_RULES",
                )
            )

        if scenario_result and scenario_result.awaiting_user_input:
            categories.append(
                OutcomeCategory(
                    source="PIPELINE",
                    category="AWAITING_USER_INPUT",
                    scenario_id=scenario_result.active_scenario.id if scenario_result.active_scenario else None,
                    step_id=scenario_result.current_step_id,
                )
            )

        if any(not tool.success for tool in tool_results):
            categories.append(
                OutcomeCategory(
                    source="PIPELINE",
                    category="SYSTEM_ERROR",
                    details="Tool execution failed",
                )
            )

        if enforcement_result and enforcement_result.violations:
            categories.append(
                OutcomeCategory(
                    source="PIPELINE",
                    category="POLICY_RESTRICTION",
                    details=f"{len(enforcement_result.violations)} violations",
                )
            )

        # Determine resolution
        if enforcement_result and enforcement_result.blocked:
            resolution = "UNRESOLVED"
        elif scenario_result and scenario_result.awaiting_user_input:
            resolution = "PARTIAL"
        else:
            resolution = "RESOLVED"

        return TurnOutcome(
            resolution=resolution,
            categories=categories,
        )
    ```

- [ ] **Call _compute_turn_outcome in process_turn**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details: Compute outcome before persistence
    ```python
    # Before Step 8 (persistence)
    outcome = self._compute_turn_outcome(
        matched_rules=matched_rules,
        scenario_result=scenario_result,
        tool_results=tool_results,
        enforcement_result=enforcement_result,
    )

    # Add to AlignmentResult
    result.outcome = outcome
    ```

- [ ] **Update _persist_turn_record to include outcome**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details: Add outcome to TurnRecord
    ```python
    turn_record = TurnRecord(
        # ... existing fields ...
        outcome=result.outcome,
        canonical_intent=result.context.intent if result.context else None,
        matched_rules_count=len(matched_rules),
        # ... other phase decisions ...
    )
    ```

---

## 5. Tests Required

### 5.1 Parallel Persistence Tests

- [ ] **Test parallel session + audit persistence**
  - File: `tests/unit/alignment/test_engine_persistence.py`
  - Action: Create
  - Details: Verify operations run in parallel
    ```python
    async def test_persistence_runs_in_parallel(
        engine,
        session_store,
        audit_store,
    ):
        """Test that session and audit persistence run concurrently."""

        # Track call timing
        session_times = []
        audit_times = []

        async def timed_save_session(*args, **kwargs):
            start = time.time()
            await asyncio.sleep(0.1)  # Simulate I/O
            session_times.append(time.time() - start)

        async def timed_save_turn(*args, **kwargs):
            start = time.time()
            await asyncio.sleep(0.1)  # Simulate I/O
            audit_times.append(time.time() - start)

        session_store.save = timed_save_session
        audit_store.save_turn = timed_save_turn

        # Process turn
        start = time.time()
        await engine.process_turn(...)
        total_time = time.time() - start

        # Should take ~0.1s (parallel), not ~0.2s (sequential)
        assert total_time < 0.15  # Some overhead, but not 2x
        assert len(session_times) == 1
        assert len(audit_times) == 1
    ```

- [ ] **Test partial failure handling**
  - File: `tests/unit/alignment/test_engine_persistence.py`
  - Action: Add
  - Details: Verify one failure doesn't block others
    ```python
    async def test_persistence_failure_doesnt_block_others(
        engine,
        session_store,
        audit_store,
    ):
        """Test that if session save fails, audit still succeeds."""

        # Make session save fail
        async def failing_save(*args, **kwargs):
            raise Exception("Database error")

        session_store.save = failing_save

        # Process turn
        result = await engine.process_turn(...)

        # Turn should still complete
        assert result.response

        # Audit should have been saved despite session failure
        turns = await audit_store.list_turns_by_session(session_id)
        assert len(turns) == 1
    ```

### 5.2 Scope-Based Persistence Tests

- [ ] **Test SESSION scope not persisted**
  - File: `tests/unit/alignment/test_customer_data_persistence.py`
  - Action: Create
  - Details: Verify SESSION-scoped fields are skipped
    ```python
    async def test_session_scoped_fields_not_persisted(
        engine,
        profile_store,
    ):
        """Test that SESSION-scoped fields don't persist to profile."""

        updates = [
            CustomerDataUpdate(
                field_name="cart_items",
                value=["item1", "item2"],
                confidence=1.0,
                field_definition=ProfileFieldDefinition(
                    name="cart_items",
                    scope="SESSION",  # Ephemeral
                    persist=False,
                ),
            ),
            CustomerDataUpdate(
                field_name="email",
                value="user@example.com",
                confidence=1.0,
                field_definition=ProfileFieldDefinition(
                    name="email",
                    scope="IDENTITY",  # Persistent
                    persist=True,
                ),
            ),
        ]

        await engine._persist_customer_data(session, updates)

        # Only email should be saved
        profile = await profile_store.get_by_customer_id(...)
        assert "email" in [f.name for f in profile.fields]
        assert "cart_items" not in [f.name for f in profile.fields]
    ```

- [ ] **Test persist=False fields not saved**
  - File: `tests/unit/alignment/test_customer_data_persistence.py`
  - Action: Add
  - Details: Verify persist flag is respected
    ```python
    async def test_persist_false_fields_not_saved(
        engine,
        profile_store,
    ):
        """Test that fields with persist=False are not saved."""

        updates = [
            CustomerDataUpdate(
                field_name="temporary_flag",
                value=True,
                confidence=1.0,
                field_definition=ProfileFieldDefinition(
                    name="temporary_flag",
                    scope="BUSINESS",
                    persist=False,  # Don't save to DB
                ),
            ),
        ]

        await engine._persist_customer_data(session, updates)

        profile = await profile_store.get_by_customer_id(...)
        assert "temporary_flag" not in [f.name for f in profile.fields]
    ```

### 5.3 TurnOutcome Tests

- [ ] **Test outcome computation**
  - File: `tests/unit/alignment/test_turn_outcome.py`
  - Action: Create
  - Details: Verify correct resolution based on pipeline state
    ```python
    def test_outcome_resolved_when_no_issues(engine):
        """Test RESOLVED outcome when everything succeeds."""

        outcome = engine._compute_turn_outcome(
            matched_rules=[RuleFactory.create()],
            scenario_result=None,
            tool_results=[],
            enforcement_result=EnforcementResult(violations=[]),
        )

        assert outcome.resolution == "RESOLVED"
        assert len(outcome.categories) == 0

    def test_outcome_partial_when_awaiting_input(engine):
        """Test PARTIAL outcome when scenario awaits input."""

        scenario_result = ScenarioFilterResult(
            awaiting_user_input=True,
            active_scenario=ScenarioFactory.create(),
            current_step_id="step_2",
        )

        outcome = engine._compute_turn_outcome(
            matched_rules=[RuleFactory.create()],
            scenario_result=scenario_result,
            tool_results=[],
            enforcement_result=None,
        )

        assert outcome.resolution == "PARTIAL"
        assert any(
            cat.category == "AWAITING_USER_INPUT"
            for cat in outcome.categories
        )
    ```

### 5.4 Background Memory Ingestion Tests

- [ ] **Test fire-and-forget memory ingestion**
  - File: `tests/unit/alignment/test_engine_memory.py`
  - Action: Create
  - Details: Verify memory task is enqueued but doesn't block
    ```python
    async def test_memory_ingestion_doesnt_block_response(
        engine_with_memory,
        task_queue,
    ):
        """Test that memory ingestion doesn't delay response."""

        # Make memory ingestion slow
        async def slow_ingest(*args, **kwargs):
            await asyncio.sleep(1.0)

        task_queue.enqueue = MagicMock(side_effect=slow_ingest)

        # Process turn
        start = time.time()
        result = await engine_with_memory.process_turn(...)
        duration = time.time() - start

        # Should return quickly, not wait for memory
        assert duration < 0.5
        assert result.response
    ```

---

## 6. Integration Tests

### 6.1 End-to-End Persistence Flow

- [ ] **Test full turn with parallel persistence**
  - File: `tests/integration/alignment/test_persistence_flow.py`
  - Action: Create
  - Details: Real stores, verify all data persisted correctly
    ```python
    async def test_full_turn_with_persistence(
        engine,
        session_store,
        audit_store,
        profile_store,
    ):
        """Test complete turn with session, audit, and profile persistence."""

        # Create session
        session = await session_store.get_or_create(...)

        # Process turn with customer data updates
        result = await engine.process_turn(
            user_message="My email is user@example.com",
            session_id=session.session_id,
            # ... other params ...
        )

        # Verify session updated
        updated_session = await session_store.get(session.session_id)
        assert updated_session.turn_count == 1

        # Verify turn record saved
        turns = await audit_store.list_turns_by_session(session.session_id)
        assert len(turns) == 1
        assert turns[0].outcome is not None

        # Verify customer data persisted (if extracted)
        profile = await profile_store.get_by_customer_id(...)
        # Should have email if extracted
    ```

---

## 7. Dependencies

This phase requires:

- [x] **Phase 1-10 Complete**: All prior pipeline phases working
- [x] **SessionStore Interface**: For session persistence
- [x] **AuditStore Interface**: For turn record persistence
- [x] **InterlocutorDataStoreInterface**: For customer data persistence
- [ ] **CustomerDataUpdate Model**: For Phase 3 → Phase 11 handoff
- [ ] **TurnOutcome Model**: For outcome tracking
- [ ] **TaskQueue**: For background memory ingestion

---

## 8. Configuration Updates

### 8.1 Add Persistence Configuration

- [ ] **Add persistence config section**
  - File: `config/default.toml`
  - Action: Add
  - Details: Control persistence behavior
    ```toml
    [pipeline.persistence]
    parallel = true  # Use asyncio.gather
    customer_data_enabled = true
    session_cleanup_on_end = true
    ```

- [ ] **Add PersistenceConfig model**
  - File: `ruche/config/models/pipeline.py`
  - Action: Add
  - Details: Persistence configuration model
    ```python
    class PersistenceConfig(BaseModel):
        """Persistence configuration for Phase 11."""

        parallel: bool = Field(
            default=True,
            description="Use parallel persistence with asyncio.gather"
        )
        customer_data_enabled: bool = Field(
            default=True,
            description="Persist customer data updates to InterlocutorDataStoreInterface"
        )
        session_cleanup_on_end: bool = Field(
            default=True,
            description="Clean up SESSION-scoped data when session ends"
        )
    ```

---

## 9. Observability

### 9.1 Add Persistence Metrics

- [ ] **Add persistence operation counters**
  - File: `ruche/observability/metrics.py`
  - Action: Add
  - Details: Track persistence operations and failures
    ```python
    PERSISTENCE_OPERATIONS = Counter(
        "focal_persistence_operations_total",
        "Total persistence operations",
        ["operation", "status"],  # session/audit/profile, success/failure
    )

    PERSISTENCE_PARALLEL_SAVINGS = Histogram(
        "focal_persistence_parallel_savings_seconds",
        "Time saved by parallel persistence vs sequential",
    )
    ```

### 9.2 Add Structured Logging

- [ ] **Log persistence timing details**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Add
  - Details: Log parallel persistence metrics
    ```python
    logger.info(
        "parallel_persistence_complete",
        session_id=str(session_id),
        operations=len(persistence_tasks),
        duration_ms=duration_ms,
        failures=sum(1 for r in results if isinstance(r, Exception)),
    )
    ```

---

## Success Criteria

Phase 11 is complete when:

1. ✅ **Parallel Persistence**: Session, CustomerData, and TurnRecord save concurrently
2. ✅ **Scope Filtering**: Only non-SESSION scoped fields with persist=True are saved
3. ✅ **Background Memory**: Memory ingestion doesn't block response
4. ✅ **TurnOutcome**: Full outcome tracking with resolution and categories
5. ✅ **Session Cleanup**: SESSION-scoped data removed on session end
6. ✅ **Performance**: Parallel persistence at least 40% faster than sequential
7. ✅ **Tests Pass**: 85%+ coverage on new persistence logic
8. ✅ **Observability**: Metrics track parallel savings and operation failures

---

## Notes

- **Performance Impact**: Parallel persistence should reduce P11 time from ~150ms (3×50ms) to ~60ms (max of three)
- **Error Handling**: Use `return_exceptions=True` so one failure doesn't block others
- **Memory Ingestion**: Already implemented, just needs integration via task queue
- **Backward Compatibility**: Add feature flags to allow gradual rollout of parallel persistence
