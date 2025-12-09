"""Unit tests for VariableMerger."""

import pytest
from uuid import uuid4

from soldier.alignment.execution.variable_merger import VariableMerger
from soldier.alignment.execution.models import ToolResult


@pytest.fixture
def merger() -> VariableMerger:
    return VariableMerger()


def test_merge_known_vars_only_no_tool_results(merger: VariableMerger) -> None:
    """Test merging when there are only known_vars and no tool results."""
    known_vars = {"name": "Alice", "email": "alice@example.com"}

    engine_variables = merger.merge_tool_results(known_vars, [])

    assert engine_variables == known_vars


def test_merge_tool_results_new_variables(merger: VariableMerger) -> None:
    """Test merging tool results that add new variables."""
    known_vars = {"name": "Alice"}

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"email": "alice@example.com"},
        ),
        ToolResult(
            tool_name="tool_2",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=50.0,
            variables_filled={"phone": "555-1234"},
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert engine_variables == {
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "555-1234",
    }


def test_merge_with_conflicts_later_override(merger: VariableMerger) -> None:
    """Test that later tool results override earlier ones in case of conflict."""
    known_vars = {"name": "Alice"}

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"email": "old@example.com"},
        ),
        ToolResult(
            tool_name="tool_2",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=50.0,
            variables_filled={"email": "new@example.com"},  # Conflict
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    # Later tool should win
    assert engine_variables["email"] == "new@example.com"


def test_merge_tool_overrides_known_var(merger: VariableMerger) -> None:
    """Test that tool results can override pre-resolved variables."""
    known_vars = {"name": "OldName"}

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"name": "NewName"},
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert engine_variables["name"] == "NewName"


def test_failed_tools_skip_their_variables(merger: VariableMerger) -> None:
    """Test that failed tools don't contribute their variables_filled."""
    known_vars = {"name": "Alice"}

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"email": "alice@example.com"},
        ),
        ToolResult(
            tool_name="tool_2",
            rule_id=uuid4(),
            success=False,  # Failed
            error="timeout",
            execution_time_ms=5000.0,
            variables_filled={"phone": "555-1234"},  # Should be ignored
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert engine_variables == {"name": "Alice", "email": "alice@example.com"}
    assert "phone" not in engine_variables


def test_empty_variables_filled(merger: VariableMerger) -> None:
    """Test handling tool results with empty variables_filled."""
    known_vars = {"name": "Alice"}

    tool_results = [
        ToolResult(
            tool_name="side_effect_tool",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={},  # No variables filled
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert engine_variables == known_vars


def test_multiple_variables_from_single_tool(merger: VariableMerger) -> None:
    """Test tool filling multiple variables at once."""
    known_vars = {}

    tool_results = [
        ToolResult(
            tool_name="enrichment_tool",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={
                "name": "Alice",
                "email": "alice@example.com",
                "phone": "555-1234",
                "address": "123 Main St",
            },
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert len(engine_variables) == 4
    assert engine_variables["name"] == "Alice"
    assert engine_variables["email"] == "alice@example.com"
    assert engine_variables["phone"] == "555-1234"
    assert engine_variables["address"] == "123 Main St"


def test_preserve_known_vars_not_overridden(merger: VariableMerger) -> None:
    """Test that known_vars not touched by tools are preserved."""
    known_vars = {
        "name": "Alice",
        "account_type": "premium",
        "balance": 100,
    }

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"email": "alice@example.com"},  # Only adds email
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    # Original known_vars should be preserved
    assert engine_variables["name"] == "Alice"
    assert engine_variables["account_type"] == "premium"
    assert engine_variables["balance"] == 100
    assert engine_variables["email"] == "alice@example.com"


def test_empty_known_vars_and_results(merger: VariableMerger) -> None:
    """Test merging with no known vars and no tool results."""
    engine_variables = merger.merge_tool_results({}, [])

    assert engine_variables == {}


def test_mixed_success_and_failure_tools(merger: VariableMerger) -> None:
    """Test merging with mix of successful and failed tools."""
    known_vars = {"base": "value"}

    tool_results = [
        ToolResult(
            tool_name="tool_1",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=100.0,
            variables_filled={"var1": "value1"},
        ),
        ToolResult(
            tool_name="tool_2",
            rule_id=uuid4(),
            success=False,
            error="error",
            execution_time_ms=50.0,
            variables_filled={"var2": "value2"},  # Ignored
        ),
        ToolResult(
            tool_name="tool_3",
            rule_id=uuid4(),
            success=True,
            execution_time_ms=75.0,
            variables_filled={"var3": "value3"},
        ),
    ]

    engine_variables = merger.merge_tool_results(known_vars, tool_results)

    assert engine_variables == {
        "base": "value",
        "var1": "value1",
        "var3": "value3",
    }
    assert "var2" not in engine_variables
