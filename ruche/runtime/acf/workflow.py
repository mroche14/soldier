"""Hatchet workflow integration for LogicalTurn processing.

This module IS the Agent Conversation Fabric. It orchestrates:
- Session mutex (single-writer rule)
- Message accumulation (turn boundaries)
- Agent invocation (Brain execution)
- Commit and response (persistence)
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID, uuid4

from redis.asyncio import Redis

from ruche.observability.logging import get_logger
from ruche.runtime.acf.models import LogicalTurn, LogicalTurnStatus
from ruche.runtime.acf.mutex import SessionMutex, build_session_key
from ruche.runtime.acf.turn_manager import TurnManager

logger = get_logger(__name__)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


@dataclass
class WorkflowInput:
    """Input for LogicalTurnWorkflow."""

    tenant_id: str
    agent_id: str
    interlocutor_id: str
    channel: str
    message_id: str
    message_content: str
    session_key: str | None = None  # Computed if not provided

    def get_session_key(self) -> str:
        """Get or compute session key."""
        if self.session_key:
            return self.session_key
        return build_session_key(
            self.tenant_id,
            self.agent_id,
            self.interlocutor_id,
            self.channel,
        )


@dataclass
class WorkflowOutput:
    """Output from LogicalTurnWorkflow."""

    turn_id: str
    status: str  # "complete", "superseded", "failed"
    response: str | None = None
    error: str | None = None
    message_count: int = 0


class LogicalTurnWorkflow:
    """Hatchet workflow for processing a LogicalTurn.

    This workflow IS the Agent Conversation Fabric. It manages:
    - Session mutex for single-writer rule
    - Message accumulation for turn boundaries
    - Agent/Brain invocation for processing
    - Commit and response for persistence

    Workflow steps:
    1. acquire_mutex - Get session lock (held across all steps)
    2. accumulate - Wait for message completion
    3. run_agent - Execute Agent's Brain
    4. commit_and_respond - Persist state, send response
    5. release_mutex - Release session lock (in commit or on_failure)
    """

    WORKFLOW_NAME = "logical-turn"

    def __init__(
        self,
        redis: Redis,
        alignment_engine: Any,
        session_store: Any,
        message_store: Any,
        audit_store: Any,
        turn_manager: TurnManager | None = None,
        mutex_timeout: int = 300,
        mutex_blocking_timeout: float = 10.0,
    ) -> None:
        """Initialize workflow.

        Args:
            redis: Redis client for mutex and state
            alignment_engine: AlignmentEngine for Brain execution
            session_store: Session state persistence
            message_store: Message retrieval
            audit_store: Turn record persistence
            turn_manager: Adaptive accumulation manager
            mutex_timeout: How long lock is held before auto-release
            mutex_blocking_timeout: How long to wait for lock acquisition
        """
        self._redis = redis
        self._alignment_engine = alignment_engine
        self._session_store = session_store
        self._message_store = message_store
        self._audit_store = audit_store
        self._turn_manager = turn_manager or TurnManager()
        self._mutex = SessionMutex(
            redis=redis,
            lock_timeout=mutex_timeout,
            blocking_timeout=mutex_blocking_timeout,
        )

    async def acquire_mutex(self, session_key: str) -> dict[str, Any]:
        """Step 1: Acquire exclusive session lock.

        IMPORTANT: Do NOT use context manager - lock must persist across steps.
        Lock is released explicitly in commit_and_respond or on_failure.

        Args:
            session_key: Composite session identifier

        Returns:
            Step result with lock status
        """
        lock_key = await self._mutex.acquire_direct(session_key)

        if lock_key is None:
            logger.warning(
                "mutex_acquisition_failed",
                session_key=session_key,
            )
            return {
                "status": "lock_failed",
                "session_key": session_key,
                "retry": True,
            }

        logger.info(
            "mutex_acquired",
            session_key=session_key,
            lock_key=lock_key,
        )

        return {
            "status": "locked",
            "session_key": session_key,
            "lock_key": lock_key,
            "locked_at": utc_now().isoformat(),
        }

    async def accumulate(
        self,
        turn_id: UUID,
        session_key: str,
        initial_message_id: str,
        initial_content: str,
        channel: str,
        wait_for_event: Callable[[int], Any] | None = None,
    ) -> dict[str, Any]:
        """Step 2: Accumulate messages until turn is complete.

        This step waits for additional messages and absorbs them
        into the current turn based on adaptive timing.

        Args:
            turn_id: Logical turn identifier
            session_key: Session identifier
            initial_message_id: First message ID
            initial_content: First message content
            channel: Communication channel
            wait_for_event: Callback to wait for new message events

        Returns:
            Step result with accumulated turn
        """
        now = utc_now()

        # Create initial turn
        turn = LogicalTurn(
            id=turn_id,
            session_key=session_key,
            messages=[UUID(initial_message_id)],
            first_at=now,
            last_at=now,
        )

        # Calculate initial wait time
        wait_ms = self._turn_manager.suggest_wait_ms(
            message_content=initial_content,
            channel=channel,
            messages_in_turn=1,
        )

        logger.info(
            "accumulation_started",
            turn_id=str(turn_id),
            initial_wait_ms=wait_ms,
            channel=channel,
        )

        # If no event callback provided, skip accumulation loop
        # (useful for channels like email where messages are always complete)
        if wait_for_event is None or wait_ms == 0:
            turn.mark_processing(reason="no_accumulation")
            return {
                "turn": turn.model_dump(mode="json"),
                "status": "ready_to_process",
                "message_count": len(turn.messages),
            }

        # Accumulation loop
        while True:
            # Wait for timeout or new message event
            event = await wait_for_event(wait_ms)

            if event is None:
                # Timeout - accumulation complete
                turn.mark_processing(reason="timeout")

                logger.info(
                    "accumulation_complete",
                    turn_id=str(turn_id),
                    message_count=len(turn.messages),
                    reason="timeout",
                )

                return {
                    "turn": turn.model_dump(mode="json"),
                    "status": "ready_to_process",
                    "message_count": len(turn.messages),
                }

            # New message event received
            new_message_id = event.get("message_id")
            new_content = event.get("content", "")
            timestamp_str = event.get("timestamp")
            timestamp = (
                datetime.fromisoformat(timestamp_str)
                if timestamp_str
                else utc_now()
            )

            logger.info(
                "new_message_during_accumulation",
                turn_id=str(turn_id),
                new_message_id=new_message_id,
            )

            if turn.can_absorb_message():
                # Absorb into current turn
                turn.absorb_message(UUID(new_message_id), timestamp)

                # Recalculate wait time
                wait_ms = self._turn_manager.suggest_wait_ms(
                    message_content=new_content,
                    channel=channel,
                    messages_in_turn=len(turn.messages),
                )

                logger.info(
                    "message_absorbed",
                    turn_id=str(turn_id),
                    message_count=len(turn.messages),
                    new_wait_ms=wait_ms,
                )
            else:
                # Cannot absorb - complete current turn
                turn.mark_processing(reason="cannot_absorb")

                logger.info(
                    "accumulation_complete_with_queued",
                    turn_id=str(turn_id),
                    queued_message_id=new_message_id,
                )

                return {
                    "turn": turn.model_dump(mode="json"),
                    "status": "ready_to_process",
                    "message_count": len(turn.messages),
                    "queued_message_id": new_message_id,
                }

    async def run_agent(
        self,
        turn_data: dict[str, Any],
        tenant_id: str,
        agent_id: str,
        interlocutor_id: str,
        channel: str,
        check_pending: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Step 3: Execute the Agent's Brain.

        Runs the alignment pipeline with interrupt checking.

        Args:
            turn_data: Serialized LogicalTurn from accumulate step
            tenant_id: Tenant UUID string
            agent_id: Agent UUID string
            interlocutor_id: Customer UUID string
            channel: Communication channel
            check_pending: Callback to check for pending messages

        Returns:
            Step result with pipeline output
        """
        turn = LogicalTurn(**turn_data)

        logger.info(
            "pipeline_starting",
            turn_id=str(turn.id),
            message_count=len(turn.messages),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        try:
            # Get message contents for processing
            message_contents = []
            for msg_id in turn.messages:
                msg = await self._message_store.get(msg_id)
                if msg:
                    message_contents.append(msg.content if hasattr(msg, "content") else str(msg))

            combined_message = " ".join(message_contents) if message_contents else ""

            # Run alignment engine
            result = await self._alignment_engine.process_turn(
                message=combined_message,
                tenant_id=UUID(tenant_id),
                agent_id=UUID(agent_id),
                session_id=None,  # Will be resolved by engine
                channel=channel,
                channel_user_id=interlocutor_id,
            )

            turn.mark_complete()

            logger.info(
                "pipeline_complete",
                turn_id=str(turn.id),
                response_length=len(result.response) if result.response else 0,
            )

            return {
                "status": "complete",
                "turn": turn.model_dump(mode="json"),
                "response": result.response,
                "response_segments": [s.model_dump(mode="json") for s in result.response_segments] if result.response_segments else [],
            }

        except Exception as e:
            logger.error(
                "pipeline_failed",
                turn_id=str(turn.id),
                error=str(e),
            )
            return {
                "status": "failed",
                "turn": turn.model_dump(mode="json"),
                "error": str(e),
            }

    async def commit_and_respond(
        self,
        pipeline_output: dict[str, Any],
        lock_key: str | None,
        session_key: str,
    ) -> dict[str, Any]:
        """Step 4: Commit changes and send response.

        Persists the turn record and releases the mutex.

        Args:
            pipeline_output: Result from run_agent step
            lock_key: Redis lock key to release
            session_key: Session identifier

        Returns:
            Final workflow result
        """
        status = pipeline_output.get("status", "unknown")
        turn_data = pipeline_output.get("turn", {})
        turn_id = turn_data.get("id", "unknown")
        response = pipeline_output.get("response")

        try:
            if status == "complete":
                # Save turn record to audit store
                if self._audit_store:
                    await self._audit_store.save_turn_record(
                        turn_id=turn_id,
                        session_key=session_key,
                        messages=turn_data.get("messages", []),
                        response=response,
                    )

                logger.info(
                    "turn_committed",
                    turn_id=turn_id,
                    session_key=session_key,
                )

            return {
                "status": status,
                "turn_id": turn_id,
                "response": response,
                "response_sent": status == "complete",
            }

        finally:
            # Always release mutex
            if lock_key:
                await self._release_mutex(lock_key, session_key)

    async def _release_mutex(self, lock_key: str, session_key: str) -> None:
        """Release the session mutex.

        Args:
            lock_key: Redis lock key
            session_key: Session identifier for logging
        """
        try:
            await self._mutex.release_direct(lock_key)
            logger.info(
                "mutex_released",
                session_key=session_key,
            )
        except Exception as e:
            logger.error(
                "mutex_release_failed",
                session_key=session_key,
                error=str(e),
            )

    async def on_failure(
        self,
        lock_key: str | None,
        session_key: str | None,
        error: str,
    ) -> None:
        """Handle workflow failure.

        Release lock and log failure.

        Args:
            lock_key: Redis lock key if acquired
            session_key: Session identifier
            error: Error message
        """
        if lock_key and session_key:
            await self._release_mutex(lock_key, session_key)

        logger.error(
            "logical_turn_workflow_failed",
            session_key=session_key,
            error=error,
        )

    async def run(self, input_data: WorkflowInput) -> WorkflowOutput:
        """Execute the complete workflow.

        This method orchestrates all steps sequentially.
        In production with Hatchet, each step runs as a durable step.

        Args:
            input_data: Workflow input

        Returns:
            WorkflowOutput with result
        """
        session_key = input_data.get_session_key()
        turn_id = uuid4()
        lock_key: str | None = None

        try:
            # Step 1: Acquire mutex
            mutex_result = await self.acquire_mutex(session_key)
            if mutex_result["status"] == "lock_failed":
                return WorkflowOutput(
                    turn_id=str(turn_id),
                    status="failed",
                    error="Could not acquire session lock",
                )
            lock_key = mutex_result.get("lock_key")

            # Step 2: Accumulate (no event callback for now - single message)
            accumulate_result = await self.accumulate(
                turn_id=turn_id,
                session_key=session_key,
                initial_message_id=input_data.message_id,
                initial_content=input_data.message_content,
                channel=input_data.channel,
                wait_for_event=None,  # No Hatchet event support yet
            )

            # Step 3: Run agent
            pipeline_result = await self.run_agent(
                turn_data=accumulate_result["turn"],
                tenant_id=input_data.tenant_id,
                agent_id=input_data.agent_id,
                interlocutor_id=input_data.interlocutor_id,
                channel=input_data.channel,
            )

            # Step 4: Commit and respond
            final_result = await self.commit_and_respond(
                pipeline_output=pipeline_result,
                lock_key=lock_key,
                session_key=session_key,
            )

            return WorkflowOutput(
                turn_id=str(turn_id),
                status=final_result["status"],
                response=final_result.get("response"),
                message_count=accumulate_result.get("message_count", 1),
            )

        except Exception as e:
            await self.on_failure(lock_key, session_key, str(e))
            return WorkflowOutput(
                turn_id=str(turn_id),
                status="failed",
                error=str(e),
            )


def register_workflow(hatchet: Any, workflow: LogicalTurnWorkflow) -> Any:
    """Register the LogicalTurn workflow with Hatchet.

    Args:
        hatchet: Hatchet SDK instance
        workflow: Configured workflow instance

    Returns:
        Registered Hatchet workflow class
    """
    @hatchet.workflow(name=LogicalTurnWorkflow.WORKFLOW_NAME)
    class HatchetLogicalTurnWorkflow:
        """Hatchet workflow wrapper for LogicalTurn processing."""

        @hatchet.step(retries=3, retry_delay="2s")
        async def acquire_mutex(self, ctx: Any) -> dict:
            """Step 1: Acquire session mutex."""
            input_data = ctx.workflow_input() or {}
            session_key = build_session_key(
                input_data["tenant_id"],
                input_data["agent_id"],
                input_data["interlocutor_id"],
                input_data["channel"],
            )
            return await workflow.acquire_mutex(session_key)

        @hatchet.step()
        async def accumulate(self, ctx: Any) -> dict:
            """Step 2: Accumulate messages."""
            input_data = ctx.workflow_input() or {}
            mutex_output = ctx.step_output("acquire_mutex")

            if mutex_output.get("status") == "lock_failed":
                return {"status": "skipped", "reason": "lock_failed"}

            session_key = mutex_output["session_key"]
            turn_id = uuid4()

            async def wait_for_event(timeout_ms: int) -> dict | None:
                """Wait for new message event from Hatchet."""
                return await ctx.wait_for_event(
                    timeout_ms=timeout_ms,
                    event_types=["new_message"],
                )

            return await workflow.accumulate(
                turn_id=turn_id,
                session_key=session_key,
                initial_message_id=input_data["message_id"],
                initial_content=input_data.get("message_content", ""),
                channel=input_data["channel"],
                wait_for_event=wait_for_event,
            )

        @hatchet.step()
        async def run_agent(self, ctx: Any) -> dict:
            """Step 3: Execute agent brain."""
            input_data = ctx.workflow_input() or {}
            accumulate_output = ctx.step_output("accumulate")

            if accumulate_output.get("status") == "skipped":
                return {"status": "skipped", "reason": "accumulate_skipped"}

            async def check_pending() -> bool:
                """Check for pending messages."""
                event = await ctx.check_event("new_message", block=False)
                return event is not None

            return await workflow.run_agent(
                turn_data=accumulate_output["turn"],
                tenant_id=input_data["tenant_id"],
                agent_id=input_data["agent_id"],
                interlocutor_id=input_data["interlocutor_id"],
                channel=input_data["channel"],
                check_pending=check_pending,
            )

        @hatchet.step()
        async def commit_and_respond(self, ctx: Any) -> dict:
            """Step 4: Commit and respond."""
            mutex_output = ctx.step_output("acquire_mutex")
            pipeline_output = ctx.step_output("run_agent")

            lock_key = mutex_output.get("lock_key")
            session_key = mutex_output.get("session_key", "")

            return await workflow.commit_and_respond(
                pipeline_output=pipeline_output,
                lock_key=lock_key,
                session_key=session_key,
            )

        @hatchet.on_failure()
        async def handle_failure(self, ctx: Any) -> None:
            """Handle workflow failure."""
            mutex_output = ctx.step_output("acquire_mutex") or {}
            lock_key = mutex_output.get("lock_key")
            session_key = mutex_output.get("session_key")

            await workflow.on_failure(
                lock_key=lock_key,
                session_key=session_key,
                error=str(ctx.error) if hasattr(ctx, "error") else "Unknown error",
            )

    return HatchetLogicalTurnWorkflow
