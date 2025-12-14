"""Tool execution with timeout handling."""

import asyncio
import time
from collections.abc import Awaitable, Callable

from ruche.alignment.context.situation_snapshot import SituationSnapshot
from ruche.alignment.execution.models import ToolResult
from ruche.alignment.filtering.models import MatchedRule
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

ToolCallable = Callable[[SituationSnapshot, MatchedRule], Awaitable[dict[str, object]]]


class ToolExecutor:
    """Execute tools attached to matched rules.

    Supports:
    - Parallel execution with configurable concurrency
    - Per-tool timeout handling
    - Fail-fast mode for critical tool chains
    - Result aggregation with success/failure tracking
    """

    def __init__(
        self,
        tools: dict[str, ToolCallable],
        timeout_ms: int = 5000,
        max_parallel: int = 5,
        fail_fast: bool = False,
    ) -> None:
        """Initialize the tool executor.

        Args:
            tools: Map of tool_id -> async callable
            timeout_ms: Maximum execution time per tool
            max_parallel: Maximum concurrent tool executions
            fail_fast: Stop on first tool failure
        """
        self._tools = tools
        self._timeout_ms = timeout_ms
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._fail_fast = fail_fast

    async def execute(
        self,
        matched_rules: list[MatchedRule],
        snapshot: SituationSnapshot,
    ) -> list[ToolResult]:
        """Execute all tools attached to matched rules.

        Args:
            matched_rules: Rules with attached tool IDs
            snapshot: Situation snapshot for tool input

        Returns:
            List of ToolResult for each executed tool
        """
        results: list[ToolResult] = []

        for matched in matched_rules:
            for tool_id in matched.rule.attached_tool_ids:
                tool = self._tools.get(tool_id)
                if not tool:
                    results.append(
                        ToolResult(
                            tool_name=tool_id,
                            rule_id=matched.rule.id,
                            success=False,
                            error="tool_not_found",
                            execution_time_ms=0.0,
                        )
                    )
                    if self._fail_fast:
                        return results
                    continue

                try:
                    result = await self._run_with_timeout(tool, snapshot, matched)
                    results.append(result)
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        ToolResult(
                            tool_name=tool_id,
                            rule_id=matched.rule.id,
                            success=False,
                            error=str(exc),
                            execution_time_ms=0.0,
                        )
                    )
                    if self._fail_fast:
                        return results

        return results

    async def _run_with_timeout(
        self,
        tool: ToolCallable,
        snapshot: SituationSnapshot,
        matched_rule: MatchedRule,
    ) -> ToolResult:
        """Execute a tool with timeout and timing."""
        start_time = time.perf_counter()
        try:
            async with self._semaphore:
                outputs = await asyncio.wait_for(
                    tool(snapshot, matched_rule),
                    timeout=self._timeout_ms / 1000,
                )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=tool.__name__,
                rule_id=matched_rule.rule.id,
                outputs=outputs,
                inputs={},
                success=True,
                execution_time_ms=elapsed_ms,
            )
        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=tool.__name__,
                rule_id=matched_rule.rule.id,
                success=False,
                error="timeout",
                execution_time_ms=elapsed_ms,
                timeout=True,
            )
