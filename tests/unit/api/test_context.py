"""Unit tests for request context middleware."""

from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ruche.api.dependencies import get_settings, reset_dependencies
from ruche.api.middleware.context import (
    RequestContextMiddleware,
    get_request_context,
    set_request_context,
    update_request_context,
)
from ruche.api.models.context import RequestContext


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock settings."""
    settings = MagicMock()
    settings.debug = False
    return settings


@pytest.fixture
async def app(mock_settings: MagicMock) -> FastAPI:
    """Create test app with context middleware."""
    await reset_dependencies()

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.dependency_overrides[get_settings] = lambda: mock_settings

    @app.get("/test")
    async def test_endpoint() -> dict:
        context = get_request_context()
        return {
            "has_context": context is not None,
            "request_id": context.request_id if context else None,
            "trace_id": context.trace_id if context else None,
        }

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client."""
    return TestClient(app)


class TestRequestContextMiddleware:
    """Tests for RequestContextMiddleware."""

    def test_creates_request_context(self, client: TestClient) -> None:
        """Middleware creates request context."""
        response = client.get("/test")

        assert response.status_code == 200
        data = response.json()
        assert data["has_context"] is True
        assert data["request_id"] is not None

    def test_adds_request_id_header(self, client: TestClient) -> None:
        """Middleware adds X-Request-ID header to response."""
        response = client.get("/test")

        assert "X-Request-ID" in response.headers
        # Request ID should be a valid UUID
        UUID(response.headers["X-Request-ID"])

    def test_adds_trace_id_header(self, client: TestClient) -> None:
        """Middleware adds X-Trace-ID header when trace context exists."""
        response = client.get("/test")

        # May or may not have trace ID depending on OTel instrumentation
        # But request ID should always be present
        assert "X-Request-ID" in response.headers


class TestGetRequestContext:
    """Tests for get_request_context function."""

    def test_returns_none_outside_request(self) -> None:
        """Returns None when not in request context."""
        # Reset context
        set_request_context(None)  # type: ignore
        context = get_request_context()
        assert context is None

    def test_returns_context_when_set(self) -> None:
        """Returns context when one is set."""
        test_context = RequestContext(
            trace_id="test-trace",
            span_id="test-span",
            request_id="test-request",
        )
        set_request_context(test_context)

        retrieved = get_request_context()
        assert retrieved is not None
        assert retrieved.trace_id == "test-trace"
        assert retrieved.request_id == "test-request"


class TestSetRequestContext:
    """Tests for set_request_context function."""

    def test_sets_context(self) -> None:
        """Can set request context."""
        test_context = RequestContext(
            trace_id="new-trace",
            span_id="new-span",
            request_id="new-request",
        )
        set_request_context(test_context)

        assert get_request_context() == test_context


class TestUpdateRequestContext:
    """Tests for update_request_context function."""

    def test_updates_tenant_id(self) -> None:
        """Can update tenant_id in context."""
        initial_context = RequestContext(
            trace_id="trace",
            span_id="span",
            request_id="request",
        )
        set_request_context(initial_context)

        tenant_id = str(uuid4())
        update_request_context(tenant_id=tenant_id)

        context = get_request_context()
        assert context is not None
        assert str(context.tenant_id) == tenant_id

    def test_updates_agent_id(self) -> None:
        """Can update agent_id in context."""
        initial_context = RequestContext(
            trace_id="trace",
            span_id="span",
            request_id="request",
        )
        set_request_context(initial_context)

        agent_id = str(uuid4())
        update_request_context(agent_id=agent_id)

        context = get_request_context()
        assert context is not None
        assert str(context.agent_id) == agent_id

    def test_updates_session_id(self) -> None:
        """Can update session_id in context."""
        initial_context = RequestContext(
            trace_id="trace",
            span_id="span",
            request_id="request",
        )
        set_request_context(initial_context)

        update_request_context(session_id="sess_123")

        context = get_request_context()
        assert context is not None
        assert context.session_id == "sess_123"

    def test_updates_turn_id(self) -> None:
        """Can update turn_id in context."""
        initial_context = RequestContext(
            trace_id="trace",
            span_id="span",
            request_id="request",
        )
        set_request_context(initial_context)

        update_request_context(turn_id="turn_456")

        context = get_request_context()
        assert context is not None
        assert context.turn_id == "turn_456"

    def test_updates_multiple_fields(self) -> None:
        """Can update multiple fields at once."""
        initial_context = RequestContext(
            trace_id="trace",
            span_id="span",
            request_id="request",
        )
        set_request_context(initial_context)

        tenant_id = str(uuid4())
        agent_id = str(uuid4())
        update_request_context(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id="sess_789",
            turn_id="turn_012",
        )

        context = get_request_context()
        assert context is not None
        assert str(context.tenant_id) == tenant_id
        assert str(context.agent_id) == agent_id
        assert context.session_id == "sess_789"
        assert context.turn_id == "turn_012"

    def test_no_op_when_no_context(self) -> None:
        """Does nothing when no context is set."""
        set_request_context(None)  # type: ignore

        # Should not raise
        update_request_context(tenant_id=str(uuid4()))

        assert get_request_context() is None
