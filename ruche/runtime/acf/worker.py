"""Hatchet worker entrypoint for ACF LogicalTurn processing.

This module provides the worker implementation for running ACF workflows.
It integrates the LogicalTurnWorkflow with Hatchet's durable execution engine.

Usage:
    # CLI command (defined in pyproject.toml)
    ruche-worker

    # Programmatic usage
    from ruche.runtime.acf.worker import run_worker
    await run_worker()
"""

import asyncio
import signal
import sys
from typing import Any

from redis.asyncio import Redis

from ruche.config import get_settings
from ruche.infrastructure.jobs.client import HatchetClient
from ruche.observability.logging import get_logger, setup_logging
from ruche.runtime.acf.workflow import LogicalTurnWorkflow, register_workflow

logger = get_logger(__name__)


async def create_redis_client() -> Redis:
    """Create Redis client from configuration.

    Returns:
        Redis client for mutex and state management
    """
    settings = get_settings()
    redis_config = settings.storage.session

    if redis_config.backend != "redis":
        raise ValueError(
            f"Session backend must be 'redis' for ACF worker, got '{redis_config.backend}'"
        )

    # Parse Redis URL from connection string or construct from host/port
    redis_url = getattr(redis_config, "url", None)
    if not redis_url:
        host = getattr(redis_config, "host", "localhost")
        port = getattr(redis_config, "port", 6379)
        redis_url = f"redis://{host}:{port}"

    redis = Redis.from_url(
        redis_url,
        decode_responses=False,  # ACF works with bytes for mutex
        encoding="utf-8",
    )

    logger.info(
        "redis_client_created",
        url=redis_url.split("@")[-1] if "@" in redis_url else redis_url,  # Redact auth
    )

    return redis


async def create_stores(
    settings,
) -> tuple[Any, Any, Any]:
    """Create store instances from configuration.

    Uses settings.storage to determine backend type (inmemory or postgres).

    Returns:
        Tuple of (session_store, message_store, audit_store)
    """
    from ruche.audit.stores.inmemory import InMemoryAuditStore
    from ruche.conversation.stores.inmemory import InMemorySessionStore

    # Session store (currently Redis or InMemory)
    session_backend = settings.storage.session.backend
    if session_backend == "redis":
        try:
            from ruche.conversation.stores.redis import RedisSessionStore
            from redis.asyncio import Redis

            redis_url = getattr(settings.storage.session, "connection_url", None)
            if not redis_url:
                host = getattr(settings.storage.session, "host", "localhost")
                port = getattr(settings.storage.session, "port", 6379)
                redis_url = f"redis://{host}:{port}"

            redis_client = Redis.from_url(redis_url)
            # Test connection
            await redis_client.ping()
            session_store = RedisSessionStore(redis_client)
            logger.info("session_store_created", backend="redis", url=redis_url.split("@")[-1])
        except Exception as e:
            logger.warning(
                "redis_connection_failed",
                error=str(e),
                fallback="inmemory",
            )
            session_store = InMemorySessionStore()
            session_backend = "inmemory"
    else:
        session_store = InMemorySessionStore()
        logger.info("session_store_created", backend="inmemory")

    # Message store (not yet implemented)
    message_store = None

    # Audit store
    # Note: PostgreSQL audit store causes circular import issues
    # Use InMemory for now until issue is resolved
    audit_store = InMemoryAuditStore()
    audit_backend = "inmemory"
    logger.info("audit_store_created", backend="inmemory")

    logger.info(
        "stores_initialized",
        session_backend=session_backend,
        audit_backend=audit_backend,
    )

    return session_store, message_store, audit_store


async def create_agent_runtime(settings) -> Any:
    """Create AgentRuntime instance.

    Returns:
        AgentRuntime for agent lifecycle management
    """
    from ruche.infrastructure.stores.config.inmemory import InMemoryConfigStore
    from ruche.runtime.agent.runtime import AgentRuntime
    from ruche.runtime.brain.factory import BrainFactory
    from ruche.runtime.toolbox.gateway import ToolGateway

    # Create ConfigStore
    # Note: PostgresConfigStore is incomplete (missing channel/tool methods)
    # Always use InMemory for now until full implementation is complete
    config_store = InMemoryConfigStore()
    logger.info("config_store_created", backend="inmemory")

    # Create IdempotencyCache (simple in-memory implementation)
    class SimpleIdempotencyCache:
        """Simple in-memory idempotency cache."""

        def __init__(self):
            self._cache: dict[str, dict] = {}

        async def get(self, key: str) -> dict | None:
            return self._cache.get(key)

        async def set(self, key: str, value: dict, ttl: int) -> None:
            self._cache[key] = value

    idem_cache = SimpleIdempotencyCache()

    # Create ToolGateway with empty providers
    tool_gateway = ToolGateway(
        providers={},
        idem_cache=idem_cache,
    )
    logger.info("tool_gateway_created", provider_count=0)

    # Create BrainFactory (brain factory)
    # For now, we'll register FOCAL brain factory
    from ruche.brains.focal.pipeline import FocalCognitivePipeline

    def create_focal_brain(agent):
        """Factory function for FOCAL brain."""
        # FOCAL brain needs providers and stores - placeholder for now
        # This will be properly wired when we connect the full stack
        return None

    brain_factory = BrainFactory(
        focal_factory=create_focal_brain,
    )
    logger.info("brain_factory_created", available_types=brain_factory.available_types)

    # Create AgentRuntime
    agent_runtime = AgentRuntime(
        config_store=config_store,
        tool_gateway=tool_gateway,
        brain_factory=brain_factory,
        max_cache_size=1000,
    )
    logger.info("agent_runtime_created", max_cache_size=1000)

    return agent_runtime


