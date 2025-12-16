"""In-memory implementation of TaskStore."""

from datetime import UTC, datetime
from uuid import UUID

from ruche.domain.agenda import Task, TaskStatus
from ruche.runtime.agenda.store import TaskStore


class InMemoryTaskStore(TaskStore):
    """In-memory implementation of TaskStore for testing and development.

    Uses simple dict storage with linear scan for queries.
    Not suitable for production use.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._tasks: dict[UUID, Task] = {}

    async def save(self, task: Task) -> None:
        """Save or update a task."""
        self._tasks[task.id] = task

    async def get(self, task_id: UUID) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_due_tasks(
        self,
        before: datetime,
        limit: int = 100,
    ) -> list[Task]:
        """Get tasks that are due for execution."""
        now = datetime.now(UTC)
        results = []

        for task in self._tasks.values():
            # Only scheduled tasks
            if task.status != TaskStatus.SCHEDULED:
                continue

            # Check if expired
            if task.is_expired:
                continue

            # Check scheduled_for
            if task.scheduled_for > before:
                continue

            # Check execute_after if set
            if task.execute_after and task.execute_after > before:
                continue

            results.append(task)

        # Sort by scheduled_for ascending (oldest first)
        results.sort(key=lambda t: t.scheduled_for)
        return results[:limit]

    async def get_interlocutor_tasks(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """Get all tasks for an interlocutor."""
        results = []

        for task in self._tasks.values():
            if task.tenant_id != tenant_id:
                continue
            if task.interlocutor_id != interlocutor_id:
                continue
            if status is not None and task.status != status:
                continue

            results.append(task)

        # Sort by scheduled_for descending (newest first)
        results.sort(key=lambda t: t.scheduled_for, reverse=True)
        return results

    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        **fields: dict,
    ) -> None:
        """Update task status and optional fields."""
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = status
        for key, value in fields.items():
            if hasattr(task, key):
                setattr(task, key, value)

        self._tasks[task_id] = task
