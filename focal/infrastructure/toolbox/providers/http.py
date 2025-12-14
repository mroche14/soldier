"""HTTP tool provider adapter.

Executes tools via HTTP APIs (REST, GraphQL, etc).
Stub implementation - to be completed when HTTP tool support is needed.
"""

from typing import Any

from focal.infrastructure.toolbox.models import ToolResult


class HTTPProvider:
    """HTTP tool provider.

    Executes tools by making HTTP requests to external APIs.
    """

    async def execute(
        self,
        tool_id: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> ToolResult:
        """Execute an HTTP tool.

        Args:
            tool_id: HTTP endpoint identifier
            inputs: Request parameters
            config: HTTP configuration (method, headers, etc)

        Returns:
            ToolResult with execution outcome
        """
        # Stub implementation
        return ToolResult(
            tool_id=tool_id,
            success=False,
            error="HTTP provider not yet implemented",
            execution_time_ms=0,
            provider="http",
        )
