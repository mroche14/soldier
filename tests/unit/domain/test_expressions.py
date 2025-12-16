"""Tests for domain-level expression evaluator.

Tests cover:
- Basic expression evaluation (numeric, string, boolean)
- Safe function usage
- Error handling (syntax errors, undefined variables)
- Syntax validation
- Integration with the convenience function evaluate_expression()
"""

import pytest

from ruche.domain.rules.expressions import ExpressionEvaluator, evaluate_expression


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def evaluator():
    """Create ExpressionEvaluator instance."""
    return ExpressionEvaluator()


# =============================================================================
# Tests: Basic Expression Evaluation
# =============================================================================


class TestBasicExpressionEvaluation:
    """Tests for basic expression evaluation."""

    def test_evaluates_simple_numeric_comparison(self, evaluator):
        """Evaluates simple numeric comparison."""
        passed, error = evaluator.evaluate(
            expression="amount <= 50",
            variables={"amount": 30},
        )

        assert passed is True
        assert error is None

    def test_evaluates_failed_numeric_comparison(self, evaluator):
        """Evaluates failed numeric comparison."""
        passed, error = evaluator.evaluate(
            expression="amount <= 50",
            variables={"amount": 75},
        )

        assert passed is False
        assert "amount <= 50" in error
        assert "False" in error

    def test_evaluates_string_equality(self, evaluator):
        """Evaluates string equality."""
        passed, error = evaluator.evaluate(
            expression="status == 'active'",
            variables={"status": "active"},
        )

        assert passed is True
        assert error is None

    def test_evaluates_boolean_expression(self, evaluator):
        """Evaluates boolean expression."""
        passed, error = evaluator.evaluate(
            expression="is_verified and not is_blocked",
            variables={"is_verified": True, "is_blocked": False},
        )

        assert passed is True
        assert error is None

    def test_evaluates_list_membership(self, evaluator):
        """Evaluates list membership."""
        passed, error = evaluator.evaluate(
            expression="tier in ['gold', 'platinum']",
            variables={"tier": "gold"},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: Safe Functions
# =============================================================================


class TestSafeFunctions:
    """Tests for safe function usage."""

    def test_uses_len_function(self, evaluator):
        """Uses len() function."""
        passed, error = evaluator.evaluate(
            expression="len(items) > 0",
            variables={"items": [1, 2, 3]},
        )

        assert passed is True
        assert error is None

    def test_uses_abs_function(self, evaluator):
        """Uses abs() function."""
        passed, error = evaluator.evaluate(
            expression="abs(delta) < 100",
            variables={"delta": -50},
        )

        assert passed is True
        assert error is None

    def test_uses_lower_function(self, evaluator):
        """Uses lower() function."""
        passed, error = evaluator.evaluate(
            expression="lower(name) == 'john'",
            variables={"name": "JOHN"},
        )

        assert passed is True
        assert error is None

    def test_uses_upper_function(self, evaluator):
        """Uses upper() function."""
        passed, error = evaluator.evaluate(
            expression="upper(code) == 'ABC'",
            variables={"code": "abc"},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_undefined_variable(self, evaluator):
        """Handles undefined variable error."""
        passed, error = evaluator.evaluate(
            expression="undefined_var > 0",
            variables={},
        )

        assert passed is False
        assert error is not None
        assert "undefined_var" in error.lower()

    def test_handles_invalid_syntax(self, evaluator):
        """Handles invalid syntax error."""
        passed, error = evaluator.evaluate(
            expression="amount >>>",
            variables={"amount": 10},
        )

        assert passed is False
        assert error is not None

    def test_handles_division_by_zero(self, evaluator):
        """Handles division by zero error."""
        passed, error = evaluator.evaluate(
            expression="100 / divisor > 0",
            variables={"divisor": 0},
        )

        assert passed is False
        assert error is not None

    def test_treats_zero_as_false(self, evaluator):
        """Treats numeric zero as False."""
        passed, error = evaluator.evaluate(
            expression="count",
            variables={"count": 0},
        )

        assert passed is False
        assert error is not None

    def test_treats_nonzero_as_true(self, evaluator):
        """Treats non-zero numeric as True."""
        passed, error = evaluator.evaluate(
            expression="count",
            variables={"count": 42},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: Syntax Validation
# =============================================================================


class TestSyntaxValidation:
    """Tests for syntax validation."""

    def test_validates_constant_expression(self):
        """Validates constant expression syntax (no variables)."""
        valid, error = ExpressionEvaluator.validate_syntax("100 > 50")

        assert valid is True
        assert error is None

    def test_validates_expression_with_literals(self):
        """Validates expression with literal values."""
        valid, error = ExpressionEvaluator.validate_syntax("True and False")

        assert valid is True
        assert error is None

    def test_rejects_invalid_syntax(self):
        """Rejects invalid syntax."""
        valid, error = ExpressionEvaluator.validate_syntax("amount <<< 100")

        assert valid is False
        assert error is not None

    def test_rejects_unclosed_parenthesis(self):
        """Rejects unclosed parenthesis."""
        valid, error = ExpressionEvaluator.validate_syntax("(a > b")

        assert valid is False
        assert error is not None


# =============================================================================
# Tests: Convenience Function
# =============================================================================


class TestConvenienceFunction:
    """Tests for the convenience function evaluate_expression()."""

    def test_returns_true_for_passing_expression(self):
        """Returns True for passing expression."""
        result = evaluate_expression(
            expression="amount <= 50",
            context={"amount": 30},
        )

        assert result is True

    def test_returns_false_for_failing_expression(self):
        """Returns False for failing expression."""
        result = evaluate_expression(
            expression="amount <= 50",
            context={"amount": 75},
        )

        assert result is False

    def test_returns_false_for_error_cases(self):
        """Returns False for error cases (undefined variable)."""
        result = evaluate_expression(
            expression="undefined_var > 0",
            context={},
        )

        assert result is False


# =============================================================================
# Tests: Real-World Scenarios
# =============================================================================


class TestRealWorldScenarios:
    """Integration tests for real-world scenarios."""

    def test_refund_amount_constraint(self, evaluator):
        """Enforces refund amount constraint."""
        # Within limit
        passed, _ = evaluator.evaluate(
            expression="refund_amount <= 50",
            variables={"refund_amount": 45},
        )
        assert passed is True

        # Exceeds limit
        passed, _ = evaluator.evaluate(
            expression="refund_amount <= 50",
            variables={"refund_amount": 75},
        )
        assert passed is False

    def test_customer_tier_restriction(self, evaluator):
        """Enforces customer tier restriction."""
        # Allowed tier
        passed, _ = evaluator.evaluate(
            expression="customer_tier in ['gold', 'platinum', 'diamond']",
            variables={"customer_tier": "gold"},
        )
        assert passed is True

        # Restricted tier
        passed, _ = evaluator.evaluate(
            expression="customer_tier in ['gold', 'platinum', 'diamond']",
            variables={"customer_tier": "bronze"},
        )
        assert passed is False

    def test_combined_business_rule(self, evaluator):
        """Enforces combined business rule."""
        passed, _ = evaluator.evaluate(
            expression="(is_verified or is_admin) and amount <= max_amount",
            variables={
                "is_verified": True,
                "is_admin": False,
                "amount": 100,
                "max_amount": 200,
            },
        )
        assert passed is True

    def test_response_length_limit(self, evaluator):
        """Enforces response length limit."""
        passed, _ = evaluator.evaluate(
            expression="len(response_text) <= 1000",
            variables={"response_text": "This is a short response"},
        )
        assert passed is True
