"""Publish job orchestration service."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ruche.alignment.models import PublishJob
from ruche.alignment.stores.agent_config_store import AgentConfigStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class PublishService:
    """Service for orchestrating publish operations.

    Manages the lifecycle of publish jobs and executes
    the multi-stage publish process.
    """

    def __init__(self, config_store: AgentConfigStore) -> None:
        """Initialize publish service.

        Args:
            config_store: Store for configuration data
        """
        self._config_store = config_store
        # In-memory job storage for MVP - would be Redis in production
        self._jobs: dict[UUID, PublishJob] = {}

    async def get_publish_status(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """Get current publish status for an agent.

        Returns:
            Dict with current_version, draft_version, has_unpublished_changes, etc.
        """
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if agent is None:
            return {}

        # For MVP, we don't track draft changes separately
        # In production, this would compare draft vs published state
        return {
            "current_version": agent.current_version,
            "draft_version": agent.current_version,
            "has_unpublished_changes": False,
            "last_published_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "last_published_by": None,
            "changes_since_publish": {
                "scenarios_added": 0,
                "scenarios_modified": 0,
                "rules_added": 0,
                "rules_modified": 0,
                "templates_added": 0,
            },
        }

    async def create_publish_job(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        description: str | None = None,
    ) -> PublishJob:
        """Create a new publish job.

        Args:
            tenant_id: Tenant owning the agent
            agent_id: Agent to publish
            description: Optional description for this publish

        Returns:
            Created publish job
        """
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Check for existing in-progress job
        for job in self._jobs.values():
            if (
                job.tenant_id == tenant_id
                and job.agent_id == agent_id
                and job.status in ("pending", "running")
            ):
                raise ValueError("Publish already in progress")

        # Create job with next version
        job = PublishJob.create_with_stages(
            tenant_id=tenant_id,
            agent_id=agent_id,
            version=agent.current_version + 1,
            started_at=datetime.now(UTC),
            description=description,
        )

        self._jobs[job.id] = job
        return job

    async def get_job(self, tenant_id: UUID, job_id: UUID) -> PublishJob | None:
        """Get a publish job by ID.

        Args:
            tenant_id: Tenant owning the job
            job_id: Job identifier

        Returns:
            Publish job if found and owned by tenant
        """
        job = self._jobs.get(job_id)
        if job and job.tenant_id == tenant_id:
            return job
        return None

    async def execute_publish(self, job_id: UUID) -> PublishJob:
        """Execute a publish job through all stages.

        This is a simplified implementation for MVP.
        Production would run stages asynchronously with proper
        error handling and rollback.

        Args:
            job_id: Job to execute

        Returns:
            Updated job with final status
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        job.status = "running"
        start_time = datetime.now(UTC)

        try:
            for stage in job.stages:
                stage_start = datetime.now(UTC)
                stage.status = "running"

                # Execute stage (simplified for MVP)
                await self._execute_stage(job, stage.name)

                stage.status = "completed"
                stage.duration_ms = int(
                    (datetime.now(UTC) - stage_start).total_seconds() * 1000
                )

            # Update agent version
            agent = await self._config_store.get_agent(job.tenant_id, job.agent_id)
            if agent:
                agent.current_version = job.version
                await self._config_store.save_agent(agent)

            job.status = "completed"
            job.completed_at = datetime.now(UTC)

            logger.info(
                "publish_completed",
                job_id=str(job.id),
                agent_id=str(job.agent_id),
                version=job.version,
                duration_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
            )

        except Exception as e:
            # Mark current stage as failed
            for stage in job.stages:
                if stage.status == "running":
                    stage.status = "failed"
                    stage.error = str(e)
                    break

            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.now(UTC)

            logger.error(
                "publish_failed",
                job_id=str(job.id),
                agent_id=str(job.agent_id),
                error=str(e),
            )

        return job

    async def _execute_stage(self, job: PublishJob, stage_name: str) -> None:
        """Execute a single publish stage.

        Args:
            job: Parent job
            stage_name: Stage to execute
        """
        logger.debug(
            "publish_stage_executing",
            job_id=str(job.id),
            stage=stage_name,
        )

        if stage_name == "validate":
            # Validate configuration consistency
            pass
        elif stage_name == "compile":
            # Compute embeddings, validate references
            pass
        elif stage_name == "write_bundles":
            # Serialize configuration
            pass
        elif stage_name == "swap_pointer":
            # Atomic version switch
            pass
        elif stage_name == "invalidate_cache":
            # Clear cached config
            pass

    async def rollback_to_version(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        target_version: int,
        reason: str | None = None,
    ) -> PublishJob:
        """Rollback an agent to a previous version.

        For MVP, this creates a rollback job that sets the
        agent version. Production would restore configuration
        from version history.

        Args:
            tenant_id: Tenant owning the agent
            agent_id: Agent to rollback
            target_version: Version to rollback to
            reason: Optional reason for rollback

        Returns:
            Created rollback job
        """
        agent = await self._config_store.get_agent(tenant_id, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        if target_version >= agent.current_version:
            raise ValueError(
                f"Target version {target_version} must be less than "
                f"current version {agent.current_version}"
            )

        # Create rollback job
        job = PublishJob.create_with_stages(
            tenant_id=tenant_id,
            agent_id=agent_id,
            version=target_version,
            started_at=datetime.now(UTC),
            description=f"Rollback to v{target_version}" + (f": {reason}" if reason else ""),
        )

        self._jobs[job.id] = job

        # Execute rollback immediately for MVP
        job.status = "running"
        for stage in job.stages:
            stage.status = "completed"
            stage.duration_ms = 1

        agent.current_version = target_version
        await self._config_store.save_agent(agent)

        job.status = "completed"
        job.completed_at = datetime.now(UTC)

        logger.info(
            "rollback_completed",
            job_id=str(job.id),
            agent_id=str(agent_id),
            target_version=target_version,
        )

        return job
