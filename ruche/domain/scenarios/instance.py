"""Scenario instance models for runtime state.

Contains ScenarioInstance which tracks active scenario execution state.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class ScenarioInstance(BaseModel):
    """Runtime state of an active scenario execution.

    Tracks which scenario is active, which step we're on, and
    execution history within a session.
    """

    model_config = ConfigDict(frozen=False, validate_assignment=True)

    id: UUID = Field(default_factory=uuid4, description="Unique instance ID")
    scenario_id: UUID = Field(..., description="Scenario being executed")
    current_step_id: UUID = Field(..., description="Current step")
    session_id: UUID = Field(..., description="Session this instance belongs to")
    entered_at: datetime = Field(default_factory=utc_now, description="When scenario started")
    last_step_at: datetime = Field(default_factory=utc_now, description="Last step transition")
    step_history: list[UUID] = Field(
        default_factory=list, description="Step IDs visited in order"
    )
    completed: bool = Field(default=False, description="Has reached terminal step")
    completed_at: datetime | None = Field(default=None, description="When completed")

    def transition_to(self, step_id: UUID) -> None:
        """Record transition to a new step."""
        self.step_history.append(self.current_step_id)
        self.current_step_id = step_id
        self.last_step_at = utc_now()

    def complete(self) -> None:
        """Mark scenario as completed."""
        self.completed = True
        self.completed_at = utc_now()
