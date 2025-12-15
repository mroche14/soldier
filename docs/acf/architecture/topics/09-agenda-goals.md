# Agenda & Goals System

> **Topic**: Proactive customer engagement and follow-up tracking
> **Dependencies**: LogicalTurn (goals scoped to beats), Hatchet (workflow execution)
> **Impacts**: Session lifecycle, outbound messaging, 360 customer experience

---

## Overview

The **Agenda & Goals** system transforms Soldier from reactive support to proactive customer lifecycle management. It enables:

- **Goals**: Expected responses or outcomes from a conversation turn
- **Agenda Tasks**: Scheduled proactive outreach (follow-ups, reminders, check-ins)

### The Problem

Without agenda/goals:
```
Customer: "I'll think about it and get back to you"
Agent: "Sounds good!"
... silence forever ...
```

### The Solution

```
Customer: "I'll think about it and get back to you"
Agent: "Sounds good! I'll check back in 24 hours if I don't hear from you."

[Goal created: expect response within 24h]
[AgendaTask scheduled: follow_up at T+24h]

... 24 hours later, no response ...

[Hatchet workflow triggers]
Agent (proactively): "Hi! Just following up on our conversation about X..."
```

---

## Core Models

### Goal

A **Goal** represents an expected outcome from a conversation:

```python
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class GoalStatus(str, Enum):
    PENDING = "pending"       # Awaiting completion
    ACHIEVED = "achieved"     # Customer met the goal
    EXPIRED = "expired"       # Timeout without achievement
    CANCELLED = "cancelled"   # Explicitly cancelled

class GoalType(str, Enum):
    RESPONSE_EXPECTED = "response_expected"     # Customer should respond
    ACTION_EXPECTED = "action_expected"         # Customer should take action
    CONFIRMATION_EXPECTED = "confirmation_expected"  # Customer should confirm
    INFORMATION_EXPECTED = "information_expected"    # Customer should provide info

class Goal(BaseModel):
    """
    Expected outcome from a conversation turn.

    Goals are created during response planning (P8) and
    tracked until achieved, expired, or cancelled.
    """

    id: UUID = Field(default_factory=uuid4)

    # Scoping
    tenant_id: UUID
    agent_id: UUID
    customer_id: UUID
    session_id: UUID
    beat_id: UUID  # The LogicalTurn that created this goal

    # Goal definition
    goal_type: GoalType
    description: str  # Human-readable description
    expected_response_pattern: str | None = None  # Regex or semantic pattern

    # Timing
    created_at: datetime
    deadline: datetime  # When goal expires
    achieved_at: datetime | None = None

    # Status
    status: GoalStatus = GoalStatus.PENDING

    # Context from creating beat
    context_snapshot: dict = Field(default_factory=dict)

    # Linked agenda task (if follow-up scheduled)
    follow_up_task_id: UUID | None = None

    def is_active(self) -> bool:
        return self.status == GoalStatus.PENDING

    def check_expired(self, now: datetime) -> bool:
        if self.status == GoalStatus.PENDING and now > self.deadline:
            self.status = GoalStatus.EXPIRED
            return True
        return False

    def mark_achieved(self, achieving_beat_id: UUID) -> None:
        self.status = GoalStatus.ACHIEVED
        self.achieved_at = datetime.utcnow()
```

### AgendaTask

An **AgendaTask** is a scheduled proactive action:

