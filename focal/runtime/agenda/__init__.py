"""Agenda-driven task execution layer.

Enables proactive agent actions that bypass ACF:
- Scheduled follow-ups
- Reminders and notifications
- Maintenance tasks

Key distinction from ACF:
- Agent-initiated (not customer messages)
- No session mutex needed
- Direct pipeline execution
"""

from focal.runtime.agenda.models import (
    ScheduledTask,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from focal.runtime.agenda.scheduler import AgendaScheduler
from focal.runtime.agenda.workflow import TaskWorkflow

__all__ = [
    # Models
    "Task",
    "ScheduledTask",
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    # Components
    "AgendaScheduler",
    "TaskWorkflow",
]
