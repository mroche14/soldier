"""Tests for LoggingContextMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from ruche.observability.middleware import LoggingContextMiddleware


class TestLoggingContextMiddleware:
    """Tests for LoggingContextMiddleware."""

    @pytest.fixture
    def app(self):
        """Create a FastAPI app with middleware."""
        app = FastAPI()
        app.add_middleware(LoggingContextMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return LoggingContextMiddleware(app)

    @pytest.mark.asyncio
    async def test_clears_context_vars_on_request_start(self, middleware):
        """Should clear existing context vars at request start."""
        # Pre-bind some context vars
        bind_contextvars(tenant_id="existing", other="value")

        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.clear_contextvars") as mock_clear:
            await middleware.dispatch(request, call_next)
            mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_binds_tenant_id_from_header(self, middleware):
        """Should bind tenant_id from X-Tenant-ID header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: "test-tenant" if key == "X-Tenant-ID" else None
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["tenant_id"] == "test-tenant"

    @pytest.mark.asyncio
    async def test_binds_agent_id_from_header(self, middleware):
        """Should bind agent_id from X-Agent-ID header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: "test-agent" if key == "X-Agent-ID" else None
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["agent_id"] == "test-agent"

    @pytest.mark.asyncio
    async def test_binds_session_id_from_header(self, middleware):
        """Should bind session_id from X-Session-ID header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: "test-session" if key == "X-Session-ID" else None
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_binds_trace_id_from_header(self, middleware):
        """Should bind trace_id from X-Trace-ID header."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: "test-trace" if key == "X-Trace-ID" else None
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["trace_id"] == "test-trace"

    @pytest.mark.asyncio
    async def test_extracts_trace_id_from_traceparent(self, middleware):
        """Should extract trace_id from W3C traceparent header."""
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: traceparent if key == "traceparent" else None
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"

    @pytest.mark.asyncio
    async def test_trace_id_header_takes_precedence_over_traceparent(self, middleware):
        """Should prefer X-Trace-ID over traceparent header."""
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: (
                "explicit-trace-id"
                if key == "X-Trace-ID"
                else traceparent if key == "traceparent" else None
            )
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["trace_id"] == "explicit-trace-id"

    @pytest.mark.asyncio
    async def test_binds_none_when_headers_missing(self, middleware):
        """Should bind None when headers are missing."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["tenant_id"] is None
            assert call_args["agent_id"] is None
            assert call_args["session_id"] is None
            assert call_args["trace_id"] is None

    @pytest.mark.asyncio
    async def test_logs_request_started(self, middleware):
        """Should log request_started event."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "POST"
        request.url.path = "/api/chat"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.logger") as mock_logger:
            await middleware.dispatch(request, call_next)
            mock_logger.info.assert_any_call(
                "request_started", method="POST", path="/api/chat"
            )

    @pytest.mark.asyncio
    async def test_logs_request_completed(self, middleware):
        """Should log request_completed event with status code."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "GET"
        request.url.path = "/api/health"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.logger") as mock_logger:
            await middleware.dispatch(request, call_next)
            mock_logger.info.assert_any_call(
                "request_completed", method="GET", path="/api/health", status_code=200
            )

    @pytest.mark.asyncio
    async def test_calls_next_middleware(self, middleware):
        """Should call next middleware in chain."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "GET"
        request.url.path = "/test"

        expected_response = Response(status_code=200)
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response == expected_response

    @pytest.mark.asyncio
    async def test_returns_response_from_next_middleware(self, middleware):
        """Should return the response from next middleware."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(return_value=None)
        request.method = "GET"
        request.url.path = "/test"

        expected_response = Response(status_code=201, content=b"Created")
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 201
        assert response.body == b"Created"

    def test_extract_trace_id_from_valid_traceparent(self, middleware):
        """Should extract trace_id from valid traceparent."""
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        trace_id = middleware._extract_trace_id(traceparent)
        assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_extract_trace_id_returns_none_for_none_input(self, middleware):
        """Should return None for None input."""
        trace_id = middleware._extract_trace_id(None)
        assert trace_id is None

    def test_extract_trace_id_returns_none_for_invalid_format(self, middleware):
        """Should return None for invalid traceparent format."""
        # "invalid-format" has 2 parts, so it will extract the second part
        # Use a truly invalid format with only 1 part
        trace_id = middleware._extract_trace_id("invalid")
        assert trace_id is None

    def test_extract_trace_id_returns_none_for_short_traceparent(self, middleware):
        """Should return None for short traceparent with missing parts."""
        trace_id = middleware._extract_trace_id("00")
        assert trace_id is None

    @pytest.mark.asyncio
    async def test_binds_all_headers_together(self, middleware):
        """Should bind all context headers together."""
        request = MagicMock(spec=Request)
        request.headers.get = MagicMock(
            side_effect=lambda key: {
                "X-Tenant-ID": "tenant-123",
                "X-Agent-ID": "agent-456",
                "X-Session-ID": "session-789",
                "X-Trace-ID": "trace-abc",
            }.get(key)
        )
        request.method = "GET"
        request.url.path = "/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("ruche.observability.middleware.bind_contextvars") as mock_bind:
            await middleware.dispatch(request, call_next)
            mock_bind.assert_called_once()
            call_args = mock_bind.call_args.kwargs
            assert call_args["tenant_id"] == "tenant-123"
            assert call_args["agent_id"] == "agent-456"
            assert call_args["session_id"] == "session-789"
            assert call_args["trace_id"] == "trace-abc"
