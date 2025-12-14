# Phase 7: Tool Execution Implementation Checklist

> **Reference Documents**:
> - `docs/focal_turn_pipeline/README.md` - Phase 7 specification (P7.1-P7.7)
> - `docs/focal_turn_pipeline/analysis/gap_analysis.md` - Phase 7 gap analysis
> - `IMPLEMENTATION_PLAN.md` - Phase 10 (partial tool execution already exists)

**Status**: PARTIAL (40% complete per gap analysis)

**What Exists**:
- `ToolExecutor` with parallel execution, timeouts, fail-fast
- `VariableResolver` for template string resolution
- `Rule.attached_tool_ids` field
- `ScenarioStep.tool_ids` field

**What's Missing**:
- `ToolBinding` model with `when` timing (BEFORE/DURING/AFTER)
- Tool scheduling based on timing and scenario phase
- Variable requirement computation
- Variable resolution from InterlocutorDataStore → Session → Tool execution
- Future tool queue for AFTER_STEP tools

---

## Phase Overview

**Goal**: Execute tenant tools with proper scheduling, variable resolution, and timing control.

**Core Principles**:
1. **Tool Timing**: Tools execute at BEFORE_STEP, DURING_STEP, or AFTER_STEP based on binding
2. **Variable Resolution Order**: InterlocutorDataStore → Session → Tool execution
3. **Parallel Execution**: Tools without dependencies run in parallel
4. **Fail-Fast/Graceful**: Configurable failure handling
5. **Async Everything**: All tool calls are async

**Pipeline Position**: After P6 (Scenario Orchestration), before P8 (Response Planning)

**Inputs**:
- `ScenarioContributionPlan` (from P6)
- `applied_rules` (from P5)
- `InterlocutorDataStore` (updated in P3)
- `SessionState` (current session variables)

**Outputs**:
- `engine_variables: dict[str, Any]` (merged variables for response generation)
- `tool_results: list[ToolResult]` (execution outcomes)
- Future tool queue (for AFTER_STEP tools)

---

## 1. Models & Core Types

### 1.1 ToolBinding Model

- [x] **Create ToolBinding model**
  - File: `ruche/pipelines/focal/models/tool_binding.py`
  - Action: Created
  - **Implemented**: Created with fields `tool_id`, `when`, `required_variables`, `depends_on`
  - Details:
    ```python
    from pydantic import BaseModel, Field
    from typing import Literal

    class ToolBinding(BaseModel):
        """Tool execution binding with timing and variable tracking."""
        tool_id: str = Field(..., description="Tool identifier from ToolHub")
        when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] = Field(
            default="DURING_STEP",
            description="When to execute tool relative to step"
        )
        required_variables: list[str] = Field(
            default_factory=list,
            description="Variable names this tool can fill"
        )
        depends_on: list[str] = Field(
            default_factory=list,
            description="Tool IDs that must execute first"
        )
    ```

- [x] **Export ToolBinding from models**
  - File: `ruche/pipelines/focal/models/__init__.py`
  - Action: Modified
  - **Implemented**: Added ToolBinding import and export
  - Details: Add `from ruche.pipelines.focal.models.tool_binding import ToolBinding`

### 1.2 Update Rule Model

- [x] **Add tool_bindings field to Rule**
  - File: `ruche/pipelines/focal/models/rule.py`
  - Action: Modified
  - **Implemented**: Added `tool_bindings: list[ToolBinding]` field, marked `attached_tool_ids` as deprecated
  - Details:
    - Import `ToolBinding` from `ruche.pipelines.focal.models.tool_binding`
    - Add field: `tool_bindings: list[ToolBinding] = Field(default_factory=list)`
    - Keep `attached_tool_ids` for backward compatibility (deprecated)
    - Add migration note in docstring about deprecating `attached_tool_ids`

### 1.3 Update ScenarioStep Model

- [x] **Add tool_bindings field to ScenarioStep**
  - File: `ruche/pipelines/focal/models/scenario.py`
  - Action: Modified
  - **Implemented**: Added `tool_bindings: list[ToolBinding]` field, marked `tool_ids` as deprecated
  - Details:
    - Import `ToolBinding` from `ruche.pipelines.focal.models.tool_binding`
    - Add field: `tool_bindings: list[ToolBinding] = Field(default_factory=list)`
    - Keep `tool_ids` for backward compatibility (deprecated)
    - Add migration note in docstring about deprecating `tool_ids`

