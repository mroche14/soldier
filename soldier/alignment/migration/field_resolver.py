"""Missing field resolver for retrieving field values without user interaction.

Attempts to resolve missing data without asking the customer:
1. Check customer profile (cross-session, persistent)
2. Check session variables (current conversation)
3. Extract from conversation history (LLM-based)

Enhanced with:
- Schema validation via ProfileFieldValidator
- Lineage tracking for extracted values
- Collection prompts from ProfileFieldDefinition
"""

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from soldier.alignment.migration.models import FieldResolutionResult, ResolutionSource
from soldier.observability.logging import get_logger
from soldier.profile.enums import SourceType
from soldier.providers.llm import LLMMessage

if TYPE_CHECKING:
    from soldier.conversation.models import Session
    from soldier.profile.models import ProfileFieldDefinition
    from soldier.profile.store import ProfileStore
    from soldier.profile.validation import ProfileFieldValidator

logger = get_logger(__name__)

# Confidence thresholds
USE_THRESHOLD = 0.85  # Minimum confidence to use extracted value
NO_CONFIRM_THRESHOLD = 0.95  # Confidence above which no confirmation needed


EXTRACTION_PROMPT = """You are extracting structured data from a conversation.

## Instructions
- Look for the requested field in the conversation history
- Return the value if explicitly stated or clearly implied
- If the value is uncertain or ambiguous, indicate lower confidence
- If the value is not found, indicate not_found

## Field to extract
Name: {field_name}
Type: {field_type}
Description: {field_description}

## Conversation History
{conversation_history}

## Response Format (JSON only)
{{
    "found": true/false,
    "value": "<extracted value or null>",
    "confidence": 0.0-1.0,
    "source_quote": "<exact quote where you found this, or null>"
}}

Respond with JSON only, no other text."""


