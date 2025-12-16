"""Logging context middleware for observability.

Binds tenant_id, agent_id, session_id, and trace_id to structlog contextvars
for the duration of each request.
"""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Middleware that binds request context to structlog contextvars.

    Extracts tenant_id, agent_id, session_id, and trace_id from request headers
    and binds them to structlog contextvars for automatic inclusion in all logs
    within the request lifecycle.

    Headers:
        X-Tenant-ID: Tenant identifier
        X-Agent-ID: Agent identifier
        X-Session-ID: Session identifier
        X-Trace-ID: Distributed trace identifier
        traceparent: W3C trace context (fallback for trace_id)
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and bind logging context."""
        # Clear any existing context vars
        clear_contextvars()

        # Extract identifiers from headers
        tenant_id = request.headers.get("X-Tenant-ID")
        agent_id = request.headers.get("X-Agent-ID")
        session_id = request.headers.get("X-Session-ID")
        trace_id = request.headers.get("X-Trace-ID") or self._extract_trace_id(
            request.headers.get("traceparent")
        )

        # Bind context variables for all logs in this request
        bind_contextvars(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            trace_id=trace_id,
        )

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)  # type: ignore[misc]

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

        return response  # type: ignore[no-any-return]

    @staticmethod
    def _extract_trace_id(traceparent: str | None) -> str | None:
        """Extract trace_id from W3C traceparent header.

        Format: version-trace_id-parent_id-trace_flags
        Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

        Args:
            traceparent: W3C traceparent header value

        Returns:
            Extracted trace_id or None
        """
        if not traceparent:
            return None
        parts = traceparent.split("-")
        return parts[1] if len(parts) >= 2 else None
