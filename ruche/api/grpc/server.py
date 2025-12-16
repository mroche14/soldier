"""gRPC server implementation.

This module provides the gRPC server for high-performance API access.
Implementation is mostly complete. See docs/architecture/stub-files.md
for remaining work and docs/architecture/api-layer.md for requirements.
"""

import asyncio

import grpc

from ruche.api.grpc import chat_pb2_grpc, config_pb2_grpc, memory_pb2_grpc
from ruche.api.grpc.services.chat_service import ChatService
from ruche.api.grpc.services.config_service import ConfigService
from ruche.api.grpc.services.memory_service import MemoryService
from ruche.brains.focal.pipeline import FocalCognitivePipeline
from ruche.brains.focal.stores import AgentConfigStore
from ruche.conversation.store import SessionStore
from ruche.infrastructure.stores.memory.interface import MemoryStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class GRPCServer:
    """gRPC server for high-performance API access.

    Provides:
    - Bidirectional streaming for real-time chat
    - Lower latency than REST for internal services
    - Protocol buffer serialization
    - Service mesh integration
    """

    def __init__(
        self,
        alignment_engine: FocalCognitivePipeline,
        session_store: SessionStore,
        config_store: AgentConfigStore,
        memory_store: MemoryStore,
        host: str = "0.0.0.0",
        port: int = 50051,
    ) -> None:
        """Initialize gRPC server.

        Args:
            alignment_engine: FOCAL brain pipeline for processing turns
            session_store: Session store for session management
            config_store: Agent configuration store
            memory_store: Memory storage backend
            host: Host to bind to (default: 0.0.0.0)
            port: Port to bind to (default: 50051)
        """
        self._alignment_engine = alignment_engine
        self._session_store = session_store
        self._config_store = config_store
        self._memory_store = memory_store
        self._host = host
        self._port = port
        self._server: grpc.aio.Server | None = None

    async def start(self) -> None:
        """Start the gRPC server.

        Initializes and starts the server with all services.
        """
        logger.info("grpc_server_starting", host=self._host, port=self._port)

        # Create server
        self._server = grpc.aio.server()

        # Register services
        chat_pb2_grpc.add_ChatServiceServicer_to_server(
            ChatService(self._alignment_engine, self._session_store),
            self._server,
        )

        memory_pb2_grpc.add_MemoryServiceServicer_to_server(
            MemoryService(self._memory_store),
            self._server,
        )

        config_pb2_grpc.add_ConfigServiceServicer_to_server(
            ConfigService(self._config_store),
            self._server,
        )

        # Bind to port
        self._server.add_insecure_port(f"{self._host}:{self._port}")

        # Start server
        await self._server.start()

        logger.info("grpc_server_started", host=self._host, port=self._port)

    async def stop(self, grace_period: float = 5.0) -> None:
        """Stop the gRPC server.

        Args:
            grace_period: Grace period in seconds for graceful shutdown
        """
        if self._server is None:
            return

        logger.info("grpc_server_stopping", grace_period=grace_period)

        await self._server.stop(grace_period)

        logger.info("grpc_server_stopped")

    async def wait_for_termination(self) -> None:
        """Wait for the server to terminate.

        Blocks until the server is stopped.
        """
        if self._server is None:
            return

        await self._server.wait_for_termination()


async def serve(
    alignment_engine: FocalCognitivePipeline,
    session_store: SessionStore,
    config_store: AgentConfigStore,
    memory_store: MemoryStore,
    host: str = "0.0.0.0",
    port: int = 50051,
) -> None:
    """Start and run the gRPC server.

    Convenience function to start the server and wait for termination.

    Args:
        alignment_engine: FOCAL brain pipeline for processing turns
        session_store: Session store for session management
        config_store: Agent configuration store
        memory_store: Memory storage backend
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 50051)
    """
    server = GRPCServer(
        alignment_engine=alignment_engine,
        session_store=session_store,
        config_store=config_store,
        memory_store=memory_store,
        host=host,
        port=port,
    )

    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("grpc_server_interrupted")
        await server.stop()


if __name__ == "__main__":
    # Example usage - in production, dependencies would be injected
    logger.warning("grpc_server_example_mode", msg="Running in example mode with None dependencies")

    # In production, get these from dependency injection:
    # - alignment_engine from get_alignment_engine()
    # - session_store from get_session_store()
    # - config_store from get_config_store()
    # - memory_store from get_memory_store()

    # For now, this will fail if run directly - that's expected
    # Use the REST API for now, or integrate gRPC server into your app startup
