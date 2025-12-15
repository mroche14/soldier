"""Unit tests for health check endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ruche.brains.focal.stores.inmemory import InMemoryAgentConfigStore
from ruche.api.dependencies import (
    get_audit_store,
    get_config_store,
    get_session_store,
    get_settings,
    reset_dependencies,
)
from ruche.api.routes.health import router
from ruche.audit.stores.inmemory import InMemoryAuditStore
from ruche.conversation.stores.inmemory import InMemorySessionStore


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock settings."""
    settings = MagicMock()
    settings.debug = False
    return settings


@pytest.fixture
def config_store() -> InMemoryAgentConfigStore:
    """In-memory config store."""
    return InMemoryAgentConfigStore()


@pytest.fixture
def session_store() -> InMemorySessionStore:
    """In-memory session store."""
    return InMemorySessionStore()


@pytest.fixture
def audit_store() -> InMemoryAuditStore:
    """In-memory audit store."""
    return InMemoryAuditStore()


@pytest.fixture
async def app(
    mock_settings: MagicMock,
    config_store: InMemoryAgentConfigStore,
    session_store: InMemorySessionStore,
    audit_store: InMemoryAuditStore,
) -> FastAPI:
    """Create test FastAPI app."""
    await reset_dependencies()

    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_config_store] = lambda: config_store
    app.dependency_overrides[get_session_store] = lambda: session_store
    app.dependency_overrides[get_audit_store] = lambda: audit_store

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_200_when_healthy(self, client: TestClient) -> None:
        """Health check returns 200 when all components healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
        assert "components" in data

    def test_health_includes_component_status(self, client: TestClient) -> None:
        """Health check includes status for each component."""
        response = client.get("/health")

        data = response.json()
        components = data["components"]

        # Should have config, session, and audit stores
        component_names = [c["name"] for c in components]
        assert "config_store" in component_names
        assert "session_store" in component_names
        assert "audit_store" in component_names

        # All should be healthy
        for component in components:
            assert component["status"] == "healthy"

    def test_health_includes_version(self, client: TestClient) -> None:
        """Health check includes service version."""
        response = client.get("/health")

        data = response.json()
        assert data["version"] == "1.0.0"


class TestMetricsEndpoint:
    """Tests for GET /metrics endpoint."""

    def test_metrics_returns_prometheus_format(self, client: TestClient) -> None:
        """Metrics endpoint returns Prometheus format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_content_has_prometheus_markers(
        self, client: TestClient
    ) -> None:
        """Metrics content has typical Prometheus markers."""
        response = client.get("/metrics")

        content = response.text
        # Should have some metrics (python_info is always present)
        assert len(content) > 0
