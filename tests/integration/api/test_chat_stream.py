"""Integration tests for SSE streaming chat endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ruche.alignment.engine import AlignmentResult
from ruche.alignment.stores.inmemory import InMemoryAgentConfigStore
from ruche.api.app import create_app
from ruche.api.dependencies import (
    get_alignment_engine,
    get_audit_store,
    get_config_store,
    get_session_store,
    get_settings,
    reset_dependencies,
)
from ruche.api.middleware.auth import get_tenant_context
from ruche.api.models.context import TenantContext
from ruche.audit.stores.inmemory import InMemoryAuditStore
from ruche.conversation.stores.inmemory import InMemorySessionStore


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def tenant_context(tenant_id):
    """Test tenant context."""
    return TenantContext(tenant_id=tenant_id, tier="pro")


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock()
    settings.debug = True
    settings.api.cors_origins = ["*"]
    settings.api.cors_allow_credentials = True
    settings.api.rate_limit.enabled = False
    settings.observability.tracing.enabled = False
    return settings


@pytest.fixture
def mock_alignment_engine(tenant_id, agent_id):
    """Mock alignment engine that yields streaming tokens."""
    engine = MagicMock()
    session_id = uuid4()

    async def mock_stream(*_args, **_kwargs):
        """Async generator that yields tokens."""
        tokens = ["Hello", " ", "world", "!"]
        for token in tokens:
            yield token

    engine.process_turn_stream = mock_stream
    engine.process_turn = AsyncMock(
        return_value=AlignmentResult(
            response="Hello world!",
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            user_message="Hello",
        )
    )
    return engine


@pytest.fixture
async def app(
    tenant_context,
    mock_settings,
    mock_alignment_engine,
):
    """Create test FastAPI app."""
    await reset_dependencies()

    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_tenant_context] = lambda: tenant_context
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_config_store] = lambda: InMemoryAgentConfigStore()
    app.dependency_overrides[get_session_store] = lambda: InMemorySessionStore()
    app.dependency_overrides[get_audit_store] = lambda: InMemoryAuditStore()
    app.dependency_overrides[get_alignment_engine] = lambda: mock_alignment_engine

    return app


@pytest.fixture
def client(app):
    """Test client."""
    return TestClient(app)


class TestChatStreamEndpoint:
    """Integration tests for POST /v1/chat/stream endpoint."""

    def test_stream_returns_sse_content_type(
        self,
        client: TestClient,
        tenant_id,
        agent_id,
    ) -> None:
        """Streaming endpoint returns text/event-stream content type."""
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "test@example.com",
                "message": "Hello",
            },
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_emits_token_events(
        self,
        client: TestClient,
        tenant_id,
        agent_id,
    ) -> None:
        """Streaming endpoint emits token events."""
        events = []
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "test@example.com",
                "message": "Hello",
            },
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)

        # Should have token events
        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) > 0

    def test_stream_ends_with_done_event(
        self,
        client: TestClient,
        tenant_id,
        agent_id,
    ) -> None:
        """Streaming endpoint ends with done event."""
        events = []
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "test@example.com",
                "message": "Hello",
            },
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)

        # Last event should be done
        assert len(events) > 0
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1

    def test_done_event_includes_metadata(
        self,
        client: TestClient,
        tenant_id,
        agent_id,
    ) -> None:
        """Done event includes turn_id and session_id."""
        events = []
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "test@example.com",
                "message": "Hello",
            },
        ) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    events.append(data)

        done_event = next((e for e in events if e.get("type") == "done"), None)
        assert done_event is not None
        assert "turn_id" in done_event
        assert "session_id" in done_event

    def test_stream_invalid_request_returns_error(
        self,
        client: TestClient,
    ) -> None:
        """Invalid request returns error response."""
        response = client.post(
            "/v1/chat/stream",
            json={
                "message": "Hello",
                # Missing required fields
            },
        )

        assert response.status_code == 400