### 1.4 Tool Execution Models

- [x] **Enhance ToolResult model**
  - File: `ruche/pipelines/focal/execution/models.py`
  - Action: Modified
  - **Implemented**: Added `when`, `variables_filled`, `tool_binding` fields. Created `ToolExecutionResult` model
  - Details:
    - Add `when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] | None` field
    - Add `variables_filled: dict[str, Any]` field (maps variable name → value)
    - Add `tool_binding: ToolBinding | None` field (reference to binding)

---

## 2. Tool Binding Collection (P7.1)

### 2.1 Tool Binding Collector

- [x] **Create ToolBindingCollector class**
  - File: `ruche/pipelines/focal/execution/tool_binding_collector.py`
  - Action: Created
  - **Implemented**: Created with support for collecting from rules and scenario steps, deduplication, and legacy fallback
  - Details:
    ```python
    class ToolBindingCollector:
        """Collects tool bindings from scenarios and rules."""

        async def collect_bindings(
            self,
            contribution_plan: ScenarioContributionPlan,
            applied_rules: list[MatchedRule],
        ) -> list[ToolBinding]:
            """Collect all tool bindings from contributing scenarios and rules.

            Collection order:
            1. Rules (GLOBAL → SCENARIO → STEP)
            2. Scenario steps (current + contributing)

            Returns: Deduplicated list of ToolBinding
            """
    ```
  - Implementation:
    - Collect from `applied_rules` → `rule.tool_bindings`
    - Collect from contributing scenario steps → `step.tool_bindings`
    - Deduplicate by `(tool_id, when)` tuple
    - Log total bindings collected

### 2.2 Tests

- [x] **Create collector tests**
  - File: `tests/unit/alignment/execution/test_tool_binding_collector.py`
  - Action: Create
  - Test cases:
    - Collect from rules only
    - Collect from scenario steps only
    - Collect from both rules and steps
    - Deduplication of duplicate bindings
    - Empty collection (no tools)
    - Multiple BEFORE/DURING/AFTER bindings

---

## 3. Variable Requirement Analysis (P7.2)

### 3.1 Variable Requirement Analyzer

- [x] **Create VariableRequirementAnalyzer class**
  - File: `ruche/pipelines/focal/execution/variable_requirement_analyzer.py`
  - Action: Created
  - **Implemented**: Created with regex-based variable extraction from rules and templates
  - Details:
    ```python
    class VariableRequirementAnalyzer:
        """Analyzes which variables are required for the current turn."""

        def compute_required_variables(
            self,
            tool_bindings: list[ToolBinding],
            applied_rules: list[MatchedRule],
            current_step: ScenarioStep | None,
        ) -> set[str]:
            """Compute set of variable names needed for this turn.

            Sources:
            1. Tool bindings → required_variables
            2. Rule action_text → extract {variable} placeholders
            3. Step template → extract {variable} placeholders

            Returns: Set of variable names (strings)
            """
    ```
  - Implementation:
    - Parse `tool_bindings` for `required_variables`
    - Parse rule `action_text` for `{variable}` placeholders using regex
    - Parse step `template_id` content for `{variable}` placeholders
    - Return deduplicated set

### 3.2 Tests

- [x] **Create analyzer tests**
  - File: `tests/unit/alignment/execution/test_variable_requirement_analyzer.py`
  - Action: Create
  - Test cases:
    - Extract from tool bindings
    - Extract from rule action_text placeholders
    - Extract from step templates
    - Empty requirements
    - Duplicate variable names (deduplication)

---

## 4. Variable Resolution (P7.3)

### 4.1 Variable Resolution Service

