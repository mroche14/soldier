# Phase 6: Scenario Orchestration - Implementation Checklist

> **Reference**: `docs/focal_turn_pipeline/README.md` (Phase 6), `docs/focal_turn_pipeline/analysis/gap_analysis.md` (P6.1-P6.4)
> **Status**: PARTIAL (60% implemented)
> **Dependencies**: Phase 5 (Rule Selection), outputs to Phase 7 (Tool Execution), Phase 8 (Response Planning)

---

## Overview

Phase 6 handles **scenario lifecycle management** and **multi-scenario contribution planning**. Unlike rule filtering (which decides WHICH rules apply), scenario orchestration decides:

1. **Lifecycle**: START / CONTINUE / PAUSE / COMPLETE / CANCEL scenarios
2. **Transitions**: Which step to move to (including step skipping)
3. **Contributions**: What each active scenario wants to contribute to the response

**Key Principle**: A customer can be in **multiple scenarios simultaneously**, and the response can combine contributions from all of them.

**Current State**:
- ✅ START, CONTINUE, EXIT, RELOCALIZE actions exist
- ❌ PAUSE, COMPLETE, CANCEL actions missing
- ❌ Step skipping logic not implemented
- ❌ ScenarioContribution / ScenarioContributionPlan models missing (blocks Phase 8)
- ❌ Multi-scenario coordination not implemented

---

## Phase Breakdown (from focal_turn_pipeline.md)

| Sub-Phase | Goal | Inputs | Outputs |
|-----------|------|--------|---------|
| **P6.1** | Build scenario selection context | `selected_scenario_candidates`, `SessionState`, `applied_rules`, `Relationship`s | `ScenarioSelectionContext` |
| **P6.2** | Scenario lifecycle decisions | `ScenarioSelectionContext`, `SituationalSnapshot`, `canonical_intent_label` | `list[ScenarioLifecycleDecision]` |
| **P6.3** | Step transition evaluation | ACTIVE `ScenarioInstance`s, `ScenarioTransition`s, `SituationalSnapshot`, `CustomerDataStore` | `list[ScenarioStepTransitionDecision]` |
| **P6.4** | Determine scenario contributions | lifecycle & step decisions, step metadata, `applied_rules` | `ScenarioContributionPlan` |

---

## Implementation Tasks

### 1. Models - Lifecycle and Contribution (P6.2, P6.4)

- [x] **Create ScenarioLifecycleDecision model**
  - File: `soldier/alignment/filtering/models.py`
  - Action: Add new model
  - Details:
    ```python
    class ScenarioLifecycleAction(str, Enum):
        """Lifecycle actions for scenarios."""
        START = "start"
        CONTINUE = "continue"
        PAUSE = "pause"
        COMPLETE = "complete"
        CANCEL = "cancel"

    class ScenarioLifecycleDecision(BaseModel):
        """Decision about scenario lifecycle for this turn."""
        scenario_id: UUID
        action: ScenarioLifecycleAction
        reasoning: str
        confidence: float = Field(ge=0.0, le=1.0, default=1.0)
        # Only for START
        entry_step_id: UUID | None = None
        # Only for PAUSE/COMPLETE/CANCEL
        source_step_id: UUID | None = None
    ```

- [x] **Create ScenarioStepTransitionDecision model**
  - File: `soldier/alignment/filtering/models.py`
  - Action: Add new model
  - Details:
    ```python
    class ScenarioStepTransitionDecision(BaseModel):
        """Decision about step transition within a scenario."""
        scenario_id: UUID
        source_step_id: UUID
        target_step_id: UUID
        was_skipped: bool = Field(default=False, description="True if steps were skipped")
        skipped_steps: list[UUID] = Field(default_factory=list, description="IDs of skipped steps")
        reasoning: str
        confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    ```

