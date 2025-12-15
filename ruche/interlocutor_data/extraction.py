"""Profile schema extraction service.

Uses LLM to automatically extract required profile fields from scenarios and rules.
Generates InterlocutorDataField and ScenarioFieldRequirement suggestions.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from ruche.config.models.agent import AgentConfig
from ruche.observability.logging import get_logger
from ruche.interlocutor_data.enums import FallbackAction, RequiredLevel, ValidationMode
from ruche.interlocutor_data.models import InterlocutorDataField, ScenarioFieldRequirement

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """Result from schema extraction."""

    field_names: list[str]
    confidence_scores: dict[str, float]
    needs_human_review: bool
    raw_llm_response: str | None = None


@dataclass
class FieldDefinitionSuggestion:
    """Suggested field definition from extraction."""

    name: str
    display_name: str
    value_type: str
    description: str | None = None
    validation_regex: str | None = None
    collection_prompt: str | None = None
    confidence: float = 0.0


@dataclass
class ExtractionOutput:
    """Full output from schema extraction."""

    requirements: list[ScenarioFieldRequirement]
    field_definitions: list[InterlocutorDataField]
    needs_human_review: bool
    extraction_results: list[ExtractionResult] = field(default_factory=list)


# Extraction prompt templates
EXTRACTION_PROMPT = """Analyze the following {content_type} and identify any customer profile fields
that would be needed to evaluate conditions or personalize responses.

{content_type} content:
{content}

Extract a list of profile fields that are referenced or implied. For each field:
1. Field name (snake_case, e.g., date_of_birth, email_address)
2. Display name (human readable)
3. Value type (string, email, phone, date, number, boolean, json)
4. Whether it's required to proceed (hard requirement) or just helpful (soft requirement)

Respond in JSON format:
{{
  "fields": [
    {{
      "name": "field_name",
      "display_name": "Human Readable Name",
      "value_type": "string|email|phone|date|number|boolean|json",
      "required_level": "hard|soft",
      "confidence": 0.0-1.0,
      "reasoning": "why this field is needed"
    }}
  ]
}}

Only include fields that are explicitly referenced or strongly implied by the content.
"""

FIELD_DEFINITION_PROMPT = """Generate a complete field definition for the following profile field:

Field: {field_name}
Context: This field is used in scenarios/rules for customer personalization.

Provide:
1. A collection prompt (how to ask the customer for this information)
2. Validation regex (if applicable)
3. Example values for extraction