```python
class TaskType(str, Enum):
    FOLLOW_UP = "follow_up"           # Check if goal achieved
    REMINDER = "reminder"             # Remind about something
    CHECK_IN = "check_in"             # General check-in
    NOTIFICATION = "notification"     # Send information
    ESCALATION = "escalation"         # Escalate to human

class TaskStatus(str, Enum):
    SCHEDULED = "scheduled"   # Waiting to execute
    EXECUTING = "executing"   # Currently running
    COMPLETED = "completed"   # Successfully executed
    FAILED = "failed"         # Execution failed
    CANCELLED = "cancelled"   # Explicitly cancelled

class AgendaTask(BaseModel):
    """
    Scheduled proactive outreach task.

    Tasks are executed by Hatchet workflows at the scheduled time.
    """

    id: UUID = Field(default_factory=uuid4)

    # Scoping
    tenant_id: UUID
    agent_id: UUID
    customer_id: UUID
    session_id: UUID | None = None  # May create new session

    # Task definition
    task_type: TaskType
    description: str

    # Scheduling
    scheduled_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: datetime | None = None

    # Status
    status: TaskStatus = TaskStatus.SCHEDULED
    failure_reason: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    # Linked goal (if this is a follow-up)
    goal_id: UUID | None = None

    # Context for execution
    context: dict = Field(default_factory=dict)
    # e.g., {"original_topic": "refund request", "customer_name": "John"}

    # Channel preference
    preferred_channel: str | None = None  # Use customer's preferred if None

    # Template for outbound message
    message_template: str | None = None
    # e.g., "Hi {customer_name}, following up on your {original_topic}..."

    def is_due(self, now: datetime) -> bool:
        return (
            self.status == TaskStatus.SCHEDULED
            and now >= self.scheduled_at
        )

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries
```

---

## Goal Creation (P8 Integration)

Goals are created during response planning:

```python
class ResponsePlanner:
    """Creates response plans with optional goals."""

    async def create_plan(
        self,
        turn: LogicalTurn,
        context: TurnContext,
    ) -> ResponsePlan:
        # ... existing planning logic ...

        plan = ResponsePlan(
            segments=segments,
            tools_to_execute=tools,
        )

        # Detect if we should create a goal
        goal = await self._detect_goal_opportunity(plan, context)
        if goal:
            plan.attached_goal = goal

            # Optionally schedule follow-up
            if self._should_schedule_follow_up(goal, context):
                task = self._create_follow_up_task(goal, context)
                plan.attached_agenda_task = task

        return plan

    async def _detect_goal_opportunity(
        self,
        plan: ResponsePlan,
        context: TurnContext,
    ) -> Goal | None:
        """Detect if this response warrants a goal."""

        # Asked a question → expect answer
        if plan.asks_question:
            return Goal(
                tenant_id=context.tenant_id,
                agent_id=context.agent_id,
                customer_id=context.customer_id,
                session_id=context.session_id,
                beat_id=context.turn.id,
                goal_type=GoalType.RESPONSE_EXPECTED,
                description=f"Response to: {plan.question_summary}",
                deadline=datetime.utcnow() + timedelta(hours=24),
                context_snapshot={"question": plan.question_summary},
            )

        # Offered something → expect decision
        if plan.makes_offer:
            return Goal(
                goal_type=GoalType.ACTION_EXPECTED,
                description=f"Decision on: {plan.offer_summary}",
                deadline=datetime.utcnow() + timedelta(hours=48),
                # ...
            )

        return None

    def _create_follow_up_task(
        self,
        goal: Goal,
        context: TurnContext,
    ) -> AgendaTask:
        """Create follow-up task for a goal."""
        return AgendaTask(
            tenant_id=goal.tenant_id,
            agent_id=goal.agent_id,
            customer_id=goal.customer_id,
            session_id=goal.session_id,
            task_type=TaskType.FOLLOW_UP,
            description=f"Follow up on: {goal.description}",
            scheduled_at=goal.deadline,  # Follow up when goal expires
            goal_id=goal.id,
            context={
                "goal_description": goal.description,
                "original_beat_id": str(goal.beat_id),
            },
        )
```

---

## Goal Achievement Detection

Check if incoming messages achieve pending goals:

```python
class GoalChecker:
    """Checks if incoming turns achieve pending goals."""

    def __init__(self, goal_store: GoalStore):
        self._store = goal_store

    async def check_goals(
        self,
        turn: LogicalTurn,
        context: TurnContext,
    ) -> list[Goal]:
        """
        Check if this turn achieves any pending goals.

        Called early in brain (P2 or P3).
        """
        # Get pending goals for this customer/session
        pending_goals = await self._store.get_pending_goals(
            tenant_id=context.tenant_id,
            customer_id=context.customer_id,
            session_id=context.session_id,
        )

        achieved = []
        for goal in pending_goals:
            if await self._check_achievement(goal, turn, context):
                goal.mark_achieved(achieving_beat_id=turn.id)
                await self._store.save(goal)

                # Cancel associated follow-up task
                if goal.follow_up_task_id:
                    await self._cancel_follow_up(goal.follow_up_task_id)

                achieved.append(goal)

        return achieved

    async def _check_achievement(
        self,
        goal: Goal,
        turn: LogicalTurn,
        context: TurnContext,
    ) -> bool:
        """Determine if turn achieves goal."""

        # Simple: any response achieves RESPONSE_EXPECTED
        if goal.goal_type == GoalType.RESPONSE_EXPECTED:
            return True

        # Pattern matching for specific expected responses
        if goal.expected_response_pattern:
            combined_text = " ".join(
                msg.content for msg in context.messages
            )
            if re.search(goal.expected_response_pattern, combined_text, re.I):
                return True

        # Semantic matching (optional, more sophisticated)
        # Could use embeddings to check if response is relevant to goal

        return False
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

        # Check if goal was achieved (no need to follow up)
        if task.goal_id:
            goal_store = ctx.services.goal_store
            goal = await goal_store.get(task.goal_id)
            if goal and goal.status == GoalStatus.ACHIEVED:
                task.status = TaskStatus.CANCELLED
                await task_store.save(task)
                return {"status": "goal_achieved", "skip": True}

        task.status = TaskStatus.EXECUTING
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
        task = AgendaTask(**task_data)

        # Load customer context
        customer_store = ctx.services.customer_store
        customer = await customer_store.get(task.customer_id)

        # Generate message using template or LLM
        if task.message_template:
            message = task.message_template.format(
                customer_name=customer.name,
                **task.context,
            )
        else:
            # Use LLM to generate contextual follow-up
            message = await ctx.services.llm.generate(
                prompt=f"""Generate a friendly follow-up message.
                Context: {task.context}
                Customer: {customer.name}
                Task type: {task.task_type}
                Keep it brief and natural.""",
            )

        return {
            "skip": False,
            "message": message,
            "channel": task.preferred_channel or customer.preferred_channel,
        }

    @hatchet.step()
    async def send_message(self, ctx: Context) -> dict:
        """Send the follow-up message."""
        if ctx.step_output("generate_message").get("skip"):
            return {"status": "skipped"}

        task_data = ctx.step_output("load_context")["task"]
        task = AgendaTask(**task_data)
        message = ctx.step_output("generate_message")["message"]
        channel = ctx.step_output("generate_message")["channel"]

        try:
            # Send via channel adapter
            channel_adapter = ctx.services.channel_adapter
            await channel_adapter.send_outbound(
                customer_id=task.customer_id,
                channel=channel,
                message=message,
                context={"agenda_task_id": str(task.id)},
            )

            # Update task status
            task.status = TaskStatus.COMPLETED
            task.executed_at = datetime.utcnow()
            await ctx.services.agenda_store.save(task)

            # Create audit record
            await ctx.services.audit_store.record_outbound(
                task_id=task.id,
                customer_id=task.customer_id,
                channel=channel,
                message=message,
            )

            return {"status": "sent", "channel": channel}

        except ChannelError as e:
            task.status = TaskStatus.FAILED
            task.failure_reason = str(e)
            task.retry_count += 1

            if task.can_retry():
                task.status = TaskStatus.SCHEDULED
                task.scheduled_at = datetime.utcnow() + timedelta(hours=1)

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

### GoalStore

```python
class GoalStore(ABC):
    """Interface for goal persistence."""

    @abstractmethod
    async def save(self, goal: Goal) -> None: ...

    @abstractmethod
    async def get(self, goal_id: UUID) -> Goal | None: ...

    @abstractmethod
    async def get_pending_goals(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        session_id: UUID | None = None,
    ) -> list[Goal]: ...

    @abstractmethod
    async def get_expired_goals(
        self,
        before: datetime,
        limit: int = 100,
    ) -> list[Goal]: ...