- [x] **Create ScenarioContribution model** (P6.4)
  - File: `soldier/alignment/planning/__init__.py` (new directory)
  - Action: Create directory and model file
  - Details:
    ```python
    class ContributionType(str, Enum):
        """What the scenario wants to do this turn."""
        ASK = "ask"  # Ask a question
        INFORM = "inform"  # Provide information
        CONFIRM = "confirm"  # Confirm an action
        ACTION_HINT = "action_hint"  # Suggest tool execution
        NONE = "none"  # Silent this turn

    class ScenarioContribution(BaseModel):
        """What a single scenario contributes to this turn."""
        scenario_id: UUID
        scenario_name: str
        current_step_id: UUID
        current_step_name: str
        contribution_type: ContributionType
        # For ASK: fields to collect
        fields_to_ask: list[str] = Field(default_factory=list)
        # For INFORM: template or guidance
        inform_template_id: UUID | None = None
        # For CONFIRM: action description
        action_to_confirm: str | None = None
        # For ACTION_HINT: tool suggestions
        suggested_tools: list[str] = Field(default_factory=list)
        # Priority for merging
        priority: int = Field(default=0, description="Higher priority wins conflicts")
    ```

- [x] **Create ScenarioContributionPlan model** (P6.4)
  - File: `soldier/alignment/planning/models.py`
  - Action: Add to planning models
  - Details:
    ```python
    class ScenarioContributionPlan(BaseModel):
        """Aggregated plan of what all scenarios want to contribute."""
        contributions: list[ScenarioContribution]
        primary_scenario_id: UUID | None = Field(
            default=None, description="Highest priority scenario"
        )
        has_asks: bool = Field(default=False, description="Any ASK contributions")
        has_confirms: bool = Field(default=False, description="Any CONFIRM contributions")
        has_action_hints: bool = Field(default=False, description="Any ACTION_HINT contributions")

        @property
        def active_scenario_ids(self) -> list[UUID]:
            return [c.scenario_id for c in self.contributions]
    ```

- [x] **Create ScenarioSelectionContext model** (P6.1)
  - File: `soldier/alignment/filtering/models.py`
  - Action: Add new model
  - Details:
    ```python
    class ScenarioSelectionContext(BaseModel):
        """Context for scenario lifecycle decisions."""
        candidates: list[ScoredScenario]
        active_instances: list[ScenarioInstance]  # From SessionState
        applied_rules: list[Rule]
        # From SituationalSnapshot (when Phase 2 implemented)
        canonical_intent: str | None = None
        intent_confidence: float | None = None
    ```

- [x] **Create ScenarioInstance model** (SessionState component)
  - File: `soldier/conversation/models/session.py`
  - Action: Add new model for tracking active scenarios
  - Details:
    ```python
    class ScenarioInstance(BaseModel):
        """Active scenario instance in a session."""
        scenario_id: UUID
        scenario_version: int
        current_step_id: UUID
        visited_steps: dict[UUID, int] = Field(
            default_factory=dict, description="step_id -> visit_count"
        )
        started_at: datetime
        last_active_at: datetime
        paused_at: datetime | None = None
        variables: dict[str, Any] = Field(
            default_factory=dict, description="Scenario-scoped variables"
        )
        status: Literal["active", "paused", "completed", "cancelled"] = "active"
    ```

- [x] **Update Session model with scenario instances**
  - File: `soldier/conversation/models/session.py`
  - Action: Modify Session model
  - Details:
    ```python
    class Session(BaseModel):
        # ... existing fields ...
        active_scenarios: list[ScenarioInstance] = Field(
            default_factory=list, description="Currently active scenarios"
        )
        # Deprecate single scenario tracking (migration needed)
        # active_scenario_id: UUID | None = None
        # current_step_id: UUID | None = None
        # visited_steps: dict[UUID, int] = Field(default_factory=dict)
    ```

---

### 2. Lifecycle Actions - PAUSE, COMPLETE, CANCEL (P6.2)