Respond in JSON format:
{{
  "collection_prompt": "polite question to ask customer",
  "validation_regex": "optional regex pattern",
  "examples": ["example1", "example2"]
}}
"""


class InterlocutorDataSchemaExtractor:
    """Extracts profile field requirements from scenarios and rules.

    Uses LLM to analyze scenario conditions, step content, and rule
    conditions to identify what customer data would be needed.

    Features:
    - Confidence scoring (0.0 to 1.0)
    - Human review flag when confidence < 0.8
    - Field definition suggestions with collection prompts
    """

    def __init__(
        self,
        llm_executor: Any | None = None,
        confidence_threshold: float = 0.8,
    ) -> None:
        """Initialize extractor.

        Args:
            llm_executor: LLM executor for extraction (None for mock mode)
            confidence_threshold: Threshold below which human review is flagged
        """
        self._llm = llm_executor
        self._confidence_threshold = confidence_threshold

    async def extract_requirements(
        self,
        content: str,
        content_type: str = "scenario",
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        scenario_id: UUID | None = None,
    ) -> ExtractionResult:
        """Extract profile field requirements from content.

        Args:
            content: Text content to analyze (scenario or rule)
            content_type: Type of content ("scenario" or "rule")
            tenant_id: Optional tenant ID for result tracking
            agent_id: Optional agent ID for result tracking
            scenario_id: Optional scenario ID for linking requirements

        Returns:
            ExtractionResult with field names and confidence scores
        """
        if self._llm is None:
            # Mock mode - return empty result
            logger.warning(
                "schema_extraction_mock_mode",
                content_type=content_type,
            )
            return ExtractionResult(
                field_names=[],
                confidence_scores={},
                needs_human_review=True,
                raw_llm_response=None,
            )

        prompt = EXTRACTION_PROMPT.format(
            content_type=content_type,
            content=content,
        )

        try:
            response = await self._llm.generate(prompt)
            parsed = self._parse_extraction_response(response)

            needs_review = any(
                score < self._confidence_threshold
                for score in parsed["confidence_scores"].values()
            )

            logger.info(
                "schema_extraction_completed",
                content_type=content_type,
                field_count=len(parsed["field_names"]),
                needs_review=needs_review,
            )

            return ExtractionResult(
                field_names=parsed["field_names"],
                confidence_scores=parsed["confidence_scores"],
                needs_human_review=needs_review,
                raw_llm_response=response,
            )

        except Exception as e:
            logger.error(
                "schema_extraction_failed",
                content_type=content_type,
                error=str(e),
            )
            return ExtractionResult(
                field_names=[],
                confidence_scores={},
                needs_human_review=True,
                raw_llm_response=None,
            )

    async def suggest_field_definitions(
        self,
        field_names: list[str],
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[FieldDefinitionSuggestion]:
        """Generate field definition suggestions for extracted fields.

        Args:
            field_names: List of field names to generate definitions for
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            List of FieldDefinitionSuggestion objects
        """
        suggestions = []

        for name in field_names:
            suggestion = await self._suggest_single_field(name)
            suggestions.append(suggestion)

        logger.info(
            "field_definitions_suggested",
            field_count=len(suggestions),
        )

        return suggestions

    async def _suggest_single_field(self, field_name: str) -> FieldDefinitionSuggestion:
        """Generate suggestion for a single field."""
        # Infer type from field name patterns
        inferred_type = self._infer_type_from_name(field_name)
        display_name = self._generate_display_name(field_name)

        if self._llm is None:
            # Return basic suggestion without LLM
            return FieldDefinitionSuggestion(
                name=field_name,
                display_name=display_name,
                value_type=inferred_type,
                description=None,
                validation_regex=self._get_default_regex(inferred_type),
                collection_prompt=self._get_default_prompt(display_name, inferred_type),
                confidence=0.5,  # Lower confidence without LLM
            )

        prompt = FIELD_DEFINITION_PROMPT.format(field_name=field_name)

        try:
            response = await self._llm.generate(prompt)
            parsed = self._parse_field_definition_response(response)

            return FieldDefinitionSuggestion(
                name=field_name,
                display_name=display_name,
                value_type=inferred_type,
                description=parsed.get("description"),
                validation_regex=parsed.get("validation_regex"),
                collection_prompt=parsed.get("collection_prompt"),
                confidence=0.9,
            )

        except Exception:
            # Fall back to basic suggestion
            return FieldDefinitionSuggestion(
                name=field_name,
                display_name=display_name,
                value_type=inferred_type,
                confidence=0.5,
            )

    def create_requirements(
        self,
        extraction_result: ExtractionResult,
        tenant_id: UUID,
        agent_id: UUID,
        scenario_id: UUID,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Create ScenarioFieldRequirement objects from extraction result.

        Args:
            extraction_result: Result from extract_requirements
            tenant_id: Tenant identifier
            agent_id: Agent identifier
            scenario_id: Scenario identifier
            step_id: Optional step identifier

        Returns:
            List of ScenarioFieldRequirement objects
        """
        requirements = []

        for i, field_name in enumerate(extraction_result.field_names):
            confidence = extraction_result.confidence_scores.get(field_name, 0.5)

            requirement = ScenarioFieldRequirement(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scenario_id=scenario_id,
                step_id=step_id,
                field_name=field_name,
                required_level=RequiredLevel.HARD if confidence > 0.7 else RequiredLevel.SOFT,
                fallback_action=FallbackAction.ASK,
                collection_order=i,
                needs_human_review=confidence < self._confidence_threshold,
            )
            requirements.append(requirement)

        return requirements

    def create_field_definitions(
        self,
        suggestions: list[FieldDefinitionSuggestion],
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[InterlocutorDataField]:
        """Create InterlocutorDataField objects from suggestions.

        Args:
            suggestions: List of field definition suggestions
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            List of InterlocutorDataField objects
        """
        definitions = []

        for suggestion in suggestions:
            definition = InterlocutorDataField(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                name=suggestion.name,
                display_name=suggestion.display_name,
                description=suggestion.description,
                value_type=suggestion.value_type,
                validation_regex=suggestion.validation_regex,
                validation_mode=ValidationMode.STRICT if suggestion.validation_regex else ValidationMode.WARN,
                collection_prompt=suggestion.collection_prompt,
            )
            definitions.append(definition)

        return definitions

    def _parse_extraction_response(self, response: str) -> dict:
        """Parse LLM response for extraction."""
        import json

        try:
            data = json.loads(response)
            fields = data.get("fields", [])

            field_names = [f["name"] for f in fields]
            confidence_scores = {f["name"]: f.get("confidence", 0.5) for f in fields}

            return {
                "field_names": field_names,
                "confidence_scores": confidence_scores,
            }
        except (json.JSONDecodeError, KeyError):
            return {"field_names": [], "confidence_scores": {}}

    def _parse_field_definition_response(self, response: str) -> dict:
        """Parse LLM response for field definition."""
        import json

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _infer_type_from_name(self, field_name: str) -> str:
        """Infer field type from name patterns."""
        name_lower = field_name.lower()

        if "email" in name_lower:
            return "email"
        if "phone" in name_lower or "mobile" in name_lower or "cell" in name_lower:
            return "phone"
        if "date" in name_lower or "dob" in name_lower or "birth" in name_lower:
            return "date"
        if "age" in name_lower or "count" in name_lower or "number" in name_lower:
            return "number"
        if "is_" in name_lower or "has_" in name_lower or name_lower.startswith("enabled"):
            return "boolean"

        return "string"

    def _generate_display_name(self, field_name: str) -> str:
        """Generate human-readable display name from field name."""
        return field_name.replace("_", " ").title()

    def _get_default_regex(self, value_type: str) -> str | None:
        """Get default validation regex for type."""
        patterns = {
            "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
            "phone": r"^\+?[1-9]\d{6,14}$",
        }
        return patterns.get(value_type)

    def _get_default_prompt(self, display_name: str, value_type: str) -> str:
        """Get default collection prompt."""
        prompts = {
            "email": f"Could you please provide your {display_name.lower()}?",
            "phone": f"What is your {display_name.lower()}?",
            "date": f"When is your {display_name.lower()}? (YYYY-MM-DD format)",
            "number": f"What is your {display_name.lower()}?",
            "boolean": f"Do you have {display_name.lower()}? (yes/no)",
        }
        return prompts.get(value_type, f"Please provide your {display_name.lower()}.")
