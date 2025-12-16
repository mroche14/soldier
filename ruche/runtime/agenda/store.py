"""TaskStore abstract interface for agenda persistence."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ruche.domain.agenda import Task, TaskStatus


class TaskStore(ABC):
    """Abstract interface for task storage.

    Manages scheduled tasks with support for due-task queries
    and status-based filtering.
    """

    @abstractmethod
    async def save(self, task: Task) -> None:
        """Save or update a task.

        Args:
            task: Task to persist
        """
        pass

    @abstractmethod
    async def get(self, task_id: UUID) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_due_tasks(
        self,
        before: datetime,
        limit: int = 100,
    ) -> list[Task]:
        """Get tasks that are due for execution.

        Filters for:
        - status = SCHEDULED
        - scheduled_for <= before
        - execute_after <= before (if set)
        - not expired

        Args:
            before: Time threshold for due tasks
            limit: Maximum tasks to return

        Returns:
            List of due tasks ordered by scheduled_for ascending
        """
        pass

    @abstractmethod
    async def get_interlocutor_tasks(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """Get all tasks for an interlocutor.

        Args:
            tenant_id: Tenant identifier
            interlocutor_id: Interlocutor identifier
            status: Optional status filter

        Returns:
            List of tasks for the interlocutor
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        **fields: dict,
    ) -> None:
        """Update task status and optional fields.

        Args:
            task_id: Task identifier
            status: New status
            fields: Additional fields to update (started_at, completed_at, etc.)
        """
        pass