- [x] **Enhance VariableResolver for multi-source resolution**
  - File: `ruche/pipelines/focal/execution/variable_resolver.py`
  - Action: Modified
  - **Implemented**: Added `resolve_variables()` method with InterlocutorDataStore → Session priority resolution
  - Details:
    - Keep existing `resolve()` method for template string resolution
    - Add new method:
    ```python
    async def resolve_variables(
        self,
        required_vars: set[str],
        customer_profile: InterlocutorDataStore,
        session: Session,
    ) -> tuple[dict[str, Any], set[str]]:
        """Resolve variables from InterlocutorDataStore and Session.

        Resolution order:
        1. InterlocutorDataStore.fields (active status only)
        2. Session.variables

        Args:
            required_vars: Set of variable names to resolve
            customer_profile: Customer data store
            session: Session state

        Returns:
            (known_vars, missing_vars): Resolved values and still-missing names
        """
    ```
  - Implementation:
    - First check `customer_profile.fields` for active fields matching variable names
    - Then check `session.variables` for session-scoped variables
    - Return `(known_vars, missing_vars)` tuple
    - Log resolution source for each variable (profile vs session)

### 4.2 Tests

- [x] **Enhance variable resolver tests**
  - File: `tests/unit/alignment/execution/test_variable_resolver.py`
  - Action: Modify
  - Test cases:
    - Resolve from profile only
    - Resolve from session only
    - Resolve from both (profile priority)
    - Partial resolution (some missing)
    - All missing
    - All resolved

---

## 5. Tool Scheduling (P7.4)

### 5.1 Tool Scheduler

- [x] **Create ToolScheduler class**
  - File: `ruche/pipelines/focal/execution/tool_scheduler.py`
  - Action: Created
  - **Implemented**: Created with phase filtering, dependency ordering via topological sort, and variable-based scheduling
  - Details:
    ```python
    class ToolScheduler:
        """Determines which tools to execute now based on timing and missing variables."""

        def schedule_tools(
            self,
            tool_bindings: list[ToolBinding],
            missing_vars: set[str],
            current_phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"],
        ) -> list[tuple[str, list[str]]]:
            """Determine tool calls allowed in current phase.

            Args:
                tool_bindings: All available tool bindings
                missing_vars: Variables still needed
                current_phase: Current execution phase

            Returns:
                List of (tool_id, vars_to_fill) tuples for execution
            """
    ```
  - Implementation:
    - Filter bindings by `when == current_phase`
    - For each binding, check if it fills any `missing_vars`
    - Build dependency graph using `depends_on`
    - Return topologically sorted list of tool calls
    - Log scheduled tools with timing

### 5.2 Future Tool Queue

- [x] **Create FutureToolQueue class**
  - File: `ruche/pipelines/focal/execution/tool_scheduler.py`
  - Action: Created (same file as ToolScheduler)
  - **Implemented**: Created with session-based queuing for AFTER_STEP tools
  - Details:
    ```python
    class FutureToolQueue:
        """Tracks tools scheduled for future execution (AFTER_STEP)."""

        def add_tools(
            self,
            tool_bindings: list[ToolBinding],
            session_id: UUID,
        ) -> None:
            """Add AFTER_STEP tools to queue."""

        def get_pending_tools(
            self,
            session_id: UUID,
        ) -> list[ToolBinding]:
            """Get tools waiting to execute after step completes."""

        def clear_session(self, session_id: UUID) -> None:
            """Clear queue for session (step transition)."""
    ```
  - Implementation:
    - Use in-memory dict: `session_id → list[ToolBinding]`
    - Filter for `when == "AFTER_STEP"`
    - Provide methods to add, get, and clear

### 5.3 Tests

- [x] **Create scheduler tests**
  - File: `tests/unit/alignment/execution/test_tool_scheduler.py`
  - Action: Create
  - Test cases:
    - Schedule BEFORE_STEP tools only
    - Schedule DURING_STEP tools only
    - Schedule AFTER_STEP tools only
    - Dependency ordering (depends_on)
    - Filter by missing variables
    - Empty schedule (no matching tools)
    - Future tool queue add/get/clear

---

## 6. Enhanced Tool Execution (P7.5)

### 6.1 Enhance ToolExecutor

- [ ] **Update ToolExecutor for new ToolBinding model**
  - File: `ruche/pipelines/focal/execution/tool_executor.py`
  - Action: Modify
  - Details:
    - Update `execute()` signature:
    ```python
    async def execute_scheduled_tools(
        self,
        scheduled_tools: list[tuple[str, list[str]]],  # (tool_id, vars_to_fill)
        known_vars: dict[str, Any],
        context: Context,
    ) -> list[ToolResult]:
    ```
  - Implementation:
    - Pass `known_vars` to tools as input context
    - Track `variables_filled` in ToolResult
    - Support dependency-based ordering
    - Keep existing timeout, parallel, fail-fast logic
    - Update logging to include timing phase

