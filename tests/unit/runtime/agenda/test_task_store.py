"""Tests for TaskStore implementations."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ruche.domain.agenda import Task, TaskPriority, TaskStatus, TaskType
from ruche.runtime.agenda.stores.inmemory import InMemoryTaskStore


@pytest.fixture
def task_store():
    """Create in-memory task store."""
    return InMemoryTaskStore()


@pytest.mark.asyncio
class TestInMemoryTaskStore:
    """Test suite for InMemoryTaskStore."""

    async def test_save_and_get_task(self, task_store):
        """Test saving and retrieving a task."""
        task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=datetime.now(UTC) + timedelta(hours=1),
        )

        await task_store.save(task)

        retrieved = await task_store.get(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.task_type == TaskType.FOLLOW_UP

    async def test_get_nonexistent_task(self, task_store):
        """Test getting a task that doesn't exist."""
        result = await task_store.get(uuid4())
        assert result is None

    async def test_get_due_tasks(self, task_store):
        """Test getting due tasks."""
        now = datetime.now(UTC)

        task1 = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=now - timedelta(hours=1),
        )

        task2 = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.REMINDER,
            scheduled_for=now + timedelta(hours=1),
        )

        task3 = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.NOTIFICATION,
            scheduled_for=now - timedelta(minutes=30),
        )

        await task_store.save(task1)
        await task_store.save(task2)
        await task_store.save(task3)

        due_tasks = await task_store.get_due_tasks(before=now, limit=10)

        assert len(due_tasks) == 2
        assert task1.id in [t.id for t in due_tasks]
        assert task3.id in [t.id for t in due_tasks]
        assert task2.id not in [t.id for t in due_tasks]

    async def test_get_due_tasks_excludes_expired(self, task_store):
        """Test that expired tasks are excluded."""
        now = datetime.now(UTC)

        expired_task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
        )

        await task_store.save(expired_task)

        due_tasks = await task_store.get_due_tasks(before=now, limit=10)

        assert len(due_tasks) == 0

    async def test_get_due_tasks_respects_execute_after(self, task_store):
        """Test that execute_after is respected."""
        now = datetime.now(UTC)

        task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=now - timedelta(hours=1),
            execute_after=now + timedelta(hours=1),
        )

        await task_store.save(task)

        due_tasks = await task_store.get_due_tasks(before=now, limit=10)

        assert len(due_tasks) == 0

    async def test_get_due_tasks_only_scheduled(self, task_store):
        """Test that only scheduled tasks are returned."""
        now = datetime.now(UTC)

        scheduled_task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=now - timedelta(hours=1),
            status=TaskStatus.SCHEDULED,
        )

        running_task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.REMINDER,
            scheduled_for=now - timedelta(hours=1),
            status=TaskStatus.RUNNING,
        )

        await task_store.save(scheduled_task)
        await task_store.save(running_task)

        due_tasks = await task_store.get_due_tasks(before=now, limit=10)

        assert len(due_tasks) == 1
        assert due_tasks[0].id == scheduled_task.id

    async def test_get_interlocutor_tasks(self, task_store):
        """Test getting tasks for an interlocutor."""
        tenant_id = uuid4()
        interlocutor_id = uuid4()

        task1 = Task(
            tenant_id=tenant_id,
            agent_id=uuid4(),
            interlocutor_id=interlocutor_id,
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=datetime.now(UTC),
        )

        task2 = Task(
            tenant_id=tenant_id,
            agent_id=uuid4(),
            interlocutor_id=interlocutor_id,
            task_type=TaskType.REMINDER,
            scheduled_for=datetime.now(UTC),
        )

        other_task = Task(
            tenant_id=tenant_id,
            agent_id=uuid4(),
            interlocutor_id=uuid4(),
            task_type=TaskType.NOTIFICATION,
            scheduled_for=datetime.now(UTC),
        )

        await task_store.save(task1)
        await task_store.save(task2)
        await task_store.save(other_task)

        tasks = await task_store.get_interlocutor_tasks(tenant_id, interlocutor_id)

        assert len(tasks) == 2
        assert task1.id in [t.id for t in tasks]
        assert task2.id in [t.id for t in tasks]

    async def test_update_status(self, task_store):
        """Test updating task status."""
        task = Task(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            task_type=TaskType.FOLLOW_UP,
            scheduled_for=datetime.now(UTC),
        )

        await task_store.save(task)

        await task_store.update_status(
            task.id,
            TaskStatus.COMPLETED,
            completed_at=datetime.now(UTC),
        )

        updated = await task_store.get(task.id)
        assert updated.status == TaskStatus.COMPLETED
        assert updated.completed_at is not None
