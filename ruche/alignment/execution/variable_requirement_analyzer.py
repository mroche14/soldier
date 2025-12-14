"""Variable requirement analysis for tool execution."""

import re
from typing import Any

from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.models.tool_binding import ToolBinding
from ruche.observability.logging import get_logger

logger = get_logger(__name__)

# Regex to extract {variable} placeholders from text
VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


class VariableRequirementAnalyzer:
    """Analyzes which variables are required for the current turn."""

    def compute_required_variables(
        self,
        tool_bindings: list[ToolBinding],
        applied_rules: list[MatchedRule],
        current_step: Any | None = None,
    ) -> set[str]:
        """Compute set of variable names needed for this turn.

        Sources:
        1. Tool bindings → required_variables
        2. Rule action_text → extract {variable} placeholders
        3. Step template → extract {variable} placeholders (if provided)

        Args:
            tool_bindings: Tool bindings from collector
            applied_rules: Rules from Phase 5
            current_step: Current scenario step (optional)

        Returns:
            Set of variable names (strings)
        """
        required: set[str] = set()

        # From tool bindings
        for binding in tool_bindings:
            required.update(binding.required_variables)

        # From rule action_text placeholders
        for matched in applied_rules:
            if matched.rule.action_text:
                variables = VARIABLE_PATTERN.findall(matched.rule.action_text)
                required.update(variables)

        # From step template (if provided and has text)
        if current_step:
            # Try to extract from template_id or description
            if hasattr(current_step, "description") and current_step.description:
                variables = VARIABLE_PATTERN.findall(current_step.description)
                required.update(variables)

        logger.info(
            "computed_required_variables",
            total_required=len(required),
            from_tool_bindings=sum(len(b.required_variables) for b in tool_bindings),
            from_rules=sum(
                len(VARIABLE_PATTERN.findall(m.rule.action_text))
                for m in applied_rules
                if m.rule.action_text
            ),
        )

        return required