- [x] **Add PAUSE action to ScenarioAction enum**
  - File: `soldier/alignment/filtering/models.py`
  - Action: Modify ScenarioAction enum
  - Details:
    ```python
    class ScenarioAction(str, Enum):
        NONE = "none"
        START = "start"
        CONTINUE = "continue"
        TRANSITION = "transition"
        EXIT = "exit"  # Deprecate in favor of COMPLETE/CANCEL
        RELOCALIZE = "relocalize"
        PAUSE = "pause"  # NEW: Temporarily pause scenario
        COMPLETE = "complete"  # NEW: Successfully complete scenario
        CANCEL = "cancel"  # NEW: Abort scenario without completion
    ```

- [x] **Implement PAUSE detection logic**
  - File: `soldier/alignment/orchestration/orchestrator.py`
  - Action: Add method to ScenarioOrchestrator
  - Details: Implemented in `_should_pause_scenario()` with loop detection and user signal handling

- [x] **Implement COMPLETE detection logic**
  - File: `soldier/alignment/orchestration/orchestrator.py`
  - Action: Add method to ScenarioOrchestrator
  - Details: Implemented in `_should_complete_scenario()` with terminal step detection

- [x] **Implement CANCEL detection logic**
  - File: `soldier/alignment/orchestration/orchestrator.py`
  - Action: Add method to ScenarioOrchestrator
  - Details: Implemented in `_should_cancel_scenario()` with user signal handling

- [x] **Add ScenarioSignal.PAUSE and ScenarioSignal.CANCEL**
  - File: `soldier/alignment/context/models.py`
  - Action: Extend ScenarioSignal enum
  - Details:
    ```python
    class ScenarioSignal(str, Enum):
        NONE = "none"
        EXIT = "exit"
        PAUSE = "pause"  # NEW
        CANCEL = "cancel"  # NEW
    ```

---

### 3. Step Transition Logic - Step Skipping (P6.3)

- [x] **Implement step skipping detection**
  - File: `soldier/alignment/filtering/scenario_filter.py`
  - Action: Add new method
  - Details:
    ```python
    async def _find_furthest_reachable_step(
        self,
        scenario: Scenario,
        current_step_id: UUID,
        customer_data: dict[str, Any],
        session_variables: dict[str, Any],
    ) -> tuple[UUID, list[UUID]]:
        """Find furthest step we can skip to based on available data.

        Example:
            Steps: [collect_order_id] → [collect_reason] → [confirm_refund]
            User message: "Refund order #123, item was damaged"
            Available data: order_id="123", reason="damaged"
            Result: Skip to [confirm_refund], skipped=[collect_order_id, collect_reason]

        Args:
            scenario: Scenario definition
            current_step_id: Where we are now
            customer_data: Data from CustomerProfile
            session_variables: Data from Session

        Returns:
            (furthest_step_id, list_of_skipped_step_ids)
        """
        current_step = next(s for s in scenario.steps if s.id == current_step_id)
        all_data = {**customer_data, **session_variables}

        # BFS to find furthest reachable step
        furthest = current_step_id
        skipped = []

        # Check each downstream step
        for step in scenario.steps:
            if step.can_skip and self._has_required_fields(step, all_data):
                # Check if reachable via transitions
                if self._is_downstream_of(scenario, current_step_id, step.id):
                    furthest = step.id
                    skipped = self._get_intermediate_steps(
                        scenario, current_step_id, step.id
                    )

        return furthest, skipped

    def _has_required_fields(
        self, step: ScenarioStep, available_data: dict[str, Any]
    ) -> bool:
        """Check if step's required fields are available."""
        required = step.collects_profile_fields or []
        return all(field in available_data for field in required)

    def _is_downstream_of(
        self, scenario: Scenario, source_id: UUID, target_id: UUID
    ) -> bool:
        """Check if target is reachable from source via transitions."""
        # BFS through transitions
        visited = set()
        queue = [source_id]

        while queue:
            current = queue.pop(0)
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)

            current_step = next(s for s in scenario.steps if s.id == current)
            for transition in current_step.transitions:
                queue.append(transition.to_step_id)

        return False

    def _get_intermediate_steps(
        self, scenario: Scenario, source_id: UUID, target_id: UUID
    ) -> list[UUID]:
        """Get steps between source and target (for skipping)."""
        # Shortest path BFS
        # Return list of step IDs between source and target
        # Implementation details...
        pass
    ```

