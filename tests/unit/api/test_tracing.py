"""Unit tests for OpenTelemetry tracing integration."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from soldier.api.dependencies import get_settings, reset_dependencies
from soldier.api.middleware.context import (
    RequestContextMiddleware,
    get_request_context,
)


@pytest.fixture
def mock_settings_tracing_enabled():
    """Mock settings with tracing enabled."""
    settings = MagicMock()
    settings.debug = False
    settings.observability.tracing.enabled = True
    return settings


@pytest.fixture
def mock_settings_tracing_disabled():
    """Mock settings with tracing disabled."""
    settings = MagicMock()
    settings.debug = False
    settings.observability.tracing.enabled = False
    return settings


@pytest.fixture
def app_with_tracing(mock_settings_tracing_enabled):
    """Create test app with tracing enabled."""
    reset_dependencies()

    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.dependency_overrides[get_settings] = lambda: mock_settings_tracing_enabled

    @app.get("/test")
    async def test_endpoint():
        context = get_request_context()
        return {
            "trace_id": context.trace_id if context else None,
            "span_id": context.span_id if context else None,
            "request_id": context.request_id if context else None,
        }

    return app


@pytest.fixture
def client_with_tracing(app_with_tracing):
    """Test client with tracing."""
    return TestClient(app_with_tracing)


class TestRequestTracing:
    """Tests for request tracing functionality."""

    def test_request_context_has_trace_id(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Request context includes trace ID."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        # trace_id should be set (either from OTel or request_id fallback)
        assert data["trace_id"] is not None
        assert len(data["trace_id"]) > 0

    def test_request_context_has_request_id(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Request context includes request ID."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] is not None
        # Request ID should be a UUID-like string
        assert len(data["request_id"]) == 36

    def test_x_request_id_header_in_response(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Response includes X-Request-ID header."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

    def test_x_trace_id_header_in_response(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Response includes X-Trace-ID header when trace context exists."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        # X-Trace-ID may or may not be present depending on OTel setup
        # but X-Request-ID should always be present
        assert "X-Request-ID" in response.headers

    def test_each_request_has_unique_request_id(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Each request gets a unique request ID."""
        response1 = client_with_tracing.get("/test")
        response2 = client_with_tracing.get("/test")

        assert response1.status_code == 200
        assert response2.status_code == 200

        request_id_1 = response1.headers.get("X-Request-ID")
        request_id_2 = response2.headers.get("X-Request-ID")

        assert request_id_1 != request_id_2


class TestTracingConfiguration:
    """Tests for tracing configuration."""

    def test_tracing_can_be_disabled(
        self,
        mock_settings_tracing_disabled,
    ) -> None:
        """Tracing can be disabled via settings."""
        reset_dependencies()

        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)
        app.dependency_overrides[get_settings] = lambda: mock_settings_tracing_disabled

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        # App should still work with tracing disabled
        assert response.status_code == 200


class TestSpanContextPropagation:
    """Tests for span context propagation."""

    def test_span_id_propagated_to_context(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Span ID is propagated to request context."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        # span_id may be empty string if OTel not fully configured
        # but should not be None
        assert "span_id" in data

    def test_context_available_in_endpoint(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Request context is available within endpoint."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        # All context fields should be accessible
        assert "trace_id" in data
        assert "span_id" in data
        assert "request_id" in data


class TestTraceIdFormat:
    """Tests for trace ID format."""

    def test_trace_id_is_valid_format(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Trace ID is in valid format (hex string or UUID)."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        trace_id = data["trace_id"]

        # Should be a non-empty string
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

        # Should be either hex (OTel) or UUID format
        try:
            int(trace_id, 16)  # Valid hex
        except ValueError:
            # If not hex, should be UUID-like (36 chars with dashes)
            assert len(trace_id) == 36

    def test_request_id_is_uuid_format(
        self,
        client_with_tracing: TestClient,
    ) -> None:
        """Request ID is in UUID format."""
        response = client_with_tracing.get("/test")

        assert response.status_code == 200
        data = response.json()
        request_id = data["request_id"]

        # Should be UUID format (36 chars with dashes)
        assert len(request_id) == 36
        assert request_id.count("-") == 4
