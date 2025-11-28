"""Pipeline result models for alignment engine.

Contains the main AlignmentResult and timing models.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from soldier.alignment.context.models import Context
from soldier.alignment.enforcement.models import EnforcementResult
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule, ScenarioFilterResult
from soldier.alignment.generation.models import GenerationResult
from soldier.alignment.retrieval.models import RetrievalResult


class PipelineStepTiming(BaseModel):
    """Timing information for a single pipeline step."""

    step: str = Field(..., description="Step name")
    started_at: datetime
    ended_at: datetime
    duration_ms: float = Field(ge=0)
    skipped: bool = False
    skip_reason: str | None = None


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
    context: Context | None = None
    retrieval: RetrievalResult | None = None
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
