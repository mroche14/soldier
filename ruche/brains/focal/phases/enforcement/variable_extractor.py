"""Extract variables from response text for enforcement expressions."""

import re
from typing import Any

from ruche.conversation.models import Session
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class VariableExtractor:
    """Extract variables from response text using regex patterns.

    Variables are extracted for use in deterministic enforcement expressions.
    Merges extracted variables with session and profile context.
    """

    # Regex patterns for common variable types
    AMOUNT_PATTERN = re.compile(
        r"\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)|"
        r"(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|dollars?|€|EUR|£|GBP)",
        re.IGNORECASE,
    )
    PERCENTAGE_PATTERN = re.compile(
        r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage)",
        re.IGNORECASE,
    )

    def extract_variables(
        self,
        response: str,
        session: Session | None = None,
        profile_variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract all variables from response, session, and profile.

        Args:
            response: Generated response text to extract from
            session: Current session for session variables
            profile_variables: Pre-extracted profile fields as dict

        Returns:
            Merged dictionary of all variables (response > session > profile priority)
        """
        variables: dict[str, Any] = {}

        # 1. Add profile variables (lowest priority)
        if profile_variables:
            variables.update(profile_variables)

        # 2. Extract from session (medium priority)
        if session:
            variables.update(self._extract_from_session(session))

        # 3. Extract from response text (highest priority)
        variables.update(self._extract_amounts(response))
        variables.update(self._extract_percentages(response))
        variables.update(self._extract_boolean_flags(response))

        logger.debug(
            "variables_extracted",
            variable_count=len(variables),
            variable_keys=list(variables.keys()),
        )

        return variables

    def _extract_amounts(self, text: str) -> dict[str, float]:
        """Extract monetary amounts from text.

        Returns:
            Dictionary with 'amount' key (highest amount found)
        """
        matches = self.AMOUNT_PATTERN.findall(text)
        if not matches:
            return {}

        # Each match is a tuple of groups, find the non-empty one
        amounts = []
        for match in matches:
            amount_str = match[0] or match[1]
            # Remove commas and convert to float
            amount_str = amount_str.replace(",", "")
            try:
                amounts.append(float(amount_str))
            except ValueError:
                continue

        if not amounts:
            return {}

        # Return the highest amount found
        return {"amount": max(amounts)}

    def _extract_percentages(self, text: str) -> dict[str, float]:
        """Extract percentages from text.

        Returns:
            Dictionary with 'discount_percent' key (highest percentage found)
        """
        matches = self.PERCENTAGE_PATTERN.findall(text)
        if not matches:
            return {}

        percentages = []
        for match in matches:
            try:
                percentages.append(float(match))
            except ValueError:
                continue

        if not percentages:
            return {}

        # Return the highest percentage found
        return {"discount_percent": max(percentages)}

    def _extract_boolean_flags(self, text: str) -> dict[str, bool]:
        """Extract boolean flags based on keyword presence.

        Returns:
            Dictionary with boolean flags for common constraint types
        """
        lower_text = text.lower()

        return {
            "contains_refund": "refund" in lower_text,
            "contains_promise": any(
                word in lower_text for word in ["promise", "guarantee", "will definitely"]
            ),
            "contains_competitor": any(
                word in lower_text for word in ["competitor", "alternative", "instead try"]
            ),
            "contains_apology": any(
                word in lower_text for word in ["sorry", "apologize", "apologies"]
            ),
        }

    def _extract_from_session(self, session: Session) -> dict[str, Any]:
        """Extract variables from session context.

        Args:
            session: Current session

        Returns:
            Dictionary of session variables
        """
        variables: dict[str, Any] = {}

        # Add session-level custom variables if they exist
        if hasattr(session, "variables") and session.variables:
            variables.update(session.variables)

        return variables
