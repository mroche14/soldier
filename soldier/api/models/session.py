"""Session response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from soldier.api.models.chat import ScenarioState


class SessionResponse(BaseModel):
    """Session state response for GET /v1/sessions/{id}."""

    session_id: str
    tenant_id: str
    agent_id: str
    channel: str
    user_channel_id: str

    active_scenario_id: str | None = None
    active_step_id: str | None = None

    turn_count: int = 0
    variables: dict[str, Any] = Field(default_factory=dict)
    rule_fires: dict[str, int] = Field(default_factory=dict)

    config_version: int | None = None
    created_at: datetime
    last_activity_at: datetime


class TurnResponse(BaseModel):
    """Single turn in conversation history."""

    turn_id: str
    turn_number: int
    user_message: str
    agent_response: str

    matched_rules: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)

    scenario_before: ScenarioState | None = None
    scenario_after: ScenarioState | None = None

    latency_ms: int = 0
    tokens_used: int = 0
    timestamp: datetime


class TurnListResponse(BaseModel):
    """Paginated turn history response."""

    items: list[TurnResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
