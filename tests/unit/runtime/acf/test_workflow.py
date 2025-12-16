"""Tests for LogicalTurnWorkflow - the ACF orchestration layer.

Tests cover:
- WorkflowInput/WorkflowOutput dataclasses
- LogicalTurnWorkflow step methods
- Full workflow orchestration via run()
- Error handling and mutex release
"""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from ruche.runtime.acf.workflow import (
    LogicalTurnWorkflow,
    WorkflowInput,
    WorkflowOutput,
    utc_now,
)
from ruche.runtime.acf.models import LogicalTurn, LogicalTurnStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()

    # Mock lock behavior
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=True)
    mock_lock.release = AsyncMock()
    mock_lock.extend = AsyncMock(return_value=True)
    redis.lock = MagicMock(return_value=mock_lock)
    redis.exists = AsyncMock(return_value=0)
    redis.delete = AsyncMock(return_value=1)

    return redis


@pytest.fixture
def mock_agent_runtime():
    """Create mock AgentRuntime."""
    runtime = AsyncMock()

    # Mock agent context
    agent_ctx = MagicMock()
    agent_ctx.brain = AsyncMock()

    # Mock brain result
    brain_result = MagicMock()
    brain_result.response = "Hello, how can I help you?"
    brain_result.response_segments = []
    agent_ctx.brain.think = AsyncMock(return_value=brain_result)

    runtime.get_or_create = AsyncMock(return_value=agent_ctx)

    return runtime


@pytest.fixture
def mock_session_store():
    """Create mock session store."""
    return AsyncMock()


@pytest.fixture
def mock_message_store():
    """Create mock message store."""
    return AsyncMock()


@pytest.fixture
def mock_audit_store():
    """Create mock audit store."""
    store = AsyncMock()
    store.save_turn_record = AsyncMock()
    return store


@pytest.fixture
def workflow(
    mock_redis,
    mock_agent_runtime,
    mock_session_store,
    mock_message_store,
    mock_audit_store,
):
    """Create workflow instance with mocks."""
    return LogicalTurnWorkflow(
        redis=mock_redis,
        agent_runtime=mock_agent_runtime,
        session_store=mock_session_store,
        message_store=mock_message_store,
        audit_store=mock_audit_store,
        mutex_timeout=30,
        mutex_blocking_timeout=5.0,
    )


@pytest.fixture
def sample_input():
    """Create sample workflow input."""
    return WorkflowInput(
        tenant_id=str(uuid4()),
        agent_id=str(uuid4()),
        interlocutor_id=str(uuid4()),
        channel="webchat",
        message_id=str(uuid4()),
        message_content="Hello, I need help",
    )


# =============================================================================
# Tests: WorkflowInput
# =============================================================================


class TestWorkflowInput:
    """Tests for WorkflowInput dataclass."""

    def test_creates_with_required_fields(self):
        """Creates input with required fields."""
        input_data = WorkflowInput(
            tenant_id="tenant-123",
            agent_id="agent-456",
            interlocutor_id="customer-789",
            channel="whatsapp",
            message_id="msg-001",
            message_content="Hello",
        )

        assert input_data.tenant_id == "tenant-123"
        assert input_data.agent_id == "agent-456"
        assert input_data.interlocutor_id == "customer-789"
        assert input_data.channel == "whatsapp"
        assert input_data.message_id == "msg-001"
        assert input_data.message_content == "Hello"

    def test_session_key_computed_when_not_provided(self):
        """Computes session key from component IDs."""
        input_data = WorkflowInput(
            tenant_id="tenant-123",
            agent_id="agent-456",
            interlocutor_id="customer-789",
            channel="whatsapp",
            message_id="msg-001",
            message_content="Hello",
        )

        expected = "tenant-123:agent-456:customer-789:whatsapp"
        assert input_data.get_session_key() == expected

    def test_session_key_used_when_provided(self):
        """Uses provided session key instead of computing."""
        input_data = WorkflowInput(
            tenant_id="tenant-123",
            agent_id="agent-456",
            interlocutor_id="customer-789",
            channel="whatsapp",
            message_id="msg-001",
            message_content="Hello",
            session_key="custom:session:key",
        )

        assert input_data.get_session_key() == "custom:session:key"


