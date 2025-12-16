"""ChatService gRPC implementation."""

import time
from uuid import UUID, uuid4

import grpc

from ruche.api.grpc import chat_pb2, chat_pb2_grpc
from ruche.brains.focal.pipeline import FocalCognitivePipeline
from ruche.brains.focal.result import AlignmentResult
from ruche.conversation.models import Channel, Session, SessionStatus
from ruche.conversation.store import SessionStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ChatService(chat_pb2_grpc.ChatServiceServicer):
    """gRPC ChatService implementation.

    Provides chat message processing via gRPC with unary and streaming methods.
    """

    def __init__(
        self,
        alignment_engine: FocalCognitivePipeline,
        session_store: SessionStore,
    ) -> None:
        """Initialize ChatService.

        Args:
            alignment_engine: FOCAL brain pipeline for processing turns
            session_store: Session store for session management
        """
        self._engine = alignment_engine
        self._session_store = session_store

    async def _get_or_create_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        channel: str,
        user_channel_id: str,
        session_id: str | None,
    ) -> Session:
        """Get existing session or create a new one.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID
            channel: Channel name
            user_channel_id: User's channel identifier
            session_id: Optional existing session ID

        Returns:
            Session object

        Raises:
            grpc.RpcError: If session_id provided but not found
        """
        if session_id:
            # Try to get existing session
            try:
                existing = await self._session_store.get(UUID(session_id))
                if existing:
                    return existing
            except ValueError:
                # Invalid UUID format
                pass
            raise grpc.aio.AioRpcError(
                grpc.StatusCode.NOT_FOUND,
                f"Session {session_id} not found",
            )

        # Try to find session by channel identity
        channel_enum = Channel(channel) if channel in [c.value for c in Channel] else Channel.API
        existing = await self._session_store.get_by_channel(
            tenant_id, channel_enum, user_channel_id
        )
        if existing and existing.status == SessionStatus.ACTIVE:
            return existing

        # Create new session
        new_session = Session(
            session_id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=channel_enum,
            user_channel_id=user_channel_id,
            config_version=1,
            status=SessionStatus.ACTIVE,
        )
        await self._session_store.save(new_session)

        logger.info(
            "session_created",
            session_id=str(new_session.session_id),
            tenant_id=str(tenant_id),
            channel=channel,
        )

        return new_session

    def _map_result_to_response(
        self, result: AlignmentResult
    ) -> chat_pb2.ChatResponse:
        """Map AlignmentResult to gRPC ChatResponse.

        Args:
            result: The result from the alignment engine

        Returns:
            gRPC ChatResponse
        """
        # Build scenario state
        scenario = None
        if result.scenario_result and result.scenario_result.scenario_id:
            scenario = chat_pb2.ScenarioState(
                id=str(result.scenario_result.scenario_id),
                step=str(result.scenario_result.target_step_id)
                if result.scenario_result.target_step_id
                else "",
            )

        # Calculate tokens
        tokens_used = 0
        if result.generation:
            tokens_used = result.generation.prompt_tokens + result.generation.completion_tokens

        # Build matched rules list
        matched_rule_ids: list[str] = [
            str(r.rule.id) for r in result.matched_rules if r.rule.id is not None
        ]

        # Build tools called list
        tools_called_ids: list[str] = [
            str(tr.tool_id)
            for tr in result.tool_results
            if tr.success and tr.tool_id is not None
        ]

        return chat_pb2.ChatResponse(
            response=result.response,
            session_id=str(result.session_id),
            turn_id=str(result.turn_id),
            scenario=scenario,
            matched_rules=matched_rule_ids,
            tools_called=tools_called_ids,
            tokens_used=tokens_used,
            latency_ms=int(result.total_time_ms),
        )

    async def SendMessage(
        self, request: chat_pb2.ChatRequest, context: grpc.aio.ServicerContext
    ) -> chat_pb2.ChatResponse:
        """Process a user message and return agent response.

        Args:
            request: Chat request with message and context
            context: gRPC context

        Returns:
            ChatResponse with agent response and metadata
        """
        start_time = time.time()

        logger.info(
            "grpc_chat_request_received",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            channel=request.channel,
            has_session_id=bool(request.session_id),
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return chat_pb2.ChatResponse()

        # Get or create session
        session = await self._get_or_create_session(
            tenant_id=tenant_id,
            agent_id=agent_id,
            channel=request.channel,
            user_channel_id=request.user_channel_id,
            session_id=request.session_id if request.session_id else None,
        )

        # Process through alignment engine
        result = await self._engine.process_turn(
            message=request.message,
            session_id=session.session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        # Map to response
        response = self._map_result_to_response(result)

        # Override latency with actual measured time
        elapsed_ms = int((time.time() - start_time) * 1000)
        response.latency_ms = elapsed_ms

        logger.info(
            "grpc_chat_request_completed",
            turn_id=str(result.turn_id),
            latency_ms=elapsed_ms,
            matched_rules_count=len(response.matched_rules),
            tokens_used=response.tokens_used,
        )

        return response

    async def SendMessageStream(
        self, request: chat_pb2.ChatRequest, context: grpc.aio.ServicerContext
    ):
        """Process a user message with streaming response.

        Args:
            request: Chat request with message and context
            context: gRPC context

        Yields:
            ChatChunk with tokens or done event
        """
        start_time = time.time()

        logger.info(
            "grpc_chat_stream_request_received",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            channel=request.channel,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            yield chat_pb2.ChatChunk(
                error=chat_pb2.ErrorEvent(
                    code="INVALID_ARGUMENT",
                    message=f"Invalid UUID: {e}",
                )
            )
            return

        try:
            # Get or create session
            session = await self._get_or_create_session(
                tenant_id=tenant_id,
                agent_id=agent_id,
                channel=request.channel,
                user_channel_id=request.user_channel_id,
                session_id=request.session_id if request.session_id else None,
            )

            # Process through alignment engine
            # TODO: Implement actual streaming from AlignmentEngine
            result = await self._engine.process_turn(
                message=request.message,
                session_id=session.session_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

            # Emit response as token events (simulated streaming)
            words = result.response.split()
            for i, word in enumerate(words):
                content = word + (" " if i < len(words) - 1 else "")
                yield chat_pb2.ChatChunk(token=content)

            # Calculate tokens
            tokens_used = 0
            if result.generation:
                tokens_used = (
                    result.generation.prompt_tokens + result.generation.completion_tokens
                )

            # Build matched rules list
            matched_rule_ids: list[str] = [
                str(r.rule.id) for r in result.matched_rules if r.rule.id is not None
            ]

            # Build tools called list
            tools_called_ids: list[str] = [
                str(tr.tool_id)
                for tr in result.tool_results
                if tr.success and tr.tool_id is not None
            ]

            # Build scenario state
            scenario = None
            if result.scenario_result and result.scenario_result.scenario_id:
                scenario = chat_pb2.ScenarioState(
                    id=str(result.scenario_result.scenario_id),
                    step=str(result.scenario_result.target_step_id)
                    if result.scenario_result.target_step_id
                    else "",
                )

            # Emit done event
            elapsed_ms = int((time.time() - start_time) * 1000)
            done_response = chat_pb2.ChatResponse(
                response=result.response,
                session_id=str(result.session_id),
                turn_id=str(result.turn_id),
                scenario=scenario,
                matched_rules=matched_rule_ids,
                tools_called=tools_called_ids,
                tokens_used=tokens_used,
                latency_ms=elapsed_ms,
            )
            yield chat_pb2.ChatChunk(done=done_response)

            logger.info(
                "grpc_chat_stream_completed",
                turn_id=str(result.turn_id),
                latency_ms=elapsed_ms,
            )

        except Exception as e:
            logger.exception("grpc_chat_stream_error", error=str(e))
            yield chat_pb2.ChatChunk(
                error=chat_pb2.ErrorEvent(
                    code="INTERNAL_ERROR",
                    message="An error occurred",
                )
            )
