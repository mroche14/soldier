"""Task queue implementations for async memory ingestion."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any
from uuid import uuid4


class TaskQueue(ABC):
    """Abstract interface for task queue implementations."""

    @abstractmethod
    async def enqueue(
        self,
        job_type: str,
        **kwargs: Any,
    ) -> str:
        """Enqueue a task.

        Args:
            job_type: Type of job to execute
            **kwargs: Job parameters

        Returns:
            Job ID
        """
        pass

    @abstractmethod
    def register(self, job_type: str, handler: Callable[..., Any]) -> None:
        """Register a task handler.

        Args:
            job_type: Type of job this handler processes
            handler: Async callable to process the job
        """
        pass


class InMemoryTaskQueue(TaskQueue):
    """In-memory task queue for development and testing."""

    def __init__(self) -> None:
        """Initialize in-memory task queue."""
        self._queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._worker_task: asyncio.Task[None] | None = None

    def register(self, job_type: str, handler: Callable[..., Any]) -> None:
        """Register a task handler.

        Args:
            job_type: Type of job this handler processes
            handler: Async callable to process the job
        """
        self._handlers[job_type] = handler

    async def enqueue(
        self,
        job_type: str,
        **kwargs: Any,
    ) -> str:
        """Enqueue a task.

        Args:
            job_type: Type of job to execute
            **kwargs: Job parameters

        Returns:
            Job ID
        """
        job_id = str(uuid4())
        await self._queue.put((job_id, job_type, kwargs))

        # Start worker if not running
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

        return job_id

    async def _worker(self) -> None:
        """Background worker that processes queued tasks."""
        while True:
            try:
                # Wait for a task with timeout
                job_id, job_type, kwargs = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )

                # Get handler for this job type
                handler = self._handlers.get(job_type)
                if handler is None:
                    continue

                # Execute handler in background
                asyncio.create_task(self._execute_task(job_id, job_type, handler, kwargs))

            except TimeoutError:
                # Check if queue is empty, if so exit worker
                if self._queue.empty():
                    break
                continue
            except Exception:
                # Continue processing on error
                continue

    async def _execute_task(
        self,
        _job_id: str,
        _job_type: str,
        handler: Callable[..., Any],
        kwargs: dict[str, Any],
    ) -> None:
        """Execute a single task with error handling.

        Args:
            _job_id: Unique job identifier (reserved for future observability)
            _job_type: Type of job (reserved for future observability)
            handler: Handler function to call
            kwargs: Job parameters
        """
        import contextlib

        with contextlib.suppress(Exception):
            # Silently fail - observability handled by handler
            await handler(**kwargs)


class RedisTaskQueue(TaskQueue):
    """Redis-based task queue for production (optional)."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis task queue.

        Args:
            redis_url: Redis connection URL
        """
        self._redis_url = redis_url
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._queue: Any = None  # rq.Queue, but rq is optional dependency
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy-initialize Redis queue."""
        if self._initialized:
            return

        try:
            from redis import Redis  # type: ignore[import-not-found]
            from rq import Queue  # type: ignore[import-not-found]

            redis_conn = Redis.from_url(self._redis_url)
            self._queue = Queue(connection=redis_conn)
            self._initialized = True
        except ImportError as err:
            raise RuntimeError(
                "rq and redis packages required for RedisTaskQueue. "
                "Install with: uv add rq redis"
            ) from err

    def register(self, job_type: str, handler: Callable[..., Any]) -> None:
        """Register a task handler.

        Args:
            job_type: Type of job this handler processes
            handler: Async callable to process the job
        """
        self._handlers[job_type] = handler

    async def enqueue(
        self,
        job_type: str,
        **kwargs: Any,
    ) -> str:
        """Enqueue a task to Redis queue.

        Args:
            job_type: Type of job to execute
            **kwargs: Job parameters

        Returns:
            Job ID
        """
        self._ensure_initialized()

        handler = self._handlers.get(job_type)
        if handler is None:
            raise ValueError(f"No handler registered for job type: {job_type}")

        # Enqueue job to Redis
        job = self._queue.enqueue(
            handler,
            **kwargs,
            job_timeout=600,  # 10 minutes
            result_ttl=3600,  # Keep result for 1 hour
            failure_ttl=86400,  # Keep failures for 1 day
        )

        return str(job.id)