# =============================================================================
# Tests: WorkflowOutput
# =============================================================================


class TestWorkflowOutput:
    """Tests for WorkflowOutput dataclass."""

    def test_creates_complete_output(self):
        """Creates output for successful completion."""
        output = WorkflowOutput(
            turn_id="turn-123",
            status="complete",
            response="Hello!",
            message_count=1,
        )

        assert output.turn_id == "turn-123"
        assert output.status == "complete"
        assert output.response == "Hello!"
        assert output.message_count == 1
        assert output.error is None

    def test_creates_failed_output(self):
        """Creates output for failure."""
        output = WorkflowOutput(
            turn_id="turn-123",
            status="failed",
            error="Lock acquisition failed",
        )

        assert output.status == "failed"
        assert output.error == "Lock acquisition failed"
        assert output.response is None


# =============================================================================
# Tests: LogicalTurnWorkflow.acquire_mutex()
# =============================================================================


class TestWorkflowAcquireMutex:
    """Tests for acquire_mutex step."""

    @pytest.mark.asyncio
    async def test_acquires_lock_successfully(self, workflow, mock_redis):
        """Acquires lock and returns locked status."""
        result = await workflow.acquire_mutex("tenant:agent:customer:web")

        assert result["status"] == "locked"
        assert result["session_key"] == "tenant:agent:customer:web"
        assert "lock_key" in result
        assert "locked_at" in result

    @pytest.mark.asyncio
    async def test_returns_lock_failed_when_cannot_acquire(self, workflow, mock_redis):
        """Returns lock_failed when lock unavailable."""
        # Make lock acquisition fail
        mock_lock = mock_redis.lock.return_value
        mock_lock.acquire = AsyncMock(return_value=False)

        # Re-mock acquire_direct to return None
        workflow._mutex.acquire_direct = AsyncMock(return_value=None)

        result = await workflow.acquire_mutex("tenant:agent:customer:web")

        assert result["status"] == "lock_failed"
        assert result["retry"] is True


# =============================================================================
# Tests: LogicalTurnWorkflow.accumulate()
# =============================================================================


class TestWorkflowAccumulate:
    """Tests for accumulate step."""

    @pytest.mark.asyncio
    async def test_creates_turn_with_initial_message(self, workflow):
        """Creates turn with initial message."""
        turn_id = uuid4()

        result = await workflow.accumulate(
            turn_id=turn_id,
            session_key="tenant:agent:customer:web",
            initial_message_id=str(uuid4()),
            initial_content="Hello",
            channel="webchat",
            wait_for_event=None,
        )

        assert result["status"] == "ready_to_process"
        assert result["message_count"] == 1
        assert "turn" in result

    @pytest.mark.asyncio
    async def test_skips_accumulation_when_no_event_callback(self, workflow):
        """Skips accumulation loop when wait_for_event is None."""
        turn_id = uuid4()

        result = await workflow.accumulate(
            turn_id=turn_id,
            session_key="test:session",
            initial_message_id=str(uuid4()),
            initial_content="Hi",
            channel="email",  # Email typically has no accumulation
            wait_for_event=None,
        )

        # Should immediately return ready_to_process
        assert result["status"] == "ready_to_process"
        turn_data = result["turn"]
        assert turn_data["status"] == LogicalTurnStatus.PROCESSING.value

    @pytest.mark.asyncio
    async def test_accumulates_additional_messages(self, workflow):
        """Absorbs additional messages during accumulation."""
        turn_id = uuid4()
        message_sequence = [
            {"message_id": str(uuid4()), "content": "second message"},
            None,  # Timeout - end accumulation
        ]
        call_count = [0]

        async def mock_wait_for_event(timeout_ms):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(message_sequence):
                return message_sequence[idx]
            return None

        result = await workflow.accumulate(
            turn_id=turn_id,
            session_key="test:session",
            initial_message_id=str(uuid4()),
            initial_content="first message",
            channel="webchat",
            wait_for_event=mock_wait_for_event,
        )

        assert result["status"] == "ready_to_process"
        assert result["message_count"] == 2  # Initial + absorbed

    @pytest.mark.asyncio
    async def test_completes_on_timeout(self, workflow):
        """Completes accumulation when timeout occurs."""
        turn_id = uuid4()

        async def mock_wait_for_event(timeout_ms):
            return None  # Timeout

        result = await workflow.accumulate(
            turn_id=turn_id,
            session_key="test:session",
            initial_message_id=str(uuid4()),
            initial_content="Hello",
            channel="webchat",
            wait_for_event=mock_wait_for_event,
        )

        assert result["status"] == "ready_to_process"


