"""Task workflow for agenda-driven execution.

TaskWorkflow executes scheduled tasks directly, bypassing ACF since
these are agent-initiated actions, not customer responses.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ruche.domain.agenda import Task, TaskStatus, TaskType
from ruche.observability.logging import get_logger
from ruche.runtime.agenda.store import TaskStore
from ruche.runtime.agent.runtime import AgentRuntime

logger = get_logger(__name__)


class TaskWorkflow:
    """Workflow for executing scheduled tasks.

    Unlike LogicalTurnWorkflow (which uses ACF for customer messages),
    TaskWorkflow executes agent-initiated tasks directly:
    - No session mutex (agent-initiated)
    - No message accumulation
    - Direct pipeline execution with task context

    Example tasks:
    - Follow-up on previous conversation
    - Send reminder about pending action
    - Proactive notification
    """

    def __init__(
        self,
        task_store: TaskStore,
        agent_runtime: AgentRuntime,
    ):
        """Initialize task workflow.

        Args:
            task_store: Task persistence store
            agent_runtime: Agent runtime for Brain execution
        """
        self._task_store = task_store
        self._agent_runtime = agent_runtime

    async def execute(self, task: Task) -> dict[str, Any]:
        """Execute a scheduled task.

        Args:
            task: Task to execute

        Returns:
            Execution result

        Raises:
            TaskExecutionError: If execution fails
        """
        logger.info(
            "task_workflow_started",
            task_id=str(task.id),
            task_type=task.task_type.value,
            tenant_id=str(task.tenant_id),
            agent_id=str(task.agent_id),
        )

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(UTC)
        await self._task_store.save(task)

        try:
            result = await self._execute_task_type(task)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(UTC)
            await self._task_store.save(task)

            logger.info(
                "task_workflow_completed",
                task_id=str(task.id),
                task_type=task.task_type.value,
            )

            return result

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.last_error = str(e)
            task.attempts += 1
            await self._task_store.save(task)

            logger.error(
                "task_workflow_failed",
                task_id=str(task.id),
                task_type=task.task_type.value,
                error=str(e),
            )

            raise

    async def _execute_task_type(self, task: Task) -> dict[str, Any]:
        """Route task execution based on task type.

        Args:
            task: Task to execute

        Returns:
            Task-specific result
        """
        if task.task_type in (
            TaskType.FOLLOW_UP,
            TaskType.REMINDER,
            TaskType.NOTIFICATION,
        ):
            return await self._execute_proactive_message(task)
        elif task.task_type == TaskType.CLEANUP:
            return await self._execute_cleanup(task)
        elif task.task_type == TaskType.SYNC:
            return await self._execute_sync(task)
        elif task.task_type == TaskType.CUSTOM:
            return await self._execute_custom(task)
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")

    async def _execute_proactive_message(self, task: Task) -> dict[str, Any]:
        """Execute a proactive message task (follow-up, reminder, notification).

        Args:
            task: Task to execute

        Returns:
            Execution result with generated message
        """
        logger.info(
            "executing_proactive_message",
            task_id=str(task.id),
            task_type=task.task_type.value,
        )

        agent_ctx = await self._agent_runtime.get_or_create(
            task.tenant_id,
            task.agent_id,
        )

        prompt = self._build_proactive_prompt(task)

        from ruche.runtime.acf.models import FabricTurnContextImpl, LogicalTurn
        from ruche.runtime.agent.context import AgentTurnContext

        logical_turn = LogicalTurn(
            id=task.id,
            session_key=f"agenda:{task.id}",
            messages=[],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
        )

        fabric_ctx = FabricTurnContextImpl(
            logical_turn=logical_turn,
            session_key=logical_turn.session_key,
            channel="system",
            _check_pending=lambda: False,
            _route_event=self._route_event,
        )

        turn_ctx = AgentTurnContext(
            fabric=fabric_ctx,
            agent_context=agent_ctx,
        )

        result = await agent_ctx.brain.think(turn_ctx)

        logger.info(
            "proactive_message_generated",
            task_id=str(task.id),
            response_length=len(result.response),
        )

        return {
            "status": "complete",
            "task_type": task.task_type.value,
            "response": result.response,
            "message": result.response,
        }

    def _build_proactive_prompt(self, task: Task) -> str:
        """Build prompt for proactive message generation.

        Args:
            task: Task context

        Returns:
            Prompt string
        """
        if task.task_type == TaskType.FOLLOW_UP:
            context = task.payload.get("context", "our previous conversation")
            return (
                f"Generate a friendly follow-up message about {context}. "
                "Keep it brief and natural."
            )
        elif task.task_type == TaskType.REMINDER:
            reminder_text = task.payload.get("reminder_text", "pending action")
            return (
                f"Generate a gentle reminder about: {reminder_text}. "
                "Be polite and helpful."
            )
        elif task.task_type == TaskType.NOTIFICATION:
            notification_text = task.payload.get("notification_text", "an event")
            return (
                f"Notify the customer about: {notification_text}. "
                "Be clear and informative."
            )
        else:
            return "Generate a proactive message based on the task context."

    async def _execute_cleanup(self, task: Task) -> dict[str, Any]:
        """Execute a cleanup task.

        Args:
            task: Cleanup task

        Returns:
            Cleanup result
        """
        logger.info(
            "executing_cleanup",
            task_id=str(task.id),
        )

        return {
            "status": "complete",
            "task_type": "cleanup",
            "message": "Cleanup task completed (stub)",
        }

    async def _execute_sync(self, task: Task) -> dict[str, Any]:
        """Execute a sync task.

        Args:
            task: Sync task

        Returns:
            Sync result
        """
        logger.info(
            "executing_sync",
            task_id=str(task.id),
        )

        return {
            "status": "complete",
            "task_type": "sync",
            "message": "Sync task completed (stub)",
        }

    async def _execute_custom(self, task: Task) -> dict[str, Any]:
        """Execute a custom task.

        Args:
            task: Custom task

        Returns:
            Custom task result
        """
        logger.info(
            "executing_custom",
            task_id=str(task.id),
        )

        return {
            "status": "complete",
            "task_type": "custom",
            "message": "Custom task completed (stub)",
        }

    async def _route_event(self, event: Any) -> None:
        """Route ACF events from Brain.

        Args:
            event: ACFEvent to route
        """
        from ruche.runtime.acf.events import ACFEvent

        if not isinstance(event, ACFEvent):
            logger.warning(
                "invalid_event_type",
                event_type=type(event).__name__,
            )
            return

        logger.info(
            "agenda_event_emitted",
            event_type=event.type,
            task_id=str(event.logical_turn_id) if event.logical_turn_id else None,
        )
