# Agenda System

> **Topic**: Proactive customer engagement and scheduled tasks
> **Dependencies**: LogicalTurn, Hatchet (workflow execution)
> **Impacts**: Session lifecycle, outbound messaging, proactive customer experience

---

## Overview

The **Agenda** system enables proactive, agent-initiated actions that bypass ACF. It enables:

- **Scheduled Tasks**: Proactive outreach (follow-ups, reminders, notifications)
- **Agent-Initiated Actions**: Tasks that don't require session mutex coordination

### The Problem

Without agenda:
```
Customer: "I'll think about it and get back to you"
Agent: "Sounds good!"
... silence forever ...
```

### The Solution

```
Customer: "I'll think about it and get back to you"
Agent: "Sounds good! I'll check back in 24 hours if I don't hear from you."

[Task scheduled: follow_up at T+24h]

... 24 hours later ...

[Hatchet workflow triggers]
Agent (proactively): "Hi! Just following up on our conversation about X..."
```

---

## Core Models

### Task

A **Task** is a scheduled proactive action:

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class TaskType(str, Enum):
    # Proactive outreach
    FOLLOW_UP = "follow_up"       # Check in on previous conversation
    REMINDER = "reminder"         # Remind about pending action
    NOTIFICATION = "notification" # Notify about event

    # Maintenance
    CLEANUP = "cleanup"           # Clean up expired data
    SYNC = "sync"                 # Sync with external system

    # Custom
    CUSTOM = "custom"             # Custom task type

class TaskStatus(str, Enum):
    SCHEDULED = "scheduled"   # Waiting to execute
    RUNNING = "running"       # Currently executing
    COMPLETED = "completed"   # Executed successfully
    FAILED = "failed"         # Execution failed
    CANCELLED = "cancelled"   # Cancelled before execution

class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class Task(BaseModel):
    """
    A scheduled task for proactive agent action.

    Tasks are agent-initiated actions that don't require ACF coordination.
    They bypass the session mutex since they're not responding to customer messages.
    """

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Agent that will execute")

    # Task definition
    task_type: TaskType = Field(..., description="Type of task")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)

    # Target (optional - depends on task type)
    interlocutor_id: UUID | None = Field(default=None, description="Target customer")
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
        return datetime.utcnow() > self.expires_at

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.attempts < self.max_attempts
```

---

## Task Creation

Tasks can be created during response planning or by explicit agent logic:

```python
from datetime import datetime, timedelta

class TaskScheduler:
    """Schedules proactive tasks."""

    async def schedule_follow_up(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        interlocutor_id: UUID,
        session_id: UUID,
        context: dict,
        delay_hours: int = 24,
    ) -> Task:
        """Schedule a follow-up task."""
        task = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            interlocutor_id=interlocutor_id,
            session_id=session_id,
            task_type=TaskType.FOLLOW_UP,
            priority=TaskPriority.NORMAL,
            scheduled_for=datetime.utcnow() + timedelta(hours=delay_hours),
            payload=context,
            metadata={"created_by": "response_planner"},
        )

        await self._task_store.save(task)
        return task

    async def schedule_reminder(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        interlocutor_id: UUID,
        scheduled_for: datetime,
        reminder_text: str,
    ) -> Task:
        """Schedule a reminder task."""
        task = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            interlocutor_id=interlocutor_id,
            task_type=TaskType.REMINDER,
            priority=TaskPriority.HIGH,
            scheduled_for=scheduled_for,
            payload={"reminder_text": reminder_text},
        )

        await self._task_store.save(task)
        return task
