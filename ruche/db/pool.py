"""PostgreSQL connection pool management.

Provides a centralized connection pool for all PostgreSQL stores.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import structlog

from ruche.db.errors import ConnectionError

logger = structlog.get_logger(__name__)


class PostgresPool:
    """Manages asyncpg connection pool with health checks.

    Usage:
        pool = PostgresPool(dsn="postgresql://...")
        await pool.connect()
        try:
            async with pool.acquire() as conn:
                result = await conn.fetch("SELECT * FROM ...")
        finally:
            await pool.close()
    """

    def __init__(
        self,
        dsn: str | None = None,
        min_size: int = 5,
        max_size: int = 20,
        max_inactive_connection_lifetime: float = 300.0,
        command_timeout: float = 60.0,
    ) -> None:
        """Initialize pool configuration.

        Args:
            dsn: Database connection string. Falls back to environment variables.
            min_size: Minimum number of connections to keep open.
            max_size: Maximum number of connections in the pool.
            max_inactive_connection_lifetime: Close connections idle longer than this (seconds).
            command_timeout: Default timeout for queries (seconds).
        """
        self._dsn = dsn or self._get_dsn_from_env()
        self._min_size = min_size
        self._max_size = max_size
        self._max_inactive_connection_lifetime = max_inactive_connection_lifetime
        self._command_timeout = command_timeout
        self._pool: asyncpg.Pool | None = None

    @staticmethod
    def _get_dsn_from_env() -> str:
        """Get database DSN from environment variables."""
        dsn = os.environ.get("RUCHE_DATABASE_URL")
        if dsn:
            return dsn

        dsn = os.environ.get("DATABASE_URL")
        if dsn:
            return dsn

        # Build from individual components
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        user = os.environ.get("POSTGRES_USER", "focal")
        password = os.environ.get("POSTGRES_PASSWORD", "focal")
        database = os.environ.get("POSTGRES_DB", "focal")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    async def connect(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                max_inactive_connection_lifetime=self._max_inactive_connection_lifetime,
                command_timeout=self._command_timeout,
            )
            logger.info(
                "postgres_pool_connected",
                min_size=self._min_size,
                max_size=self._max_size,
            )
        except Exception as e:
            logger.error("postgres_pool_connection_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}", cause=e) from e

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("postgres_pool_closed")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.fetch("SELECT ...")

        Note: Auto-connects if not already connected.
        """
        if self._pool is None:
            await self.connect()

        try:
            async with self._pool.acquire() as connection:
                yield connection
        except asyncpg.PostgresError as e:
            logger.error("postgres_connection_error", error=str(e))
            raise ConnectionError(f"PostgreSQL error: {e}", cause=e) from e

    async def health_check(self) -> bool:
        """Check if the pool is healthy.

        Returns:
            True if pool is connected and responsive.
        """
        if self._pool is None:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.warning("postgres_health_check_failed", error=str(e))
            return False

    @property
    def is_connected(self) -> bool:
        """Check if pool is initialized."""
        return self._pool is not None

    @property
    def size(self) -> int:
        """Get current pool size."""
        if self._pool is None:
            return 0
        return self._pool.get_size()

    @property
    def free_size(self) -> int:
        """Get number of free connections in pool."""
        if self._pool is None:
            return 0
        return self._pool.get_idle_size()
