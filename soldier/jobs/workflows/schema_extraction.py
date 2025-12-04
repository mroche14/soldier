"""Schema extraction workflow.

Background job that extracts profile field requirements from scenarios and rules.
Non-blocking - failures don't prevent scenario/rule creation.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from soldier.observability.logging import get_logger
from soldier.profile.extraction import ProfileItemSchemaExtractor
from soldier.profile.store import ProfileStore

logger = get_logger(__name__)


@dataclass
class ExtractSchemaInput:
    """Input for schema extraction workflow."""

    tenant_id: str
    agent_id: str
    content_id: str  # scenario_id or rule_id
    content_type: str  # "scenario" or "rule"
    content_text: str  # The actual text to analyze


@dataclass
class ExtractSchemaOutput:
    """Output from schema extraction workflow."""

    requirements_created: int
    definitions_created: int
    needs_human_review: bool
    success: bool
    error: str | None = None


class ExtractSchemaRequirementsWorkflow:
    """Workflow to extract schema requirements from scenarios/rules.

    This workflow:
    1. Analyzes scenario or rule text with LLM
    2. Extracts required profile fields
    3. Creates ScenarioFieldRequirement entries
    4. Optionally creates ProfileFieldDefinition suggestions

    Non-blocking: Failures don't prevent the scenario/rule from being created.
    Idempotent: Re-running updates existing requirements.
    """

    WORKFLOW_NAME = "extract-schema-requirements"

    def __init__(
        self,
        extractor: ProfileItemSchemaExtractor,
        profile_store: ProfileStore,
    ) -> None:
        """Initialize workflow.

        Args:
            extractor: Schema extractor service
            profile_store: Profile store for persisting requirements
        """
        self._extractor = extractor
        self._store = profile_store

    async def run(self, input_data: ExtractSchemaInput) -> ExtractSchemaOutput:
        """Execute the schema extraction workflow.

        Args:
            input_data: Workflow input with content to analyze

        Returns:
            ExtractSchemaOutput with creation counts
        """
        try:
            tenant_id = UUID(input_data.tenant_id)
            agent_id = UUID(input_data.agent_id)
            content_id = UUID(input_data.content_id)
        except ValueError as e:
            return ExtractSchemaOutput(
                requirements_created=0,
                definitions_created=0,
                needs_human_review=True,
                success=False,
                error=f"Invalid UUID: {e}",
            )

        try:
            # Step 1: Extract requirements from content
            extraction_result = await self._extractor.extract_requirements(
                content=input_data.content_text,
                content_type=input_data.content_type,
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=content_id if input_data.content_type == "scenario" else None,
            )

            if not extraction_result.field_names:
                logger.info(
                    "schema_extraction_no_fields",
                    content_type=input_data.content_type,
                    content_id=str(content_id),
                )
                return ExtractSchemaOutput(
                    requirements_created=0,
                    definitions_created=0,
                    needs_human_review=False,
                    success=True,
                )

            # Step 2: Create requirements
            requirements = self._extractor.create_requirements(
                extraction_result=extraction_result,
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=content_id,
            )

            # Step 3: Persist requirements
            for req in requirements:
                await self._store.save_scenario_requirement(req)

            # Step 4: Generate field definition suggestions
            suggestions = await self._extractor.suggest_field_definitions(
                field_names=extraction_result.field_names,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

            # Step 5: Create and persist field definitions (if they don't exist)
            definitions = self._extractor.create_field_definitions(
                suggestions=suggestions,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )

            definitions_created = 0
            for definition in definitions:
                # Check if definition already exists
                existing = await self._store.get_field_definition(
                    tenant_id, agent_id, definition.name
                )
                if not existing:
                    await self._store.save_field_definition(definition)
                    definitions_created += 1

            logger.info(
                "schema_extraction_completed",
                content_type=input_data.content_type,
                content_id=str(content_id),
                requirements_created=len(requirements),
                definitions_created=definitions_created,
                needs_review=extraction_result.needs_human_review,
            )

            return ExtractSchemaOutput(
                requirements_created=len(requirements),
                definitions_created=definitions_created,
                needs_human_review=extraction_result.needs_human_review,
                success=True,
            )

        except Exception as e:
            logger.error(
                "schema_extraction_failed",
                content_type=input_data.content_type,
                content_id=input_data.content_id,
                error=str(e),
            )
            return ExtractSchemaOutput(
                requirements_created=0,
                definitions_created=0,
                needs_human_review=True,
                success=False,
                error=str(e),
            )


def register_workflow(
    hatchet: Any,
    extractor: ProfileItemSchemaExtractor,
    profile_store: ProfileStore,
) -> Any:
    """Register the schema extraction workflow with Hatchet.

    Args:
        hatchet: Hatchet SDK instance
        extractor: Schema extractor service
        profile_store: Profile store for persisting requirements

    Returns:
        Registered workflow
    """
    workflow_instance = ExtractSchemaRequirementsWorkflow(extractor, profile_store)

    @hatchet.workflow(name=ExtractSchemaRequirementsWorkflow.WORKFLOW_NAME)
    class HatchetExtractSchemaRequirementsWorkflow:
        """Hatchet workflow wrapper for schema extraction."""

        @hatchet.step(retries=2, retry_delay="30s")
        async def extract_schema(self, context: Any) -> dict:
            """Execute the extraction step."""
            input_data = context.workflow_input()
            result = await workflow_instance.run(
                ExtractSchemaInput(
                    tenant_id=input_data["tenant_id"],
                    agent_id=input_data["agent_id"],
                    content_id=input_data["content_id"],
                    content_type=input_data["content_type"],
                    content_text=input_data["content_text"],
                )
            )
            return {
                "requirements_created": result.requirements_created,
                "definitions_created": result.definitions_created,
                "needs_human_review": result.needs_human_review,
                "success": result.success,
                "error": result.error,
            }

    return HatchetExtractSchemaRequirementsWorkflow
