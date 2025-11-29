"""Unit tests for ToolExecutor."""

import asyncio

import pytest

from soldier.alignment.context.models import Context
from soldier.alignment.execution.tool_executor import ToolExecutor
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.models import Rule
from tests.factories.alignment import RuleFactory


def _matched_rule(rule: Rule) -> MatchedRule:
    return MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")


@pytest.mark.asyncio
async def test_tool_executor_runs_tools_and_returns_outputs() -> None:
    async def sample_tool(context: Context, matched_rule: MatchedRule):
        return {"echo": context.message, "rule": matched_rule.rule.name}

    rule = RuleFactory.create(attached_tool_ids=["sample_tool"])
    executor = ToolExecutor({"sample_tool": sample_tool}, timeout_ms=1000)

    results = await executor.execute([_matched_rule(rule)], Context(message="hi"))

    assert len(results) == 1
    result = results[0]
    assert result.success is True
    assert result.outputs == {"echo": "hi", "rule": rule.name}


@pytest.mark.asyncio
async def test_tool_executor_marks_timeout() -> None:
    async def slow_tool(context: Context, matched_rule: MatchedRule):
        await asyncio.sleep(0.2)
        return {}

    rule = RuleFactory.create(attached_tool_ids=["slow_tool"])
    executor = ToolExecutor({"slow_tool": slow_tool}, timeout_ms=50)

    results = await executor.execute([_matched_rule(rule)], Context(message="hi"))

    assert results[0].success is False
    assert results[0].timeout is True
    assert results[0].error == "timeout"


@pytest.mark.asyncio
async def test_tool_executor_fail_fast_stops_execution() -> None:
    async def failing_tool(context: Context, matched_rule: MatchedRule):
        raise RuntimeError("boom")

    async def should_not_run(context: Context, matched_rule: MatchedRule):
        return {"ok": True}

    rule = RuleFactory.create(attached_tool_ids=["failing_tool", "should_not_run"])
    executor = ToolExecutor(
        {"failing_tool": failing_tool, "should_not_run": should_not_run},
        timeout_ms=100,
        fail_fast=True,
    )

    results = await executor.execute([_matched_rule(rule)], Context(message="test"))

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "boom"
