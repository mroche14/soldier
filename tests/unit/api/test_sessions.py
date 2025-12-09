"""Unit tests for session management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from focal.api.dependencies import (
    get_audit_store,
    get_session_store,
    get_settings,
    reset_dependencies,
)
from focal.api.exceptions import FocalAPIError
from focal.api.middleware.auth import get_tenant_context
from focal.api.models.context import TenantContext
from focal.api.models.errors import ErrorBody, ErrorResponse
from focal.api.routes.sessions import router
from focal.audit.models import TurnRecord
from focal.conversation.models import Channel, Session
from focal.conversation.models.turn import ToolCall


@pytest.fixture
def tenant_id() -> UUID:
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id() -> UUID:
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def tenant_context(tenant_id: UUID) -> TenantContext:
    """Test tenant context."""
    return TenantContext(tenant_id=tenant_id, tier="pro")


@pytest.fixture
def session(tenant_id: UUID, agent_id: UUID) -> Session:
    """Test session."""
    return Session(
        session_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=Channel.WEBCHAT,
        user_channel_id="test@example.com",
        config_version=1,
        turn_count=3,
        variables={"user_name": "Test User"},
    )


@pytest.fixture
def turn_records(session: Session, tenant_id: UUID) -> list[TurnRecord]:
    """Test turn records."""
    now = datetime.now(UTC)
    return [
        TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=session.agent_id,
            session_id=session.session_id,
            turn_number=1,
            user_message="Hello",
            agent_response="Hi there!",
            matched_rule_ids=[uuid4()],
            tool_calls=[
                ToolCall(
                    tool_id="tool_1",
                    tool_name="greeting_tool",
                    input={},
                    output="Hello!",
                    success=True,
                    latency_ms=50,
                )
            ],
            latency_ms=150,
            tokens_used=50,
            timestamp=now,
        ),
        TurnRecord(
            turn_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=session.agent_id,
            session_id=session.session_id,
            turn_number=2,
            user_message="How are you?",
            agent_response="I'm doing well!",
            matched_rule_ids=[],
            tool_calls=[],
            latency_ms=120,
            tokens_used=40,
            timestamp=now,
        ),
    ]


@pytest.fixture
def mock_session_store(session: Session) -> MagicMock:
    """Mock session store."""
    store = MagicMock()
    store.get = AsyncMock(return_value=session)
    store.delete = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_audit_store(turn_records: list[TurnRecord]) -> MagicMock:
    """Mock audit store."""
    store = MagicMock()
    store.list_turns_by_session = AsyncMock(return_value=turn_records)
    return store


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock settings."""
    settings = MagicMock()
    settings.debug = False
    return settings


@pytest.fixture
async def app(
    tenant_context: TenantContext,
    mock_session_store: MagicMock,
    mock_audit_store: MagicMock,
    mock_settings: MagicMock,
) -> FastAPI:
    """Create test FastAPI app."""
    await reset_dependencies()

    app = FastAPI()
    app.include_router(router)

    # Register exception handler for FocalAPIError
    @app.exception_handler(FocalAPIError)
    async def focal_api_error_handler(
        _request, exc: FocalAPIError
    ) -> JSONResponse:
        error_body = ErrorBody(
            code=exc.error_code,
            message=exc.message,
        )
        response = ErrorResponse(error=error_body)
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )

    # Override dependencies
    app.dependency_overrides[get_tenant_context] = lambda: tenant_context
    app.dependency_overrides[get_session_store] = lambda: mock_session_store
    app.dependency_overrides[get_audit_store] = lambda: mock_audit_store
    app.dependency_overrides[get_settings] = lambda: mock_settings

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client."""
    return TestClient(app, raise_server_exceptions=False)


class TestGetSession:
    """Tests for GET /sessions/{session_id} endpoint."""

    def test_get_session_returns_session(
        self,
        client: TestClient,
        session: Session,
        mock_session_store: MagicMock,
    ) -> None:
        """Successfully retrieves a session."""
        response = client.get(f"/sessions/{session.session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == str(session.session_id)
        assert data["tenant_id"] == str(session.tenant_id)
        assert data["agent_id"] == str(session.agent_id)
        assert data["channel"] == "webchat"
        assert data["turn_count"] == 3
        assert data["variables"]["user_name"] == "Test User"

    def test_get_session_not_found(
        self,
        client: TestClient,
        mock_session_store: MagicMock,
    ) -> None:
        """Returns 404 when session doesn't exist."""
        mock_session_store.get = AsyncMock(return_value=None)

        response = client.get(f"/sessions/{uuid4()}")

        assert response.status_code == 404

    def test_get_session_invalid_uuid(self, client: TestClient) -> None:
        """Returns 404 for invalid session ID."""
        response = client.get("/sessions/not-a-uuid")

        assert response.status_code == 404

    def test_get_session_wrong_tenant(
        self,
        client: TestClient,
        session: Session,
        mock_session_store: MagicMock,
    ) -> None:
        """Returns 404 when session belongs to different tenant."""
        # Create session with different tenant
        other_session = Session(
            session_id=session.session_id,
            tenant_id=uuid4(),  # Different tenant
            agent_id=session.agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="test@example.com",
            config_version=1,
        )
        mock_session_store.get = AsyncMock(return_value=other_session)

        response = client.get(f"/sessions/{session.session_id}")

        assert response.status_code == 404