```

### AgendaStore

```python
class AgendaStore(ABC):
    """Interface for agenda task persistence."""

    @abstractmethod
    async def save(self, task: AgendaTask) -> None: ...

    @abstractmethod
    async def get_task(self, task_id: UUID) -> AgendaTask | None: ...

    @abstractmethod
    async def get_due_tasks(
        self,
        before: datetime,
        limit: int = 100,
    ) -> list[AgendaTask]: ...

    @abstractmethod
    async def get_customer_tasks(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        status: TaskStatus | None = None,
    ) -> list[AgendaTask]: ...
```

---

## Configuration

```toml
[agenda]
enabled = true

# Goal defaults
default_goal_timeout_hours = 24
max_goals_per_session = 10

# Task execution
max_retries = 3
retry_delay_hours = 1

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
# Goals
goals_created = Counter("goals_created_total", "Goals created", ["goal_type"])
goals_achieved = Counter("goals_achieved_total", "Goals achieved", ["goal_type"])
goals_expired = Counter("goals_expired_total", "Goals expired", ["goal_type"])

goal_achievement_time = Histogram(
    "goal_achievement_duration_hours",
    "Time to achieve goals",
    buckets=[1, 4, 12, 24, 48, 72],
)

# Tasks
tasks_scheduled = Counter("agenda_tasks_scheduled_total", "Tasks scheduled", ["task_type"])
tasks_executed = Counter("agenda_tasks_executed_total", "Tasks executed", ["task_type", "status"])

task_execution_delay = Histogram(
    "agenda_task_execution_delay_seconds",
    "Delay between scheduled and actual execution",
    buckets=[0, 60, 300, 600, 3600],
)
```

### Logging

```python
logger.info(
    "goal_created",
    goal_id=str(goal.id),
    goal_type=goal.goal_type.value,
    beat_id=str(goal.beat_id),
    deadline=goal.deadline.isoformat(),
)

logger.info(
    "agenda_task_executed",
    task_id=str(task.id),
    task_type=task.task_type.value,
    status=result_status,
    delay_seconds=delay,
)
```

---

## Testing

```python
# Test: Goal created on question
async def test_goal_created_on_question():
    plan = await planner.create_plan(turn, context)

    # Plan asks "What's your order number?"
    assert plan.attached_goal is not None
    assert plan.attached_goal.goal_type == GoalType.RESPONSE_EXPECTED

# Test: Goal achieved on response
async def test_goal_achieved_on_response():
    # Create pending goal
    goal = Goal(goal_type=GoalType.RESPONSE_EXPECTED, ...)
    await goal_store.save(goal)

    # Customer responds
    achieved = await goal_checker.check_goals(turn, context)

    assert len(achieved) == 1
    assert achieved[0].status == GoalStatus.ACHIEVED

# Test: Follow-up cancelled when goal achieved
async def test_follow_up_cancelled_on_achievement():
    # Goal with follow-up task
    goal = Goal(..., follow_up_task_id=task.id)
    task = AgendaTask(status=TaskStatus.SCHEDULED, ...)

    # Achieve goal
    goal.mark_achieved(turn.id)
    await goal_checker._cancel_follow_up(task.id)

    updated_task = await agenda_store.get_task(task.id)
    assert updated_task.status == TaskStatus.CANCELLED
```

---

## Related Topics

- [01-logical-turn.md](01-logical-turn.md) - Goals scoped to beats
- [06-hatchet-integration.md](06-hatchet-integration.md) - Workflow execution
- [08-config-hierarchy.md](08-config-hierarchy.md) - Feature enablement
- [10-channel-capabilities.md](10-channel-capabilities.md) - Outbound channel selection
