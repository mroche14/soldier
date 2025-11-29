"""Tests for agent management endpoints."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from soldier.alignment.models import Agent, AgentSettings
from soldier.alignment.stores.inmemory import InMemoryConfigStore
from soldier.api.dependencies import get_config_store
from soldier.api.exceptions import SoldierAPIError
from soldier.api.middleware.auth import TenantContextDep, get_tenant_context
from soldier.api.models.context import TenantContext
from soldier.api.models.errors import ErrorBody, ErrorResponse
from soldier.api.routes.agents import router


@pytest.fixture
def tenant_id() -> UUID:
    """Fixed tenant ID for tests."""
    return uuid4()


@pytest.fixture
def tenant_context(tenant_id: UUID) -> TenantContext:
    """Create a test tenant context."""
    return TenantContext(
        tenant_id=str(tenant_id),
        user_id="test-user",
        roles=["admin"],
        tier="enterprise",
    )


@pytest.fixture
def config_store() -> InMemoryConfigStore:
    """Create a fresh in-memory config store."""
    return InMemoryConfigStore()


@pytest.fixture
def app(config_store: InMemoryConfigStore, tenant_context: TenantContext) -> FastAPI:
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(router, tags=["Agents"])

    # Override dependencies
    app.dependency_overrides[get_config_store] = lambda: config_store
    app.dependency_overrides[get_tenant_context] = lambda: tenant_context

    # Register exception handler for SoldierAPIError
    @app.exception_handler(SoldierAPIError)
    async def soldier_api_error_handler(
        request: Request, exc: SoldierAPIError
    ) -> JSONResponse:
        error_body = ErrorBody(code=exc.error_code, message=exc.message)
        response = ErrorResponse(error=error_body)
        return JSONResponse(status_code=exc.status_code, content=response.model_dump())

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestCreateAgent:
    """Tests for POST /agents endpoint."""

    def test_create_agent_success(self, client: TestClient, tenant_id: UUID) -> None:
        """Test creating an agent with valid data."""
        response = client.post(
            "/agents",
            json={
                "name": "Test Agent",
                "description": "A test agent",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Agent"
        assert data["description"] == "A test agent"
        assert data["enabled"] is True
        assert data["current_version"] == 1
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_agent_with_settings(self, client: TestClient) -> None:
        """Test creating an agent with custom settings."""
        response = client.post(
            "/agents",
            json={
                "name": "Custom Agent",
                "settings": {
                    "llm_provider": "anthropic",
                    "llm_model": "claude-3-5-sonnet",
                    "temperature": 0.5,
                    "max_tokens": 2048,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["settings"]["llm_provider"] == "anthropic"
        assert data["settings"]["llm_model"] == "claude-3-5-sonnet"
        assert data["settings"]["temperature"] == 0.5
        assert data["settings"]["max_tokens"] == 2048

    def test_create_agent_minimal(self, client: TestClient) -> None:
        """Test creating an agent with only required fields."""
        response = client.post(
            "/agents",
            json={"name": "Minimal Agent"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Agent"
        assert data["description"] is None

    def test_create_agent_empty_name_fails(self, client: TestClient) -> None:
        """Test that empty name is rejected."""
        response = client.post(
            "/agents",
            json={"name": ""},
        )

        assert response.status_code == 422


class TestGetAgent:
    """Tests for GET /agents/{agent_id} endpoint."""

    def test_get_agent_success(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test retrieving an existing agent."""
        # Create agent directly in store
        agent = Agent.create(
            tenant_id=tenant_id,
            name="Test Agent",
            description="Test description",
        )
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.get(f"/agents/{agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(agent.id)
        assert data["name"] == "Test Agent"
        assert data["description"] == "Test description"

    def test_get_agent_with_stats(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test retrieving agent with stats included."""
        agent = Agent.create(
            tenant_id=tenant_id,
            name="Test Agent",
        )
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.get(f"/agents/{agent.id}?include_stats=true")

        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert data["stats"]["total_sessions"] == 0

    def test_get_nonexistent_agent(self, client: TestClient) -> None:
        """Test retrieving a non-existent agent returns 400."""
        fake_id = uuid4()
        response = client.get(f"/agents/{fake_id}")

        assert response.status_code == 400  # AgentNotFoundError uses 400


class TestUpdateAgent:
    """Tests for PUT /agents/{agent_id} endpoint."""

    def test_update_agent_name(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test updating agent name."""
        agent = Agent.create(tenant_id=tenant_id, name="Original Name")
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.put(
            f"/agents/{agent.id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_agent_enabled(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test disabling an agent."""
        agent = Agent.create(tenant_id=tenant_id, name="Test Agent")
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.put(
            f"/agents/{agent.id}",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    def test_update_agent_settings(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test updating agent settings."""
        agent = Agent.create(tenant_id=tenant_id, name="Test Agent")
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.put(
            f"/agents/{agent.id}",
            json={
                "settings": {
                    "llm_provider": "openai",
                    "temperature": 0.9,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["llm_provider"] == "openai"
        assert data["settings"]["temperature"] == 0.9

    def test_update_nonexistent_agent(self, client: TestClient) -> None:
        """Test updating a non-existent agent returns error."""
        fake_id = uuid4()
        response = client.put(
            f"/agents/{fake_id}",
            json={"name": "New Name"},
        )

        assert response.status_code == 400


class TestDeleteAgent:
    """Tests for DELETE /agents/{agent_id} endpoint."""

    def test_delete_agent_success(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test soft-deleting an agent."""
        agent = Agent.create(tenant_id=tenant_id, name="Test Agent")
        import asyncio
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.delete(f"/agents/{agent.id}")

        assert response.status_code == 204

        # Verify agent is soft-deleted - get_agent returns None for deleted agents
        # so we check the internal store directly
        deleted_agent = config_store._agents.get(agent.id)
        assert deleted_agent is not None
        assert deleted_agent.is_deleted is True

    def test_delete_nonexistent_agent(self, client: TestClient) -> None:
        """Test deleting a non-existent agent returns error."""
        fake_id = uuid4()
        response = client.delete(f"/agents/{fake_id}")

        assert response.status_code == 400


class TestListAgents:
    """Tests for GET /agents endpoint."""

    def test_list_agents_empty(self, client: TestClient) -> None:
        """Test listing agents when none exist."""
        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_agents_with_data(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test listing agents with data."""
        import asyncio

        # Create multiple agents
        for i in range(3):
            agent = Agent.create(
                tenant_id=tenant_id,
                name=f"Agent {i}",
            )
            asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        response = client.get("/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    def test_list_agents_pagination(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test pagination of agents list."""
        import asyncio

        # Create 5 agents
        for i in range(5):
            agent = Agent.create(tenant_id=tenant_id, name=f"Agent {i}")
            asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        # Get first page
        response = client.get("/agents?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True

        # Get second page
        response = client.get("/agents?limit=2&offset=2")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["has_more"] is True

    def test_list_agents_filter_by_enabled(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test filtering agents by enabled status."""
        import asyncio

        # Create enabled and disabled agents
        agent1 = Agent.create(tenant_id=tenant_id, name="Enabled Agent")
        agent2 = Agent.create(tenant_id=tenant_id, name="Disabled Agent")
        agent2.enabled = False
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent1))
        asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent2))

        # Filter by enabled=true
        response = client.get("/agents?enabled=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Enabled Agent"

        # Filter by enabled=false
        response = client.get("/agents?enabled=false")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Disabled Agent"

    def test_list_agents_sorting(
        self, client: TestClient, config_store: InMemoryConfigStore, tenant_id: UUID
    ) -> None:
        """Test sorting agents by name."""
        import asyncio

        # Create agents with different names
        for name in ["Zebra", "Apple", "Mango"]:
            agent = Agent.create(tenant_id=tenant_id, name=name)
            asyncio.get_event_loop().run_until_complete(config_store.save_agent(agent))

        # Sort by name ascending
        response = client.get("/agents?sort_by=name&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        names = [a["name"] for a in data["items"]]
        assert names == ["Apple", "Mango", "Zebra"]

        # Sort by name descending
        response = client.get("/agents?sort_by=name&sort_order=desc")
        data = response.json()
        names = [a["name"] for a in data["items"]]
        assert names == ["Zebra", "Mango", "Apple"]
