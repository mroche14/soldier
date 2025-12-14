"""ToolGateway for routing tool executions to providers.

Routes tool calls to appropriate providers (Composio, HTTP, internal functions).
"""

from typing import Any

from ruche.infrastructure.toolbox.models import ToolDefinition, ToolResult
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ToolGateway:
    """Routes tool executions to the appropriate provider.

    Manages provider registration and delegates execution based on
    the tool's provider field.
    """

    def __init__(self) -> None:
        """Initialize the gateway with empty provider registry."""
        self._providers: dict[str, Any] = {}

    def register_provider(self, provider_name: str, provider: Any) -> None:
        """Register a tool provider.

        Args:
            provider_name: Provider identifier (e.g., 'composio', 'http')
            provider: Provider instance with execute() method
        """
        self._providers[provider_name] = provider
        logger.info("tool_provider_registered", provider=provider_name)

    async def execute(
        self,
        tool: ToolDefinition,
        inputs: dict[str, Any],
        *,
        tenant_id: str,
        agent_id: str,
    ) -> ToolResult:
        """Execute a tool via its provider.

        Args:
            tool: Tool definition
            inputs: Input parameters for the tool
            tenant_id: Tenant context
            agent_id: Agent context

        Returns:
            ToolResult with execution outcome

        Raises:
            ValueError: If provider not found
        """
        provider = self._providers.get(tool.provider)
        if not provider:
            return ToolResult(
                tool_id=tool.id,
                success=False,
                error=f"Provider '{tool.provider}' not registered",
                execution_time_ms=0,
                provider=tool.provider,
            )

        logger.debug(
            "executing_tool",
            tool_id=tool.id,
            provider=tool.provider,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        try:
            result = await provider.execute(
                tool_id=tool.provider_tool_id,
                inputs=inputs,
                config=tool.config,
            )
            return result
        except Exception as e:
            logger.error(
                "tool_execution_failed",
                tool_id=tool.id,
                error=str(e),
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            return ToolResult(
                tool_id=tool.id,
                success=False,
                error=str(e),
                execution_time_ms=0,
                provider=tool.provider,
            )

    def list_providers(self) -> list[str]:
        """Get list of registered provider names."""
        return list(self._providers.keys())
