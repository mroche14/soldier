"""Pytest fixtures for store integration tests.

Provides Docker-based fixtures for PostgreSQL and Redis testing.
Tests skip gracefully when infrastructure is unavailable.
"""

import os
import subprocess
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as redis

from focal.db.pool import PostgresPool


def docker_available() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def postgres_available() -> bool:
    """Check if PostgreSQL container is running and accessible."""
    if not docker_available():
        return False

    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "postgres" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def redis_available() -> bool:
    """Check if Redis container is running and accessible."""
    if not docker_available():
        return False

    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "redis" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def postgres_dsn() -> str:
    """Get PostgreSQL DSN for tests."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://focal:focal@localhost:5432/focal",
    )


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Get Redis URL for tests."""
    # Default to 6381 to match docker-compose.yml configuration
    return os.environ.get("TEST_REDIS_URL", "redis://localhost:6381/0")


@pytest_asyncio.fixture(scope="function")
async def postgres_pool(postgres_dsn: str) -> AsyncIterator[PostgresPool]:
    """Create PostgreSQL connection pool for tests.

    Skips tests if PostgreSQL is not available.
    Uses function scope to avoid event loop issues across tests.
    """
    if not postgres_available():
        pytest.skip("PostgreSQL not available (run 'docker compose up -d postgres')")

    pool = PostgresPool(dsn=postgres_dsn, min_size=2, max_size=5)
    await pool.connect()

    # Verify connection works
    healthy = await pool.health_check()
    if not healthy:
        pytest.skip("PostgreSQL health check failed")

    yield pool

    await pool.close()


@pytest_asyncio.fixture(scope="function")
async def redis_client(redis_url: str) -> AsyncIterator[redis.Redis]:
    """Create Redis client for tests.

    Skips tests if Redis is not available.
    Uses function scope to avoid event loop issues across tests.
    """
    if not redis_available():
        pytest.skip("Redis not available (run 'docker compose up -d redis')")

    client = redis.from_url(redis_url, decode_responses=True)

    # Verify connection works
    try:
        await client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis connection failed")

    yield client

    await client.aclose()


@pytest.fixture
def tenant_id():
    """Generate a unique tenant ID for test isolation."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Generate a unique agent ID for tests."""
    return uuid4()


@pytest.fixture
def customer_profile_id():
    """Generate a unique customer profile ID for tests."""
    return uuid4()


@pytest_asyncio.fixture
async def clean_redis(redis_client: redis.Redis, tenant_id):
    """Clean up Redis keys for the test tenant after each test."""
    yield

    # Clean up all keys for this tenant
    pattern = f"*{tenant_id}*"
    async for key in redis_client.scan_iter(match=pattern):
        await redis_client.delete(key)


@pytest_asyncio.fixture
async def clean_postgres(postgres_pool: PostgresPool, tenant_id):
    """Clean up PostgreSQL data for the test tenant after each test.

    Note: This is a basic cleanup. For production, use proper
    transaction rollback or database cleanup strategies.
    """
    # Clean up BEFORE the test to ensure fresh state
    async with postgres_pool.acquire() as conn:
        # Clean memory tables (use group_id, not tenant_id)
        # These tables use group_id patterns like "tenant1:session1" or "tenant1"
        memory_tables = ["relationships", "entities", "episodes"]
        for table in memory_tables:
            try:
                # Delete all records for common test group_ids
                await conn.execute(f"DELETE FROM {table}")  # noqa: S608
            except Exception:
                pass

        # Clean tenant-scoped tables
        tenant_tables = [
            "audit_events",
            "turn_records",
            "profile_assets",
            "profile_fields",
            "channel_identities",
            "customer_profiles",
            "migration_plans",
            "scenario_archives",
            "tool_activations",
            "variables",
            "templates",
            "rules",
            "scenarios",
            "agents",
        ]
        for table in tenant_tables:
            try:
                await conn.execute(
                    f"DELETE FROM {table} WHERE tenant_id = $1",  # noqa: S608
                    tenant_id,
                )
            except Exception:
                pass

    yield

    # Clean up AFTER the test as well
    async with postgres_pool.acquire() as conn:
        for table in memory_tables:
            try:
                await conn.execute(f"DELETE FROM {table}")  # noqa: S608
            except Exception:
                pass

        for table in tenant_tables:
            try:
                await conn.execute(
                    f"DELETE FROM {table} WHERE tenant_id = $1",  # noqa: S608
                    tenant_id,
                )
            except Exception:
                pass