# =============================================================================
# Tests: LogicalTurnWorkflow.run_agent()
# =============================================================================


class TestWorkflowRunAgent:
    """Tests for run_agent step."""

    @pytest.mark.asyncio
    async def test_executes_brain_successfully(self, workflow, mock_agent_runtime):
        """Executes brain and returns response."""
        turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.PROCESSING,
        )

        result = await workflow.run_agent(
            turn_data=turn.model_dump(mode="json"),
            tenant_id=str(uuid4()),
            agent_id=str(uuid4()),
            interlocutor_id=str(uuid4()),
            channel="webchat",
        )

        assert result["status"] == "complete"
        assert result["response"] == "Hello, how can I help you?"
        mock_agent_runtime.get_or_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_failed_on_brain_error(self, workflow, mock_agent_runtime):
        """Returns failed status when brain raises exception."""
        turn = LogicalTurn(
            id=uuid4(),
            session_key="test:session",
            messages=[uuid4()],
            first_at=datetime.now(UTC),
            last_at=datetime.now(UTC),
            status=LogicalTurnStatus.PROCESSING,
        )

        # Make brain raise exception
        agent_ctx = mock_agent_runtime.get_or_create.return_value
        agent_ctx.brain.think = AsyncMock(side_effect=RuntimeError("Brain failed"))

        result = await workflow.run_agent(
            turn_data=turn.model_dump(mode="json"),
            tenant_id=str(uuid4()),
            agent_id=str(uuid4()),
            interlocutor_id=str(uuid4()),
            channel="webchat",
        )

        assert result["status"] == "failed"
        assert "Brain failed" in result["error"]


# =============================================================================
# Tests: LogicalTurnWorkflow.commit_and_respond()
# =============================================================================


class TestWorkflowCommitAndRespond:
    """Tests for commit_and_respond step."""

    @pytest.mark.asyncio
    async def test_commits_successful_turn(self, workflow, mock_audit_store):
        """Commits turn record to audit store."""
        pipeline_output = {
            "status": "complete",
            "turn": {"id": str(uuid4()), "messages": [str(uuid4())]},
            "response": "Hello!",
        }

        result = await workflow.commit_and_respond(
            pipeline_output=pipeline_output,
            lock_key="sesslock:test:session",
            session_key="test:session",
        )

        assert result["status"] == "complete"
        assert result["response_sent"] is True
        mock_audit_store.save_turn_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_releases_mutex_after_commit(self, workflow, mock_redis):
        """Releases mutex after committing."""
        pipeline_output = {
            "status": "complete",
            "turn": {"id": str(uuid4()), "messages": []},
            "response": "Done",
        }

        await workflow.commit_and_respond(
            pipeline_output=pipeline_output,
            lock_key="sesslock:test:session",
            session_key="test:session",
        )

        # Verify mutex release was called
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_releases_mutex_even_on_failure(self, workflow, mock_redis, mock_audit_store):
        """Releases mutex even when commit fails."""
        mock_audit_store.save_turn_record = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        pipeline_output = {
            "status": "complete",
            "turn": {"id": str(uuid4()), "messages": []},
            "response": "Done",
        }

        # Should not raise - mutex release is in finally block
        try:
            await workflow.commit_and_respond(
                pipeline_output=pipeline_output,
                lock_key="sesslock:test:session",
                session_key="test:session",
            )
        except Exception:
            pass

        # Mutex should still be released
        mock_redis.delete.assert_called()


