"""LLM output parsing for structured generation.

Parses LLM responses that include both response text and semantic categories.
"""

import json

from pydantic import BaseModel, ValidationError

from focal.alignment.models.outcome import OutcomeCategory
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class LLMOutput(BaseModel):
    """Structured output from generation LLM."""

    response: str
    categories: list[str] = []


def parse_llm_output(raw_output: str) -> tuple[str, list[OutcomeCategory]]:
    """Parse LLM output into response and categories.

    Args:
        raw_output: Raw string from LLM

    Returns:
        (response_text, categories)

    Handles both JSON and plain text fallback.
    """
    # Try to parse as JSON first
    try:
        data = json.loads(raw_output)
        output = LLMOutput(**data)

        # Convert category strings to enum
        categories = []
        for cat_str in output.categories:
            try:
                categories.append(OutcomeCategory(cat_str))
            except ValueError:
                logger.warning("unknown_category", category=cat_str)

        return output.response, categories

    except (json.JSONDecodeError, ValidationError) as e:
        # Fallback: treat entire output as response
        logger.debug("llm_output_not_json", error=str(e))
        return raw_output, [OutcomeCategory.ANSWERED]
