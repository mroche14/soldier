"""Unit tests for chat endpoint."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ruche.alignment.engine import AlignmentEngine
from ruche.alignment.result import AlignmentResult
from ruche.api.dependencies import (
    get_alignment_engine,
    get_session_store,
    get_settings,
    reset_dependencies,
)
from ruche.api.middleware.auth import get_tenant_context
from ruche.api.models.context import TenantContext
from ruche.api.routes.chat import router
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.stores.inmemory import InMemorySessionStore


@pytest.fixture
def tenant_id() -> UUID:
    """Test tenant ID."""
    return UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def agent_id() -> UUID:
    """Test agent ID."""
    return UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@pytest.fixture
def tenant_context(tenant_id: UUID) -> TenantContext:
    """Test tenant context."""
    return TenantContext(
        tenant_id=tenant_id,
        user_id="test_user",
        roles=["user"],
        tier="pro",
    )


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock settings."""
    settings = MagicMock()
    settings.debug = False
    settings.api.rate_limit.enabled = False
    return settings


@pytest.fixture
def session_store() -> InMemorySessionStore:
    """In-memory session store."""
    return InMemorySessionStore()


@pytest.fixture
def mock_engine(tenant_id: UUID, agent_id: UUID) -> AsyncMock:
    """Mock alignment engine."""
    engine = AsyncMock(spec=AlignmentEngine)

    # Create a mock result
    result = AlignmentResult(
        turn_id=uuid4(),
        session_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        user_message="Hello",
        response="Hello! How can I help you?",
        matched_rules=[],
        tool_results=[],
        total_time_ms=100.0,
    )

    engine.process_turn.return_value = result
    return engine


@pytest.fixture
async def app(
    tenant_context: TenantContext,
    mock_settings: MagicMock,
    session_store: InMemorySessionStore,
    mock_engine: AsyncMock,
) -> FastAPI:
    """Create test FastAPI app."""
    await reset_dependencies()

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    # Register exception handlers from app module
    from ruche.api.app import _register_exception_handlers

    _register_exception_handlers(app)

    # Override dependencies
    app.dependency_overrides[get_tenant_context] = lambda: tenant_context
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_session_store] = lambda: session_store
    app.dependency_overrides[get_alignment_engine] = lambda: mock_engine

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client."""
    return TestClient(app)


class TestChatEndpoint:
    """Tests for POST /v1/chat endpoint."""

    def test_chat_creates_session_when_not_provided(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
        mock_engine: AsyncMock,
    ) -> None:
        """Chat without session_id creates a new session."""
        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "turn_id" in data
        assert "response" in data
        assert data["response"] == "Hello! How can I help you?"

    def test_chat_uses_existing_session(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
        session_store: InMemorySessionStore,
        mock_engine: AsyncMock,
    ) -> None:
        """Chat with session_id uses existing session."""
        # Create a session first
        import asyncio

        session = Session(
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="user123",
            config_version=1,
            status=SessionStatus.ACTIVE,
        )
        asyncio.get_event_loop().run_until_complete(session_store.save(session))

        # Update mock to return result with this session ID
        mock_engine.process_turn.return_value.session_id = session.session_id

        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
                "session_id": str(session.session_id),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == str(session.session_id)

    def test_chat_returns_matched_rules(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
        mock_engine: AsyncMock,
    ) -> None:
        """Chat response includes matched rules."""
        from ruche.alignment.filtering.models import MatchedRule
        from tests.factories.alignment import RuleFactory

        # Add matched rules to the result
        rule1 = RuleFactory.create(tenant_id=tenant_id, agent_id=agent_id)
        rule2 = RuleFactory.create(tenant_id=tenant_id, agent_id=agent_id)
        mock_engine.process_turn.return_value.matched_rules = [
            MatchedRule(rule=rule1, match_score=0.9, relevance_score=0.8),
            MatchedRule(rule=rule2, match_score=0.7, relevance_score=0.6),
        ]

        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["matched_rules"]) == 2

    def test_chat_returns_latency(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Chat response includes latency_ms."""
        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "latency_ms" in data
        assert data["latency_ms"] >= 0

    def test_chat_invalid_request_returns_400(
        self,
        client: TestClient,
        tenant_id: UUID,
    ) -> None:
        """Invalid request returns 400 error."""
        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                # Missing required fields
            },
        )

        assert response.status_code == 400  # Validation error (our exception handler returns 400)

    def test_chat_session_not_found_returns_404(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Non-existent session_id returns 404."""
        response = client.post(
            "/v1/chat",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
                "session_id": str(uuid4()),  # Non-existent session
            },
        )

        assert response.status_code == 404


class TestChatStreamEndpoint:
    """Tests for POST /v1/chat/stream endpoint."""

    def test_stream_returns_sse(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Stream endpoint returns SSE response."""
        response = client.post(
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_emits_token_events(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Stream emits token events with content."""
        response = client.post(
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        content = response.text
        assert "event: token" in content
        assert "event: done" in content

    def test_stream_ends_with_done_event(
        self,
        client: TestClient,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Stream ends with done event containing metadata."""
        response = client.post(
            "/v1/chat/stream",
            json={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "channel": "webchat",
                "user_channel_id": "user123",
                "message": "Hello",
            },
        )

        content = response.text
        # Check that done event is present with expected fields
        assert "event: done" in content
        assert "turn_id" in content
        assert "session_id" in content
