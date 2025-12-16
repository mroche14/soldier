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

from ruche.domain.agenda import (
    ScheduledTask,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from ruche.runtime.agenda.scheduler import AgendaScheduler
from ruche.runtime.agenda.store import TaskStore
from ruche.runtime.agenda.stores.inmemory import InMemoryTaskStore
from ruche.runtime.agenda.workflow import TaskWorkflow

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
    # Storage
    "TaskStore",
    "InMemoryTaskStore",
]
