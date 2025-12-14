"""Chat endpoints for message processing."""

import time
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Header
from sse_starlette.sse import EventSourceResponse

from focal.alignment.result import AlignmentResult
from focal.api.dependencies import (
    AlignmentEngineDep,
    SessionStoreDep,
    SettingsDep,
)
from focal.api.exceptions import AgentNotFoundError, SessionNotFoundError
from focal.api.middleware.auth import TenantContextDep
from focal.api.middleware.context import update_request_context
from focal.api.models.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    ErrorEvent,
    ScenarioState,
    TokenEvent,
)
from focal.conversation.models import Channel, Session, SessionStatus
from focal.conversation.store import SessionStore
from focal.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _map_alignment_result_to_response(result: AlignmentResult) -> ChatResponse:
    """Map AlignmentResult to ChatResponse.

    Args:
        result: The result from the alignment engine

    Returns:
        ChatResponse for the API
    """
    scenario = None
    if result.scenario_result and result.scenario_result.scenario_id:
        scenario = ScenarioState(
            id=str(result.scenario_result.scenario_id),
            step=str(result.scenario_result.target_step_id)
            if result.scenario_result.target_step_id
            else None,
        )

    # Calculate total tokens from generation result
    tokens_used = 0
    if result.generation:
        tokens_used = result.generation.prompt_tokens + result.generation.completion_tokens

    # Build matched rules list (filter out rules with None IDs)
    matched_rule_ids: list[str] = [
        str(r.rule.id) for r in result.matched_rules if r.rule.id is not None
    ]

    # Build tools called list (filter out None tool_ids and convert to string)
    tools_called_ids: list[str] = [
        str(tr.tool_id) for tr in result.tool_results if tr.success and tr.tool_id is not None
    ]

    return ChatResponse(
        response=result.response,
        session_id=str(result.session_id),
        turn_id=str(result.turn_id),
        scenario=scenario,
        matched_rules=matched_rule_ids,
        tools_called=tools_called_ids,
        tokens_used=tokens_used,
        latency_ms=int(result.total_time_ms),
    )


async def _get_or_create_session(
    session_store: SessionStore,
    tenant_id: UUID,
    agent_id: UUID,
    channel: str,
    user_channel_id: str,
    session_id: str | None,
) -> Session:
    """Get existing session or create a new one.

    Args:
        session_store: Session store
        tenant_id: Tenant ID
        agent_id: Agent ID
        channel: Channel name
        user_channel_id: User's channel identifier
        session_id: Optional existing session ID

    Returns:
        Session object

    Raises:
        SessionNotFoundError: If session_id provided but not found
    """
    if session_id:
        # Try to get existing session
        try:
            existing = await session_store.get(UUID(session_id))
            if existing:
                return existing
        except ValueError:
            # Invalid UUID format - treat as not found
            pass
        raise SessionNotFoundError(f"Session {session_id} not found")

    # Try to find session by channel identity
    channel_enum = Channel(channel) if channel in [c.value for c in Channel] else Channel.API
    existing = await session_store.get_by_channel(tenant_id, channel_enum, user_channel_id)
    if existing and existing.status == SessionStatus.ACTIVE:
        return existing

    # Create new session
    new_session = Session(
        session_id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=channel_enum,
        user_channel_id=user_channel_id,
        config_version=1,  # Default version
        status=SessionStatus.ACTIVE,
    )
    await session_store.save(new_session)

    logger.info(
        "session_created",
        session_id=str(new_session.session_id),
        tenant_id=str(tenant_id),
        channel=channel,
    )

    return new_session