```

---

## Hatchet Workflows

### Follow-Up Workflow

```python
@hatchet.workflow()
class FollowUpWorkflow:
    """
    Executes scheduled follow-up tasks.

    Triggered by Hatchet scheduler when task is due.
    """

    @hatchet.step()
    async def load_context(self, ctx: Context) -> dict:
        """Load task and verify it should still execute."""
        task_id = ctx.workflow_input()["task_id"]

        task_store = ctx.services.agenda_store
        task = await task_store.get_task(task_id)

        if task is None:
            return {"status": "not_found", "skip": True}

        if task.status != TaskStatus.SCHEDULED:
            return {"status": "already_processed", "skip": True}

        # Check if task has expired
        if task.is_expired:
            task.status = TaskStatus.CANCELLED
            await task_store.save(task)
            return {"status": "expired", "skip": True}

        task.status = TaskStatus.RUNNING
        await task_store.save(task)

        return {
            "status": "ready",
            "skip": False,
            "task": task.model_dump(),
        }

    @hatchet.step()
    async def generate_message(self, ctx: Context) -> dict:
        """Generate the follow-up message."""
        if ctx.step_output("load_context")["skip"]:
            return {"skip": True}

        task_data = ctx.step_output("load_context")["task"]
        task = Task(**task_data)

        # Load interlocutor context
        interlocutor_store = ctx.services.interlocutor_store
        interlocutor = await interlocutor_store.get(task.interlocutor_id)

        # Generate message using LLM
        message = await ctx.services.llm.generate(
            prompt=f"""Generate a friendly follow-up message.
            Context: {task.payload}
            Interlocutor: {interlocutor.name}
            Task type: {task.task_type}
            Keep it brief and natural.""",
        )

        return {
            "skip": False,
            "message": message,
            "channel": interlocutor.preferred_channel,
        }

    @hatchet.step()
    async def send_message(self, ctx: Context) -> dict:
        """Send the follow-up message."""
        if ctx.step_output("generate_message").get("skip"):
            return {"status": "skipped"}

        task_data = ctx.step_output("load_context")["task"]
        task = Task(**task_data)
        message = ctx.step_output("generate_message")["message"]
        channel = ctx.step_output("generate_message")["channel"]

        try:
            # Send via channel adapter
            channel_adapter = ctx.services.channel_adapter
            await channel_adapter.send_outbound(
                interlocutor_id=task.interlocutor_id,
                channel=channel,
                message=message,
                context={"agenda_task_id": str(task.id)},
            )

            # Update task status
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            await ctx.services.agenda_store.save(task)

            # Create audit record
            await ctx.services.audit_store.record_outbound(
                task_id=task.id,
                interlocutor_id=task.interlocutor_id,
                channel=channel,
                message=message,
            )

            return {"status": "sent", "channel": channel}

        except ChannelError as e:
            task.status = TaskStatus.FAILED
            task.last_error = str(e)
            task.attempts += 1

            if task.can_retry():
                task.status = TaskStatus.SCHEDULED
                task.scheduled_for = datetime.utcnow() + timedelta(hours=1)

            await ctx.services.agenda_store.save(task)
            return {"status": "failed", "error": str(e), "will_retry": task.can_retry()}

    @hatchet.on_failure()
    async def handle_failure(self, ctx: Context):
        """Handle workflow failure."""
        task_id = ctx.workflow_input().get("task_id")
        ctx.log.error(
            "follow_up_workflow_failed",
            task_id=task_id,
            error=str(ctx.error),
        )
```

### Agenda Scheduler

Periodic job to trigger due tasks:

```python
@hatchet.workflow()
class AgendaSchedulerWorkflow:
    """
    Periodic workflow that finds and triggers due agenda tasks.

    Runs every minute via Hatchet cron.
    """

    @hatchet.step()
    async def find_due_tasks(self, ctx: Context) -> dict:
        """Find all tasks that are due for execution."""
        agenda_store = ctx.services.agenda_store
        now = datetime.utcnow()

        due_tasks = await agenda_store.get_due_tasks(
            before=now,
            limit=100,
        )

        return {
            "task_ids": [str(t.id) for t in due_tasks],
            "count": len(due_tasks),
        }

    @hatchet.step()
    async def trigger_tasks(self, ctx: Context) -> dict:
        """Trigger workflow for each due task."""
        task_ids = ctx.step_output("find_due_tasks")["task_ids"]

        triggered = 0
        for task_id in task_ids:
            await ctx.services.hatchet.run_workflow(
                "FollowUpWorkflow",
                input={"task_id": task_id},
            )
            triggered += 1

        return {"triggered": triggered}
```

---

## Storage

### TaskStore

```python
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