- [ ] **Add dependency execution support**
  - File: `ruche/pipelines/focal/execution/tool_executor.py`
  - Action: Modify
  - Details:
    - Build dependency graph from `scheduled_tools`
    - Execute tools in topological order
    - Pass outputs from dependency tools as inputs to dependent tools
    - Track execution order in logs

### 6.2 Tests

- [ ] **Update tool executor tests**
  - File: `tests/unit/alignment/execution/test_tool_executor.py`
  - Action: Modify
  - Test cases:
    - Execute with known_vars passed to tools
    - Track variables_filled in results
    - Dependency ordering execution
    - Pass dependency outputs as inputs
    - Existing tests still pass (timeout, parallel, fail-fast)

---

## 7. Result Merging (P7.6)

### 7.1 Variable Merger

- [x] **Create VariableMerger class**
  - File: `ruche/pipelines/focal/execution/variable_merger.py`
  - Action: Created
  - **Implemented**: Created with conflict detection and provenance tracking
  - Details:
    ```python
    class VariableMerger:
        """Merges variables from multiple sources into engine_variables."""

        def merge_tool_results(
            self,
            known_vars: dict[str, Any],
            tool_results: list[ToolResult],
        ) -> dict[str, Any]:
            """Merge tool results into engine_variables.

            Merge order:
            1. Start with known_vars (profile + session)
            2. Add variables_filled from each ToolResult
            3. Later tools override earlier tools if conflict

            Returns:
                engine_variables: dict[str, Any]
            """
    ```
  - Implementation:
    - Start with copy of `known_vars`
    - Iterate `tool_results` in execution order
    - Merge `variables_filled` from each successful result
    - Log conflicts (same variable from multiple tools)
    - Track provenance (which tool filled which variable)

### 7.2 Tests

- [x] **Create merger tests**
  - File: `tests/unit/alignment/execution/test_variable_merger.py`
  - Action: Create
  - Test cases:
    - Merge known_vars only (no tool results)
    - Merge tool results (new variables)
    - Merge with conflicts (later override)
    - Track provenance
    - Failed tools (skip their variables_filled)

---

## 8. Integration

### 8.1 ToolExecutionOrchestrator

- [x] **Create orchestrator for full P7 flow**
  - File: `ruche/pipelines/focal/execution/tool_execution_orchestrator.py`
  - Action: Created
  - **Implemented**: Created orchestrator coordinating all P7.1-P7.7 substeps
  - Details:
    ```python
    class ToolExecutionOrchestrator:
        """Orchestrates complete tool execution flow (P7.1 - P7.7)."""

        def __init__(
            self,
            binding_collector: ToolBindingCollector,
            requirement_analyzer: VariableRequirementAnalyzer,
            variable_resolver: VariableResolver,
            scheduler: ToolScheduler,
            executor: ToolExecutor,
            merger: VariableMerger,
        ):
            ...

        async def execute_phase(
            self,
            contribution_plan: ScenarioContributionPlan,
            applied_rules: list[MatchedRule],
            customer_profile: InterlocutorDataStore,
            session: Session,
            context: Context,
            phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"],
        ) -> ToolExecutionResult:
            """Execute complete tool execution flow for given phase.

            Flow:
            1. Collect tool bindings (P7.1)
            2. Compute required variables (P7.2)
            3. Resolve from profile/session (P7.3)
            4. Schedule tools for phase (P7.4)
            5. Execute scheduled tools (P7.5)
            6. Merge results (P7.6)
            7. Queue future tools (P7.7)

            Returns: ToolExecutionResult with engine_variables, tool_results, queued_tools
            """
    ```

- [x] **Create ToolExecutionResult model**
  - File: `ruche/pipelines/focal/execution/models.py`
  - Action: Modified
  - **Implemented**: Created ToolExecutionResult with all required fields
  - Details:
    ```python
    class ToolExecutionResult(BaseModel):
        """Result of tool execution phase."""
        engine_variables: dict[str, Any]
        tool_results: list[ToolResult]
        missing_variables: set[str]
        queued_tools: list[ToolBinding]  # AFTER_STEP tools
        phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"]
    ```

