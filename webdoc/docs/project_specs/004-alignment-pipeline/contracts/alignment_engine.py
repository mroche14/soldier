"""Alignment Engine Contract - Interface specification for Phase 11."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# --- Supporting Types ---


class ScenarioAction(str, Enum):
    """Action to take regarding scenario navigation."""

    NONE = "none"  # No scenario action
    START = "start"  # Start a new scenario
    CONTINUE = "continue"  # Stay in current step
    TRANSITION = "transition"  # Move to new step
    EXIT = "exit"  # Exit scenario
    RELOCALIZE = "relocalize"  # Recovery to valid step


class TemplateMode(str, Enum):
    """How a template should be used in generation."""

    EXCLUSIVE = "exclusive"  # Use exact template, skip LLM
    SUGGEST = "suggest"  # Include in prompt, LLM can adapt
    FALLBACK = "fallback"  # Use when enforcement fails


# --- Pipeline Step Results ---


class PipelineStepTiming(BaseModel):
    """Timing information for a single pipeline step."""

    step: str = Field(..., description="Step name")
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    skipped: bool = False
    skip_reason: str | None = None


class MatchedRule(BaseModel):
    """A rule determined to apply to the current turn."""

    rule_id: UUID
    rule_name: str
    match_score: float = Field(ge=0.0, le=1.0, description="Retrieval score")
    relevance_score: float = Field(ge=0.0, le=1.0, description="LLM-judged relevance")
    reasoning: str = Field(default="", description="Why it matches (for audit)")


class ScenarioFilterResult(BaseModel):
    """Result of scenario filtering/navigation."""

    action: ScenarioAction
    scenario_id: UUID | None = None
    source_step_id: UUID | None = None
    target_step_id: UUID | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str = ""

    # For relocalization
    was_relocalized: bool = False
    original_step_id: UUID | None = None


class ToolResult(BaseModel):
    """Outcome of executing a tool."""

    tool_name: str
    tool_id: UUID | None = None
    rule_id: UUID

    # Execution details
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None

    # Status
    success: bool
    execution_time_ms: float = Field(ge=0)
    timeout: bool = False


class GenerationResult(BaseModel):
    """Result of response generation."""

    response: str = Field(..., min_length=1)

    # Template info
    template_used: UUID | None = None
    template_mode: TemplateMode | None = None

    # LLM details
    model: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    generation_time_ms: float = Field(default=0.0, ge=0)


class ConstraintViolation(BaseModel):
    """A detected constraint violation."""

    rule_id: UUID
    rule_name: str
    violation_type: str
    details: str
    severity: str = "hard"


class EnforcementResult(BaseModel):
    """Result of enforcement validation."""

    passed: bool
    violations: list[ConstraintViolation] = Field(default_factory=list)

    # Remediation
    regeneration_attempted: bool = False
    regeneration_succeeded: bool = False
    fallback_used: bool = False
    fallback_template_id: UUID | None = None

    # Final response
    final_response: str


# --- Main Result ---


class AlignmentResult(BaseModel):
    """Complete result of processing a turn through the alignment pipeline.

    This is the primary output of the AlignmentEngine. It contains
    all intermediate results for auditability and debugging.
    """

    # Identifiers
    turn_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    tenant_id: UUID
    agent_id: UUID

    # Input
    user_message: str

    # Pipeline outputs
    matched_rules: list[MatchedRule] = Field(default_factory=list)
    scenario_result: ScenarioFilterResult | None = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    generation: GenerationResult | None = None
    enforcement: EnforcementResult | None = None

    # Final output
    response: str = Field(..., description="The response to return to user")

    # Metadata
    pipeline_timings: list[PipelineStepTiming] = Field(default_factory=list)
    total_time_ms: float = Field(default=0.0, ge=0)

    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Engine Interface ---


class AlignmentEngine(ABC):
    """Interface for the alignment pipeline orchestrator.

    The AlignmentEngine coordinates all pipeline steps:
    1. Context extraction - Understand the user message
    2. Retrieval - Find candidate rules, scenarios, memory
    3. Reranking - Optionally reorder candidates
    4. Rule filtering - LLM judges which rules apply
    5. Scenario filtering - Navigate scenario graph
    6. Tool execution - Run tools from matched rules
    7. Generation - Generate response (or use template)
    8. Enforcement - Validate against hard constraints
    9. Persistence - Save session state and audit records

    Each step can be enabled/disabled via configuration.
    The engine handles errors gracefully at each step.

    Example:
        ```python
        engine = AlignmentEngine(
            config_store=config_store,
            session_store=session_store,
            # ... other dependencies
        )

        result = await engine.process_turn(
            message="I want to return order #12345",
            session=session,
            agent_config=agent_config,
        )

        print(result.response)  # The response to send to user
        print(result.matched_rules)  # Which rules applied
        print(result.total_time_ms)  # Processing time
        ```

    Contract guarantees:
        - Always returns an AlignmentResult (never raises on normal input)
        - result.response is always non-empty
        - All pipeline_timings entries present even if step was skipped
        - Errors in individual steps don't crash the pipeline
        - Session state is persisted before returning
        - Audit records are written before returning
    """

    @abstractmethod
    async def process_turn(
        self,
        message: str,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> AlignmentResult:
        """Process a user message through the alignment pipeline.

        Args:
            message: The user's message
            session_id: Session identifier
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            AlignmentResult with response and all intermediate results

        Raises:
            ValueError: If message is empty or identifiers are invalid
            RuntimeError: If critical pipeline components are misconfigured
        """
        pass