# =============================================================================
# Tests: LogicalTurnWorkflow.on_failure()
# =============================================================================


class TestWorkflowOnFailure:
    """Tests for on_failure handler."""

    @pytest.mark.asyncio
    async def test_releases_mutex_on_failure(self, workflow, mock_redis):
        """Releases mutex when workflow fails."""
        await workflow.on_failure(
            lock_key="sesslock:test:session",
            session_key="test:session",
            error="Something went wrong",
        )

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_handles_missing_lock_key(self, workflow, mock_redis):
        """Handles failure when no lock was acquired."""
        await workflow.on_failure(
            lock_key=None,
            session_key="test:session",
            error="Failed before lock acquisition",
        )

        # Should not attempt to release
        mock_redis.delete.assert_not_called()


# =============================================================================
# Tests: LogicalTurnWorkflow.run() - Full orchestration
# =============================================================================


class TestWorkflowRun:
    """Tests for full workflow orchestration."""

    @pytest.mark.asyncio
    async def test_executes_all_steps_successfully(self, workflow, sample_input):
        """Runs all workflow steps in sequence."""
        output = await workflow.run(sample_input)

        assert output.status == "complete"
        assert output.response == "Hello, how can I help you?"
        assert output.message_count == 1
        assert output.error is None

    @pytest.mark.asyncio
    async def test_fails_when_mutex_unavailable(self, workflow, sample_input):
        """Returns failed when cannot acquire mutex."""
        workflow._mutex.acquire_direct = AsyncMock(return_value=None)

        output = await workflow.run(sample_input)

        assert output.status == "failed"
        assert "lock" in output.error.lower()

    @pytest.mark.asyncio
    async def test_releases_mutex_on_exception(self, workflow, sample_input, mock_redis):
        """Releases mutex when exception occurs during processing."""
        workflow._agent_runtime.get_or_create = AsyncMock(
            side_effect=RuntimeError("Runtime error")
        )

        output = await workflow.run(sample_input)

        assert output.status == "failed"
        # Mutex should have been released via on_failure
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_generates_unique_turn_id(self, workflow, sample_input):
        """Generates unique turn ID for each run."""
        output1 = await workflow.run(sample_input)
        output2 = await workflow.run(sample_input)

        assert output1.turn_id != output2.turn_id


# =============================================================================
# Tests: _route_event()
# =============================================================================


class TestWorkflowRouteEvent:
    """Tests for internal event routing."""

    @pytest.mark.asyncio
    async def test_routes_valid_acf_event(self, workflow):
        """Routes valid ACF events."""
        from ruche.runtime.acf.events import ACFEvent, ACFEventType

        event = ACFEvent(
            type=ACFEventType.TURN_STARTED,
            logical_turn_id=uuid4(),
            session_key="test:session",
            payload={"test": "data"},
        )

        # Should not raise
        await workflow._route_event(event)

    @pytest.mark.asyncio
    async def test_logs_warning_for_invalid_event(self, workflow):
        """Logs warning for non-ACFEvent objects."""
        # Should not raise, just log warning
        await workflow._route_event({"not": "an event"})


# =============================================================================
# Tests: utc_now()
# =============================================================================


class TestUtcNow:
    """Tests for utc_now helper."""

    def test_returns_utc_datetime(self):
        """Returns datetime with UTC timezone."""
        now = utc_now()
        assert now.tzinfo == UTC

    def test_returns_current_time(self):
        """Returns approximately current time."""
        before = datetime.now(UTC)
        now = utc_now()
        after = datetime.now(UTC)

        assert before <= now <= after