- [x] **Integrate step skipping into evaluate()**
  - File: `soldier/alignment/filtering/scenario_filter.py`
  - Action: Modify evaluate() method
  - Details: Integrated step skipping logic after checking profile requirements

- [x] **Add skipped_steps field to ScenarioFilterResult**
  - File: `soldier/alignment/filtering/models.py`
  - Action: Modify ScenarioFilterResult
  - Details:
    ```python
    class ScenarioFilterResult(BaseModel):
        # ... existing fields ...
        skipped_steps: list[UUID] = Field(
            default_factory=list,
            description="Steps skipped due to available data",
        )
    ```

---

### 4. Multi-Scenario Support (P6.1, P6.2)

- [x] **Create ScenarioOrchestrator class** (new)
  - File: `soldier/alignment/orchestration/__init__.py` (new directory)
  - Action: Create new orchestrator for multi-scenario handling
  - Details:
    ```python
    class ScenarioOrchestrator:
        """Orchestrates multiple simultaneous scenarios.

        Replaces single-scenario ScenarioFilter for multi-scenario support.
        """

        def __init__(
            self,
            config_store: AgentConfigStore,
            profile_store: ProfileStore | None = None,
        ):
            self._config_store = config_store
            self._profile_store = profile_store

        async def make_lifecycle_decisions(
            self,
            tenant_id: UUID,
            context: Context,
            candidates: list[ScoredScenario],
            active_instances: list[ScenarioInstance],
            applied_rules: list[Rule],
            customer_profile: CustomerProfile | None = None,
        ) -> list[ScenarioLifecycleDecision]:
            """Decide lifecycle actions for all scenarios (P6.2).

            Returns decisions for:
            - Each active scenario (CONTINUE/PAUSE/COMPLETE/CANCEL)
            - Top candidates (START if conditions met)
            """
            decisions = []

            # Evaluate active scenarios
            for instance in active_instances:
                decision = await self._evaluate_active_scenario(
                    tenant_id, instance, context, customer_profile
                )
                decisions.append(decision)

            # Evaluate candidates for START
            for candidate in candidates:
                if not self._is_already_active(candidate.scenario_id, active_instances):
                    decision = await self._evaluate_candidate(
                        tenant_id, candidate, context, customer_profile
                    )
                    if decision.action == ScenarioLifecycleAction.START:
                        decisions.append(decision)

            return decisions

        async def make_transition_decisions(
            self,
            tenant_id: UUID,
            active_instances: list[ScenarioInstance],
            lifecycle_decisions: list[ScenarioLifecycleDecision],
            customer_profile: CustomerProfile | None = None,
        ) -> list[ScenarioStepTransitionDecision]:
            """Decide step transitions for continuing scenarios (P6.3)."""
            transitions = []

            # Only for scenarios that are CONTINUE
            continuing = [
                d for d in lifecycle_decisions
                if d.action == ScenarioLifecycleAction.CONTINUE
            ]

            for decision in continuing:
                instance = next(
                    i for i in active_instances if i.scenario_id == decision.scenario_id
                )
                transition = await self._evaluate_transition(
                    tenant_id, instance, customer_profile
                )
                transitions.append(transition)

            return transitions
    ```