### 8.2 FocalCognitivePipeline Integration

- [ ] **Add tool execution to FocalCognitivePipeline**
  - File: `ruche/pipelines/focal/engine.py`
  - Action: Modify
  - Details:
    - Add `tool_orchestrator: ToolExecutionOrchestrator` to `__init__`
    - Call orchestrator between P6 (scenario) and P8 (planning):
    ```python
    # After scenario orchestration
    tool_result = await self._tool_orchestrator.execute_phase(
        contribution_plan=contribution_plan,
        applied_rules=matched_rules,
        customer_profile=customer_profile,
        session=session,
        context=context,
        phase="DURING_STEP",  # or BEFORE_STEP based on scenario phase
    )
    ```
    - Pass `tool_result.engine_variables` to response generation
    - Store `tool_result` in `AlignmentResult`

- [ ] **Update AlignmentResult model**
  - File: `ruche/pipelines/focal/result.py`
  - Action: Modify
  - Details:
    - Add `tool_execution_result: ToolExecutionResult | None` field
    - Add `engine_variables: dict[str, Any]` field (shortcut to tool_result.engine_variables)

### 8.3 Tests

- [ ] **Create orchestrator tests**
  - File: `tests/unit/alignment/execution/test_tool_execution_orchestrator.py`
  - Action: Create
  - Test cases:
    - Full P7.1-P7.7 flow
    - BEFORE_STEP phase
    - DURING_STEP phase
    - AFTER_STEP phase
    - Tool dependency chains
    - Partial variable resolution

- [ ] **Create integration test**
  - File: `tests/integration/alignment/test_tool_execution_flow.py`
  - Action: Create
  - Test cases:
    - End-to-end with real stores (in-memory)
    - Tool fills profile variable
    - Tool fills session variable
    - Multiple tools in dependency chain
    - Tool timeout handling

---

## 9. Configuration

### 9.1 Tool Execution Config

- [x] **Add tool execution configuration**
  - File: `ruche/config/models/pipeline.py`
  - Action: Modified
  - **Implemented**: Enhanced ToolExecutionConfig with BEFORE/DURING/AFTER enable flags
  - Details:
    ```python
    class ToolExecutionConfig(BaseModel):
        """Tool execution phase configuration."""
        enabled: bool = True
        default_timeout_ms: int = 5000
        max_parallel: int = 5
        fail_fast: bool = False
        enable_before_step: bool = True
        enable_during_step: bool = True
        enable_after_step: bool = True
    ```

- [x] **Add to PipelineConfig**
  - File: `ruche/config/models/pipeline.py`
  - Action: Already exists
  - **Implemented**: tool_execution field already present in PipelineConfig
  - Details: Add `tool_execution: ToolExecutionConfig = Field(default_factory=ToolExecutionConfig)`

- [x] **Add to default.toml**
  - File: `config/default.toml`
  - Action: Modified
  - **Implemented**: Added [pipeline.tool_execution] section with all configuration options
  - Details:
    ```toml
    [pipeline.tool_execution]
    enabled = true
    default_timeout_ms = 5000
    max_parallel = 5
    fail_fast = false
    enable_before_step = true
    enable_during_step = true
    enable_after_step = true
    ```

---

## 10. Observability

### 10.1 Metrics

- [ ] **Add tool execution metrics**
  - File: `ruche/observability/metrics.py`
  - Action: Modify
  - Details:
    ```python
    # Counters
    tool_executions_total = Counter(
        "focal_tool_executions_total",
        "Total tool executions",
        ["tool_id", "phase", "status"]
    )

    tool_variables_filled_total = Counter(
        "focal_tool_variables_filled_total",
        "Variables filled by tools",
        ["tool_id", "variable_name"]
    )

    # Histograms
    tool_execution_duration_seconds = Histogram(
        "focal_tool_execution_duration_seconds",
        "Tool execution duration",
        ["tool_id", "phase"]
    )

    tool_dependency_chain_length = Histogram(
        "focal_tool_dependency_chain_length",
        "Length of tool dependency chains"
    )
    ```

### 10.2 Structured Logging

