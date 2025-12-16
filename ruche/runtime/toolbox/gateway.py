"""ToolGateway for routing tool executions to providers.

Infrastructure-level tool execution. Routes to providers and manages idempotency.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Protocol

from ruche.observability.logging import get_logger
from ruche.runtime.toolbox.context import ToolExecutionContext
from ruche.runtime.toolbox.models import ToolResult

logger = get_logger(__name__)


class ToolProvider(Protocol):
    """Provider for executing tools against external services.

    Each provider knows how to call its specific backend.
    """

    async def call(
        self,
        tool_name: str,
        args: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute tool and return result.

        Args:
            tool_name: Name of tool to execute
            args: Tool arguments
            config: Provider-specific configuration

        Returns:
            Tool execution result data

        Raises:
            ToolExecutionError: On execution failure
        """
        ...


class ToolExecutionError(Exception):
    """Error during tool execution."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        """Initialize error.

        Args:
            tool_name: Name of tool that failed
            message: Error message
            details: Additional error details
        """
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class IdempotencyCache(Protocol):
    """Cache for tool idempotency."""

    async def get(self, key: str) -> dict[str, Any] | None:
        """Get cached result if exists.

        Args:
            key: Idempotency key

        Returns:
            Cached result data or None
        """
        ...

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        """Cache result with TTL.

        Args:
            key: Idempotency key
            value: Result data to cache
            ttl: Time to live in seconds
        """
        ...


class ToolGateway:
    """Infrastructure-level tool execution.

    Routes to providers, handles idempotency.
    Does NOT know tool semantics (that's Toolbox).
    """

    def __init__(
        self,
        providers: dict[str, ToolProvider],
        idem_cache: IdempotencyCache,
        default_idem_ttl: int = 86400,  # 24 hours
    ):
        """Initialize gateway.

        Args:
            providers: Map of provider names to provider instances
            idem_cache: Idempotency cache implementation
            default_idem_ttl: Default cache TTL in seconds
        """
        self._providers = providers
        self._idem_cache = idem_cache
        self._default_idem_ttl = default_idem_ttl

    async def execute(self, ctx: ToolExecutionContext) -> ToolResult:
        """Execute tool with idempotency check.

        Args:
            ctx: Execution context with tool details

        Returns:
            Tool execution result
        """
        # Build idempotency key
        business_key = self._extract_business_key(ctx)
        idem_key = ctx.build_idempotency_key(business_key)

        # Check idempotency cache
        cached = await self._idem_cache.get(idem_key)
        if cached:
            logger.info(
                "tool_execution_cache_hit",
                tool_name=ctx.tool_name,
                tenant_id=str(ctx.tenant_id),
                agent_id=str(ctx.agent_id),
            )
            return ToolResult(
                status="success",
                data=cached,
                cached=True,
            )

        # Get provider
        provider = self._providers.get(ctx.gateway)
        if not provider:
            logger.error(
                "tool_gateway_not_found",
                gateway=ctx.gateway,
                tool_name=ctx.tool_name,
                tenant_id=str(ctx.tenant_id),
            )
            return ToolResult(
                status="error",
                error=f"Unknown gateway: {ctx.gateway}",
            )

        # Execute
        start_time = datetime.utcnow()
        try:
            logger.debug(
                "tool_execution_started",
                tool_name=ctx.tool_name,
                gateway=ctx.gateway,
                tenant_id=str(ctx.tenant_id),
                agent_id=str(ctx.agent_id),
            )

            result_data = await provider.call(
                ctx.tool_name,
                ctx.args,
                ctx.gateway_config,
            )

            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            logger.info(
                "tool_execution_completed",
                tool_name=ctx.tool_name,
                gateway=ctx.gateway,
                tenant_id=str(ctx.tenant_id),
                agent_id=str(ctx.agent_id),
                execution_time_ms=execution_time,
            )

            result = ToolResult(
                status="success",
                data=result_data,
                execution_time_ms=execution_time,
            )

            # Cache successful result
            await self._idem_cache.set(
                idem_key,
                result_data,
                ttl=self._default_idem_ttl,
            )

            return result

        except ToolExecutionError as e:
            execution_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            logger.error(
                "tool_execution_failed",
                tool_name=ctx.tool_name,
                error=str(e),
                details=e.details,
                tenant_id=str(ctx.tenant_id),
                agent_id=str(ctx.agent_id),
                execution_time_ms=execution_time,
            )
            return ToolResult(
                status="error",
                error=str(e),
                execution_time_ms=execution_time,
            )

    def _extract_business_key(self, ctx: ToolExecutionContext) -> str:
        """Extract business key from args for idempotency.

        Uses tool's gateway_config to identify key fields.
        Falls back to hashing all args.

        Args:
            ctx: Execution context

        Returns:
            Business key for idempotency
        """
        key_fields = ctx.gateway_config.get("idempotency_key_fields", [])
        if key_fields:
            return ":".join(str(ctx.args.get(f, "")) for f in key_fields)
        else:
            # Fallback: hash all args
            return hashlib.sha256(
                json.dumps(ctx.args, sort_keys=True).encode()
            ).hexdigest()[:16]