- [x] **Implement contribution determination** (P6.4)
  - File: `soldier/alignment/orchestration/orchestrator.py`
  - Action: Add method to ScenarioOrchestrator
  - Details:
    ```python
    async def determine_contributions(
        self,
        tenant_id: UUID,
        lifecycle_decisions: list[ScenarioLifecycleDecision],
        transition_decisions: list[ScenarioStepTransitionDecision],
        applied_rules: list[Rule],
    ) -> ScenarioContributionPlan:
        """Determine what each scenario contributes to response (P6.4).

        Returns:
            ScenarioContributionPlan with contributions from each active scenario
        """
        contributions = []

        # Build contributions for each active scenario
        for decision in lifecycle_decisions:
            if decision.action not in [
                ScenarioLifecycleAction.CONTINUE,
                ScenarioLifecycleAction.START,
            ]:
                continue  # PAUSE/COMPLETE/CANCEL don't contribute

            # Find current step
            if decision.action == ScenarioLifecycleAction.START:
                step_id = decision.entry_step_id
            else:
                # Find from transition decisions
                transition = next(
                    (t for t in transition_decisions
                     if t.scenario_id == decision.scenario_id),
                    None
                )
                step_id = transition.target_step_id if transition else None

            if not step_id:
                continue

            # Load scenario and step
            scenario = await self._config_store.get_scenario(
                tenant_id, decision.scenario_id
            )
            step = next(s for s in scenario.steps if s.id == step_id)

            # Determine contribution type
            contribution = await self._build_contribution(
                scenario, step, applied_rules
            )
            contributions.append(contribution)

        # Build plan
        plan = ScenarioContributionPlan(contributions=contributions)

        # Set primary scenario (highest priority)
        if contributions:
            plan.primary_scenario_id = max(
                contributions, key=lambda c: c.priority
            ).scenario_id

        # Set flags
        plan.has_asks = any(c.contribution_type == ContributionType.ASK
                           for c in contributions)
        plan.has_confirms = any(c.contribution_type == ContributionType.CONFIRM
                               for c in contributions)
        plan.has_action_hints = any(c.contribution_type == ContributionType.ACTION_HINT
                                   for c in contributions)

        return plan

    async def _build_contribution(
        self,
        scenario: Scenario,
        step: ScenarioStep,
        applied_rules: list[Rule],
    ) -> ScenarioContribution:
        """Build contribution for a single scenario/step."""
        # Determine contribution type based on step metadata
        contribution_type = ContributionType.NONE

        if step.collects_profile_fields:
            contribution_type = ContributionType.ASK
        elif step.performs_action and step.is_required_action:
            contribution_type = ContributionType.CONFIRM
        elif step.tool_ids:
            contribution_type = ContributionType.ACTION_HINT
        elif step.template_ids:
            contribution_type = ContributionType.INFORM

        return ScenarioContribution(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            current_step_id=step.id,
            current_step_name=step.name,
            contribution_type=contribution_type,
            fields_to_ask=step.collects_profile_fields,
            inform_template_id=step.template_ids[0] if step.template_ids else None,
            action_to_confirm=step.checkpoint_description if step.is_checkpoint else None,
            suggested_tools=step.tool_ids,
            priority=0,  # TODO: Compute from scenario priority + step priority
        )
    ```

---

### 5. AlignmentEngine Integration

- [ ] **Update AlignmentEngine to use ScenarioOrchestrator**
  - File: `soldier/alignment/engine.py`
  - Action: Replace ScenarioFilter with ScenarioOrchestrator
  - Details:
    ```python
    # In __init__:
    from soldier.alignment.orchestration import ScenarioOrchestrator

    self._scenario_orchestrator = ScenarioOrchestrator(
        config_store=config_store,
        profile_store=profile_store,
    )

    # In process_turn(), replace scenario filtering:
    # OLD:
    # scenario_result = await self._scenario_filter.evaluate(...)

    # NEW:
    lifecycle_decisions = await self._scenario_orchestrator.make_lifecycle_decisions(
        tenant_id=tenant_id,
        context=context,
        candidates=scenario_candidates,
        active_instances=session.active_scenarios,
        applied_rules=matched_rules,
        customer_profile=customer_profile,
    )

    transition_decisions = await self._scenario_orchestrator.make_transition_decisions(
        tenant_id=tenant_id,
        active_instances=session.active_scenarios,
        lifecycle_decisions=lifecycle_decisions,
        customer_profile=customer_profile,
    )

    contribution_plan = await self._scenario_orchestrator.determine_contributions(
        tenant_id=tenant_id,
        lifecycle_decisions=lifecycle_decisions,
        transition_decisions=transition_decisions,
        applied_rules=matched_rules,
    )
    ```