- [ ] **Add logging throughout tool execution**
  - Files: All new tool execution classes
  - Action: Modify
  - Details:
    - Log tool binding collection with count
    - Log required variables computation
    - Log variable resolution (source: profile/session)
    - Log tool scheduling (phase, tool_id, deps)
    - Log tool execution start/end (timing, status)
    - Log variable merging with conflicts

---

## 11. Documentation

### 11.1 Update CLAUDE.md

- [ ] **Add tool execution section to CLAUDE.md**
  - File: `CLAUDE.md`
  - Action: Modify
  - Details:
    - Add section: "## Tool Execution Module"
    - Document `ToolBinding` model with timing
    - Document variable resolution order
    - Document BEFORE/DURING/AFTER phases
    - Document dependency execution

### 11.2 Add Implementation Notes

- [ ] **Create tool execution design notes**
  - File: `docs/design/tool-execution.md` (optional, create if needed)
  - Action: Create (optional)
  - Details:
    - Document tool timing semantics
    - Document variable resolution algorithm
    - Document dependency ordering
    - Include examples

---

## 12. Migration Path

### 12.1 Backward Compatibility

- [x] **Support legacy attached_tool_ids**
  - File: `ruche/pipelines/focal/execution/tool_binding_collector.py`
  - Action: Implemented
  - **Implemented**: Added fallback to attached_tool_ids with deprecation warnings
  - Details:
    - If `rule.tool_bindings` is empty, fall back to `rule.attached_tool_ids`
    - Convert to `ToolBinding(tool_id=id, when="DURING_STEP")`
    - Log deprecation warning

- [x] **Support legacy tool_ids on ScenarioStep**
  - File: `ruche/pipelines/focal/execution/tool_binding_collector.py`
  - Action: Implemented
  - **Implemented**: Added fallback to tool_ids with deprecation warnings
  - Details:
    - If `step.tool_bindings` is empty, fall back to `step.tool_ids`
    - Convert to `ToolBinding(tool_id=id, when="DURING_STEP")`
    - Log deprecation warning

---

## Dependencies

**Requires Phase 6 Complete**:
- [ ] `ScenarioContributionPlan` model exists (Phase 6 output)
- [ ] Scenario orchestration provides current step context
- [ ] `applied_rules` available from Phase 5

**Requires Phase 3 Complete**:
- [ ] `InterlocutorDataStore` with active fields
- [ ] `InterlocutorDataStoreInterface` interface
- [ ] Field status tracking

**Requires Session Store**:
- [ ] `Session.variables` field exists
- [ ] Session updates persist

---

## Testing Strategy

### Unit Tests
- Each component (collector, analyzer, resolver, scheduler, merger) independently tested
- Mock dependencies
- Edge cases: empty, conflicts, missing data

### Integration Tests
- Full P7.1-P7.7 flow with in-memory stores
- Tool dependency chains
- Variable resolution from profile and session
- Timeout and failure handling

### Contract Tests
- Tool executor behavior contracts
- Variable resolver behavior contracts

---

## Success Criteria

- [ ] All checkboxes above completed
- [ ] All unit tests pass (>85% coverage)
- [ ] All integration tests pass
- [ ] `ToolBinding` model with timing implemented
- [ ] Variable resolution from InterlocutorDataStore → Session working
- [ ] BEFORE/DURING/AFTER scheduling working
- [ ] Dependency execution working
- [ ] FocalCognitivePipeline integration complete
- [ ] Metrics and logging in place
- [ ] Documentation updated

---

## Notes

### Variable Resolution Order
The spec requires strict resolution order:
1. **InterlocutorDataStore** (profile fields with `status == "active"`)
2. **Session** (session.variables)
3. **Tool execution** (as last resort)

### Tool Timing Semantics
- **BEFORE_STEP**: Execute before entering step (data prefetch)
- **DURING_STEP**: Execute during step processing (default)
- **AFTER_STEP**: Execute after step completes (cleanup, notifications)

### Parallel Execution
Tools without dependencies (`depends_on = []`) execute in parallel up to `max_parallel` limit.

### Fail-Fast vs Graceful
- **Fail-fast**: Stop on first tool failure, return partial results
- **Graceful**: Continue executing all tools, collect all failures

### Integration with Phase 8
Phase 8 (Response Planning) will use `engine_variables` to build the response plan. Missing variables may trigger ASK response type.
