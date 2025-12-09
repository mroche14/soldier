"""Deterministic enforcement using expression evaluation."""

from typing import Any

from simpleeval import EvalWithCompoundTypes, InvalidExpression

from soldier.observability.logging import get_logger

logger = get_logger(__name__)


class DeterministicEnforcer:
    """Evaluate enforcement expressions deterministically.

    Uses simpleeval for safe expression evaluation without arbitrary code execution.
    Supports mathematical comparisons, logical operators, and safe functions.
    """

    # Safe functions whitelist - only these functions are allowed in expressions
    SAFE_FUNCTIONS = {
        "len": len,
        "abs": abs,
        "min": min,
        "max": max,
        "lower": lambda s: s.lower() if isinstance(s, str) else s,
        "upper": lambda s: s.upper() if isinstance(s, str) else s,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

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
        try:
            evaluator = EvalWithCompoundTypes(
                names=variables,
                functions=self.SAFE_FUNCTIONS,
            )

            result = evaluator.eval(expression)

            # Convert result to boolean
            if not isinstance(result, bool):
                # For numeric results, treat 0 as False, non-zero as True
                passed = bool(result)
            else:
                passed = result

            if passed:
                return (True, None)
            else:
                return (
                    False,
                    f"Expression '{expression}' evaluated to False with variables: {variables}",
                )

        except InvalidExpression as e:
            logger.warning(
                "enforcement_expression_syntax_error",
                expression=expression,
                error=str(e),
            )
            return (False, f"Invalid expression syntax: {e}")

        except KeyError as e:
            logger.warning(
                "enforcement_expression_undefined_variable",
                expression=expression,
                missing_variable=str(e),
            )
            return (False, f"Undefined variable in expression: {e}")

        except Exception as e:  # noqa: BLE001
            logger.error(
                "enforcement_expression_evaluation_error",
                expression=expression,
                error=str(e),
            )
            return (False, f"Expression evaluation error: {e}")

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
        try:
            # Try to parse with empty variables
            evaluator = EvalWithCompoundTypes(
                names={},
                functions=DeterministicEnforcer.SAFE_FUNCTIONS,
            )
            # Don't actually evaluate, just parse
            evaluator.eval(expression)
            return (True, None)

        except InvalidExpression as e:
            return (False, f"Invalid syntax: {e}")

        except KeyError:
            # Undefined variables are OK during validation
            return (True, None)

        except Exception as e:  # noqa: BLE001
            return (False, f"Validation error: {e}")