- [ ] **Add ScenarioContributionPlan to AlignmentResult**
  - File: `soldier/alignment/result.py`
  - Action: Modify AlignmentResult
  - Details:
    ```python
    class AlignmentResult(BaseModel):
        # ... existing fields ...
        scenario_contribution_plan: ScenarioContributionPlan | None = None
        lifecycle_decisions: list[ScenarioLifecycleDecision] = Field(default_factory=list)
        transition_decisions: list[ScenarioStepTransitionDecision] = Field(default_factory=list)
    ```

- [ ] **Update session state persistence**
  - File: `soldier/alignment/engine.py`
  - Action: Modify _update_and_persist_session() method
  - Details:
    ```python
    async def _update_and_persist_session(
        self,
        session: Session,
        lifecycle_decisions: list[ScenarioLifecycleDecision],
        transition_decisions: list[ScenarioStepTransitionDecision],
        # ... other params
    ) -> None:
        """Update session with scenario lifecycle and transitions."""

        # Update active scenarios based on lifecycle decisions
        for decision in lifecycle_decisions:
            if decision.action == ScenarioLifecycleAction.START:
                instance = ScenarioInstance(
                    scenario_id=decision.scenario_id,
                    scenario_version=1,  # TODO: Get from scenario
                    current_step_id=decision.entry_step_id,
                    started_at=datetime.utcnow(),
                    last_active_at=datetime.utcnow(),
                    status="active",
                )
                session.active_scenarios.append(instance)

            elif decision.action == ScenarioLifecycleAction.PAUSE:
                instance = self._find_instance(session, decision.scenario_id)
                instance.status = "paused"
                instance.paused_at = datetime.utcnow()

            elif decision.action == ScenarioLifecycleAction.COMPLETE:
                instance = self._find_instance(session, decision.scenario_id)
                instance.status = "completed"
                # Remove from active list
                session.active_scenarios = [
                    i for i in session.active_scenarios
                    if i.scenario_id != decision.scenario_id
                ]

            elif decision.action == ScenarioLifecycleAction.CANCEL:
                instance = self._find_instance(session, decision.scenario_id)
                instance.status = "cancelled"
                session.active_scenarios = [
                    i for i in session.active_scenarios
                    if i.scenario_id != decision.scenario_id
                ]

        # Update step positions based on transitions
        for transition in transition_decisions:
            instance = self._find_instance(session, transition.scenario_id)
            instance.current_step_id = transition.target_step_id
            instance.last_active_at = datetime.utcnow()

            # Track visited steps
            for step_id in [transition.source_step_id, transition.target_step_id]:
                instance.visited_steps[step_id] = (
                    instance.visited_steps.get(step_id, 0) + 1
                )

        # Persist
        await self._session_store.save(session)
    ```

---

### 6. Configuration

- [x] **Add scenario orchestration config**
  - File: `config/default.toml`
  - Action: Add new section
  - Details:
    ```toml
    [pipeline.scenario_orchestration]
    enabled = true
    max_loop_count = 3  # Existing
    max_simultaneous_scenarios = 5  # NEW: Limit active scenarios
    block_on_missing_hard_fields = true  # Existing
    enable_step_skipping = true  # NEW: Enable automatic step skipping
    enable_multi_scenario = true  # NEW: Allow multiple active scenarios
    ```

- [x] **Create ScenarioOrchestrationConfig model**
  - File: `soldier/config/models/pipeline.py`
  - Action: Add new config model
  - Details:
    ```python
    class ScenarioOrchestrationConfig(BaseModel):
        enabled: bool = True
        max_loop_count: int = Field(default=3, ge=1)
        max_simultaneous_scenarios: int = Field(default=5, ge=1, le=20)
        block_on_missing_hard_fields: bool = True
        enable_step_skipping: bool = True
        enable_multi_scenario: bool = True
    ```

---

### 7. Tests

- [x] **Unit tests for ScenarioLifecycleDecision**
  - File: `tests/unit/alignment/filtering/test_lifecycle_models.py`
  - Action: Create new test file
  - Details:
    - Test model validation
    - Test all lifecycle actions
    - Test confidence bounds

