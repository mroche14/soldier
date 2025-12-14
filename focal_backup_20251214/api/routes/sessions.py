"""Session management endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from focal.api.dependencies import AuditStoreDep, SessionStoreDep
from focal.api.exceptions import SessionNotFoundError
from focal.api.middleware.auth import TenantContextDep
from focal.api.middleware.context import update_request_context
from focal.api.models.session import (
    SessionResponse,
    TurnListResponse,
    TurnResponse,
)
from focal.audit.models import TurnRecord
from focal.conversation.models import Session
from focal.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions")


def _map_session_to_response(session: Session) -> SessionResponse:
    """Map Session model to SessionResponse.

    Args:
        session: Session domain model

    Returns:
        SessionResponse for API
    """
    return SessionResponse(
        session_id=str(session.session_id),
        tenant_id=str(session.tenant_id),
        agent_id=str(session.agent_id),
        channel=session.channel.value,
        user_channel_id=session.user_channel_id,
        active_scenario_id=str(session.active_scenario_id)
        if session.active_scenario_id
        else None,
        active_step_id=str(session.active_step_id) if session.active_step_id else None,
        turn_count=session.turn_count,
        variables=session.variables,
        rule_fires=session.rule_fires,
        config_version=session.config_version,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
    )


def _map_turn_to_response(turn: TurnRecord, turn_number: int) -> TurnResponse:
    """Map TurnRecord to TurnResponse.

    Args:
        turn: TurnRecord from audit store
        turn_number: The turn number in sequence

    Returns:
        TurnResponse for API
    """
    return TurnResponse(
        turn_id=str(turn.turn_id),
        turn_number=turn_number,
        user_message=turn.user_message,
        agent_response=turn.agent_response,
        matched_rules=[str(r) for r in turn.matched_rule_ids],
        tools_called=[tc.tool_name for tc in turn.tool_calls],
        latency_ms=int(turn.latency_ms),
        tokens_used=turn.tokens_used,
        timestamp=turn.timestamp,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    tenant_context: TenantContextDep,
    session_store: SessionStoreDep,
) -> SessionResponse:
    """Get session state.

    Retrieve the current state of a session including active scenario,
    variables, and turn count.

    Args:
        session_id: Session identifier
        tenant_context: Authenticated tenant context
        session_store: Session store

    Returns:
        SessionResponse with session state

    Raises:
        SessionNotFoundError: If session doesn't exist
    """
    update_request_context(session_id=session_id)

    logger.debug("get_session_request", session_id=session_id)

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise SessionNotFoundError(f"Invalid session ID: {session_id}") from None

    session = await session_store.get(session_uuid)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    # Verify tenant ownership
    if session.tenant_id != tenant_context.tenant_id:
        raise SessionNotFoundError(f"Session {session_id} not found")

    return _map_session_to_response(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    tenant_context: TenantContextDep,
    session_store: SessionStoreDep,
) -> Response:
    """End a session.

    Terminate a session and clean up resources.

    Args:
        session_id: Session identifier
        tenant_context: Authenticated tenant context
        session_store: Session store

    Returns:
        204 No Content on success

    Raises:
        SessionNotFoundError: If session doesn't exist
    """
    update_request_context(session_id=session_id)

    logger.info("delete_session_request", session_id=session_id)

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise SessionNotFoundError(f"Invalid session ID: {session_id}") from None

    # Verify session exists and belongs to tenant
    session = await session_store.get(session_uuid)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    if session.tenant_id != tenant_context.tenant_id:
        raise SessionNotFoundError(f"Session {session_id} not found")

    # Delete session
    await session_store.delete(session_uuid)

    logger.info("session_deleted", session_id=session_id)

    return Response(status_code=204)


@router.get("/{session_id}/turns", response_model=TurnListResponse)
async def get_session_turns(
    session_id: str,
    tenant_context: TenantContextDep,
    session_store: SessionStoreDep,
    audit_store: AuditStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["asc", "desc"] = Query(default="desc"),
) -> TurnListResponse:
    """Get session conversation history.

    Retrieve paginated turn history for a session.

    Args:
        session_id: Session identifier
        tenant_context: Authenticated tenant context
        session_store: Session store
        audit_store: Audit store for turn records
        limit: Maximum number of turns to return (1-100)
        offset: Number of turns to skip
        sort: Sort order (asc=oldest first, desc=newest first)

    Returns:
        TurnListResponse with paginated turns

    Raises:
        SessionNotFoundError: If session doesn't exist
    """
    update_request_context(session_id=session_id)

    logger.debug(
        "get_session_turns_request",
        session_id=session_id,
        limit=limit,
        offset=offset,
        sort=sort,
    )

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise SessionNotFoundError(f"Invalid session ID: {session_id}") from None

    # Verify session exists and belongs to tenant
    session = await session_store.get(session_uuid)
    if not session:
        raise SessionNotFoundError(f"Session {session_id} not found")

    if session.tenant_id != tenant_context.tenant_id:
        raise SessionNotFoundError(f"Session {session_id} not found")

    # Get turns from audit store
    turns = await audit_store.list_turns_by_session(
        session_id=session_uuid,
        limit=limit + 1,  # Fetch one extra to check has_more
        offset=offset,
    )

    # Check if there are more results
    has_more = len(turns) > limit
    if has_more:
        turns = turns[:limit]

    # Apply sort order (audit store returns chronologically)
    if sort == "desc":
        turns = list(reversed(turns))

    # Map to response
    items = [
        _map_turn_to_response(turn, offset + i + 1) for i, turn in enumerate(turns)
    ]

    return TurnListResponse(
        items=items,
        total=session.turn_count,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
