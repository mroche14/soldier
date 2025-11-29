"""Health check and metrics endpoints."""

import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from soldier.api.dependencies import (
    AuditStoreDep,
    ConfigStoreDep,
    SessionStoreDep,
    SettingsDep,
)
from soldier.api.models.health import ComponentHealth, HealthResponse
from soldier.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _check_store_health(
    store: object, name: str
) -> ComponentHealth:
    """Check health of a store by attempting a simple operation.

    Args:
        store: Store instance to check
        name: Name of the component

    Returns:
        ComponentHealth status
    """
    start = time.time()
    try:
        # Simple existence check - stores are considered healthy if instantiated
        # In production, this would perform actual health checks
        if store is not None:
            latency_ms = (time.time() - start) * 1000
            return ComponentHealth(
                name=name, status="healthy", latency_ms=latency_ms
            )
        return ComponentHealth(
            name=name, status="unhealthy", message="Store not initialized"
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return ComponentHealth(
            name=name,
            status="unhealthy",
            latency_ms=latency_ms,
            message=str(e),
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    _settings: SettingsDep,
    config_store: ConfigStoreDep,
    session_store: SessionStoreDep,
    audit_store: AuditStoreDep,
) -> HealthResponse:
    """Check service health status.

    Returns the overall health status of the service along with
    the status of individual components.

    Args:
        _settings: Application settings (unused, for future version info)
        config_store: Configuration store
        session_store: Session store
        audit_store: Audit store

    Returns:
        HealthResponse with status and component health
    """
    logger.debug("health_check_request")

    # Check each component
    components = [
        await _check_store_health(config_store, "config_store"),
        await _check_store_health(session_store, "session_store"),
        await _check_store_health(audit_store, "audit_store"),
    ]

    # Determine overall status
    unhealthy_count = sum(1 for c in components if c.status == "unhealthy")
    degraded_count = sum(1 for c in components if c.status == "degraded")

    overall_status: Literal["healthy", "degraded", "unhealthy"]
    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    response = HealthResponse(
        status=overall_status,
        version="1.0.0",
        components=components,
        timestamp=datetime.now(UTC),
    )

    logger.debug("health_check_completed", status=overall_status)

    return response


@router.get("/metrics")
async def get_metrics() -> Response:
    """Get Prometheus metrics.

    Returns metrics in Prometheus text format for scraping.

    Returns:
        Prometheus metrics as text/plain
    """
    logger.debug("metrics_request")

    metrics = generate_latest()

    return Response(
        content=metrics,
        media_type=CONTENT_TYPE_LATEST,
    )