- [x] **Unit tests for ScenarioContribution**
  - File: `tests/unit/alignment/planning/test_contribution_models.py`
  - Action: Create new test file
  - Details:
    - Test all contribution types
    - Test ScenarioContributionPlan aggregation
    - Test priority ordering

- [x] **Unit tests for step skipping**
  - File: `tests/unit/alignment/filtering/test_step_skipping.py`
  - Action: Create new test file
  - Details: Created comprehensive tests for step skipping logic including all scenarios

- [x] **Unit tests for ScenarioOrchestrator**
  - File: `tests/unit/alignment/orchestration/test_orchestrator.py`
  - Action: Create new test file
  - Details: Created tests for lifecycle decisions, transitions, and contributions

- [x] **Unit tests for lifecycle transitions**
  - File: `tests/unit/alignment/orchestration/test_lifecycle.py`
  - Action: Create new test file
  - Details: Created tests for all lifecycle flows including multi-scenario support

- [ ] **Integration tests for multi-scenario**
  - File: `tests/integration/alignment/test_multi_scenario.py`
  - Action: Create new test file
  - Details:
    - Test two scenarios running simultaneously
    - Test scenario priority resolution
    - Test contribution merging
    - Test scenario completion while another continues

- [ ] **Integration tests for step skipping**
  - File: `tests/integration/alignment/test_step_skipping.py`
  - Action: Create new test file
  - Details:
    - Test skipping steps with profile data
    - Test skipping with session variables
    - Test partial data (skip some steps, not all)
    - Test checkpoint blocking (can't skip past checkpoint)

---

### 8. Observability

- [x] **Add scenario orchestration metrics**
  - File: `soldier/observability/metrics.py`
  - Action: Add new metrics
  - Details: Added all scenario orchestration metrics including lifecycle decisions, steps skipped, contributions, and active scenarios

- [x] **Add structured logging for orchestration**
  - File: `soldier/alignment/orchestration/orchestrator.py`
  - Action: Add logging throughout
  - Details: Added structured logging for lifecycle decisions, contributions, and step skipping

---

## LLM Template Migration (Gap Analysis Item)

> **CRITICAL**: The gap analysis identified that scenario filtering uses `.txt` template that is unused.
> The current implementation is deterministic-only. If LLM-based scenario filtering is needed, add Jinja2 template.

- [ ] **Create scenario_filter.jinja2 template (if LLM filtering needed)**
  - File: `soldier/alignment/filtering/prompts/scenario_filter.jinja2`
  - Action: Create new file
  - Details: Template for LLM-based scenario relevance judgment
    ```jinja2
    {# Scenario Filter Prompt Template #}
    Given the conversation context, determine which scenarios should be active.

    ## Current Active Scenarios
    {% for scenario in active_scenarios %}
    - {{ scenario.name }}: {{ scenario.description }} (current step: {{ scenario.current_step }})
    {% endfor %}

    ## Candidate Scenarios
    {% for scenario in candidate_scenarios %}
    - {{ scenario.name }}: {{ scenario.description }}
      Trigger: {{ scenario.trigger_description }}
    {% endfor %}

    ## User Message
    {{ user_message }}

    ## Intent
    {{ canonical_intent_label }}

    ## Instructions
    For each scenario, output: CONTINUE, START, PAUSE, COMPLETE, or CANCEL with reasoning.
    ```

- [ ] **Add LLM-based scenario evaluation option**
  - File: `soldier/alignment/filtering/scenario_filter.py`
  - Action: Add optional LLM path
  - Details: Allow LLM-based evaluation for complex scenario decisions
    ```python
    class ScenarioFilter:
        def __init__(
            self,
            llm_executor: LLMExecutor | None = None,
            template_dir: str | None = None,
            use_llm: bool = False,  # Default to deterministic
        ):
            self._use_llm = use_llm
            if use_llm and llm_executor:
                self._env = Environment(loader=FileSystemLoader(template_dir))
                self._template = self._env.get_template("scenario_filter.jinja2")

        async def evaluate(self, context, scenarios, session) -> list[ScenarioLifecycleDecision]:
            if self._use_llm:
                return await self._evaluate_with_llm(context, scenarios, session)
            return await self._evaluate_deterministic(context, scenarios, session)
    ```

- [ ] **Add config option for LLM-based scenario filtering**
  - File: `config/default.toml`
  - Action: Modify
  - Details:
    ```toml
    [pipeline.scenario_filtering]
    enabled = true
    use_llm = false  # Set to true to enable LLM-based scenario filtering
    model = "openrouter/openai/gpt-oss-120b"  # Only used if use_llm = true
    ```

---

## Migration Notes

### Backward Compatibility

The current `ScenarioFilter` uses single-scenario tracking:
- `active_scenario_id: UUID | None`
- `current_step_id: UUID | None`
- `visited_steps: dict[UUID, int]`

The new system uses multi-scenario tracking:
- `active_scenarios: list[ScenarioInstance]`

**Migration strategy**:
1. Add `active_scenarios` to Session model (done above)
2. Keep old fields temporarily for backward compatibility
3. Add migration logic in SessionStore to convert old format to new
4. Deprecate old fields in next major version

```python
# In Session model
@property
def active_scenario_id(self) -> UUID | None:
    """Deprecated: Use active_scenarios instead."""
    if self.active_scenarios:
        return self.active_scenarios[0].scenario_id
    return None

@property
def current_step_id(self) -> UUID | None:
    """Deprecated: Use active_scenarios instead."""
    if self.active_scenarios:
        return self.active_scenarios[0].current_step_id
    return None
```

---

## Dependencies

### Required Before Phase 6
- ✅ Phase 5: Rule Selection & Filtering (provides `applied_rules`)
- ⚠️ Phase 2: Situational Sensor (provides `canonical_intent_label`, `SituationalSnapshot`)
  - **Can proceed without this**: Use `context.intent` as fallback
- ⚠️ Phase 3: Customer Data Update (provides `CustomerDataStore`)
  - **Can proceed without this**: Use `CustomerProfile` directly

### Enables After Phase 6
- ⚠️ Phase 7: Tool Execution (uses `ScenarioContributionPlan` for tool bindings)
- ❌ Phase 8: Response Planning (BLOCKED - needs `ScenarioContributionPlan`)
  - **Critical**: Phase 8 is currently skipped entirely in the pipeline
  - Implementing P6.4 (ScenarioContributionPlan) unblocks Phase 8

---

## Priority Order

1. **High Priority** (Unblocks Phase 8):
   - ScenarioContribution / ScenarioContributionPlan models (P6.4)
   - determine_contributions() implementation

2. **Medium Priority** (Core Lifecycle):
   - PAUSE, COMPLETE, CANCEL actions (P6.2)
   - ScenarioOrchestrator with lifecycle decisions

3. **Lower Priority** (Enhancements):
   - Step skipping logic (P6.3)
   - Multi-scenario coordination (P6.1)

---

## Completion Criteria

Phase 6 is complete when:
- ✅ All lifecycle actions (START/CONTINUE/PAUSE/COMPLETE/CANCEL) are implemented
- ✅ Step skipping works based on available customer data
- ✅ ScenarioContributionPlan is generated and passed to Phase 8
- ✅ Multiple scenarios can run simultaneously
- ✅ Session state correctly tracks multiple active scenarios
- ✅ All tests pass with >85% coverage
- ✅ Observability metrics capture orchestration decisions

---

## References

- **Specification**: `docs/focal_turn_pipeline/README.md` (Phase 6, lines 371-416)
- **Gap Analysis**: `docs/focal_turn_pipeline/analysis/gap_analysis.md` (P6.1-P6.4, lines 240-256)
- **Current Implementation**: `soldier/alignment/filtering/scenario_filter.py`
- **Models**: `soldier/alignment/models/scenario.py`, `soldier/alignment/filtering/models.py`
- **Session Tracking**: `soldier/conversation/models/session.py`
