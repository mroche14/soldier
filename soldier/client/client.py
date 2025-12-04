"""Soldier API client.

Provides a Python client for interacting with the Soldier API.

Usage:
    from soldier.client import SoldierClient

    # With JWT token (production)
    async with SoldierClient(token="eyJ...") as client:
        agent = await client.create_agent(name="My Agent")

    # With dev mode (generates token from secret)
    async with SoldierClient.dev(tenant_id="my-tenant") as client:
        agent = await client.create_agent(name="My Agent")
        response = await client.chat(agent.id, "Hello!")
        print(response.response)
"""

import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx

from soldier.api.models.chat import ChatRequest, ChatResponse
from soldier.api.models.crud import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioUpdate,
    StepCreate,
    StepResponse,
    StepUpdate,
    TemplateCreate,
    TemplateResponse,
    VariableCreate,
    VariableResponse,
)
from soldier.api.models.health import HealthResponse


class SoldierClientError(Exception):
    """Base exception for client errors."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class SoldierClient:
    """Async client for the Soldier API.

    Attributes:
        base_url: Base URL of the Soldier API
        tenant_id: Default tenant ID for requests
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        tenant_id: str | UUID | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the client.

        Args:
            base_url: Base URL of the Soldier API
            tenant_id: Default tenant ID for all requests
            token: JWT authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.tenant_id = str(tenant_id) if tenant_id else None
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
        )

    @classmethod
    def dev(
        cls,
        tenant_id: str | UUID,
        base_url: str = "http://localhost:8000",
        secret: str | None = None,
        timeout: float = 30.0,
    ) -> "SoldierClient":
        """Create a client with a dev token for local testing.

        Generates a JWT token using the provided secret or SOLDIER_JWT_SECRET env var.

        Args:
            tenant_id: Tenant ID for the token
            base_url: Base URL of the Soldier API
            secret: JWT secret (defaults to SOLDIER_JWT_SECRET env var)
            timeout: Request timeout in seconds

        Returns:
            Configured SoldierClient with auth token
        """
        from jose import jwt

        jwt_secret = secret or os.environ.get("SOLDIER_JWT_SECRET")
        if not jwt_secret:
            raise SoldierClientError("SOLDIER_JWT_SECRET not set for dev mode")

        token = jwt.encode(
            {
                "tenant_id": str(tenant_id),
                "sub": "dev-user",
                "roles": ["admin"],
                "tier": "enterprise",
            },
            jwt_secret,
            algorithm="HS256",
        )

        return cls(
            base_url=base_url,
            tenant_id=tenant_id,
            token=token,
            timeout=timeout,
        )

    async def __aenter__(self) -> "SoldierClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _headers(self, tenant_id: str | UUID | None = None) -> dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}

        # Add authentication token
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        # Add tenant ID header (for some endpoints that use it)
        tid = tenant_id or self.tenant_id
        if tid:
            headers["X-Tenant-ID"] = str(tid)

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        tenant_id: str | UUID | None = None,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an API request."""
        response = await self._client.request(
            method=method,
            url=path,
            headers=self._headers(tenant_id),
            json=json,
            params=params,
        )

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", {}).get("message", response.text)
            except Exception:
                message = response.text

            raise SoldierClientError(
                message=message,
                status_code=response.status_code,
                details=error_data if "error_data" in dir() else None,
            )

        if response.status_code == 204:
            return {}

        return response.json()

    # Health
    async def health(self) -> HealthResponse:
        """Check API health."""
        data = await self._request("GET", "/health")
        return HealthResponse.model_validate(data)

    # Agents
    async def list_agents(self, tenant_id: str | UUID | None = None) -> list[AgentResponse]:
        """List all agents."""
        data = await self._request("GET", "/v1/agents", tenant_id=tenant_id)
        return [AgentResponse.model_validate(a) for a in data.get("agents", [])]

    async def get_agent(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> AgentResponse:
        """Get an agent by ID."""
        data = await self._request("GET", f"/v1/agents/{agent_id}", tenant_id=tenant_id)
        return AgentResponse.model_validate(data)

    async def create_agent(
        self,
        name: str,
        description: str | None = None,
        tenant_id: str | UUID | None = None,
    ) -> AgentResponse:
        """Create a new agent."""
        payload = AgentCreate(name=name, description=description)
        data = await self._request(
            "POST",
            "/v1/agents",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return AgentResponse.model_validate(data)

    async def update_agent(
        self,
        agent_id: str | UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        tenant_id: str | UUID | None = None,
    ) -> AgentResponse:
        """Update an agent."""
        payload = AgentUpdate(name=name, description=description, enabled=enabled)
        data = await self._request(
            "PUT",
            f"/v1/agents/{agent_id}",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return AgentResponse.model_validate(data)

    async def delete_agent(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> None:
        """Delete an agent."""
        await self._request("DELETE", f"/v1/agents/{agent_id}", tenant_id=tenant_id)

    # Rules
    async def list_rules(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> list[RuleResponse]:
        """List all rules for an agent."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/rules",
            tenant_id=tenant_id,
        )
        return [RuleResponse.model_validate(r) for r in data.get("items", [])]

    async def get_rule(
        self,
        agent_id: str | UUID,
        rule_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> RuleResponse:
        """Get a rule by ID."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/rules/{rule_id}",
            tenant_id=tenant_id,
        )
        return RuleResponse.model_validate(data)

    async def create_rule(
        self,
        agent_id: str | UUID,
        name: str,
        condition: str,
        action: str,
        *,
        priority: int = 0,
        enabled: bool = True,
        is_hard_constraint: bool = False,
        tenant_id: str | UUID | None = None,
    ) -> RuleResponse:
        """Create a new rule."""
        payload = RuleCreate(
            name=name,
            condition_text=condition,
            action_text=action,
            priority=priority,
            enabled=enabled,
            is_hard_constraint=is_hard_constraint,
        )
        data = await self._request(
            "POST",
            f"/v1/agents/{agent_id}/rules",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return RuleResponse.model_validate(data)

    async def update_rule(
        self,
        agent_id: str | UUID,
        rule_id: str | UUID,
        *,
        name: str | None = None,
        condition: str | None = None,
        action: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
        tenant_id: str | UUID | None = None,
    ) -> RuleResponse:
        """Update a rule."""
        payload = RuleUpdate(
            name=name,
            condition_text=condition,
            action_text=action,
            priority=priority,
            enabled=enabled,
        )
        data = await self._request(
            "PUT",
            f"/v1/agents/{agent_id}/rules/{rule_id}",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return RuleResponse.model_validate(data)

    async def delete_rule(
        self,
        agent_id: str | UUID,
        rule_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> None:
        """Delete a rule."""
        await self._request(
            "DELETE",
            f"/v1/agents/{agent_id}/rules/{rule_id}",
            tenant_id=tenant_id,
        )

    # Scenarios
    async def list_scenarios(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> list[ScenarioResponse]:
        """List all scenarios for an agent."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/scenarios",
            tenant_id=tenant_id,
        )
        return [ScenarioResponse.model_validate(s) for s in data.get("items", [])]

    async def get_scenario(
        self,
        agent_id: str | UUID,
        scenario_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> ScenarioResponse:
        """Get a scenario by ID."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/scenarios/{scenario_id}",
            tenant_id=tenant_id,
        )
        return ScenarioResponse.model_validate(data)

    async def create_scenario(
        self,
        agent_id: str | UUID,
        name: str,
        *,
        description: str | None = None,
        entry_condition: str | None = None,
        steps: list[dict] | None = None,
        tenant_id: str | UUID | None = None,
    ) -> ScenarioResponse:
        """Create a new scenario."""
        step_models = [StepCreate.model_validate(s) for s in (steps or [])]
        payload = ScenarioCreate(
            name=name,
            description=description,
            entry_condition_text=entry_condition,
            steps=step_models,
        )
        data = await self._request(
            "POST",
            f"/v1/agents/{agent_id}/scenarios",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return ScenarioResponse.model_validate(data)

    async def delete_scenario(
        self,
        agent_id: str | UUID,
        scenario_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> None:
        """Delete a scenario."""
        await self._request(
            "DELETE",
            f"/v1/agents/{agent_id}/scenarios/{scenario_id}",
            tenant_id=tenant_id,
        )

    # Templates
    async def list_templates(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> list[TemplateResponse]:
        """List all templates for an agent."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/templates",
            tenant_id=tenant_id,
        )
        return [TemplateResponse.model_validate(t) for t in data.get("templates", [])]

    async def create_template(
        self,
        agent_id: str | UUID,
        name: str,
        text: str,
        tenant_id: str | UUID | None = None,
    ) -> TemplateResponse:
        """Create a new template."""
        payload = TemplateCreate(name=name, text=text)
        data = await self._request(
            "POST",
            f"/v1/agents/{agent_id}/templates",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return TemplateResponse.model_validate(data)

    # Variables
    async def list_variables(
        self,
        agent_id: str | UUID,
        tenant_id: str | UUID | None = None,
    ) -> list[VariableResponse]:
        """List all variables for an agent."""
        data = await self._request(
            "GET",
            f"/v1/agents/{agent_id}/variables",
            tenant_id=tenant_id,
        )
        return [VariableResponse.model_validate(v) for v in data.get("variables", [])]

    async def create_variable(
        self,
        agent_id: str | UUID,
        name: str,
        description: str | None = None,
        tenant_id: str | UUID | None = None,
    ) -> VariableResponse:
        """Create a new variable."""
        payload = VariableCreate(name=name, description=description)
        data = await self._request(
            "POST",
            f"/v1/agents/{agent_id}/variables",
            tenant_id=tenant_id,
            json=payload.model_dump(exclude_none=True),
        )
        return VariableResponse.model_validate(data)

    # Chat
    async def chat(
        self,
        agent_id: str | UUID,
        message: str,
        channel: str = "api",
        user_id: str = "anonymous",
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tenant_id: str | UUID | None = None,
    ) -> ChatResponse:
        """Send a message to an agent and get a response.

        Args:
            agent_id: Agent to chat with
            message: User message
            channel: Channel identifier (api, whatsapp, slack, etc.)
            user_id: User identifier on the channel
            session_id: Optional session ID to continue conversation
            metadata: Optional additional context
            tenant_id: Optional tenant ID override

        Returns:
            ChatResponse with the agent's reply
        """
        tid = tenant_id or self.tenant_id
        if not tid:
            raise SoldierClientError("tenant_id is required for chat")

        payload = ChatRequest(
            tenant_id=UUID(str(tid)),
            agent_id=UUID(str(agent_id)),
            channel=channel,
            user_channel_id=user_id,
            message=message,
            session_id=session_id,
            metadata=metadata,
        )

        data = await self._request(
            "POST",
            "/v1/chat",
            tenant_id=tid,
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        return ChatResponse.model_validate(data)

    async def chat_stream(
        self,
        agent_id: str | UUID,
        message: str,
        channel: str = "api",
        user_id: str = "anonymous",
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tenant_id: str | UUID | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat response token by token.

        Args:
            agent_id: Agent to chat with
            message: User message
            channel: Channel identifier
            user_id: User identifier
            session_id: Optional session ID
            metadata: Optional additional context
            tenant_id: Optional tenant ID override

        Yields:
            Response tokens as they arrive
        """
        tid = tenant_id or self.tenant_id
        if not tid:
            raise SoldierClientError("tenant_id is required for chat")

        payload = ChatRequest(
            tenant_id=UUID(str(tid)),
            agent_id=UUID(str(agent_id)),
            channel=channel,
            user_channel_id=user_id,
            message=message,
            session_id=session_id,
            metadata=metadata,
        )

        async with self._client.stream(
            "POST",
            "/v1/chat/stream",
            headers=self._headers(tid),
            json=payload.model_dump(mode="json", exclude_none=True),
        ) as response:
            if response.status_code >= 400:
                content = await response.aread()
                raise SoldierClientError(
                    message=content.decode(),
                    status_code=response.status_code,
                )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    import json

                    event = json.loads(line[6:])
                    if event.get("type") == "token":
                        yield event.get("content", "")
                    elif event.get("type") == "error":
                        raise SoldierClientError(
                            message=event.get("message", "Stream error"),
                            details=event,
                        )