async def create_worker() -> tuple[Any, LogicalTurnWorkflow]:
    """Create and configure Hatchet worker with LogicalTurnWorkflow.

    Returns:
        Tuple of (Hatchet client, LogicalTurnWorkflow instance)

    Raises:
        RuntimeError: If Hatchet is disabled or unavailable
    """
    settings = get_settings()
    hatchet_config = settings.jobs.hatchet

    if not hatchet_config.enabled:
        raise RuntimeError("Hatchet is disabled in configuration")

    # Create Hatchet client
    hatchet_client = HatchetClient(hatchet_config)
    hatchet = hatchet_client.get_client()

    if hatchet is None:
        raise RuntimeError("Failed to create Hatchet client - is hatchet-sdk installed?")

    logger.info(
        "hatchet_client_created",
        server_url=hatchet_config.server_url,
        concurrency=hatchet_config.worker_concurrency,
    )

    # Create Redis client
    redis = await create_redis_client()

    # Create stores
    session_store, message_store, audit_store = await create_stores(settings)

    # Create AgentRuntime
    agent_runtime = await create_agent_runtime(settings)

    # Create LogicalTurnWorkflow instance
    workflow = LogicalTurnWorkflow(
        redis=redis,
        agent_runtime=agent_runtime,
        session_store=session_store,
        message_store=message_store,
        audit_store=audit_store,
        mutex_timeout=300,  # 5 minutes
        mutex_blocking_timeout=10.0,  # 10 seconds
    )

    logger.info("logical_turn_workflow_created")

    return hatchet, workflow


def register_workflows(hatchet: Any, workflow: LogicalTurnWorkflow) -> None:
    """Register all ACF workflows with Hatchet.

    Args:
        hatchet: Hatchet SDK instance
        workflow: LogicalTurnWorkflow instance to register
    """
    # Register LogicalTurnWorkflow
    registered_class = register_workflow(hatchet, workflow)

    logger.info(
        "workflow_registered",
        workflow_name=LogicalTurnWorkflow.WORKFLOW_NAME,
        registered_class=registered_class.__name__,
    )


async def run_worker() -> None:
    """Main worker loop - creates worker and starts processing.

    This function:
    1. Loads configuration
    2. Creates Hatchet client
    3. Creates LogicalTurnWorkflow
    4. Registers workflows
    5. Starts worker and blocks until shutdown

    Handles graceful shutdown on SIGINT/SIGTERM.
    """
    settings = get_settings()

    # Setup logging
    log_level = settings.observability.logging.level
    setup_logging(level=log_level)

    logger.info(
        "acf_worker_starting",
        server_url=settings.jobs.hatchet.server_url,
        concurrency=settings.jobs.hatchet.worker_concurrency,
    )

    try:
        # Create worker and workflow
        hatchet, workflow = await create_worker()

        # Register workflows
        register_workflows(hatchet, workflow)

        logger.info("acf_worker_ready", workflow_count=1)

        # Setup signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(sig: int, frame: Any) -> None:
            """Handle shutdown signals."""
            logger.info(
                "shutdown_signal_received",
                signal=signal.Signals(sig).name,
            )
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start worker (blocking until shutdown)
        logger.info("starting_hatchet_worker")

        # Hatchet SDK's worker.start() is blocking
        # We'll run it in a way that allows checking shutdown_event
        worker_task = asyncio.create_task(
            asyncio.to_thread(hatchet.worker.start)
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

        logger.info("shutting_down_worker")

        # Cancel worker task
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        logger.info("acf_worker_stopped")

    except Exception as e:
        logger.error(
            "acf_worker_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def main() -> None:
    """CLI entrypoint for ACF worker.

    This is registered as a console script in pyproject.toml:
        [project.scripts]
        ruche-worker = "ruche.runtime.acf.worker:main"

    Usage:
        ruche-worker
    """
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("worker_interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(
            "worker_startup_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
