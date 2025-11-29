"""Gap fill service for retrieving missing field values.

Attempts to fill missing data without asking the customer:
1. Check customer profile (cross-session, persistent)
2. Check session variables (current conversation)
3. Extract from conversation history (LLM-based)
"""

import json
from typing import TYPE_CHECKING, Any

from soldier.alignment.migration.models import GapFillResult, GapFillSource
from soldier.observability.logging import get_logger
from soldier.providers.llm.base import LLMMessage

if TYPE_CHECKING:
    from soldier.conversation.models import Session
    from soldier.memory.profile import ProfileStore
    from soldier.providers.llm.base import LLMProvider

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


class GapFillService:
    """Service for filling missing fields without user interaction.

    Implements a tiered approach:
    1. Profile data (highest priority - verified, cross-session)
    2. Session variables (current conversation data)
    3. Conversation extraction (LLM-based, lower confidence)
    """

    def __init__(
        self,
        profile_store: "ProfileStore | None" = None,
        llm_provider: "LLMProvider | None" = None,
    ) -> None:
        """Initialize the gap fill service.

        Args:
            profile_store: Store for customer profiles
            llm_provider: LLM provider for conversation extraction
        """
        self._profile_store = profile_store
        self._llm_provider = llm_provider

    async def fill_gap(
        self,
        field_name: str,
        session: "Session",
        field_type: str = "string",
        field_description: str | None = None,
    ) -> GapFillResult:
        """Try to fill a missing field without asking the user.

        Args:
            field_name: Name of the field to fill
            session: Current session
            field_type: Expected type (string, number, date, etc.)
            field_description: Human description for extraction

        Returns:
            GapFillResult with fill status and value
        """
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
            return result

        # Try conversation extraction (LLM)
        if self._llm_provider:
            result = await self.try_conversation_extraction(
                field_name=field_name,
                session=session,
                field_type=field_type,
                field_description=field_description,
            )
            if result.filled:
                logger.info(
                    "gap_fill_from_extraction",
                    session_id=str(session.session_id),
                    field_name=field_name,
                    confidence=result.confidence,
                )
                return result

        # Not found
        logger.info(
            "gap_fill_not_found",
            session_id=str(session.session_id),
            field_name=field_name,
        )
        return GapFillResult(
            field_name=field_name,
            filled=False,
            source=GapFillSource.NOT_FOUND,
        )

    async def try_profile_fill(
        self,
        field_name: str,
        session: "Session",
    ) -> GapFillResult:
        """Try to fill from customer profile.

        Args:
            field_name: Field to look up
            session: Current session

        Returns:
            GapFillResult from profile or not found
        """
        if not self._profile_store:
            return GapFillResult(
                field_name=field_name,
                filled=False,
                source=GapFillSource.NOT_FOUND,
            )

        # Look up the profile field
        profile = await self._profile_store.get_profile(
            tenant_id=session.tenant_id,
            customer_id=session.user_channel_id,
        )

        if profile and field_name in profile.fields:
            field = profile.fields[field_name]
            # Check if field is not expired
            if not field.is_expired():
                return GapFillResult(
                    field_name=field_name,
                    filled=True,
                    value=field.value,
                    source=GapFillSource.PROFILE,
                    confidence=field.confidence,
                    needs_confirmation=field.needs_confirmation,
                )

        return GapFillResult(
            field_name=field_name,
            filled=False,
            source=GapFillSource.NOT_FOUND,
        )

    def try_session_fill(
        self,
        field_name: str,
        session: "Session",
    ) -> GapFillResult:
        """Try to fill from session variables.

        Args:
            field_name: Field to look up
            session: Current session

        Returns:
            GapFillResult from session or not found
        """
        if field_name in session.variables:
            return GapFillResult(
                field_name=field_name,
                filled=True,
                value=session.variables[field_name],
                source=GapFillSource.SESSION,
                confidence=1.0,  # Session data is explicit
                needs_confirmation=False,
            )

        return GapFillResult(
            field_name=field_name,
            filled=False,
            source=GapFillSource.NOT_FOUND,
        )

    async def try_conversation_extraction(
        self,
        field_name: str,
        session: "Session",
        field_type: str = "string",
        field_description: str | None = None,
        max_turns: int = 20,
    ) -> GapFillResult:
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
            GapFillResult with extraction or not found
        """
        if not self._llm_provider:
            return GapFillResult(
                field_name=field_name,
                filled=False,
                source=GapFillSource.NOT_FOUND,
            )

        # Build conversation history string
        conversation_history = self._build_conversation_history(session, max_turns)

        if not conversation_history.strip():
            return GapFillResult(
                field_name=field_name,
                filled=False,
                source=GapFillSource.NOT_FOUND,
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
            response = await self._llm_provider.generate(
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
            return GapFillResult(
                field_name=field_name,
                filled=False,
                source=GapFillSource.NOT_FOUND,
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
    ) -> GapFillResult:
        """Parse LLM extraction response.

        Args:
            field_name: Field being extracted
            response: LLM response text

        Returns:
            GapFillResult parsed from response
        """
        try:
            # Try to parse as JSON
            data = json.loads(response.strip())

            found = data.get("found", False)
            if not found:
                return GapFillResult(
                    field_name=field_name,
                    filled=False,
                    source=GapFillSource.NOT_FOUND,
                )

            confidence = float(data.get("confidence", 0.0))

            # Check against threshold
            if confidence < USE_THRESHOLD:
                return GapFillResult(
                    field_name=field_name,
                    filled=False,
                    source=GapFillSource.NOT_FOUND,
                )

            return GapFillResult(
                field_name=field_name,
                filled=True,
                value=data.get("value"),
                source=GapFillSource.EXTRACTION,
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
            return GapFillResult(
                field_name=field_name,
                filled=False,
                source=GapFillSource.NOT_FOUND,
            )

    async def persist_extracted_values(
        self,
        session: "Session",
        results: list[GapFillResult],
    ) -> int:
        """Persist extracted values to profile for future use.

        Args:
            session: Current session
            results: Gap fill results to persist

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
            if result.source != GapFillSource.EXTRACTION:
                continue

            try:
                await self._profile_store.set_field(
                    tenant_id=session.tenant_id,
                    customer_id=session.user_channel_id,
                    field_name=result.field_name,
                    value=result.value,
                    source="conversation_extraction",
                    confidence=result.confidence,
                    needs_confirmation=result.needs_confirmation,
                )
                persisted += 1

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
    ) -> dict[str, GapFillResult]:
        """Fill multiple fields at once.

        Args:
            field_names: Fields to fill
            session: Current session
            field_definitions: Optional field type/description info

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
            )
            results[field_name] = result

        return results
