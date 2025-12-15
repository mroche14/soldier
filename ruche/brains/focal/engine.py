"""Alignment Engine - Main pipeline orchestrator.

Coordinates all pipeline steps to process user messages through
context extraction, retrieval, filtering, generation, and enforcement.

Handles the complete turn lifecycle including:
- Session loading and persistence (via SessionStore)
- Conversation history retrieval (via AuditStore)
- Turn record creation for audit trail (via AuditStore)
"""

import asyncio
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ruche.brains.focal.phases.context import SituationSensor, Turn
from ruche.brains.focal.phases.context.situation_snapshot import SituationSnapshot
from ruche.brains.focal.phases.interlocutor import InterlocutorDataUpdater
from ruche.brains.focal.phases.enforcement import EnforcementValidator, FallbackHandler
from ruche.brains.focal.phases.enforcement.models import EnforcementResult
from ruche.brains.focal.phases.execution import ToolExecutor
from ruche.brains.focal.phases.execution.models import ToolResult
from ruche.brains.focal.phases.filtering import RuleFilter, ScenarioFilter
from ruche.brains.focal.phases.filtering.models import MatchedRule, ScenarioFilterResult
from ruche.brains.focal.phases.generation import PromptBuilder, ResponseGenerator
from ruche.brains.focal.phases.generation.models import GenerationResult
from ruche.brains.focal.phases.loaders.interlocutor_data_loader import InterlocutorDataLoader
from ruche.brains.focal.phases.loaders.static_config_loader import StaticConfigLoader
from ruche.brains.focal.migration.executor import MigrationExecutor
from ruche.brains.focal.migration.field_resolver import MissingFieldResolver
from ruche.brains.focal.migration.models import (
    FieldResolutionResult,
    ReconciliationAction,
    ReconciliationResult,
)
from ruche.brains.focal.models import Rule, Template, TurnContext
from ruche.brains.focal.models.outcome import TurnOutcome
from ruche.brains.focal.phases.planning import ResponsePlanner
from ruche.brains.focal.phases.planning.models import ResponsePlan, ScenarioContributionPlan
from ruche.brains.focal.result import AlignmentResult, PipelineStepTiming
from ruche.brains.focal.retrieval import (
    IntentRetriever,
    RuleReranker,
    RuleRetriever,
    ScenarioReranker,
    ScenarioRetriever,
    decide_canonical_intent,
)
from ruche.brains.focal.retrieval.models import RetrievalResult, ScoredEpisode, ScoredScenario
from ruche.brains.focal.stores import AgentConfigStore
from ruche.brains.focal.templates_loader import load_templates_for_rules
from ruche.audit.models import TurnRecord
from ruche.audit.store import AuditStore
from ruche.config.models.migration import ScenarioMigrationConfig
from ruche.config.models.pipeline import PipelineConfig
from ruche.conversation.models import Session, StepVisit
from ruche.conversation.models.turn import ToolCall
from ruche.conversation.store import SessionStore
from ruche.interlocutor_data.models import VariableEntry
from ruche.interlocutor_data.store import InterlocutorDataStoreInterface
from ruche.interlocutor_data.validation import InterlocutorDataFieldValidator
from ruche.memory.retrieval import MemoryRetriever
from ruche.memory.retrieval.reranker import MemoryReranker
from ruche.memory.store import MemoryStore
from ruche.observability.logging import get_logger
from ruche.infrastructure.providers.embedding import EmbeddingProvider
from ruche.infrastructure.providers.llm import (
    ExecutionContext,
    LLMExecutor,
    clear_execution_context,
    create_executor,
    create_executors_from_pipeline_config,
    set_execution_context,
)
from ruche.infrastructure.providers.rerank import RerankProvider

logger = get_logger(__name__)


