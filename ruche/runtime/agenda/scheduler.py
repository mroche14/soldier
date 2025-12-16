"""Agenda scheduler for proactive task execution.

The scheduler:
1. Polls for due tasks
2. Acquires task locks (distributed)
3. Executes tasks via TaskWorkflow
4. Updates task status
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from ruche.domain.agenda import Task, TaskStatus
from ruche.observability.logging import get_logger

if TYPE_CHECKING:
    from ruche.runtime.agenda.store import TaskStore
    from ruche.runtime.agenda.workflow import TaskWorkflow

logger = get_logger(__name__)


class AgendaScheduler:
    """Scheduler for proactive agent tasks.

    Manages execution of scheduled tasks that bypass ACF:
    - Follow-ups and reminders
    - Proactive outreach
    - Maintenance tasks

    Key difference from ACF turns:
    - No session mutex needed (agent-initiated)
    - No message accumulation
    - Direct pipeline execution
    """

    def __init__(
        self,
        task_store: "TaskStore",
        task_workflow: "TaskWorkflow",
        poll_interval_seconds: int = 60,
        max_tasks_per_batch: int = 100,
    ):
        """Initialize scheduler.

        Args:
            task_store: Task persistence store
            task_workflow: Workflow executor for tasks
            poll_interval_seconds: How often to check for due tasks
            max_tasks_per_batch: Maximum tasks to process per poll
        """
        self._task_store = task_store
        self._task_workflow = task_workflow
        self._poll_interval_seconds = poll_interval_seconds
        self._max_tasks_per_batch = max_tasks_per_batch
        self._running = False
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the scheduler loop.

        Launches background task that polls for due tasks and executes them.
        """
        if self._running:
            logger.warning("scheduler_already_running")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())

        logger.info(
            "scheduler_started",
            poll_interval_seconds=self._poll_interval_seconds,
            max_tasks_per_batch=self._max_tasks_per_batch,
        )

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        if not self._running:
            return

        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        logger.info("scheduler_stopped")

    async def schedule_task(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        task: Task,
    ) -> UUID:
        """Schedule a task for execution.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            task: Task to schedule

        Returns:
            Task ID
        """
        await self._task_store.save(task)

        logger.info(
            "task_scheduled",
            task_id=str(task.id),
            task_type=task.task_type.value,
            priority=task.priority.value,
            scheduled_for=task.scheduled_for.isoformat(),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        return task.id

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False if already running/completed
        """
        task = await self._task_store.get(task_id)
        if not task:
            logger.warning("cancel_task_not_found", task_id=str(task_id))
            return False

        if task.status != TaskStatus.SCHEDULED:
            logger.warning(
                "cancel_task_wrong_status",
                task_id=str(task_id),
                status=task.status.value,
            )
            return False

        await self._task_store.update_status(task_id, TaskStatus.CANCELLED)

        logger.info(
            "task_cancelled",
            task_id=str(task_id),
            task_type=task.task_type.value,
        )

        return True

    async def _poll_loop(self) -> None:
        """Background polling loop for due tasks."""
        while self._running:
            try:
                await self._process_due_tasks()
            except Exception as e:
                logger.error("poll_loop_error", error=str(e))

            await asyncio.sleep(self._poll_interval_seconds)

    async def _process_due_tasks(self) -> None:
        """Find and execute due tasks."""
        now = datetime.now(UTC)
        due_tasks = await self._task_store.get_due_tasks(
            before=now,
            limit=self._max_tasks_per_batch,
        )

        if not due_tasks:
            return

        logger.info(
            "processing_due_tasks",
            count=len(due_tasks),
        )

        for task in due_tasks:
            if not self._running:
                break

            try:
                await self._execute_task(task)
            except Exception as e:
                logger.error(
                    "task_execution_failed",
                    task_id=str(task.id),
                    error=str(e),
                )

    async def _execute_task(self, task: Task) -> None:
        """Execute a scheduled task.

        Args:
            task: Task to execute
        """
        logger.info(
            "task_execution_started",
            task_id=str(task.id),
            task_type=task.task_type.value,
        )

        execution_start = datetime.now(UTC)

        try:
            result = await self._task_workflow.execute(task)

            execution_duration = (datetime.now(UTC) - execution_start).total_seconds()

            logger.info(
                "task_executed",
                task_id=str(task.id),
                task_type=task.task_type.value,
                status=result.get("status", "unknown"),
                duration_seconds=execution_duration,
            )

        except Exception as e:
            logger.error(
                "task_execution_error",
                task_id=str(task.id),
                task_type=task.task_type.value,
                error=str(e),
            )

            task.attempts += 1
            task.last_error = str(e)

            if task.can_retry:
                task.status = TaskStatus.SCHEDULED
                task.scheduled_for = datetime.now(UTC) + timedelta(hours=1)

                logger.info(
                    "task_retry_scheduled",
                    task_id=str(task.id),
                    attempt=task.attempts,
                    next_attempt=task.scheduled_for.isoformat(),
                )
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(UTC)

                logger.error(
                    "task_failed_max_attempts",
                    task_id=str(task.id),
                    attempts=task.attempts,
                )

            await self._task_store.save(task)
