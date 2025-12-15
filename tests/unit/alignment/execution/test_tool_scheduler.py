"""Unit tests for ToolScheduler and FutureToolQueue."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.execution.tool_scheduler import ToolScheduler, FutureToolQueue
from ruche.brains.focal.models.tool_binding import ToolBinding


@pytest.fixture
def scheduler() -> ToolScheduler:
    return ToolScheduler()


@pytest.fixture
def future_queue() -> FutureToolQueue:
    return FutureToolQueue()


def test_schedule_before_step_tools_only(scheduler: ToolScheduler) -> None:
    """Test scheduling BEFORE_STEP tools only."""
    bindings = [
        ToolBinding(tool_id="before_tool_1", when="BEFORE_STEP", required_variables=["var_a"]),
        ToolBinding(tool_id="before_tool_2", when="BEFORE_STEP", required_variables=["var_b"]),
        ToolBinding(tool_id="during_tool", when="DURING_STEP", required_variables=["var_c"]),
    ]

    missing_vars = {"var_a", "var_b", "var_c"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "BEFORE_STEP")

    assert len(scheduled) == 2
    tool_ids = {tool_id for tool_id, _ in scheduled}
    assert "before_tool_1" in tool_ids
    assert "before_tool_2" in tool_ids
    assert "during_tool" not in tool_ids


def test_schedule_during_step_tools_only(scheduler: ToolScheduler) -> None:
    """Test scheduling DURING_STEP tools only."""
    bindings = [
        ToolBinding(tool_id="before_tool", when="BEFORE_STEP", required_variables=["var_a"]),
        ToolBinding(tool_id="during_tool_1", when="DURING_STEP", required_variables=["var_b"]),
        ToolBinding(tool_id="during_tool_2", when="DURING_STEP", required_variables=["var_c"]),
    ]

    missing_vars = {"var_a", "var_b", "var_c"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    assert len(scheduled) == 2
    tool_ids = {tool_id for tool_id, _ in scheduled}
    assert "during_tool_1" in tool_ids
    assert "during_tool_2" in tool_ids
    assert "before_tool" not in tool_ids


def test_schedule_after_step_tools_only(scheduler: ToolScheduler) -> None:
    """Test scheduling AFTER_STEP tools only."""
    bindings = [
        ToolBinding(tool_id="during_tool", when="DURING_STEP", required_variables=["var_a"]),
        ToolBinding(tool_id="after_tool_1", when="AFTER_STEP", required_variables=["var_b"]),
        ToolBinding(tool_id="after_tool_2", when="AFTER_STEP", required_variables=["var_c"]),
    ]

    missing_vars = {"var_a", "var_b", "var_c"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "AFTER_STEP")

    assert len(scheduled) == 2
    tool_ids = {tool_id for tool_id, _ in scheduled}
    assert "after_tool_1" in tool_ids
    assert "after_tool_2" in tool_ids
    assert "during_tool" not in tool_ids


def test_dependency_ordering(scheduler: ToolScheduler) -> None:
    """Test that tools are ordered by dependencies."""
    bindings = [
        ToolBinding(
            tool_id="tool_c",
            when="DURING_STEP",
            required_variables=["var_c"],
            depends_on=["tool_b"],
        ),
        ToolBinding(
            tool_id="tool_b",
            when="DURING_STEP",
            required_variables=["var_b"],
            depends_on=["tool_a"],
        ),
        ToolBinding(tool_id="tool_a", when="DURING_STEP", required_variables=["var_a"]),
    ]

    missing_vars = {"var_a", "var_b", "var_c"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    # Extract tool_ids in order
    tool_ids = [tool_id for tool_id, _ in scheduled]

    # tool_a should come before tool_b, and tool_b before tool_c
    assert tool_ids.index("tool_a") < tool_ids.index("tool_b")
    assert tool_ids.index("tool_b") < tool_ids.index("tool_c")


def test_filter_by_missing_variables(scheduler: ToolScheduler) -> None:
    """Test that only tools that can fill missing variables are scheduled."""
    bindings = [
        ToolBinding(tool_id="tool_needed", when="DURING_STEP", required_variables=["missing_var"]),
        ToolBinding(tool_id="tool_not_needed", when="DURING_STEP", required_variables=["present_var"]),
    ]

    missing_vars = {"missing_var"}  # only missing_var is needed
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    assert len(scheduled) == 1
    assert scheduled[0][0] == "tool_needed"
    assert scheduled[0][1] == ["missing_var"]


def test_empty_schedule_no_matching_tools(scheduler: ToolScheduler) -> None:
    """Test scheduling when no tools match the phase."""
    bindings = [
        ToolBinding(tool_id="before_tool", when="BEFORE_STEP", required_variables=["var_a"]),
        ToolBinding(tool_id="after_tool", when="AFTER_STEP", required_variables=["var_b"]),
    ]

    missing_vars = {"var_a", "var_b"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    assert len(scheduled) == 0


def test_tools_without_required_variables_included(scheduler: ToolScheduler) -> None:
    """Test that tools without required_variables are included (side effects)."""
    bindings = [
        ToolBinding(tool_id="side_effect_tool", when="DURING_STEP", required_variables=[]),
        ToolBinding(tool_id="var_tool", when="DURING_STEP", required_variables=["var_a"]),
    ]

    missing_vars = {"var_a"}
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    # Both should be scheduled (side_effect_tool has no required_variables)
    assert len(scheduled) == 2
    tool_ids = {tool_id for tool_id, _ in scheduled}
    assert "side_effect_tool" in tool_ids
    assert "var_tool" in tool_ids


def test_complex_dependency_chain(scheduler: ToolScheduler) -> None:
    """Test complex dependency chain with multiple dependencies."""
    bindings = [
        ToolBinding(tool_id="tool_d", when="DURING_STEP", depends_on=["tool_b", "tool_c"]),
        ToolBinding(tool_id="tool_c", when="DURING_STEP", depends_on=["tool_a"]),
        ToolBinding(tool_id="tool_b", when="DURING_STEP", depends_on=["tool_a"]),
        ToolBinding(tool_id="tool_a", when="DURING_STEP"),
    ]

    missing_vars = set()  # Include all tools (no variable filtering)
    scheduled = scheduler.schedule_tools(bindings, missing_vars, "DURING_STEP")

    tool_ids = [tool_id for tool_id, _ in scheduled]

    # tool_a must come first
    assert tool_ids.index("tool_a") < tool_ids.index("tool_b")
    assert tool_ids.index("tool_a") < tool_ids.index("tool_c")

    # tool_b and tool_c must come before tool_d
    assert tool_ids.index("tool_b") < tool_ids.index("tool_d")
    assert tool_ids.index("tool_c") < tool_ids.index("tool_d")


def test_future_queue_add_tools(future_queue: FutureToolQueue) -> None:
    """Test adding AFTER_STEP tools to future queue."""
    session_id = uuid4()

    bindings = [
        ToolBinding(tool_id="after_tool_1", when="AFTER_STEP"),
        ToolBinding(tool_id="during_tool", when="DURING_STEP"),
        ToolBinding(tool_id="after_tool_2", when="AFTER_STEP"),
    ]

    future_queue.add_tools(bindings, session_id)

    pending = future_queue.get_pending_tools(session_id)

    assert len(pending) == 2
    tool_ids = {b.tool_id for b in pending}
    assert "after_tool_1" in tool_ids
    assert "after_tool_2" in tool_ids
    assert "during_tool" not in tool_ids


def test_future_queue_get_pending(future_queue: FutureToolQueue) -> None:
    """Test getting pending tools from queue."""
    session_id = uuid4()

    bindings = [ToolBinding(tool_id="after_tool", when="AFTER_STEP")]

    future_queue.add_tools(bindings, session_id)
    pending = future_queue.get_pending_tools(session_id)

    assert len(pending) == 1
    assert pending[0].tool_id == "after_tool"


def test_future_queue_clear_session(future_queue: FutureToolQueue) -> None:
    """Test clearing queue for a session."""
    session_id = uuid4()

    bindings = [ToolBinding(tool_id="after_tool", when="AFTER_STEP")]

    future_queue.add_tools(bindings, session_id)
    assert len(future_queue.get_pending_tools(session_id)) == 1

    future_queue.clear_session(session_id)
    assert len(future_queue.get_pending_tools(session_id)) == 0


def test_future_queue_multiple_sessions(future_queue: FutureToolQueue) -> None:
    """Test that queue tracks multiple sessions independently."""
    session_1 = uuid4()
    session_2 = uuid4()

    bindings_1 = [ToolBinding(tool_id="tool_1", when="AFTER_STEP")]
    bindings_2 = [ToolBinding(tool_id="tool_2", when="AFTER_STEP")]

    future_queue.add_tools(bindings_1, session_1)
    future_queue.add_tools(bindings_2, session_2)

    pending_1 = future_queue.get_pending_tools(session_1)
    pending_2 = future_queue.get_pending_tools(session_2)

    assert len(pending_1) == 1
    assert pending_1[0].tool_id == "tool_1"

    assert len(pending_2) == 1
    assert pending_2[0].tool_id == "tool_2"

    # Clearing one should not affect the other
    future_queue.clear_session(session_1)
    assert len(future_queue.get_pending_tools(session_1)) == 0
    assert len(future_queue.get_pending_tools(session_2)) == 1


def test_future_queue_empty_session(future_queue: FutureToolQueue) -> None:
    """Test getting pending tools for a session with no queued tools."""
    session_id = uuid4()

    pending = future_queue.get_pending_tools(session_id)

    assert len(pending) == 0