class AlignmentEngine:
    """Orchestrate the full alignment pipeline.

    The AlignmentEngine coordinates all pipeline steps:
    1. Context extraction - Understand the user message
    2. Retrieval - Find candidate rules
    3. Reranking - (Optional) Reorder candidates
    4. Rule filtering - LLM judges which rules apply
    5. Scenario filtering - (Optional) Navigate scenario graph
    6. Tool execution - (Optional) Run tools from matched rules
    7. Generation - Generate response
    8. Enforcement - (Optional) Validate against hard constraints

    Each step can be enabled/disabled via configuration.
    """

    def __init__(
        self,
        config_store: AgentConfigStore,
        embedding_provider: EmbeddingProvider,
        session_store: SessionStore | None = None,
        audit_store: AuditStore | None = None,
        rerank_provider: RerankProvider | None = None,
        pipeline_config: PipelineConfig | None = None,
        tool_executor: ToolExecutor | None = None,
        enforcement_validator: EnforcementValidator | None = None,
        fallback_handler: FallbackHandler | None = None,
        memory_store: MemoryStore | None = None,
        migration_config: ScenarioMigrationConfig | None = None,
        executors: dict[str, LLMExecutor] | None = None,
        profile_store: InterlocutorDataStoreInterface | None = None,
        enable_requirement_checking: bool = True,
    ) -> None:
        """Initialize the alignment engine.

        Args:
            config_store: Store for rules, scenarios, templates
            embedding_provider: Provider for embeddings
            session_store: Store for session state (optional, enables persistence)
            audit_store: Store for turn records (optional, enables audit trail)
            rerank_provider: Provider for reranking retrieval results
            pipeline_config: Pipeline configuration (includes model configs per step)
            tool_executor: Executor for tools attached to rules
            enforcement_validator: Validator for hard constraints
            fallback_handler: Handler for enforcement fallbacks
            memory_store: Store for memory episodes
            migration_config: Configuration for scenario migrations
            executors: Optional pre-configured executors (for testing)
            profile_store: Store for customer profiles (enables field requirement checking)
            enable_requirement_checking: Whether to check field requirements on scenario entry
        """
        self._config_store = config_store
        self._embedding_provider = embedding_provider
        self._session_store = session_store
        self._audit_store = audit_store
        self._config = pipeline_config or PipelineConfig()

        # Use provided executors or create from pipeline config
        if executors:
            self._executors = executors
        else:
            self._executors = create_executors_from_pipeline_config(self._config)

        # Create per-object-type rerankers if configured
        rule_reranker = None
        if rerank_provider and self._config.retrieval.rule_reranking and self._config.retrieval.rule_reranking.enabled:
            rule_reranker = RuleReranker(
                provider=rerank_provider,
                top_k=self._config.retrieval.rule_reranking.top_k,
            )

        scenario_reranker = None
        if rerank_provider and self._config.retrieval.scenario_reranking and self._config.retrieval.scenario_reranking.enabled:
            scenario_reranker = ScenarioReranker(
                provider=rerank_provider,
                top_k=self._config.retrieval.scenario_reranking.top_k,
            )

        memory_reranker = None
        if rerank_provider and self._config.retrieval.memory_reranking and self._config.retrieval.memory_reranking.enabled:
            memory_reranker = MemoryReranker(
                provider=rerank_provider,
                top_k=self._config.retrieval.memory_reranking.top_k,
            )

        # Initialize components with their respective executors
        self._situation_sensor = SituationSensor(
            llm_executor=self._executors.get(
                "situation_sensor",
                create_executor("mock/default", step_name="situation_sensor"),
            ),
            config=self._config.situation_sensor,
        )
        self._rule_retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=self._config.retrieval.rule_selection,
            reranker=rule_reranker,
        )
        self._scenario_retriever = ScenarioRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=self._config.retrieval.scenario_selection,
            reranker=scenario_reranker,
        )
        self._intent_retriever = IntentRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=self._config.retrieval.intent_selection,
        )
        self._rule_filter = RuleFilter(
            llm_executor=self._executors.get(
                "rule_filtering",
                create_executor("mock/default", step_name="rule_filtering"),
            ),
        )
        self._scenario_filter = ScenarioFilter(
            config_store=config_store,
            max_loop_count=self._config.scenario_filtering.max_loop_count,
        )
        self._tool_executor = tool_executor
        self._enforcement_validator = enforcement_validator
        self._fallback_handler = fallback_handler
        self._memory_retriever = (
            MemoryRetriever(
                memory_store=memory_store,
                embedding_provider=embedding_provider,
                selection_config=self._config.retrieval.memory_selection,
                reranker=memory_reranker,
            )
            if memory_store
            else None
        )
        self._prompt_builder = PromptBuilder()
        self._response_generator = ResponseGenerator(
            llm_executor=self._executors.get(
                "generation",
                create_executor("mock/default", step_name="generation"),
            ),
            prompt_builder=self._prompt_builder,
        )
        self._response_planner = ResponsePlanner()
        self._migration_executor = (
            MigrationExecutor(
                config_store=config_store,
                session_store=session_store,
                config=migration_config,
            )
            if session_store
            else None
        )

        # Profile store and field requirement checking
        self._profile_store = profile_store
        self._enable_requirement_checking = enable_requirement_checking
        self._missing_field_resolver = (
            MissingFieldResolver(
                profile_store=profile_store,
                llm_executor=self._executors.get(
                    "situation_sensor",  # Reuse situation sensor model for field extraction
                    create_executor("mock/default", step_name="situation_sensor"),
                ),
                field_validator=InterlocutorDataFieldValidator(),
            )
            if profile_store and enable_requirement_checking
            else None
        )

        # Phase 1 loaders
        self._interlocutor_data_loader = (
            InterlocutorDataLoader(profile_store=profile_store)
            if profile_store
            else None
        )
        self._static_config_loader = StaticConfigLoader(config_store=config_store)

        # Phase 3 customer data updater
        self._customer_data_updater = (
            InterlocutorDataUpdater(validator=InterlocutorDataFieldValidator())
            if profile_store
            else None
        )

    async def process_turn(
        self,
        message: str,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        session: Session | None = None,
        history: list[Turn] | None = None,
        persist: bool = True,
        channel: str = "api",
        channel_user_id: str | None = None,
        interlocutor_id: UUID | None = None,
    ) -> AlignmentResult:
        """Process a user message through the alignment pipeline.

        This method handles the complete turn lifecycle:
        1. Resolve customer from channel identity (Phase 1)
        2. Load session from SessionStore (if not provided)
        3. Load conversation history from AuditStore
        4. Build TurnContext with customer data and static config (Phase 1)
        5. Run all pipeline steps (context, retrieval, filtering, generation, enforcement)
        6. Update session state (rule fires, scenario step, variables)
        7. Persist session and turn record to stores

        Args:
            message: The user's message
            session_id: Session identifier
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            session: Optional pre-loaded session (skips SessionStore load)
            history: Optional conversation history (skips AuditStore load)
            persist: Whether to persist session and turn record (default True)
            channel: Channel identifier (default "api")
            channel_user_id: Channel-specific user ID (for customer resolution)
            interlocutor_id: Optional explicit customer ID (skips resolution)

        Returns:
            AlignmentResult with response and all intermediate results
        """
        start_time = time.perf_counter()
        timings: list[PipelineStepTiming] = []
        turn_id = uuid4()

        # Set execution context for all LLM calls in this turn
        set_execution_context(
            ExecutionContext(
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                turn_id=turn_id,
            )
        )

        try:
            return await self._process_turn_impl(
                message=message,
                session_id=session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                turn_id=turn_id,
                session=session,
                history=history,
                persist=persist,
                timings=timings,
                start_time=start_time,
                channel=channel,
                channel_user_id=channel_user_id,
                interlocutor_id=interlocutor_id,
            )
        finally:
            clear_execution_context()

    async def _process_turn_impl(
        self,
        message: str,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        turn_id: UUID,
        session: Session | None,
        history: list[Turn] | None,
        persist: bool,
        timings: list[PipelineStepTiming],
        start_time: float,
        channel: str,
        channel_user_id: str | None,
        interlocutor_id: UUID | None,
    ) -> AlignmentResult:
        """Internal implementation of process_turn."""
        logger.info(
            "processing_turn",
            session_id=str(session_id),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            message_length=len(message),
        )

        # Phase 1.1-1.2: Resolve customer identity
        step_start = datetime.utcnow()
        phase1_start = time.perf_counter()

        # Use channel_user_id or fallback to session_id as identifier
        effective_channel_user_id = channel_user_id or str(session_id)

        resolved_interlocutor_id, is_new_customer = await self._resolve_customer(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=channel,
            channel_user_id=effective_channel_user_id,
            interlocutor_id=interlocutor_id,
        )

        elapsed_ms = (time.perf_counter() - phase1_start) * 1000
        timings.append(
            PipelineStepTiming(
                step="customer_resolution",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        # Step 0: Load session if not provided
        if session is None and self._session_store:
            session = await self._session_store.get(session_id)

        # Step 0b: Load history from audit store if not provided
        if history is None and self._audit_store:
            history = await self._load_history(session_id)
        history = history or []

        # Step 0c: Pre-turn reconciliation for scenario migrations
        reconciliation_result = await self._pre_turn_reconciliation(
            session=session,
            tenant_id=tenant_id,
            timings=timings,
        )

        # If reconciliation requires collecting data, we may need to handle that
        # For now, COLLECT action means we prompt the user in the response
        if reconciliation_result and reconciliation_result.action == ReconciliationAction.COLLECT:
            # Return early with a response asking for the missing data
            return AlignmentResult(
                turn_id=turn_id,
                session_id=session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                user_message=message,
                snapshot=SituationSnapshot(
                    message=message,
                    intent_changed=False,
                    topic_changed=False,
                    tone="neutral",
                ),
                retrieval=RetrievalResult(),
                matched_rules=[],
                scenario_result=None,
                tool_results=[],
                generation=GenerationResult(
                    response=reconciliation_result.user_message or "I need some additional information.",
                    generation_time_ms=0,
                ),
                enforcement=EnforcementResult(
                    passed=True,
                    violations=[],
                    final_response=reconciliation_result.user_message or "I need some additional information.",
                    enforcement_time_ms=0,
                ),
                response=reconciliation_result.user_message or "I need some additional information.",
                pipeline_timings=timings,
                total_time_ms=(time.perf_counter() - start_time) * 1000,
                reconciliation_result=reconciliation_result,
            )

        # Phase 1.8: Build TurnContext
        turn_context = None
        if session:
            turn_context = await self._build_turn_context(
                tenant_id=tenant_id,
                agent_id=agent_id,
                interlocutor_id=resolved_interlocutor_id,
                session=session,
                reconciliation_result=reconciliation_result,
            )

            logger.info(
                "turn_context_built",
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
                session_id=str(session_id),
                interlocutor_id=str(resolved_interlocutor_id),
                turn_number=turn_context.turn_number,
                is_new_customer=is_new_customer,
                has_reconciliation=reconciliation_result is not None,
            )

        # Extract scenario state from session (may have changed after reconciliation)
        active_scenario_id = session.active_scenario_id if session else None
        current_step_id = session.active_step_id if session else None
        visited_steps = (
            {v.step_id: v.turn_number for v in session.step_history}
            if session
            else None
        )

        # Step 1: Situational Sensing
        snapshot = await self._sense_situation(
            message=message,
            history=history,
            timings=timings,
            tenant_id=tenant_id,
            agent_id=agent_id,
            interlocutor_id=resolved_interlocutor_id,
            previous_intent_label=None,  # TODO: Track from session
        )

        # Phase 3: Customer Data Update
        persistent_customer_updates = []
        if (
            self._config.customer_data_update.enabled
            and self._customer_data_updater
            and snapshot.candidate_variables
        ):
            step_start_p3 = datetime.utcnow()
            start_time_p3 = time.perf_counter()

            try:
                # Get customer data store from snapshot
                customer_data_store = getattr(snapshot, "customer_data_store", None)
                if customer_data_store:
                    # Load field definitions
                    customer_data_fields = []
                    if self._static_config_loader:
                        customer_data_fields_dict = await self._static_config_loader.load_customer_data_schema(
                            tenant_id=tenant_id,
                            agent_id=agent_id,
                        )
                        customer_data_fields = list(customer_data_fields_dict.values())

                    # Execute Phase 3 update
                    customer_data_store, persistent_customer_updates = await self._customer_data_updater.update(
                        customer_data_store=customer_data_store,
                        candidate_variables=snapshot.candidate_variables,
                        field_definitions=customer_data_fields,
                    )

                    logger.info(
                        "customer_data_update_completed",
                        tenant_id=str(tenant_id),
                        updates_count=len(persistent_customer_updates),
                    )

                elapsed_ms_p3 = (time.perf_counter() - start_time_p3) * 1000
                timings.append(
                    PipelineStepTiming(
                        step="customer_data_update",
                        started_at=step_start_p3,
                        ended_at=datetime.utcnow(),
                        duration_ms=elapsed_ms_p3,
                    )
                )
            except Exception as e:
                logger.warning(
                    "customer_data_update_failed",
                    error=str(e),
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                )
                elapsed_ms_p3 = (time.perf_counter() - start_time_p3) * 1000
                timings.append(
                    PipelineStepTiming(
                        step="customer_data_update",
                        started_at=step_start_p3,
                        ended_at=datetime.utcnow(),
                        duration_ms=elapsed_ms_p3,
                        skipped=True,
                        skip_reason=f"Error: {str(e)}",
                    )
                )

        # Step 2: Retrieval (get candidate rules)
        retrieval_result = await self._retrieve_rules(
            tenant_id,
            agent_id,
            snapshot,
            timings,
        )

        # Step 3: Rule Filtering
        matched_rules = await self._filter_rules(
            snapshot,
            [scored.rule for scored in retrieval_result.rules],
            timings,
        )

        # Step 4: Scenario Filtering
        scenario_result = await self._filter_scenarios(
            tenant_id,
            snapshot,
            retrieval_result.scenarios,
            active_scenario_id,
            current_step_id,
            visited_steps,
            timings,
        )

        # Step 4b: Check Scenario Field Requirements
        missing_requirements, scenario_blocked = await self._check_scenario_requirements(
            session=session,
            scenario_result=scenario_result,
            tenant_id=tenant_id,
            agent_id=agent_id,
            timings=timings,
        )

        # Step 5: Tool Execution
        tool_results = await self._execute_tools(
            matched_rules,
            snapshot,
            timings,
        )

        # Step 6: Response Planning (Phase 8)
        response_plan = await self._build_response_plan(
            scenario_result,
            matched_rules,
            tool_results,
            snapshot,
            tenant_id,
            timings,
        )

        memory_context = self._build_memory_context(retrieval_result.memory_episodes)
        templates = await load_templates_for_rules(
            self._config_store,
            tenant_id,
            matched_rules,
        )

        # Step 7: Generation
        generation_result = await self._generate_response(
            response_plan,
            snapshot,
            matched_rules,
            history,
            timings,
            tool_results,
            memory_context,
            templates,
        )

        # Step 8: Enforcement
        enforcement_result = await self._enforce_response(
            generation_result.response,
            snapshot,
            matched_rules,
            templates,
            timings,
            tenant_id,
            agent_id,
        )

        # Calculate total time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Build result
        result = AlignmentResult(
            turn_id=turn_id,
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_message=message,
            snapshot=snapshot,
            retrieval=retrieval_result,
            matched_rules=matched_rules,
            scenario_result=scenario_result,
            tool_results=tool_results,
            response_plan=response_plan,
            generation=generation_result,
            enforcement=enforcement_result,
            response=enforcement_result.final_response,
            pipeline_timings=timings,
            total_time_ms=total_time_ms,
            missing_requirements=missing_requirements,
            scenario_blocked=scenario_blocked,
            persistent_customer_updates=persistent_customer_updates,
        )

        # Step 8: Compute turn outcome
        outcome = self._compute_turn_outcome(
            matched_rules=matched_rules,
            scenario_result=scenario_result,
            tool_results=tool_results,
            enforcement_result=enforcement_result,
        )
        result.outcome = outcome

        # Step 9: Parallel persistence
        if persist:
            from ruche.observability.metrics import PERSISTENCE_DURATION

            persistence_tasks = []
            persistence_start = time.perf_counter()

            # Task 1: Session persistence
            if session and self._session_store:
                persistence_tasks.append(
                    self._update_and_persist_session(
                        session=session,
                        scenario_result=scenario_result,
                        matched_rules=matched_rules,
                        tool_results=tool_results,
                    )
                )

            # Task 2: InterlocutorData persistence (if updates exist)
            if persistent_customer_updates and self._profile_store:
                persistence_tasks.append(
                    self._persist_customer_data(
                        session=session,
                        updates=persistent_customer_updates,
                    )
                )

            # Task 3: TurnRecord
            if self._audit_store:
                persistence_tasks.append(
                    self._persist_turn_record(
                        result=result,
                        session=session,
                        generation_result=generation_result,
                        outcome=outcome,
                    )
                )

            # Execute all persistence in parallel
            if persistence_tasks:
                with PERSISTENCE_DURATION.labels(operation="parallel").time():
                    results = await asyncio.gather(*persistence_tasks, return_exceptions=True)

                # Check for exceptions in gather results
                for i, task_result in enumerate(results):
                    if isinstance(task_result, Exception):
                        logger.error(
                            "persistence_failed",
                            task_index=i,
                            error=str(task_result),
                            session_id=str(session_id),
                        )

                persistence_duration = time.perf_counter() - persistence_start
                logger.info(
                    "parallel_persistence_complete",
                    session_id=str(session_id),
                    operations=len(persistence_tasks),
                    duration_ms=persistence_duration * 1000,
                    failures=sum(1 for r in results if isinstance(r, Exception)),
                )

        logger.info(
            "turn_processed",
            session_id=str(session_id),
            turn_id=str(turn_id),
            total_time_ms=total_time_ms,
            matched_rules=len(matched_rules),
            response_length=len(result.response),
        )

        return result

    async def _load_history(
        self,
        session_id: UUID,
        limit: int = 10,
    ) -> list[Turn]:
        """Load conversation history from AuditStore.

        Converts TurnRecord objects to lightweight Turn format for context extraction.
        """
        if not self._audit_store:
            return []

        turn_records = await self._audit_store.list_turns_by_session(
            session_id,
            limit=limit,
        )

        # Convert TurnRecord to Turn format (alternating user/assistant)
        history: list[Turn] = []
        for record in turn_records:
            history.append(Turn(role="user", content=record.user_message))
            history.append(Turn(role="assistant", content=record.agent_response))

        return history

    async def _update_and_persist_session(
        self,
        session: Session,
        scenario_result: ScenarioFilterResult | None,
        matched_rules: list[MatchedRule],
        tool_results: list[ToolResult],
    ) -> None:
        """Update session state and persist to SessionStore."""
        now = datetime.now(UTC)

        # Update turn count
        session.turn_count += 1
        session.last_activity_at = now

        # Update rule fires
        for matched in matched_rules:
            rule_id = str(matched.rule.id)
            session.rule_fires[rule_id] = session.rule_fires.get(rule_id, 0) + 1
            session.rule_last_fire_turn[rule_id] = session.turn_count

        # Update variables from tool results
        for tool_result in tool_results:
            if tool_result.success and tool_result.outputs:
                for key, value in tool_result.outputs.items():
                    session.variables[key] = value
                    session.variable_updated_at[key] = now

        # Apply scenario navigation result
        if scenario_result:
            self._apply_scenario_result(session, scenario_result)

        # Persist session
        if self._session_store:
            await self._session_store.save(session)

    def _apply_scenario_result(
        self,
        session: Session,
        result: ScenarioFilterResult,
    ) -> None:
        """Apply scenario navigation result to session state."""
        now = datetime.now(UTC)

        if result.action == "start":
            session.active_scenario_id = result.scenario_id
            session.active_step_id = result.target_step_id
            session.relocalization_count = 0
            if result.target_step_id:
                session.step_history.append(
                    StepVisit(
                        step_id=result.target_step_id,
                        entered_at=now,
                        turn_number=session.turn_count,
                        transition_reason="entry",
                        confidence=result.confidence,
                    )
                )

        elif result.action == "transition":
            session.active_step_id = result.target_step_id
            if result.target_step_id:
                session.step_history.append(
                    StepVisit(
                        step_id=result.target_step_id,
                        entered_at=now,
                        turn_number=session.turn_count,
                        transition_reason=result.reasoning or "transition",
                        confidence=result.confidence,
                    )
                )

        elif result.action == "relocalize":
            session.active_step_id = result.target_step_id
            session.relocalization_count += 1
            if result.target_step_id:
                session.step_history.append(
                    StepVisit(
                        step_id=result.target_step_id,
                        entered_at=now,
                        turn_number=session.turn_count,
                        transition_reason="relocalize",
                        confidence=result.confidence,
                    )
                )

        elif result.action == "exit":
            session.active_scenario_id = None
            session.active_step_id = None
            session.active_scenario_version = None
            session.relocalization_count = 0

        # Bound step history size to prevent unbounded growth
        max_history = 100
        if len(session.step_history) > max_history:
            session.step_history = session.step_history[-max_history:]

    async def _persist_turn_record(
        self,
        result: AlignmentResult,
        session: Session | None,
        generation_result: GenerationResult,
        outcome: "TurnOutcome | None" = None,
    ) -> None:
        """Create and persist turn record to AuditStore."""
        from ruche.observability.metrics import PERSISTENCE_OPERATIONS

        if not self._audit_store:
            return

        # Convert tool results to ToolCall format
        tool_calls = [
            ToolCall(
                tool_id=str(tr.tool_id) if tr.tool_id else tr.tool_name,
                tool_name=tr.tool_name,
                input=tr.inputs,
                output=tr.outputs,
                success=tr.success,
                error=tr.error,
                latency_ms=int(tr.execution_time_ms),
            )
            for tr in result.tool_results
        ]

        # Calculate tokens used
        tokens_used = 0
        if generation_result:
            tokens_used = generation_result.prompt_tokens + generation_result.completion_tokens

        # Build tool execution list for phase decisions
        tool_executions = [
            {
                "tool_name": tr.tool_name,
                "success": tr.success,
                "error": tr.error,
                "latency_ms": tr.execution_time_ms,
            }
            for tr in result.tool_results
        ]

        # Build scenario lifecycle decisions
        scenario_lifecycle_decisions = {}
        if result.scenario_result:
            scenario_id_str = str(result.scenario_result.scenario_id) if result.scenario_result.scenario_id else "unknown"
            scenario_lifecycle_decisions[scenario_id_str] = result.scenario_result.action

        # Build step transitions
        step_transitions = {}
        if result.scenario_result and result.scenario_result.action in ("start", "transition"):
            scenario_id_str = str(result.scenario_result.scenario_id) if result.scenario_result.scenario_id else "unknown"
            step_transitions[scenario_id_str] = {
                "from_step": str(result.scenario_result.current_step_id) if result.scenario_result.current_step_id else None,
                "to_step": str(result.scenario_result.target_step_id) if result.scenario_result.target_step_id else None,
                "reason": result.scenario_result.reasoning or result.scenario_result.action,
            }

        # Extract enforcement violations
        enforcement_violations = []
        if result.enforcement and result.enforcement.violations:
            enforcement_violations = [v.message for v in result.enforcement.violations]

        turn_record = TurnRecord(
            turn_id=result.turn_id,
            tenant_id=result.tenant_id,
            agent_id=result.agent_id,
            session_id=result.session_id,
            turn_number=session.turn_count if session else 1,
            user_message=result.user_message,
            agent_response=result.response,
            matched_rule_ids=[m.rule.id for m in result.matched_rules],
            scenario_id=session.active_scenario_id if session else None,
            step_id=session.active_step_id if session else None,
            tool_calls=tool_calls,
            latency_ms=int(result.total_time_ms),
            tokens_used=tokens_used,
            timestamp=datetime.now(UTC),
            outcome=outcome,
            canonical_intent=result.snapshot.canonical_intent_label if result.snapshot else None,
            matched_rules_count=len(result.matched_rules),
            scenario_lifecycle_decisions=scenario_lifecycle_decisions,
            step_transitions=step_transitions,
            tool_executions=tool_executions,
            enforcement_violations=enforcement_violations,
            regeneration_attempts=0,  # TODO: Track this in enforcement phase
        )

        try:
            await self._audit_store.save_turn(turn_record)
            PERSISTENCE_OPERATIONS.labels(operation="turn_record", status="success").inc()
        except Exception as e:
            logger.error(
                "turn_record_persistence_failed",
                session_id=str(result.session_id),
                turn_id=str(result.turn_id),
                error=str(e),
            )
            PERSISTENCE_OPERATIONS.labels(operation="turn_record", status="failure").inc()
            raise

    async def _execute_tools(
        self,
        matched_rules: list[MatchedRule],
        snapshot: SituationSnapshot,
        timings: list[PipelineStepTiming],
    ) -> list[ToolResult]:
        """Execute tools from matched rules."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if (
            not self._config.tool_execution.enabled
            or not matched_rules
            or self._tool_executor is None
        ):
            timings.append(
                PipelineStepTiming(
                    step="tool_execution",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Tool execution disabled or no executor",
                )
            )
            return []

        results = await self._tool_executor.execute(
            matched_rules=matched_rules,
            snapshot=snapshot,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="tool_execution",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )
        return results

    async def _sense_situation(
        self,
        message: str,
        history: list[Turn],
        timings: list[PipelineStepTiming],
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        interlocutor_id: UUID | None = None,
        previous_intent_label: str | None = None,
    ) -> SituationSnapshot:
        """Extract situation snapshot from user message.

        Returns SituationSnapshot with message context and extracted fields.
        If sensor is disabled or fails, returns minimal snapshot with just message.
        """
        # If sensor disabled or missing IDs, return minimal snapshot
        if not self._config.situation_sensor.enabled or not tenant_id or not agent_id or not interlocutor_id:
            return SituationSnapshot(
                message=message,
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
            )

        step_start_sensor = datetime.utcnow()
        start_time_sensor = time.perf_counter()

        try:
            # Load customer data and schema
            customer_data_store = None
            if self._interlocutor_data_loader:
                customer_data_store = await self._interlocutor_data_loader.load(
                    interlocutor_id=interlocutor_id,
                    tenant_id=tenant_id,
                    schema={},  # Schema will be loaded separately
                )
            else:
                from ruche.interlocutor_data import InterlocutorDataStore
                customer_data_store = InterlocutorDataStore(
                    id=interlocutor_id,
                    tenant_id=tenant_id,
                    interlocutor_id=interlocutor_id,
                    channel_identities=[],
                    fields={},
                    assets=[],
                )

            # Load glossary and customer data schema
            glossary = {}
            customer_data_fields = {}
            if self._static_config_loader:
                glossary = await self._static_config_loader.load_glossary(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                )
                customer_data_fields = await self._static_config_loader.load_customer_data_schema(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                )

            # Call situation sensor
            snapshot = await self._situation_sensor.sense(
                message=message,
                history=history,
                customer_data_store=customer_data_store,
                customer_data_fields=customer_data_fields,
                glossary_items=glossary,
                previous_intent_label=previous_intent_label,
            )

            elapsed_ms_sensor = (time.perf_counter() - start_time_sensor) * 1000
            timings.append(
                PipelineStepTiming(
                    step="situation_sensor",
                    started_at=step_start_sensor,
                    ended_at=datetime.utcnow(),
                    duration_ms=elapsed_ms_sensor,
                )
            )

            return snapshot

        except Exception as e:
            logger.warning(
                "situation_sensor_failed",
                error=str(e),
                tenant_id=str(tenant_id),
                agent_id=str(agent_id),
            )
            elapsed_ms_sensor = (time.perf_counter() - start_time_sensor) * 1000
            timings.append(
                PipelineStepTiming(
                    step="situation_sensor",
                    started_at=step_start_sensor,
                    ended_at=datetime.utcnow(),
                    duration_ms=elapsed_ms_sensor,
                    skipped=True,
                    skip_reason=f"Error: {str(e)}",
                )
            )

            # Return minimal snapshot on failure
            return SituationSnapshot(
                message=message,
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
            )

    async def _retrieve_rules(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        snapshot: SituationSnapshot,
        timings: list[PipelineStepTiming],
    ) -> RetrievalResult:
        """Retrieve candidate rules, scenarios, and memory in parallel."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.retrieval.enabled:
            timings.append(
                PipelineStepTiming(
                    step="retrieval",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Retrieval disabled",
                )
            )
            return RetrievalResult()

        # Build parallel retrieval tasks
        rule_task = self._rule_retriever.retrieve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            snapshot=snapshot,
        )

        scenario_task = self._scenario_retriever.retrieve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            snapshot=snapshot,
        )

        intent_task = self._intent_retriever.retrieve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            snapshot=snapshot,
        )

        memory_task = None
        if self._memory_retriever:
            memory_task = self._memory_retriever.retrieve(
                tenant_id=tenant_id,
                agent_id=agent_id,
                snapshot=snapshot,
            )

        # Execute all retrievals in parallel (P4: rules, scenarios, intents, memory)
        tasks = [rule_task, scenario_task, intent_task]
        if memory_task:
            tasks.append(memory_task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results
        retrieval_result = results[0] if isinstance(results[0], RetrievalResult) else RetrievalResult()
        scenarios = results[1] if not isinstance(results[1], Exception) else []
        intent_candidates = results[2] if not isinstance(results[2], Exception) else []
        memories = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else []

        # Handle exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                obj_type = ["rules", "scenarios", "intents", "memory"][i] if i < 4 else "unknown"
                logger.error(
                    "retrieval_failed",
                    object_type=obj_type,
                    error=str(result),
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                )

        # P4.3: Decide canonical intent (merge LLM sensor intent with hybrid retrieval)
        sensor_intent = snapshot.new_intent_label  # From Phase 2 Situational Sensor
        sensor_confidence = None  # Phase 2 would set this, but not yet implemented
        canonical_intent, intent_score = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=intent_candidates,
        )
        snapshot.canonical_intent_label = canonical_intent
        snapshot.canonical_intent_score = intent_score

        # Merge results into RetrievalResult
        retrieval_result.scenarios = scenarios
        retrieval_result.memory_episodes = memories

        # Add selection metadata
        retrieval_result.selection_metadata["scenarios"] = {
            "strategy": self._scenario_retriever.selection_strategy_name,
            "min_score": self._config.retrieval.scenario_selection.min_score,
            "max_k": self._config.retrieval.scenario_selection.max_k,
            "min_k": self._config.retrieval.scenario_selection.min_k,
        }

        if self._memory_retriever and memories:
            retrieval_result.selection_metadata["memory"] = {
                "strategy": self._memory_retriever.selection_strategy_name,
                "min_score": self._config.retrieval.memory_selection.min_score,
                "max_k": self._config.retrieval.memory_selection.max_k,
                "min_k": self._config.retrieval.memory_selection.min_k,
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="retrieval",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        logger.debug(
            "rules_retrieved",
            count=len(retrieval_result.rules),
            elapsed_ms=elapsed_ms,
        )

        return retrieval_result

    async def _filter_rules(
        self,
        snapshot: SituationSnapshot,
        candidate_rules: list[Rule],
        timings: list[PipelineStepTiming],
    ) -> list[MatchedRule]:
        """Filter rules by relevance to snapshot."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.rule_filtering.enabled or not candidate_rules:
            timings.append(
                PipelineStepTiming(
                    step="rule_filtering",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Filtering disabled or no candidates",
                )
            )
            # Return all rules as matched with default scores
            return [
                MatchedRule(
                    rule=rule, match_score=1.0, relevance_score=1.0, reasoning="Filter disabled"
                )
                for rule in candidate_rules
            ]

        filter_result = await self._rule_filter.filter(
            snapshot=snapshot,
            candidates=candidate_rules,
            batch_size=self._config.rule_filtering.batch_size,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="rule_filtering",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        return filter_result.matched_rules

    async def _filter_scenarios(
        self,
        tenant_id: UUID,
        snapshot: SituationSnapshot,
        candidates: list[ScoredScenario],
        active_scenario_id: UUID | None,
        current_step_id: UUID | None,
        visited_steps: dict[UUID, int] | None,
        timings: list[PipelineStepTiming],
    ) -> ScenarioFilterResult | None:
        """Filter and decide scenario navigation."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.scenario_filtering.enabled:
            timings.append(
                PipelineStepTiming(
                    step="scenario_filtering",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Scenario filtering disabled",
                )
            )
            return None

        result = await self._scenario_filter.evaluate(
            tenant_id,
            snapshot,
            candidates=candidates,
            active_scenario_id=active_scenario_id,
            current_step_id=current_step_id,
            visited_steps=visited_steps,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="scenario_filtering",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        return result

    async def _build_response_plan(
        self,
        scenario_result: ScenarioFilterResult | None,
        matched_rules: list[MatchedRule],
        tool_results: list[ToolResult],
        snapshot: SituationSnapshot,
        tenant_id: UUID,
        timings: list[PipelineStepTiming],
    ) -> ResponsePlan | None:
        """Build response plan from scenario contributions and rule constraints."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.response_planning.enabled:
            timings.append(
                PipelineStepTiming(
                    step="response_planning",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Response planning disabled",
                )
            )
            return None

        # Build scenario contribution plan from scenario result
        scenario_contribution_plan = ScenarioContributionPlan(contributions=[])

        # If there's a scenario result, extract contributions
        # For now, we'll use an empty contribution plan
        # In a full implementation, Phase 6 would build this

        # Build the response plan
        response_plan = await self._response_planner.build_response_plan(
            scenario_contribution_plan=scenario_contribution_plan,
            matched_rules=matched_rules,
            tool_results={},  # Convert list to dict if needed
            snapshot=snapshot,
            tenant_id=str(tenant_id),
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="response_planning",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        return response_plan

    async def _generate_response(
        self,
        response_plan: ResponsePlan | None,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        history: list[Turn],
        timings: list[PipelineStepTiming],
        tool_results: list[ToolResult],
        memory_context: str | None,
        templates: list[Template],
        glossary_items: list | None = None,
    ) -> GenerationResult:
        """Generate response using matched rules."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.generation.enabled:
            from ruche.brains.focal.phases.generation.models import GenerationResult

            timings.append(
                PipelineStepTiming(
                    step="generation",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Generation disabled",
                )
            )
            return GenerationResult(
                response="I apologize, but I'm unable to respond at this time.",
                generation_time_ms=0,
            )

        result = await self._response_generator.generate(
            snapshot=snapshot,
            matched_rules=matched_rules,
            history=history,
            tool_results=tool_results,
            memory_context=memory_context,
            templates=templates,
            response_plan=response_plan,
            glossary_items=glossary_items,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="generation",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        return result

    async def _enforce_response(
        self,
        response: str,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
        templates: list[Template],
        timings: list[PipelineStepTiming],
        tenant_id: UUID,
        agent_id: UUID,
    ) -> EnforcementResult:
        """Run enforcement validation and optional fallback."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.enforcement.enabled or self._enforcement_validator is None:
            timings.append(
                PipelineStepTiming(
                    step="enforcement",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Enforcement disabled or no validator",
                )
            )
            return EnforcementResult(
                passed=True,
                violations=[],
                final_response=response,
                enforcement_time_ms=0.0,
            )

        result = await self._enforcement_validator.validate(
            response=response,
            snapshot=snapshot,
            matched_rules=matched_rules,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Apply fallback if still failing
        if not result.passed and self._fallback_handler:
            fallback_template = self._fallback_handler.select_fallback(templates or [])
            result = self._fallback_handler.apply_fallback(fallback_template, result)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result.enforcement_time_ms = elapsed_ms
        timings.append(
            PipelineStepTiming(
                step="enforcement",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )
        return result

    async def _persist_customer_data(
        self,
        session: Session,
        updates: list,
    ) -> None:
        """Persist customer data updates, filtering by scope.

        Only persists fields with:
        - scope != SESSION (SESSION scope is ephemeral)
        - persist = True in InterlocutorDataField

        Args:
            session: Current session
            updates: List of customer data updates from Phase 3
        """
        from ruche.interlocutor_data.enums import VariableSource
        from ruche.observability.metrics import PERSISTENCE_OPERATIONS

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
        profile = await self._profile_store.get_by_interlocutor_id(
            tenant_id=session.tenant_id,
            interlocutor_id=session.interlocutor_id,
        )

        if not profile:
            logger.warning(
                "profile_not_found_for_persistence",
                session_id=str(session.session_id),
                interlocutor_id=str(session.interlocutor_id),
            )
            PERSISTENCE_OPERATIONS.labels(operation="customer_data", status="failure").inc()
            return

        # Update each field
        for update in persistent_updates:
            try:
                field = VariableEntry(
                    name=update.field_name,
                    value=update.validated_value if update.validated_value is not None else update.raw_value,
                    value_type=update.field_definition.value_type,
                    source=VariableSource.CONVERSATION,
                    source_session_id=session.session_id,
                )

                await self._profile_store.update_field(
                    tenant_id=session.tenant_id,
                    profile_id=profile.id,
                    field=field,
                    supersede_existing=True,
                )
                PERSISTENCE_OPERATIONS.labels(operation="customer_data", status="success").inc()
            except Exception as e:
                logger.error(
                    "customer_data_field_persistence_failed",
                    session_id=str(session.session_id),
                    field_name=update.field_name,
                    error=str(e),
                )
                PERSISTENCE_OPERATIONS.labels(operation="customer_data", status="failure").inc()

        logger.info(
            "customer_data_persisted",
            session_id=str(session.session_id),
            fields_persisted=len(persistent_updates),
            fields_skipped=len(updates) - len(persistent_updates),
        )

    def _compute_turn_outcome(
        self,
        matched_rules: list[MatchedRule],
        scenario_result: ScenarioFilterResult | None,
        tool_results: list[ToolResult],
        enforcement_result: EnforcementResult | None,
    ):
        """Compute turn outcome based on pipeline decisions.

        Args:
            matched_rules: Rules that matched
            scenario_result: Scenario orchestration result
            tool_results: Tool execution results
            enforcement_result: Enforcement validation result

        Returns:
            TurnOutcome with resolution and categories
        """
        from ruche.brains.focal.models.outcome import OutcomeCategory, TurnOutcome

        categories = []

        # Pipeline-determined categories
        if not matched_rules:
            categories.append(OutcomeCategory.ANSWERED)  # No rules matched, but we answered

        # Check if scenario is waiting for user input (has missing profile fields to collect)
        awaiting_input = (
            scenario_result
            and scenario_result.missing_profile_fields
            and len(scenario_result.missing_profile_fields) > 0
        )
        if awaiting_input:
            categories.append(OutcomeCategory.AWAITING_USER_INPUT)

        if any(not tool.success for tool in tool_results):
            categories.append(OutcomeCategory.SYSTEM_ERROR)

        if enforcement_result and enforcement_result.violations:
            categories.append(OutcomeCategory.POLICY_RESTRICTION)

        # Determine resolution
        if enforcement_result and not enforcement_result.passed:
            resolution = "BLOCKED"
        elif any(not tool.success for tool in tool_results):
            resolution = "ERROR"
        elif awaiting_input:
            resolution = "PARTIAL"
        else:
            resolution = "ANSWERED"

        return TurnOutcome(
            resolution=resolution,
            categories=categories,
        )

    def _build_memory_context(self, episodes: list[ScoredEpisode]) -> str | None:
        """Format memory episodes into a text block."""
        if not episodes:
            return None
        lines = ["Recent relevant memories:"]
        for ep in episodes:
            lines.append(f"- {ep.content}")
        return "\n".join(lines)

    async def _pre_turn_reconciliation(
        self,
        session: Session | None,
        tenant_id: UUID,
        timings: list[PipelineStepTiming],
    ) -> ReconciliationResult | None:
        """Check for and apply pending migrations before processing turn.

        This method detects two scenarios that require reconciliation:
        1. Session has pending_migration flag set (marked during deployment)
        2. Session scenario_checksum doesn't match current scenario (version changed)

        Args:
            session: Current session
            tenant_id: Tenant identifier
            timings: List to append timing info

        Returns:
            ReconciliationResult if migration was performed, None otherwise
        """
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        # Skip if no session, no migration executor, or no active scenario
        if (
            session is None
            or self._migration_executor is None
            or session.active_scenario_id is None
        ):
            timings.append(
                PipelineStepTiming(
                    step="reconciliation",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="No session, executor, or active scenario",
                )
            )
            return None

        # Load current scenario version
        current_scenario = await self._config_store.get_scenario(
            tenant_id, session.active_scenario_id
        )

        if current_scenario is None:
            logger.warning(
                "scenario_not_found_for_reconciliation",
                session_id=str(session.session_id),
                scenario_id=str(session.active_scenario_id),
            )
            timings.append(
                PipelineStepTiming(
                    step="reconciliation",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="Scenario not found",
                )
            )
            return None

        # Check if reconciliation is needed
        needs_reconciliation = (
            session.pending_migration is not None
            or session.active_scenario_version != current_scenario.version
        )

        if not needs_reconciliation:
            timings.append(
                PipelineStepTiming(
                    step="reconciliation",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="No reconciliation needed",
                )
            )
            return None

        # Execute reconciliation
        logger.info(
            "executing_reconciliation",
            session_id=str(session.session_id),
            pending_migration=session.pending_migration is not None,
            version_mismatch=session.active_scenario_version != current_scenario.version,
        )

        result = await self._migration_executor.reconcile(session, current_scenario)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="reconciliation",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        logger.info(
            "reconciliation_complete",
            session_id=str(session.session_id),
            action=result.action.value,
            elapsed_ms=elapsed_ms,
        )

        return result

    async def _check_scenario_requirements(
        self,
        session: Session | None,
        scenario_result: ScenarioFilterResult | None,
        tenant_id: UUID,
        agent_id: UUID,
        timings: list[PipelineStepTiming],
    ) -> tuple[dict[str, FieldResolutionResult], bool]:
        """Check and try to fill missing field requirements for scenario entry.

        This method is called after scenario filtering when a scenario entry
        (action="start") or step transition is detected. It attempts to fill
        missing fields required by ScenarioFieldRequirement bindings.

        Args:
            session: Current session
            scenario_result: Result of scenario filtering
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            timings: List to append timing info

        Returns:
            Tuple of (missing_requirements dict, scenario_blocked bool).
            - missing_requirements: Fields that couldn't be filled
            - scenario_blocked: True if hard requirements are unmet
        """
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        # Skip if no resolver, session, or scenario result
        if (
            self._missing_field_resolver is None
            or session is None
            or scenario_result is None
        ):
            timings.append(
                PipelineStepTiming(
                    step="requirement_check",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="No resolver, session, or scenario result",
                )
            )
            return {}, False

        # Only check on scenario entry or step transition
        if scenario_result.action not in ("start", "transition"):
            timings.append(
                PipelineStepTiming(
                    step="requirement_check",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason=f"Action is {scenario_result.action}, not start/transition",
                )
            )
            return {}, False

        scenario_id = scenario_result.scenario_id
        step_id = scenario_result.target_step_id

        if scenario_id is None:
            timings.append(
                PipelineStepTiming(
                    step="requirement_check",
                    started_at=step_start,
                    ended_at=datetime.utcnow(),
                    duration_ms=0,
                    skipped=True,
                    skip_reason="No scenario ID",
                )
            )
            return {}, False

        logger.info(
            "checking_scenario_requirements",
            session_id=str(session.session_id),
            scenario_id=str(scenario_id),
            step_id=str(step_id) if step_id else None,
            action=scenario_result.action,
        )

        # Try to fill missing requirements
        fill_results = await self._missing_field_resolver.fill_scenario_requirements(
            session=session,
            scenario_id=scenario_id,
            step_id=step_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Identify unfilled requirements
        unfilled = {
            k: v for k, v in fill_results.items() if not v.filled
        }

        # Check if any hard requirements are unmet
        unfilled_hard = self._missing_field_resolver.get_unfilled_hard_requirements(
            fill_results
        )
        scenario_blocked = len(unfilled_hard) > 0

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="requirement_check",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
            )
        )

        if scenario_blocked:
            logger.warning(
                "scenario_entry_blocked",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
                unfilled_hard_count=len(unfilled_hard),
                unfilled_fields=[r.field_name for r in unfilled_hard],
            )
        elif unfilled:
            logger.info(
                "scenario_requirements_partial",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
                unfilled_soft_count=len(unfilled),
            )
        else:
            logger.info(
                "scenario_requirements_satisfied",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
            )

        return unfilled, scenario_blocked

    async def _resolve_customer(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
        channel_user_id: str,
        interlocutor_id: UUID | None = None,
    ) -> tuple[UUID, bool]:
        """Resolve customer from channel identity or create new.

        Returns:
            (interlocutor_id, is_new_customer)
        """
        if interlocutor_id:
            # Customer ID explicitly provided
            return interlocutor_id, False

        if not self._profile_store:
            # No profile store, generate ephemeral customer ID
            ephemeral_id = uuid4()
            logger.warning(
                "customer_resolution_ephemeral",
                tenant_id=str(tenant_id),
                channel=channel,
                interlocutor_id=str(ephemeral_id),
            )
            return ephemeral_id, True

        # Try to find by channel identity
        from ruche.conversation.models.enums import Channel

        try:
            channel_enum = Channel(channel)
        except ValueError:
            channel_enum = Channel.API

        profile = await self._profile_store.get_by_channel_identity(
            tenant_id=tenant_id,
            channel=channel_enum,
            channel_user_id=channel_user_id,
        )

        if profile:
            logger.info(
                "customer_resolved",
                tenant_id=str(tenant_id),
                interlocutor_id=str(profile.interlocutor_id),
                channel=channel,
            )
            return profile.interlocutor_id, False

        # Create new profile
        profile = await self._profile_store.get_or_create(
            tenant_id=tenant_id,
            channel=channel_enum,
            channel_user_id=channel_user_id,
        )

        logger.info(
            "customer_created",
            tenant_id=str(tenant_id),
            interlocutor_id=str(profile.interlocutor_id),
            channel=channel,
        )

        return profile.interlocutor_id, True

    async def _build_turn_context(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        interlocutor_id: UUID,
        session: Session,
        reconciliation_result: ReconciliationResult | None,
    ) -> TurnContext:
        """Build TurnContext (P1.8).

        Aggregates all Phase 1 outputs into a single context object.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID
            interlocutor_id: Customer ID
            session: Session state
            reconciliation_result: Result of scenario migration if applicable

        Returns:
            TurnContext with all turn-scoped data
        """
        from ruche.interlocutor_data import InterlocutorDataStore

        # Load static config if enabled
        glossary = {}
        customer_data_fields = {}

        if self._config.turn_context.load_glossary:
            try:
                glossary = await self._static_config_loader.load_glossary(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                )
            except Exception as e:
                logger.warning(
                    "glossary_load_failed",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    error=str(e),
                )

        if self._config.turn_context.load_customer_data_schema:
            try:
                customer_data_fields = await self._static_config_loader.load_customer_data_schema(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                )
            except Exception as e:
                logger.warning(
                    "customer_data_schema_load_failed",
                    tenant_id=str(tenant_id),
                    agent_id=str(agent_id),
                    error=str(e),
                )

        # Load customer data
        customer_data = None
        if self._interlocutor_data_loader:
            try:
                customer_data = await self._interlocutor_data_loader.load(
                    interlocutor_id=interlocutor_id,
                    tenant_id=tenant_id,
                    schema=customer_data_fields,
                )
            except Exception as e:
                logger.warning(
                    "customer_data_load_failed",
                    tenant_id=str(tenant_id),
                    interlocutor_id=str(interlocutor_id),
                    error=str(e),
                )
                # Create empty store on failure
                customer_data = InterlocutorDataStore(
                    id=interlocutor_id,
                    tenant_id=tenant_id,
                    interlocutor_id=interlocutor_id,
                    channel_identities=[],
                    fields={},
                    assets=[],
                )
        else:
            # No loader, create empty store
            customer_data = InterlocutorDataStore(
                id=interlocutor_id,
                tenant_id=tenant_id,
                interlocutor_id=interlocutor_id,
                channel_identities=[],
                fields={},
                assets=[],
            )

        return TurnContext(
            tenant_id=tenant_id,
            agent_id=agent_id,
            interlocutor_id=interlocutor_id,
            session_id=session.session_id,
            turn_number=session.turn_count + 1,
            session=session.model_dump(),  # Convert to dict for now
            customer_data=customer_data.model_dump(),  # Convert to dict for now
            pipeline_config=self._config.model_dump(),  # Convert to dict for now
            customer_data_fields={
                name: field.model_dump() for name, field in customer_data_fields.items()
            },
            glossary={
                term: item.model_dump() for term, item in glossary.items()
            },
            reconciliation_result=(
                reconciliation_result.model_dump() if reconciliation_result else None
            ),
            turn_started_at=datetime.now(UTC),
        )
