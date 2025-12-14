"""Request context middleware for observability."""

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from ruche.api.models.context import RequestContext
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

# Context variable for request context - accessible throughout request lifecycle
_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_request_context() -> RequestContext | None:
    """Get the current request context.

    Returns:
        The RequestContext for the current request, or None if not in a request.
    """
    return _request_context.get()


def set_request_context(context: RequestContext) -> None:
    """Set the request context for the current request.

    Args:
        context: The RequestContext to set
    """
    _request_context.set(context)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that binds request context for observability.

    Creates a RequestContext at the start of each request and makes it
    available via context variable for logging and tracing.
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and bind context."""
        # Get trace context from OpenTelemetry
        span = trace.get_current_span()
        span_context = span.get_span_context()

        trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else ""
        span_id = format(span_context.span_id, "016x") if span_context.is_valid else ""

        # Generate request ID
        request_id = str(uuid.uuid4())

        # Create request context
        context = RequestContext(
            trace_id=trace_id or request_id,
            span_id=span_id or "",
            request_id=request_id,
        )

        # Set in context var for access throughout request
        set_request_context(context)

        # Store on request state for direct access
        request.state.context = context

        # Bind context to logger
        logger.bind(
            trace_id=context.trace_id,
            request_id=context.request_id,
        )

        logger.debug(
            "request_started",
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)  # type: ignore[misc]

        logger.debug(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

        # Add trace headers to response
        response.headers["X-Request-ID"] = context.request_id
        if context.trace_id:
            response.headers["X-Trace-ID"] = context.trace_id

        return response  # type: ignore[no-any-return]


def update_request_context(
    *,
    tenant_id: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> None:
    """Update the current request context with additional identifiers.

    Called during request processing to add context as it becomes available.

    Args:
        tenant_id: Tenant identifier
        agent_id: Agent identifier
        session_id: Session identifier
        turn_id: Turn identifier
    """
    current = get_request_context()
    if not current:
        return

    # Create updated context (RequestContext is not frozen so we can update)
    from uuid import UUID

    if tenant_id:
        current.tenant_id = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
    if agent_id:
        current.agent_id = UUID(agent_id) if isinstance(agent_id, str) else agent_id
    if session_id:
        current.session_id = session_id
    if turn_id:
        current.turn_id = turn_id

    # Re-bind logger with updated context
    logger.bind(
        tenant_id=str(current.tenant_id) if current.tenant_id else None,
        agent_id=str(current.agent_id) if current.agent_id else None,
        session_id=current.session_id,
        turn_id=current.turn_id,
    )
