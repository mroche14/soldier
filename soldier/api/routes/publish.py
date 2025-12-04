"""Publishing and versioning endpoints."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

from soldier.alignment.models import PublishJob
from soldier.api.dependencies import AgentConfigStoreDep
from soldier.api.exceptions import (
    AgentNotFoundError,
    PublishInProgressError,
    PublishJobNotFoundError,
)
from soldier.api.middleware.auth import TenantContextDep
from soldier.api.models.crud import (
    PublishJobResponse,
    PublishRequest,
    PublishStageResponse,
    PublishStatusResponse,
    RollbackRequest,
)
from soldier.api.services.publish import PublishService
from soldier.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/publish")

# Module-level service instance (would be injected in production)
_publish_service: PublishService | None = None


def _get_publish_service(config_store: AgentConfigStoreDep) -> PublishService:
    """Get or create the publish service."""
    global _publish_service
    if _publish_service is None:
        _publish_service = PublishService(config_store)
    return _publish_service


async def _verify_agent_exists(
    config_store: AgentConfigStoreDep, tenant_id: UUID, agent_id: UUID
) -> None:
    """Verify agent exists and belongs to tenant."""
    agent = await config_store.get_agent(tenant_id, agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found")


def _map_publish_job_to_response(job: PublishJob) -> PublishJobResponse:
    """Map PublishJob to response."""
    return PublishJobResponse(
        publish_id=job.id,
        version=job.version,
        status=job.status,
        stages=[
            PublishStageResponse(
                name=stage.name,
                status=stage.status,
                duration_ms=stage.duration_ms,
                error=stage.error,
            )
            for stage in job.stages
        ],
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("", response_model=PublishStatusResponse)
async def get_publish_status(
    agent_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> PublishStatusResponse:
    """Get current publish status for an agent."""
    logger.debug(
        "get_publish_status_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    service = _get_publish_service(config_store)
    status = await service.get_publish_status(tenant_context.tenant_id, agent_id)

    return PublishStatusResponse(
        current_version=status.get("current_version", 1),
        draft_version=status.get("draft_version", 1),
        has_unpublished_changes=status.get("has_unpublished_changes", False),
        last_published_at=status.get("last_published_at"),
        last_published_by=status.get("last_published_by"),
        changes_since_publish=status.get("changes_since_publish", {}),
    )


@router.post("", response_model=PublishJobResponse, status_code=202)
async def initiate_publish(
    agent_id: UUID,
    request: PublishRequest,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
    background_tasks: BackgroundTasks,
) -> PublishJobResponse:
    """Initiate a publish operation.

    Returns immediately with job ID. Use GET /publish/{publish_id}
    to check progress.
    """
    logger.info(
        "initiate_publish_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    service = _get_publish_service(config_store)

    try:
        job = await service.create_publish_job(
            tenant_context.tenant_id, agent_id, request.description
        )
    except ValueError as e:
        if "already in progress" in str(e):
            raise PublishInProgressError(str(e)) from e
        raise

    # Execute publish in background
    background_tasks.add_task(service.execute_publish, job.id)

    logger.info(
        "publish_initiated",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        publish_id=str(job.id),
    )

    return _map_publish_job_to_response(job)


@router.get("/{publish_id}", response_model=PublishJobResponse)
async def get_publish_job(
    agent_id: UUID,
    publish_id: UUID,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> PublishJobResponse:
    """Get the status of a publish job."""
    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    service = _get_publish_service(config_store)
    job = await service.get_job(tenant_context.tenant_id, publish_id)

    if job is None:
        raise PublishJobNotFoundError(f"Publish job {publish_id} not found")

    return _map_publish_job_to_response(job)


@router.post("/rollback", response_model=PublishJobResponse)
async def rollback_to_version(
    agent_id: UUID,
    request: RollbackRequest,
    tenant_context: TenantContextDep,
    config_store: AgentConfigStoreDep,
) -> PublishJobResponse:
    """Rollback agent configuration to a previous version."""
    logger.info(
        "rollback_request",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        target_version=request.target_version,
    )

    await _verify_agent_exists(config_store, tenant_context.tenant_id, agent_id)

    service = _get_publish_service(config_store)

    try:
        job = await service.rollback_to_version(
            tenant_context.tenant_id,
            agent_id,
            request.target_version,
            request.reason,
        )
    except ValueError as e:
        raise AgentNotFoundError(str(e)) from e

    logger.info(
        "rollback_completed",
        tenant_id=str(tenant_context.tenant_id),
        agent_id=str(agent_id),
        target_version=request.target_version,
    )

    return _map_publish_job_to_response(job)