class TestDeleteSession:
    """Tests for DELETE /sessions/{session_id} endpoint."""

    def test_delete_session_success(
        self,
        client: TestClient,
        session: Session,
        mock_session_store: MagicMock,
    ) -> None:
        """Successfully deletes a session."""
        response = client.delete(f"/sessions/{session.session_id}")

        assert response.status_code == 204
        mock_session_store.delete.assert_called_once_with(session.session_id)

    def test_delete_session_not_found(
        self,
        client: TestClient,
        mock_session_store: MagicMock,
    ) -> None:
        """Returns 404 when session doesn't exist."""
        mock_session_store.get = AsyncMock(return_value=None)

        response = client.delete(f"/sessions/{uuid4()}")

        assert response.status_code == 404

    def test_delete_session_invalid_uuid(self, client: TestClient) -> None:
        """Returns 404 for invalid session ID."""
        response = client.delete("/sessions/not-a-uuid")

        assert response.status_code == 404

    def test_delete_session_wrong_tenant(
        self,
        client: TestClient,
        session: Session,
        mock_session_store: MagicMock,
    ) -> None:
        """Returns 404 when session belongs to different tenant."""
        other_session = Session(
            session_id=session.session_id,
            tenant_id=uuid4(),  # Different tenant
            agent_id=session.agent_id,
            channel=Channel.WEBCHAT,
            user_channel_id="test@example.com",
            config_version=1,
        )
        mock_session_store.get = AsyncMock(return_value=other_session)

        response = client.delete(f"/sessions/{session.session_id}")

        assert response.status_code == 404
        mock_session_store.delete.assert_not_called()


class TestGetSessionTurns:
    """Tests for GET /sessions/{session_id}/turns endpoint."""

    def test_get_turns_returns_list(
        self,
        client: TestClient,
        session: Session,
        turn_records: list[TurnRecord],
    ) -> None:
        """Successfully retrieves turns."""
        response = client.get(f"/sessions/{session.session_id}/turns")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_get_turns_with_pagination(
        self,
        client: TestClient,
        session: Session,
        mock_audit_store: MagicMock,
    ) -> None:
        """Pagination parameters work correctly."""
        response = client.get(
            f"/sessions/{session.session_id}/turns",
            params={"limit": 10, "offset": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5
        mock_audit_store.list_turns_by_session.assert_called_once()

    def test_get_turns_asc_sort(
        self,
        client: TestClient,
        session: Session,
        turn_records: list[TurnRecord],
    ) -> None:
        """Ascending sort returns oldest first."""
        response = client.get(
            f"/sessions/{session.session_id}/turns",
            params={"sort": "asc"},
        )

        assert response.status_code == 200
        data = response.json()
        # First turn should be oldest
        assert data["items"][0]["user_message"] == "Hello"

    def test_get_turns_desc_sort(
        self,
        client: TestClient,
        session: Session,
        turn_records: list[TurnRecord],
    ) -> None:
        """Descending sort returns newest first."""
        response = client.get(
            f"/sessions/{session.session_id}/turns",
            params={"sort": "desc"},
        )

        assert response.status_code == 200
        data = response.json()
        # First turn should be newest (reversed)
        assert data["items"][0]["user_message"] == "How are you?"

    def test_get_turns_session_not_found(
        self,
        client: TestClient,
        mock_session_store: MagicMock,
    ) -> None:
        """Returns 404 when session doesn't exist."""
        mock_session_store.get = AsyncMock(return_value=None)

        response = client.get(f"/sessions/{uuid4()}/turns")

        assert response.status_code == 404

    def test_get_turns_invalid_limit(
        self,
        client: TestClient,
        session: Session,
    ) -> None:
        """Invalid limit parameter returns error."""
        response = client.get(
            f"/sessions/{session.session_id}/turns",
            params={"limit": 200},  # Max is 100
        )

        assert response.status_code == 422

    def test_get_turns_has_more_flag(
        self,
        client: TestClient,
        session: Session,
        mock_audit_store: MagicMock,
        turn_records: list[TurnRecord],
    ) -> None:
        """has_more flag correctly indicates more results."""
        # Return more turns than limit
        extra_turn = TurnRecord(
            turn_id=uuid4(),
            tenant_id=session.tenant_id,
            agent_id=session.agent_id,
            session_id=session.session_id,
            turn_number=3,
            user_message="Extra",
            agent_response="Extra response",
            matched_rule_ids=[],
            tool_calls=[],
            latency_ms=100,
            tokens_used=30,
            timestamp=datetime.now(UTC),
        )
        mock_audit_store.list_turns_by_session = AsyncMock(
            return_value=turn_records + [extra_turn]
        )

        response = client.get(
            f"/sessions/{session.session_id}/turns",
            params={"limit": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["has_more"] is True
        assert len(data["items"]) == 2
