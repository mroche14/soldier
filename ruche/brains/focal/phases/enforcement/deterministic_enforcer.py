"""Deterministic enforcement using expression evaluation.

This module delegates to the domain-level ExpressionEvaluator to avoid
code duplication. The DeterministicEnforcer is kept as a thin wrapper
for backward compatibility with existing enforcement code.
"""

from typing import Any

from ruche.domain.rules.expressions import ExpressionEvaluator


class DeterministicEnforcer:
    """Evaluate enforcement expressions deterministically.

    This is a thin wrapper around the domain-level ExpressionEvaluator
    maintained for backward compatibility with FOCAL brain enforcement code.
    """

    def __init__(self) -> None:
        """Initialize the deterministic enforcer."""
        self._evaluator = ExpressionEvaluator()

    # Expose SAFE_FUNCTIONS for backward compatibility
    SAFE_FUNCTIONS = ExpressionEvaluator.SAFE_FUNCTIONS

    def evaluate(
        self,
        expression: str,
        variables: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Evaluate an enforcement expression with given variables.

        Args:
            expression: Expression to evaluate (e.g., "amount <= 50")
            variables: Variable context for evaluation

        Returns:
            Tuple of (passed, error_message)
            - (True, None) if expression evaluates to True
            - (False, error_msg) if expression evaluates to False or error occurs
        """
        return self._evaluator.evaluate(expression, variables)

    @staticmethod
    def validate_syntax(expression: str) -> tuple[bool, str | None]:
        """Validate expression syntax without evaluating.

        Args:
            expression: Expression to validate

        Returns:
            Tuple of (valid, error_message)
            - (True, None) if syntax is valid
            - (False, error_msg) if syntax is invalid
        """
        return ExpressionEvaluator.validate_syntax(expression)
