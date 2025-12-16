"""Turn Gateway - Message ingress layer for ACF.

This is the entry point for all incoming messages. It:
1. Checks rate limits
2. Looks up active workflows for the session
3. Decides: TRIGGER_NEW, SIGNAL_EXISTING, QUEUE, or REJECT
"""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class RawMessage(BaseModel):
    """Raw message from a channel before turn processing."""

    content: str = Field(..., description="Message text content")
    message_id: str = Field(..., description="Unique message identifier")
    timestamp: str | None = Field(default=None, description="Message timestamp")
    metadata: dict[str, str] = Field(default_factory=dict, description="Channel-specific metadata")


class TurnAction(str, Enum):
    """Actions the gateway can take for an incoming message."""

    TRIGGER_NEW = "trigger_new"  # Start new workflow
    SIGNAL_EXISTING = "signal_existing"  # Signal running workflow
    QUEUE = "queue"  # Queue for later processing
    REJECT = "reject"  # Reject the message (rate limit, etc.)


class TurnDecision(BaseModel):
    """Decision made by the gateway for an incoming message."""

    action: TurnAction = Field(..., description="Action to take")
    workflow_id: str | None = Field(
        default=None,
        description="Workflow ID (for SIGNAL_EXISTING)",
    )
    reason: str | None = Field(
        default=None,
        description="Reason for decision (especially for REJECT)",
    )
    queue_position: int | None = Field(
        default=None,
        description="Position in queue (for QUEUE action)",
    )


class ActiveTurnIndex:
    """O(1) lookup of running workflows by session key.

    Uses Redis for distributed state across pods.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_cache: dict[str, str] = {}  # Fallback for testing

    async def get_workflow_id(self, session_key: str) -> str | None:
        """Get active workflow ID for a session."""
        if self._redis:
            return await self._redis.get(f"active_turn:{session_key}")
        return self._local_cache.get(session_key)

    async def set_workflow_id(
        self,
        session_key: str,
        workflow_id: str,
        ttl_seconds: int = 300,
    ) -> None:
        """Set active workflow for a session."""
        if self._redis:
            await self._redis.set(
                f"active_turn:{session_key}",
                workflow_id,
                ex=ttl_seconds,
            )
        else:
            self._local_cache[session_key] = workflow_id

    async def clear_workflow_id(self, session_key: str) -> None:
        """Clear active workflow for a session."""
        if self._redis:
            await self._redis.delete(f"active_turn:{session_key}")
        else:
            self._local_cache.pop(session_key, None)


class TurnGateway:
    """Message ingress layer that routes to ACF workflows.

    This is the entry point for all incoming messages from any channel.
    It coordinates with the workflow orchestrator (Hatchet) to:
    - Start new workflows for new conversations
    - Signal existing workflows with new messages
    - Queue messages when workflows are busy
    - Reject messages that violate rate limits
    """

    def __init__(
        self,
        active_turn_index: ActiveTurnIndex,
        rate_limiter=None,
        workflow_client=None,
    ):
        self._index = active_turn_index
        self._rate_limiter = rate_limiter
        self._workflow_client = workflow_client

    def _make_session_key(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
        channel_user_id: str,
    ) -> str:
        """Create session key from identifiers."""
        return f"{tenant_id}:{agent_id}:{channel}:{channel_user_id}"

    async def receive_message(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
        channel_user_id: str,
        message: RawMessage,
    ) -> TurnDecision:
        """Entry point for all incoming messages.

        Args:
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            channel: Channel (whatsapp, webchat, etc.)
            channel_user_id: User's ID on the channel
            message: The incoming message

        Returns:
            TurnDecision indicating what action to take
        """
        session_key = self._make_session_key(
            tenant_id, agent_id, channel, channel_user_id
        )

        logger.info(
            "message_received",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            channel=channel,
            session_key=session_key,
        )

        # 1. Check rate limits
        if self._rate_limiter:
            allowed = await self._rate_limiter.check(session_key)
            if not allowed:
                logger.warning("rate_limit_exceeded", session_key=session_key)
                return TurnDecision(
                    action=TurnAction.REJECT,
                    reason="Rate limit exceeded",
                )

        # 2. Check for active workflow
        active_workflow_id = await self._index.get_workflow_id(session_key)

        if active_workflow_id:
            # Signal existing workflow
            logger.info(
                "signaling_existing_workflow",
                session_key=session_key,
                workflow_id=active_workflow_id,
            )
            return TurnDecision(
                action=TurnAction.SIGNAL_EXISTING,
                workflow_id=active_workflow_id,
            )

        # 3. Trigger new workflow
        logger.info("triggering_new_workflow", session_key=session_key)
        return TurnDecision(action=TurnAction.TRIGGER_NEW)

    async def register_workflow(
        self,
        session_key: str,
        workflow_id: str,
    ) -> None:
        """Register an active workflow for a session."""
        await self._index.set_workflow_id(session_key, workflow_id)

    async def unregister_workflow(self, session_key: str) -> None:
        """Unregister workflow when processing completes."""
        await self._index.clear_workflow_id(session_key)