class TaskStore(ABC):
    """Interface for task persistence."""

    @abstractmethod
    async def save(self, task: Task) -> None:
        """Save or update a task."""
        ...

    @abstractmethod
    async def get(self, task_id: UUID) -> Task | None:
        """Get a task by ID."""
        ...

    @abstractmethod
    async def get_due_tasks(
        self,
        before: datetime,
        limit: int = 100,
    ) -> list[Task]:
        """Get tasks that are due for execution."""
        ...

    @abstractmethod
    async def get_interlocutor_tasks(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """Get all tasks for an interlocutor."""
        ...

    @abstractmethod
    async def cancel_task(self, task_id: UUID) -> None:
        """Cancel a scheduled task."""
        ...
```

---

## Configuration

```toml
[agenda]
enabled = true

# Task execution
max_attempts = 3
retry_delay_hours = 1
default_task_expiry_hours = 168  # 1 week

# Scheduler
scheduler_interval_seconds = 60
max_tasks_per_batch = 100

[agenda.follow_up]
# Default follow-up timing
default_delay_hours = 24
max_delay_hours = 168  # 1 week
```

---

## Observability

### Metrics

```python
from prometheus_client import Counter, Histogram

# Task lifecycle
tasks_scheduled = Counter(
    "agenda_tasks_scheduled_total",
    "Tasks scheduled",
    ["task_type", "priority"]
)

tasks_executed = Counter(
    "agenda_tasks_executed_total",
    "Tasks executed",
    ["task_type", "status"]
)

tasks_cancelled = Counter(
    "agenda_tasks_cancelled_total",
    "Tasks cancelled",
    ["task_type", "reason"]
)

# Execution timing
task_execution_delay = Histogram(
    "agenda_task_execution_delay_seconds",
    "Delay between scheduled and actual execution",
    buckets=[0, 60, 300, 600, 3600],
)

task_execution_duration = Histogram(
    "agenda_task_execution_duration_seconds",
    "Task execution duration",
    buckets=[0.1, 0.5, 1, 5, 10, 30],
)
```

### Logging

```python
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "task_scheduled",
    task_id=str(task.id),
    task_type=task.task_type.value,
    priority=task.priority.value,
    scheduled_for=task.scheduled_for.isoformat(),
    tenant_id=str(task.tenant_id),
    agent_id=str(task.agent_id),
)

logger.info(
    "task_executed",
    task_id=str(task.id),
    task_type=task.task_type.value,
    status=task.status.value,
    attempts=task.attempts,
    duration_seconds=duration,
)
```

---

## Testing

```python
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

# Test: Task scheduling
async def test_schedule_follow_up_task():
    scheduler = TaskScheduler(task_store)

    task = await scheduler.schedule_follow_up(
        tenant_id=tenant_id,
        agent_id=agent_id,
        interlocutor_id=interlocutor_id,
        session_id=session_id,
        context={"topic": "refund request"},
        delay_hours=24,
    )

    assert task.task_type == TaskType.FOLLOW_UP
    assert task.status == TaskStatus.SCHEDULED
    assert task.scheduled_for > datetime.utcnow()

# Test: Task expiration
async def test_task_expiration():
    task = Task(
        tenant_id=tenant_id,
        agent_id=agent_id,
        task_type=TaskType.FOLLOW_UP,
        scheduled_for=datetime.utcnow(),
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )

    assert task.is_expired is True

# Test: Task retry logic
async def test_task_retry_logic():
    task = Task(
        tenant_id=tenant_id,
        agent_id=agent_id,
        task_type=TaskType.FOLLOW_UP,
        scheduled_for=datetime.utcnow(),
        attempts=2,
        max_attempts=3,
    )

    assert task.can_retry is True

    task.attempts = 3
    assert task.can_retry is False

# Test: Workflow execution
async def test_follow_up_workflow_execution():
    # Schedule task
    task = await task_store.save(task)

    # Execute workflow
    result = await workflow.run({"task_id": str(task.id)})

    assert result["status"] == "sent"

    # Verify task completed
    updated_task = await task_store.get(task.id)
    assert updated_task.status == TaskStatus.COMPLETED
```

---

## Related Topics

- [01-logical-turn.md](01-logical-turn.md) - Turn-based conversation flow
- [06-hatchet-integration.md](06-hatchet-integration.md) - Workflow execution
- [08-config-hierarchy.md](08-config-hierarchy.md) - Feature enablement
- [10-channel-capabilities.md](10-channel-capabilities.md) - Outbound channel selection