@router.post("/chat", response_model=ChatResponse)
async def process_message(
    request: ChatRequest,
    _tenant_context: TenantContextDep,
    engine: AlignmentEngineDep,
    session_store: SessionStoreDep,
    _settings: SettingsDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ChatResponse:
    """Process a user message and return agent response.

    Takes a user message and processes it through the alignment engine,
    returning the agent's response along with metadata about the turn.

    Args:
        request: Chat request with message and context
        tenant_context: Authenticated tenant context
        engine: Alignment engine for processing
        session_store: Session store for session management
        settings: Application settings
        idempotency_key: Optional key for idempotent requests

    Returns:
        ChatResponse with agent response and metadata

    Raises:
        AgentNotFoundError: If agent_id doesn't exist
        SessionNotFoundError: If session_id provided but not found
    """
    start_time = time.time()

    # Update request context for logging
    update_request_context(
        tenant_id=str(request.tenant_id),
        agent_id=str(request.agent_id),
    )

    logger.info(
        "chat_request_received",
        channel=request.channel,
        has_session_id=request.session_id is not None,
        has_idempotency_key=idempotency_key is not None,
    )

    # TODO: Implement idempotency check with Redis cache
    # if idempotency_key:
    #     cached = await idempotency_cache.get(idempotency_key)
    #     if cached:
    #         return cached

    # Get or create session
    session = await _get_or_create_session(
        session_store=session_store,
        tenant_id=request.tenant_id,
        agent_id=request.agent_id,
        channel=request.channel,
        user_channel_id=request.user_channel_id,
        session_id=request.session_id,
    )

    update_request_context(session_id=str(session.session_id))

    # Process through alignment engine
    result = await engine.process_turn(
        message=request.message,
        session_id=session.session_id,
        tenant_id=request.tenant_id,
        agent_id=request.agent_id,
    )

    update_request_context(turn_id=str(result.turn_id))

    # Map to response
    response = _map_alignment_result_to_response(result)

    # Override latency with actual measured time
    elapsed_ms = int((time.time() - start_time) * 1000)
    response.latency_ms = elapsed_ms

    logger.info(
        "chat_request_completed",
        turn_id=str(result.turn_id),
        latency_ms=elapsed_ms,
        matched_rules_count=len(response.matched_rules),
        tokens_used=response.tokens_used,
    )

    # TODO: Cache response if idempotency_key provided
    # if idempotency_key:
    #     await idempotency_cache.set(idempotency_key, response, ttl=300)

    return response


@router.post("/chat/stream")
async def process_message_stream(
    request: ChatRequest,
    _tenant_context: TenantContextDep,
    engine: AlignmentEngineDep,
    session_store: SessionStoreDep,
    _settings: SettingsDep,
) -> EventSourceResponse:
    """Process a user message with streaming response.

    Takes a user message and processes it through the alignment engine,
    streaming tokens back as Server-Sent Events as they are generated.

    Args:
        request: Chat request with message and context
        tenant_context: Authenticated tenant context
        engine: Alignment engine for processing
        session_store: Session store for session management
        settings: Application settings

    Returns:
        EventSourceResponse with SSE stream
    """
    update_request_context(
        tenant_id=str(request.tenant_id),
        agent_id=str(request.agent_id),
    )

    logger.info(
        "chat_stream_request_received",
        channel=request.channel,
    )

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        """Generate SSE events for streaming response."""
        start_time = time.time()

        try:
            # Get or create session
            session = await _get_or_create_session(
                session_store=session_store,
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                channel=request.channel,
                user_channel_id=request.user_channel_id,
                session_id=request.session_id,
            )

            update_request_context(session_id=str(session.session_id))

            # Process through alignment engine
            # TODO: Implement actual streaming from AlignmentEngine
            # For now, process synchronously and emit tokens
            result = await engine.process_turn(
                message=request.message,
                session_id=session.session_id,
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
            )

            update_request_context(turn_id=str(result.turn_id))

            # Emit response as token events (simulated streaming)
            # In a real implementation, this would stream from the LLM
            words = result.response.split()
            for i, word in enumerate(words):
                content = word + (" " if i < len(words) - 1 else "")
                token_event = TokenEvent(content=content)
                yield {"event": "token", "data": token_event.model_dump_json()}

            # Calculate total tokens from generation result
            tokens_used = 0
            if result.generation:
                tokens_used = result.generation.prompt_tokens + result.generation.completion_tokens

            # Build matched rules list (filter out rules with None IDs)
            matched_rule_ids: list[str] = [
                str(r.rule.id) for r in result.matched_rules if r.rule.id is not None
            ]

            # Build tools called list (filter out None tool_ids and convert to string)
            tools_called_ids: list[str] = [
                str(tr.tool_id) for tr in result.tool_results if tr.success and tr.tool_id is not None
            ]

            # Emit done event
            elapsed_ms = int((time.time() - start_time) * 1000)
            done_event = DoneEvent(
                turn_id=str(result.turn_id),
                session_id=str(result.session_id),
                matched_rules=matched_rule_ids,
                tools_called=tools_called_ids,
                tokens_used=tokens_used,
                latency_ms=elapsed_ms,
            )
            yield {"event": "done", "data": done_event.model_dump_json()}

            logger.info(
                "chat_stream_completed",
                turn_id=str(result.turn_id),
                latency_ms=elapsed_ms,
            )

        except SessionNotFoundError as e:
            error_event = ErrorEvent(code="SESSION_NOT_FOUND", message=str(e))
            yield {"event": "error", "data": error_event.model_dump_json()}
        except AgentNotFoundError as e:
            error_event = ErrorEvent(code="AGENT_NOT_FOUND", message=str(e))
            yield {"event": "error", "data": error_event.model_dump_json()}
        except Exception as e:
            logger.exception("chat_stream_error", error=str(e))
            error_event = ErrorEvent(code="INTERNAL_ERROR", message="An error occurred")
            yield {"event": "error", "data": error_event.model_dump_json()}

    return EventSourceResponse(event_generator())
