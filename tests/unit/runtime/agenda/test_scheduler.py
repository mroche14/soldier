"""Tests for AgendaScheduler."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ruche.domain.agenda import Task, TaskPriority, TaskStatus, TaskType
from ruche.runtime.agenda.scheduler import AgendaScheduler
from ruche.runtime.agenda.stores.inmemory import InMemoryTaskStore


class MockTaskWorkflow:
    """Mock TaskWorkflow for testing."""

    def __init__(self):
        self.executed_tasks = []

    async def execute(self, task: Task) -> dict:
        """Mock execute."""
        self.executed_tasks.append(task)
        return {"status": "complete", "task_type": task.task_type.value}


@pytest.fixture
def task_store():
    """Create in-memory task store."""
    return InMemoryTaskStore()


@pytest.fixture
def task_workflow():
    """Create mock task workflow."""
    return MockTaskWorkflow()


@pytest.fixture
def scheduler(task_store, task_workflow):
    """Create scheduler."""
    return AgendaScheduler(
        task_store=task_store,
        task_workflow=task_workflow,
        poll_interval_seconds=1,
        max_tasks_per_batch=10,
    )


@pytest.mark.asyncio
class TestAgendaScheduler:
    """Test suite for AgendaScheduler."""

    async def test_schedule_task(self, scheduler, task_store):
        """Test scheduling a task."""
        tenant_id = uuid4()
        agent_id = uuid4()

        task = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_type=TaskType.FOLLOW_UP,
            priority=TaskPriority.NORMAL,
            scheduled_for=datetime.now(UTC) + timedelta(hours=1),
        )

        task_id = await scheduler.schedule_task(tenant_id, agent_id, task)

        assert task_id == task.id

        saved_task = await task_store.get(task_id)
        assert saved_task is not None
        assert saved_task.status == TaskStatus.SCHEDULED
        assert saved_task.task_type == TaskType.FOLLOW_UP

    async def test_cancel_task(self, scheduler, task_store):
        """Test canceling a scheduled task."""
        tenant_id = uuid4()
        agent_id = uuid4()

        task = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_type=TaskType.REMINDER,
            scheduled_for=datetime.now(UTC) + timedelta(hours=1),
        )

        task_id = await scheduler.schedule_task(tenant_id, agent_id, task)

        cancelled = await scheduler.cancel_task(task_id)
        assert cancelled is True

        updated_task = await task_store.get(task_id)
        assert updated_task.status == TaskStatus.CANCELLED

    async def test_cancel_nonexistent_task(self, scheduler):
        """Test canceling a task that doesn't exist."""
        cancelled = await scheduler.cancel_task(uuid4())
        assert cancelled is False

    async def test_cancel_running_task(self, scheduler, task_store):
        """Test canceling a task that's already running."""
        tenant_id = uuid4()
        agent_id = uuid4()

        task = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_type=TaskType.REMINDER,
            scheduled_for=datetime.now(UTC),
            status=TaskStatus.RUNNING,
        )

        await task_store.save(task)

        cancelled = await scheduler.cancel_task(task.id)
        assert cancelled is False

    async def test_process_due_tasks(self, scheduler, task_store, task_workflow):
        """Test processing due tasks."""
        tenant_id = uuid4()
        agent_id = uuid4()

        task1 = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=datetime.now(UTC) - timedelta(minutes=5),
        )

        task2 = Task(
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_type=TaskType.REMINDER,
            scheduled_for=datetime.now(UTC) + timedelta(hours=1),
        )

        await task_store.save(task1)
        await task_store.save(task2)

        scheduler._running = True

        try:
            await scheduler._process_due_tasks()
        except Exception as e:
            pytest.fail(f"_process_due_tasks raised exception: {e}")

        assert len(task_workflow.executed_tasks) == 1, (
            f"Expected 1 task executed, got {len(task_workflow.executed_tasks)}. "
            f"Task store has {len(await task_store.get_due_tasks(datetime.now(UTC), 10))} due tasks."
        )
        assert task_workflow.executed_tasks[0].id == task1.id

    async def test_scheduler_lifecycle(self, scheduler):
        """Test starting and stopping scheduler."""
        await scheduler.start()
        assert scheduler._running is True

        await asyncio.sleep(0.1)

        await scheduler.stop()
        assert scheduler._running is False
