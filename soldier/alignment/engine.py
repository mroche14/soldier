"""Alignment Engine - Main pipeline orchestrator.

Coordinates all pipeline steps to process user messages through
context extraction, retrieval, filtering, generation, and enforcement.

Handles the complete turn lifecycle including:
- Session loading and persistence (via SessionStore)
- Conversation history retrieval (via AuditStore)
- Turn record creation for audit trail (via AuditStore)
"""

import time
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from soldier.alignment.context import Context, ContextExtractor, Turn
from soldier.alignment.enforcement import EnforcementValidator, FallbackHandler
from soldier.alignment.enforcement.models import EnforcementResult
from soldier.alignment.execution import ToolExecutor
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering import RuleFilter, ScenarioFilter
from soldier.alignment.filtering.models import MatchedRule, ScenarioFilterResult
from soldier.alignment.generation import PromptBuilder, ResponseGenerator
from soldier.alignment.generation.models import GenerationResult
from soldier.alignment.models import Rule, Template
from soldier.alignment.result import AlignmentResult, PipelineStepTiming
from soldier.alignment.retrieval import RuleReranker, RuleRetriever, ScenarioRetriever
from soldier.alignment.retrieval.models import RetrievalResult, ScoredEpisode, ScoredScenario
from soldier.alignment.stores import ConfigStore
from soldier.alignment.templates_loader import load_templates_for_rules
from soldier.audit.models import TurnRecord
from soldier.audit.store import AuditStore
from soldier.config.models.pipeline import PipelineConfig
from soldier.conversation.models import Session, StepVisit
from soldier.conversation.models.turn import ToolCall
from soldier.conversation.store import SessionStore
from soldier.memory.retrieval import MemoryRetriever
from soldier.memory.store import MemoryStore
from soldier.observability.logging import get_logger
from soldier.providers.embedding import EmbeddingProvider
from soldier.providers.llm import LLMProvider
from soldier.providers.rerank import RerankProvider

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
        config_store: ConfigStore,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        session_store: SessionStore | None = None,
        audit_store: AuditStore | None = None,
        rerank_provider: RerankProvider | None = None,
        pipeline_config: PipelineConfig | None = None,
        tool_executor: ToolExecutor | None = None,
        enforcement_validator: EnforcementValidator | None = None,
        fallback_handler: FallbackHandler | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        """Initialize the alignment engine.

        Args:
            config_store: Store for rules, scenarios, templates
            llm_provider: Provider for LLM operations
            embedding_provider: Provider for embeddings
            session_store: Store for session state (optional, enables persistence)
            audit_store: Store for turn records (optional, enables audit trail)
            rerank_provider: Provider for reranking retrieval results
            pipeline_config: Pipeline configuration
            tool_executor: Executor for tools attached to rules
            enforcement_validator: Validator for hard constraints
            fallback_handler: Handler for enforcement fallbacks
            memory_store: Store for memory episodes
        """
        self._config_store = config_store
        self._llm_provider = llm_provider
        self._embedding_provider = embedding_provider
        self._session_store = session_store
        self._audit_store = audit_store
        self._config = pipeline_config or PipelineConfig()

        reranker = None
        if rerank_provider and self._config.reranking.enabled:
            reranker = RuleReranker(
                provider=rerank_provider,
                top_k=self._config.reranking.top_k,
            )

        # Initialize components
        self._context_extractor = ContextExtractor(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )
        self._rule_retriever = RuleRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=self._config.retrieval.rule_selection,
            reranker=reranker,
        )
        self._scenario_retriever = ScenarioRetriever(
            config_store=config_store,
            embedding_provider=embedding_provider,
            selection_config=self._config.retrieval.scenario_selection,
        )
        self._rule_filter = RuleFilter(
            llm_provider=llm_provider,
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
            )
            if memory_store
            else None
        )
        self._prompt_builder = PromptBuilder()
        self._response_generator = ResponseGenerator(
            llm_provider=llm_provider,
            prompt_builder=self._prompt_builder,
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
    ) -> AlignmentResult:
        """Process a user message through the alignment pipeline.

        This method handles the complete turn lifecycle:
        1. Load session from SessionStore (if not provided)
        2. Load conversation history from AuditStore
        3. Run all pipeline steps (context, retrieval, filtering, generation, enforcement)
        4. Update session state (rule fires, scenario step, variables)
        5. Persist session and turn record to stores

        Args:
            message: The user's message
            session_id: Session identifier
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            session: Optional pre-loaded session (skips SessionStore load)
            history: Optional conversation history (skips AuditStore load)
            persist: Whether to persist session and turn record (default True)

        Returns:
            AlignmentResult with response and all intermediate results
        """
        start_time = time.perf_counter()
        timings: list[PipelineStepTiming] = []
        turn_id = uuid4()

        logger.info(
            "processing_turn",
            session_id=str(session_id),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            message_length=len(message),
        )

        # Step 0: Load session if not provided
        if session is None and self._session_store:
            session = await self._session_store.get(session_id)

        # Step 0b: Load history from audit store if not provided
        if history is None and self._audit_store:
            history = await self._load_history(session_id)
        history = history or []

        # Extract scenario state from session
        active_scenario_id = session.active_scenario_id if session else None
        current_step_id = session.active_step_id if session else None
        visited_steps = (
            {v.step_id: v.turn_number for v in session.step_history}
            if session
            else None
        )

        # Step 1: Context Extraction
        context = await self._extract_context(message, history, timings)

        # Step 2: Retrieval (get candidate rules)
        retrieval_result = await self._retrieve_rules(
            tenant_id,
            agent_id,
            context,
            timings,
        )

        # Step 3: Rule Filtering
        matched_rules = await self._filter_rules(
            context,
            [scored.rule for scored in retrieval_result.rules],
            timings,
        )

        # Step 4: Scenario Filtering
        scenario_result = await self._filter_scenarios(
            tenant_id,
            context,
            retrieval_result.scenarios,
            active_scenario_id,
            current_step_id,
            visited_steps,
            timings,
        )

        # Step 5: Tool Execution
        tool_results = await self._execute_tools(
            matched_rules,
            context,
            timings,
        )

        memory_context = self._build_memory_context(retrieval_result.memory_episodes)
        templates = await load_templates_for_rules(
            self._config_store,
            tenant_id,
            matched_rules,
        )

        # Step 6: Generation
        generation_result = await self._generate_response(
            context,
            matched_rules,
            history,
            timings,
            tool_results,
            memory_context,
            templates,
        )

        # Step 7: Enforcement
        enforcement_result = await self._enforce_response(
            generation_result.response,
            context,
            matched_rules,
            templates,
            timings,
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
            context=context,
            retrieval=retrieval_result,
            matched_rules=matched_rules,
            scenario_result=scenario_result,
            tool_results=tool_results,
            generation=generation_result,
            enforcement=enforcement_result,
            response=enforcement_result.final_response,
            pipeline_timings=timings,
            total_time_ms=total_time_ms,
        )

        # Step 8: Update session state and persist
        if session and persist:
            await self._update_and_persist_session(
                session=session,
                scenario_result=scenario_result,
                matched_rules=matched_rules,
                tool_results=tool_results,
            )

        # Step 9: Create and persist turn record
        if persist and self._audit_store:
            await self._persist_turn_record(
                result=result,
                session=session,
                generation_result=generation_result,
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
    ) -> None:
        """Create and persist turn record to AuditStore."""
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
        )

        await self._audit_store.save_turn(turn_record)

    async def _execute_tools(
        self,
        matched_rules: list[MatchedRule],
        context: Context,
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
            context=context,
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

    async def _extract_context(
        self,
        message: str,
        history: list[Turn],
        timings: list[PipelineStepTiming],
    ) -> Context:
        """Extract context from user message."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        mode: Literal["llm", "embedding_only", "disabled"]
        if not self._config.context_extraction.enabled:
            mode = "disabled"
        elif self._config.context_extraction.mode == "embedding":
            mode = "embedding_only"
        else:
            mode = "llm"

        context = await self._context_extractor.extract(
            message=message,
            history=history,
            mode=mode,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        timings.append(
            PipelineStepTiming(
                step="context_extraction",
                started_at=step_start,
                ended_at=datetime.utcnow(),
                duration_ms=elapsed_ms,
                skipped=not self._config.context_extraction.enabled,
            )
        )

        return context

    async def _retrieve_rules(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        context: Context,
        timings: list[PipelineStepTiming],
    ) -> RetrievalResult:
        """Retrieve candidate rules from the config store."""
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

        retrieval_result = await self._rule_retriever.retrieve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            context=context,
        )

        # Retrieve scenarios as part of the same step
        scenarios = await self._scenario_retriever.retrieve(
            tenant_id=tenant_id,
            agent_id=agent_id,
            context=context,
        )
        retrieval_result.scenarios = scenarios
        retrieval_result.selection_metadata["scenarios"] = {
            "strategy": self._scenario_retriever.selection_strategy_name,
            "min_score": self._config.retrieval.scenario_selection.min_score,
            "max_k": self._config.retrieval.scenario_selection.max_k,
            "min_k": self._config.retrieval.scenario_selection.min_k,
        }

        if self._memory_retriever:
            memories = await self._memory_retriever.retrieve(
                tenant_id=tenant_id,
                agent_id=agent_id,
                context=context,
            )
            retrieval_result.memory_episodes = memories
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
        context: Context,
        candidate_rules: list[Rule],
        timings: list[PipelineStepTiming],
    ) -> list[MatchedRule]:
        """Filter rules by relevance to context."""
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
            context=context,
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
        context: Context,
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
            context,
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

    async def _generate_response(
        self,
        context: Context,
        matched_rules: list[MatchedRule],
        history: list[Turn],
        timings: list[PipelineStepTiming],
        tool_results: list[ToolResult],
        memory_context: str | None,
        templates: list[Template],
    ) -> GenerationResult:
        """Generate response using matched rules."""
        step_start = datetime.utcnow()
        start_time = time.perf_counter()

        if not self._config.generation.enabled:
            from soldier.alignment.generation.models import GenerationResult

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
            context=context,
            matched_rules=matched_rules,
            history=history,
            tool_results=tool_results,
            memory_context=memory_context,
            templates=templates,
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
        context: Context,
        matched_rules: list[MatchedRule],
        templates: list[Template],
        timings: list[PipelineStepTiming],
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

        hard_rules = [m.rule for m in matched_rules if m.rule.is_hard_constraint]
        result = await self._enforcement_validator.validate(
            response=response,
            context=context,
            matched_rules=matched_rules,
            hard_rules=hard_rules,
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

    def _build_memory_context(self, episodes: list[ScoredEpisode]) -> str | None:
        """Format memory episodes into a text block."""
        if not episodes:
            return None
        lines = ["Recent relevant memories:"]
        for ep in episodes:
            lines.append(f"- {ep.content}")
        return "\n".join(lines)
