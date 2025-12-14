"""Agenda-driven task models.

The agenda layer enables proactive, scheduled agent actions that bypass
ACF (no mutex needed, as they're agent-initiated, not customer-initiated).
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class TaskType(str, Enum):
    """Types of scheduled tasks."""

    # Proactive outreach
    FOLLOW_UP = "follow_up"  # Check in on previous conversation
    REMINDER = "reminder"  # Remind about pending action
    NOTIFICATION = "notification"  # Notify about event

    # Maintenance
    CLEANUP = "cleanup"  # Clean up expired data
    SYNC = "sync"  # Sync with external system

    # Custom
    CUSTOM = "custom"  # Custom task type


class TaskStatus(str, Enum):
    """Task execution status."""

    SCHEDULED = "scheduled"  # Waiting to execute
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Executed successfully
    FAILED = "failed"  # Execution failed
    CANCELLED = "cancelled"  # Cancelled before execution


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """A scheduled task for proactive agent action.

    Tasks are agent-initiated actions that don't require ACF coordination.
    They bypass the session mutex since they're not responding to customer
    messages.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Agent that will execute")

    # Task definition
    task_type: TaskType = Field(..., description="Type of task")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)

    # Target (optional - depends on task type)
    customer_id: UUID | None = Field(default=None, description="Target customer")
    session_id: UUID | None = Field(default=None, description="Related session")

    # Execution
    scheduled_for: datetime = Field(..., description="When to execute")
    execute_after: datetime | None = Field(
        default=None, description="Don't execute before this time"
    )
    expires_at: datetime | None = Field(
        default=None, description="Task expires if not executed by this time"
    )

    # Task data
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Task-specific data"
    )

    # Status
    status: TaskStatus = Field(default=TaskStatus.SCHEDULED)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Execution tracking
    attempts: int = Field(default=0, description="Execution attempt count")
    max_attempts: int = Field(default=3, description="Max retry attempts")
    last_error: str | None = Field(default=None, description="Last error message")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if task has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.attempts < self.max_attempts


class ScheduledTask(BaseModel):
    """A task that has been scheduled for execution.

    This is the runtime view of a task after it's been picked up
    by the scheduler.
    """

    task: Task = Field(..., description="The underlying task")
    execution_id: UUID = Field(
        default_factory=uuid4, description="Unique execution identifier"
    )
    locked_until: datetime | None = Field(
        default=None, description="Lock expiration for distributed execution"
    )