class MissingFieldResolver:
    """Service for filling missing fields without user interaction.

    Implements a tiered approach:
    1. Profile data (highest priority - verified, cross-session)
    2. Session variables (current conversation data)
    3. Conversation extraction (LLM-based, lower confidence)

    Enhanced with:
    - Schema validation via ProfileFieldValidator (T146)
    - Collection prompts from ProfileFieldDefinition (T149)
    - Lineage tracking for extracted fields (T150)
    - Value validation before persistence (T151)
    """

    def __init__(
        self,
        profile_store: "ProfileStore | None" = None,
        llm_executor: Any = None,
        field_validator: "ProfileFieldValidator | None" = None,
    ) -> None:
        """Initialize the gap fill service.

        Args:
            profile_store: Store for customer profiles (enhanced for schema operations)
            llm_executor: LLM executor for conversation extraction
            field_validator: Service for validating extracted values against schema
        """
        self._profile_store = profile_store
        self._llm_executor = llm_executor
        self._field_validator = field_validator
        # Cache for field definitions during fill operations
        self._field_definition_cache: dict[str, ProfileFieldDefinition] = {}

    async def fill_gap(
        self,
        field_name: str,
        session: "Session",
        field_type: str = "string",
        field_description: str | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
    ) -> FieldResolutionResult:
        """Try to fill a missing field without asking the user.

        Enhanced with schema integration (T148, T149):
        - Looks up ProfileFieldDefinition for field metadata
        - Uses collection_prompt from definition for better extraction
        - Tracks lineage (source_item_id, source_item_type)
        - Validates extracted values against schema

        Args:
            field_name: Name of the field to fill
            session: Current session
            field_type: Expected type (string, number, date, etc.)
            field_description: Human description for extraction
            tenant_id: Tenant ID for schema lookup (uses session.tenant_id if None)
            agent_id: Agent ID for schema lookup (uses session.agent_id if None)

        Returns:
            FieldResolutionResult with fill status, value, and lineage information
        """
        # Resolve tenant/agent from session if not provided
        _tenant_id = tenant_id or getattr(session, "tenant_id", None)
        _agent_id = agent_id or getattr(session, "agent_id", None)

        # Look up field definition for enhanced extraction (T149)
        field_definition = await self._get_field_definition(
            field_name=field_name,
            tenant_id=_tenant_id,
            agent_id=_agent_id,
        )

        # Use definition metadata if available
        effective_type = field_type
        effective_description = field_description
        if field_definition:
            effective_type = field_definition.value_type or field_type
            # Use collection_prompt as description for better extraction
            effective_description = (
                field_definition.extraction_prompt_hint
                or field_definition.collection_prompt
                or field_description
            )

        # Try profile first (cross-session data)
        if self._profile_store:
            result = await self.try_profile_fill(
                field_name=field_name,
                session=session,
            )
            if result.filled:
                logger.info(
                    "gap_fill_from_profile",
                    session_id=str(session.session_id),
                    field_name=field_name,
                )
                # Attach field definition if found
                if field_definition:
                    result.field_definition_id = field_definition.id
                return result

        # Try session variables
        result = self.try_session_fill(
            field_name=field_name,
            session=session,
        )
        if result.filled:
            logger.info(
                "gap_fill_from_session",
                session_id=str(session.session_id),
                field_name=field_name,
            )
            # Track lineage from session (T150)
            result.source_item_type = SourceType.SESSION.value
            if field_definition:
                result.field_definition_id = field_definition.id
            return result

        # Try conversation extraction (LLM)
        if self._llm_executor:
            result = await self.try_conversation_extraction(
                field_name=field_name,
                session=session,
                field_type=effective_type,
                field_description=effective_description,
            )
            if result.filled:
                logger.info(
                    "gap_fill_from_extraction",
                    session_id=str(session.session_id),
                    field_name=field_name,
                    confidence=result.confidence,
                )
                # Track lineage for extracted values (T150)
                result.source_item_type = SourceType.TOOL.value  # LLM extraction is a tool
                if field_definition:
                    result.field_definition_id = field_definition.id
                    # Validate extracted value against schema (T151)
                    validation_errors = await self._validate_result(
                        result=result,
                        field_definition=field_definition,
                    )
                    result.validation_errors = validation_errors
                return result

        # Not found
        logger.info(
            "gap_fill_not_found",
            session_id=str(session.session_id),
            field_name=field_name,
        )
        return FieldResolutionResult(
            field_name=field_name,
            filled=False,
            source=ResolutionSource.NOT_FOUND,
            field_definition_id=field_definition.id if field_definition else None,
        )

    async def _get_field_definition(
        self,
        field_name: str,
        tenant_id: UUID | None,
        agent_id: UUID | None,
    ) -> "ProfileFieldDefinition | None":
        """Get field definition from cache or store.

        Args:
            field_name: Name of the field
            tenant_id: Tenant identifier
            agent_id: Agent identifier

        Returns:
            ProfileFieldDefinition if found, None otherwise
        """
        # Check cache first
        cache_key = f"{tenant_id}:{agent_id}:{field_name}"
        if cache_key in self._field_definition_cache:
            return self._field_definition_cache[cache_key]

        # Look up from store
        if not self._profile_store or not tenant_id or not agent_id:
            return None

        try:
            definition = await self._profile_store.get_field_definition(
                tenant_id=tenant_id,
                agent_id=agent_id,
                field_name=field_name,
            )
            if definition:
                self._field_definition_cache[cache_key] = definition
            return definition
        except Exception as e:
            logger.warning(
                "gap_fill_definition_lookup_failed",
                field_name=field_name,
                error=str(e),
            )
            return None

    async def _validate_result(
        self,
        result: FieldResolutionResult,
        field_definition: "ProfileFieldDefinition",
    ) -> list[str]:
        """Validate gap fill result against schema (T151).

        Args:
            result: The gap fill result to validate
            field_definition: Schema definition to validate against

        Returns:
            List of validation error messages
        """
        if not self._field_validator:
            return []

        if not result.filled or result.value is None:
            return []

        try:
            # Create a temporary ProfileField for validation
            from soldier.profile.enums import ProfileFieldSource
            from soldier.profile.models import ProfileField

            temp_field = ProfileField(
                name=field_definition.name,
                value=result.value,
                value_type=field_definition.value_type,
                source=ProfileFieldSource.EXTRACTED,
            )

            errors = self._field_validator.validate_field(
                field=temp_field,
                definition=field_definition,
            )

            return [f"{e.error_type}: {e.message}" for e in errors]

        except Exception as e:
            logger.warning(
                "gap_fill_validation_failed",
                field_name=result.field_name,
                error=str(e),
            )
            return [f"validation_error: {e}"]

    async def try_profile_fill(
        self,
        field_name: str,
        session: "Session",
    ) -> FieldResolutionResult:
        """Try to fill from customer profile.

        Args:
            field_name: Field to look up
            session: Current session

        Returns:
            FieldResolutionResult from profile or not found
        """
        if not self._profile_store:
            return FieldResolutionResult(
                field_name=field_name,
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            )

        try:
            # Look up the profile field using ProfileStore interface
            customer_id = getattr(session, "customer_id", None)
            if customer_id is None:
                return FieldResolutionResult(
                    field_name=field_name,
                    filled=False,
                    source=ResolutionSource.NOT_FOUND,
                )

            profile = await self._profile_store.get_by_customer_id(
                tenant_id=session.tenant_id,
                customer_id=customer_id,
            )

            if profile and field_name in profile.fields:
                field = profile.fields[field_name]
                # Check if field is active (not expired, orphaned, or superseded)
                from soldier.profile.enums import ItemStatus
                if field.status == ItemStatus.ACTIVE:
                    return FieldResolutionResult(
                        field_name=field_name,
                        filled=True,
                        value=field.value,
                        source=ResolutionSource.PROFILE,
                        confidence=field.confidence,
                        needs_confirmation=field.requires_confirmation,
                        source_item_id=field.id,
                        source_item_type=SourceType.PROFILE_FIELD.value,
                    )
        except Exception as e:
            logger.warning(
                "gap_fill_profile_lookup_failed",
                field_name=field_name,
                error=str(e),
            )

        return FieldResolutionResult(
            field_name=field_name,
            filled=False,
            source=ResolutionSource.NOT_FOUND,
        )

    def try_session_fill(
        self,
        field_name: str,
        session: "Session",
    ) -> FieldResolutionResult:
        """Try to fill from session variables.

        Args:
            field_name: Field to look up
            session: Current session

        Returns:
            FieldResolutionResult from session or not found
        """
        if field_name in session.variables:
            return FieldResolutionResult(
                field_name=field_name,
                filled=True,
                value=session.variables[field_name],
                source=ResolutionSource.SESSION,
                confidence=1.0,  # Session data is explicit
                needs_confirmation=False,
            )

        return FieldResolutionResult(
            field_name=field_name,
            filled=False,
            source=ResolutionSource.NOT_FOUND,
        )

    async def try_conversation_extraction(
        self,
        field_name: str,
        session: "Session",
        field_type: str = "string",
        field_description: str | None = None,
        max_turns: int = 20,
    ) -> FieldResolutionResult:
        """Try to extract field value from conversation history.

        Uses LLM to find and extract the field value from recent
        conversation turns.

        Args:
            field_name: Field to extract
            session: Current session
            field_type: Expected type
            field_description: Human description
            max_turns: Maximum turns to include

        Returns:
            FieldResolutionResult with extraction or not found
        """
        if not self._llm_executor:
            return FieldResolutionResult(
                field_name=field_name,
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            )

        # Build conversation history string
        conversation_history = self._build_conversation_history(session, max_turns)

        if not conversation_history.strip():
            return FieldResolutionResult(
                field_name=field_name,
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            )

        # Build extraction prompt
        prompt = EXTRACTION_PROMPT.format(
            field_name=field_name,
            field_type=field_type,
            field_description=field_description or f"The {field_name} value",
            conversation_history=conversation_history,
        )

        try:
            # Call LLM for extraction
            messages = [
                LLMMessage(role="system", content="You extract structured data from conversations."),
                LLMMessage(role="user", content=prompt),
            ]
            response = await self._llm_executor.generate(
                messages=messages,
                max_tokens=200,
            )

            # Parse response
            return self._parse_extraction_response(field_name, response.content)

        except Exception as e:
            logger.warning(
                "gap_fill_extraction_failed",
                session_id=str(session.session_id),
                field_name=field_name,
                error=str(e),
            )
            return FieldResolutionResult(
                field_name=field_name,
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            )

    def _build_conversation_history(
        self,
        session: "Session",
        max_turns: int,
    ) -> str:
        """Build conversation history string for extraction.

        Args:
            session: Current session
            max_turns: Maximum turns to include

        Returns:
            Formatted conversation history
        """
        # Get conversation messages from session
        messages = getattr(session, "message_history", [])

        if not messages:
            return ""

        # Take last N turns
        recent_messages = messages[-max_turns:]

        # Format as conversation
        lines = []
        for msg in recent_messages:
            role = getattr(msg, "role", "user")
            content = getattr(msg, "content", str(msg))
            lines.append(f"{role.upper()}: {content}")

        return "\n".join(lines)

    def _parse_extraction_response(
        self,
        field_name: str,
        response: str,
    ) -> FieldResolutionResult:
        """Parse LLM extraction response.

        Args:
            field_name: Field being extracted
            response: LLM response text

        Returns:
            FieldResolutionResult parsed from response
        """
        try:
            # Try to parse as JSON
            data = json.loads(response.strip())

            found = data.get("found", False)
            if not found:
                return FieldResolutionResult(
                    field_name=field_name,
                    filled=False,
                    source=ResolutionSource.NOT_FOUND,
                )

            confidence = float(data.get("confidence", 0.0))

            # Check against threshold
            if confidence < USE_THRESHOLD:
                return FieldResolutionResult(
                    field_name=field_name,
                    filled=False,
                    source=ResolutionSource.NOT_FOUND,
                )

            return FieldResolutionResult(
                field_name=field_name,
                filled=True,
                value=data.get("value"),
                source=ResolutionSource.EXTRACTION,
                confidence=confidence,
                needs_confirmation=confidence < NO_CONFIRM_THRESHOLD,
                extraction_quote=data.get("source_quote"),
            )

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(
                "gap_fill_parse_failed",
                field_name=field_name,
                error=str(e),
            )
            return FieldResolutionResult(
                field_name=field_name,
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            )

    async def persist_extracted_values(
        self,
        session: "Session",
        results: list[FieldResolutionResult],
        skip_validation_failures: bool = True,
    ) -> int:
        """Persist extracted values to profile for future use.

        Enhanced with lineage tracking (T150) and validation checks (T151).

        Args:
            session: Current session
            results: Gap fill results to persist
            skip_validation_failures: If True, don't persist values with validation errors

        Returns:
            Number of values persisted
        """
        if not self._profile_store:
            return 0

        persisted = 0

        for result in results:
            if not result.filled:
                continue

            # Only persist extraction results (profile/session are already persisted)
            if result.source != ResolutionSource.EXTRACTION:
                continue

            # Skip values with validation errors if configured (T151)
            if skip_validation_failures and result.validation_errors:
                logger.warning(
                    "gap_fill_persist_skipped_validation",
                    session_id=str(session.session_id),
                    field_name=result.field_name,
                    validation_errors=result.validation_errors,
                )
                continue

            try:
                # Get profile to update
                customer_id = getattr(session, "customer_id", None)
                if customer_id is None:
                    continue

                profile = await self._profile_store.get_by_customer_id(
                    tenant_id=session.tenant_id,
                    customer_id=customer_id,
                )
                if profile is None:
                    continue

                # Create ProfileField with lineage tracking (T150)
                from soldier.profile.enums import ProfileFieldSource
                from soldier.profile.models import ProfileField

                field = ProfileField(
                    name=result.field_name,
                    value=result.value,
                    value_type="string",  # Default, could be enhanced
                    source=ProfileFieldSource.EXTRACTED,
                    source_session_id=session.session_id,
                    confidence=result.confidence,
                    requires_confirmation=result.needs_confirmation,
                    source_item_type=SourceType(result.source_item_type) if result.source_item_type else None,
                    source_metadata={
                        "extraction_quote": result.extraction_quote,
                        "session_id": str(session.session_id),
                    },
                )

                await self._profile_store.update_field(
                    tenant_id=session.tenant_id,
                    profile_id=profile.id,
                    field=field,
                    supersede_existing=True,
                )
                persisted += 1

                logger.info(
                    "gap_fill_persisted",
                    session_id=str(session.session_id),
                    field_name=result.field_name,
                    source_item_type=result.source_item_type,
                    confidence=result.confidence,
                )

            except Exception as e:
                logger.warning(
                    "gap_fill_persist_failed",
                    session_id=str(session.session_id),
                    field_name=result.field_name,
                    error=str(e),
                )

        return persisted

    async def fill_multiple(
        self,
        field_names: list[str],
        session: "Session",
        field_definitions: dict[str, dict[str, Any]] | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
    ) -> dict[str, FieldResolutionResult]:
        """Fill multiple fields at once.

        Enhanced to use schema lookups (T148, T149).

        Args:
            field_names: Fields to fill
            session: Current session
            field_definitions: Optional field type/description info (overrides schema)
            tenant_id: Tenant ID for schema lookup
            agent_id: Agent ID for schema lookup

        Returns:
            Dict mapping field name to result
        """
        results = {}

        for field_name in field_names:
            field_def = (field_definitions or {}).get(field_name, {})
            result = await self.fill_gap(
                field_name=field_name,
                session=session,
                field_type=field_def.get("type", "string"),
                field_description=field_def.get("description"),
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            results[field_name] = result

        return results

    async def fill_scenario_requirements(
        self,
        session: "Session",
        scenario_id: UUID,
        step_id: UUID | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> dict[str, FieldResolutionResult]:
        """Fill missing fields required for a scenario entry/step.

        Uses get_missing_fields() from ProfileStore to determine what fields
        are needed based on ScenarioFieldRequirement bindings.

        Args:
            session: Current session
            scenario_id: Scenario to check requirements for
            step_id: Optional specific step to check
            tenant_id: Tenant ID (uses session.tenant_id if None)
            agent_id: Agent ID (uses session.agent_id if None)
            required_level: Filter by level ("hard", "soft", or None for all)

        Returns:
            Dict mapping field name to fill result. Keys are requirement field_names,
            values are FieldResolutionResult with fill status and metadata.
        """
        if not self._profile_store:
            return {}

        _tenant_id = tenant_id or getattr(session, "tenant_id", None)
        _agent_id = agent_id or getattr(session, "agent_id", None)
        _customer_id = getattr(session, "customer_id", None)

        if not _tenant_id:
            logger.warning("fill_scenario_requirements_missing_tenant_id")
            return {}

        if not _customer_id:
            logger.warning("fill_scenario_requirements_missing_customer_id")
            return {}

        try:
            # Get the customer profile using ProfileStore interface
            profile = await self._profile_store.get_by_customer_id(
                tenant_id=_tenant_id,
                customer_id=_customer_id,
            )

            if profile is None:
                logger.info(
                    "fill_scenario_requirements_no_profile",
                    session_id=str(session.session_id),
                    customer_id=str(_customer_id),
                )
                # No profile means all fields are missing - continue with empty profile
                from soldier.profile.models import CustomerProfile
                profile = CustomerProfile(
                    tenant_id=_tenant_id,
                    customer_id=_customer_id,
                )

            # get_missing_fields returns list[ScenarioFieldRequirement]
            missing_requirements = await self._profile_store.get_missing_fields(
                tenant_id=_tenant_id,
                profile=profile,
                scenario_id=scenario_id,
                step_id=step_id,
                required_level=required_level,
            )

            if not missing_requirements:
                logger.info(
                    "fill_scenario_requirements_all_satisfied",
                    session_id=str(session.session_id),
                    scenario_id=str(scenario_id),
                )
                return {}

            # Extract field names from requirements (ordered by collection_order)
            field_names = [req.field_name for req in missing_requirements]

            logger.info(
                "fill_scenario_requirements_start",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
                step_id=str(step_id) if step_id else None,
                missing_fields=field_names,
                required_level=required_level,
            )

            # Try to fill each missing field
            results = await self.fill_multiple(
                field_names=field_names,
                session=session,
                tenant_id=_tenant_id,
                agent_id=_agent_id,
            )

            # Enrich results with requirement metadata
            for req in missing_requirements:
                if req.field_name in results:
                    result = results[req.field_name]
                    # Attach requirement info for downstream handling
                    result.required_level = req.required_level.value
                    result.fallback_action = req.fallback_action.value
                    result.collection_order = req.collection_order

            # Log summary
            filled_count = sum(1 for r in results.values() if r.filled)
            unfilled_hard = sum(
                1 for r in results.values()
                if not r.filled and getattr(r, "required_level", None) == "hard"
            )

            logger.info(
                "fill_scenario_requirements_complete",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
                total_missing=len(field_names),
                filled_count=filled_count,
                unfilled_hard=unfilled_hard,
            )

            return results

        except Exception as e:
            logger.error(
                "fill_scenario_requirements_failed",
                session_id=str(session.session_id),
                scenario_id=str(scenario_id),
                error=str(e),
            )
            return {}

    def get_unfilled_hard_requirements(
        self,
        results: dict[str, FieldResolutionResult],
    ) -> list[FieldResolutionResult]:
        """Get unfilled hard requirements from fill results.

        Use this to check if scenario entry should be blocked.

        Args:
            results: Results from fill_scenario_requirements()

        Returns:
            List of unfilled hard requirements
        """
        return [
            r for r in results.values()
            if not r.filled and getattr(r, "required_level", None) == "hard"
        ]

    def get_fields_to_ask(
        self,
        results: dict[str, FieldResolutionResult],
    ) -> list[FieldResolutionResult]:
        """Get unfilled fields that should be asked from user.

        Filters for unfilled fields with fallback_action=ASK.

        Args:
            results: Results from fill_scenario_requirements()

        Returns:
            List of fields to ask, ordered by collection_order
        """
        fields_to_ask = [
            r for r in results.values()
            if not r.filled and getattr(r, "fallback_action", None) == "ask"
        ]
        # Sort by collection_order
        return sorted(
            fields_to_ask,
            key=lambda r: getattr(r, "collection_order", 0),
        )

    def clear_definition_cache(self) -> None:
        """Clear the field definition cache.

        Call this when field definitions may have been updated.
        """
        self._field_definition_cache.clear()
