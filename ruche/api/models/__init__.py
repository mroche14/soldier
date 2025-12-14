"""API models package.

Exports all request/response models for the API layer.
"""

from ruche.api.models.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    ErrorEvent,
    ScenarioState,
    StreamEvent,
    TokenEvent,
)
from ruche.api.models.context import (
    RateLimitResult,
    RequestContext,
    TenantContext,
)
from ruche.api.models.errors import (
    ErrorBody,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
)
from ruche.api.models.health import (
    ComponentHealth,
    HealthResponse,
)
from ruche.api.models.session import (
    SessionResponse,
    TurnListResponse,
    TurnResponse,
)

__all__ = [
    # Chat models
    "ChatRequest",
    "ChatResponse",
    "ScenarioState",
    "TokenEvent",
    "DoneEvent",
    "ErrorEvent",
    "StreamEvent",
    # Context models
    "TenantContext",
    "RateLimitResult",
    "RequestContext",
    # Error models
    "ErrorCode",
    "ErrorDetail",
    "ErrorBody",
    "ErrorResponse",
    # Health models
    "ComponentHealth",
    "HealthResponse",
    # Session models
    "SessionResponse",
    "TurnResponse",
    "TurnListResponse",
]
