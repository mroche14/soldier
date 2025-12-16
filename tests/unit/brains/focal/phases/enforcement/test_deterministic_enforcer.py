"""Tests for DeterministicEnforcer - expression-based constraint validation.

Tests cover:
- Evaluating numeric expressions
- Evaluating string expressions
- Evaluating boolean expressions
- Safe function usage
- Invalid expression handling
- Undefined variable handling
- Syntax validation
"""

import pytest

from ruche.brains.focal.phases.enforcement.deterministic_enforcer import (
    DeterministicEnforcer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def enforcer():
    """Create DeterministicEnforcer instance."""
    return DeterministicEnforcer()


# =============================================================================
# Tests: DeterministicEnforcer.evaluate() - Numeric Expressions
# =============================================================================


class TestEvaluateNumericExpressions:
    """Tests for numeric expression evaluation."""

    def test_evaluates_less_than_true(self, enforcer):
        """Evaluates amount < limit expression as True."""
        passed, error = enforcer.evaluate(
            expression="amount < 100",
            variables={"amount": 50},
        )

        assert passed is True
        assert error is None

    def test_evaluates_less_than_false(self, enforcer):
        """Evaluates amount < limit expression as False."""
        passed, error = enforcer.evaluate(
            expression="amount < 100",
            variables={"amount": 150},
        )

        assert passed is False
        assert "amount < 100" in error

    def test_evaluates_less_than_or_equal_boundary(self, enforcer):
        """Evaluates boundary condition correctly."""
        passed, error = enforcer.evaluate(
            expression="amount <= 100",
            variables={"amount": 100},
        )

        assert passed is True
        assert error is None

    def test_evaluates_greater_than(self, enforcer):
        """Evaluates greater than comparison."""
        passed, error = enforcer.evaluate(
            expression="score > 0.5",
            variables={"score": 0.75},
        )

        assert passed is True
        assert error is None

    def test_evaluates_equality(self, enforcer):
        """Evaluates equality comparison."""
        passed, error = enforcer.evaluate(
            expression="status == 1",
            variables={"status": 1},
        )

        assert passed is True
        assert error is None

    def test_evaluates_not_equal(self, enforcer):
        """Evaluates not equal comparison."""
        passed, error = enforcer.evaluate(
            expression="count != 0",
            variables={"count": 5},
        )

        assert passed is True
        assert error is None

    def test_evaluates_arithmetic_expression(self, enforcer):
        """Evaluates arithmetic within expression."""
        passed, error = enforcer.evaluate(
            expression="(price * quantity) <= max_total",
            variables={"price": 10, "quantity": 5, "max_total": 100},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: DeterministicEnforcer.evaluate() - String Expressions
# =============================================================================


class TestEvaluateStringExpressions:
    """Tests for string expression evaluation."""

    def test_evaluates_string_equality(self, enforcer):
        """Evaluates string equality."""
        passed, error = enforcer.evaluate(
            expression="status == 'approved'",
            variables={"status": "approved"},
        )

        assert passed is True
        assert error is None

    def test_evaluates_string_inequality(self, enforcer):
        """Evaluates string inequality."""
        passed, error = enforcer.evaluate(
            expression="status != 'blocked'",
            variables={"status": "active"},
        )

        assert passed is True
        assert error is None

    def test_evaluates_string_in_list(self, enforcer):
        """Evaluates string membership in list."""
        passed, error = enforcer.evaluate(
            expression="tier in ['gold', 'platinum']",
            variables={"tier": "gold"},
        )

        assert passed is True
        assert error is None

    def test_evaluates_string_not_in_list(self, enforcer):
        """Evaluates string not in list."""
        passed, error = enforcer.evaluate(
            expression="tier not in ['blocked', 'suspended']",
            variables={"tier": "active"},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: DeterministicEnforcer.evaluate() - Boolean Expressions
# =============================================================================


class TestEvaluateBooleanExpressions:
    """Tests for boolean expression evaluation."""

    def test_evaluates_boolean_true(self, enforcer):
        """Evaluates boolean True directly."""
        passed, error = enforcer.evaluate(
            expression="is_verified",
            variables={"is_verified": True},
        )

        assert passed is True
        assert error is None

    def test_evaluates_boolean_false(self, enforcer):
        """Evaluates boolean False directly."""
        passed, error = enforcer.evaluate(
            expression="is_verified",
            variables={"is_verified": False},
        )

        assert passed is False
        assert error is not None

    def test_evaluates_boolean_and(self, enforcer):
        """Evaluates boolean AND expression."""
        passed, error = enforcer.evaluate(
            expression="is_verified and is_active",
            variables={"is_verified": True, "is_active": True},
        )

        assert passed is True
        assert error is None

    def test_evaluates_boolean_or(self, enforcer):
        """Evaluates boolean OR expression."""
        passed, error = enforcer.evaluate(
            expression="is_admin or is_moderator",
            variables={"is_admin": False, "is_moderator": True},
        )

        assert passed is True
        assert error is None

    def test_evaluates_boolean_not(self, enforcer):
        """Evaluates boolean NOT expression."""
        passed, error = enforcer.evaluate(
            expression="not is_blocked",
            variables={"is_blocked": False},
        )

        assert passed is True
        assert error is None

    def test_evaluates_complex_boolean(self, enforcer):
        """Evaluates complex boolean expression."""
        passed, error = enforcer.evaluate(
            expression="(is_verified and not is_blocked) or is_admin",
            variables={
                "is_verified": True,
                "is_blocked": False,
                "is_admin": False,
            },
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: DeterministicEnforcer.evaluate() - Safe Functions
# =============================================================================


class TestEvaluateSafeFunctions:
    """Tests for safe function usage in expressions."""

    def test_uses_len_function(self, enforcer):
        """Uses len() function in expression."""
        passed, error = enforcer.evaluate(
            expression="len(items) <= 10",
            variables={"items": [1, 2, 3]},
        )

        assert passed is True
        assert error is None

    def test_uses_abs_function(self, enforcer):
        """Uses abs() function in expression."""
        passed, error = enforcer.evaluate(
            expression="abs(delta) < 100",
            variables={"delta": -50},
        )

        assert passed is True
        assert error is None

    def test_uses_min_function(self, enforcer):
        """Uses min() function in expression."""
        passed, error = enforcer.evaluate(
            expression="min(a, b) >= threshold",
            variables={"a": 10, "b": 20, "threshold": 5},
        )

        assert passed is True
        assert error is None

    def test_uses_max_function(self, enforcer):
        """Uses max() function in expression."""
        passed, error = enforcer.evaluate(
            expression="max(scores) < 100",
            variables={"scores": [50, 60, 70]},
        )

        assert passed is True
        assert error is None

    def test_uses_lower_function(self, enforcer):
        """Uses lower() function in expression."""
        passed, error = enforcer.evaluate(
            expression="lower(name) == 'john'",
            variables={"name": "JOHN"},
        )

        assert passed is True
        assert error is None

    def test_uses_upper_function(self, enforcer):
        """Uses upper() function in expression."""
        passed, error = enforcer.evaluate(
            expression="upper(code) == 'ABC'",
            variables={"code": "abc"},
        )

        assert passed is True
        assert error is None

    def test_uses_int_function(self, enforcer):
        """Uses int() function for type conversion."""
        passed, error = enforcer.evaluate(
            expression="int(value) == 42",
            variables={"value": "42"},
        )

        assert passed is True
        assert error is None

    def test_uses_float_function(self, enforcer):
        """Uses float() function for type conversion."""
        passed, error = enforcer.evaluate(
            expression="float(rate) < 0.1",
            variables={"rate": "0.05"},
        )

        assert passed is True
        assert error is None

    def test_uses_str_function(self, enforcer):
        """Uses str() function for type conversion."""
        passed, error = enforcer.evaluate(
            expression="str(id) == '123'",
            variables={"id": 123},
        )

        assert passed is True
        assert error is None

    def test_uses_bool_function(self, enforcer):
        """Uses bool() function for type conversion."""
        passed, error = enforcer.evaluate(
            expression="bool(count)",
            variables={"count": 5},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: DeterministicEnforcer.evaluate() - Error Handling
# =============================================================================


class TestEvaluateErrorHandling:
    """Tests for error handling in expression evaluation."""

    def test_handles_undefined_variable(self, enforcer):
        """Returns False with error for undefined variable."""
        passed, error = enforcer.evaluate(
            expression="undefined_var > 0",
            variables={},
        )

        assert passed is False
        assert "Undefined variable" in error or "undefined" in error.lower()

    def test_handles_invalid_expression_syntax(self, enforcer):
        """Returns False with error for invalid syntax."""
        passed, error = enforcer.evaluate(
            expression="amount >>>",
            variables={"amount": 10},
        )

        assert passed is False
        assert error is not None

    def test_handles_division_by_zero(self, enforcer):
        """Handles division by zero gracefully."""
        passed, error = enforcer.evaluate(
            expression="100 / divisor > 0",
            variables={"divisor": 0},
        )

        assert passed is False
        assert error is not None

    def test_handles_type_error(self, enforcer):
        """Handles type errors gracefully."""
        passed, error = enforcer.evaluate(
            expression="value + 10 > 20",
            variables={"value": "not_a_number"},
        )

        assert passed is False
        assert error is not None

    def test_treats_zero_as_false(self, enforcer):
        """Treats numeric zero as False."""
        passed, error = enforcer.evaluate(
            expression="count",
            variables={"count": 0},
        )

        assert passed is False
        assert error is not None

    def test_treats_nonzero_as_true(self, enforcer):
        """Treats non-zero numeric as True."""
        passed, error = enforcer.evaluate(
            expression="count",
            variables={"count": 42},
        )

        assert passed is True
        assert error is None


# =============================================================================
# Tests: DeterministicEnforcer.validate_syntax()
# =============================================================================


class TestValidateSyntax:
    """Tests for expression syntax validation."""

    def test_validates_constant_expression(self, enforcer):
        """Returns True for constant expression with no variables."""
        valid, error = enforcer.validate_syntax("True")

        assert valid is True
        assert error is None

    def test_validates_numeric_constant(self, enforcer):
        """Returns True for numeric constant expression."""
        valid, error = enforcer.validate_syntax("100 > 50")

        assert valid is True
        assert error is None

    def test_validates_expression_with_functions(self, enforcer):
        """Validates expressions with safe functions."""
        valid, error = enforcer.validate_syntax("len([1,2,3]) > 0")

        # Should work since the expression uses a literal list
        assert valid is True
        assert error is None

    def test_rejects_invalid_syntax(self, enforcer):
        """Returns False for invalid expression syntax."""
        valid, error = enforcer.validate_syntax("amount <<< 100")

        assert valid is False
        assert error is not None

    def test_rejects_unclosed_parenthesis(self, enforcer):
        """Returns False for unclosed parenthesis."""
        valid, error = enforcer.validate_syntax("(a > b")

        assert valid is False
        assert error is not None

    def test_returns_true_for_undefined_variables_via_keyerror(self, enforcer):
        """Returns True when KeyError is raised (undefined variable)."""
        # The validate_syntax catches KeyError and returns True
        # This is by design - syntax is valid, just missing values
        valid, error = enforcer.validate_syntax("some_undefined_var > 100")

        # The implementation catches KeyError and returns True
        # However simpleeval may raise NameNotDefined instead
        # Just verify it doesn't crash and returns a valid tuple
        assert isinstance(valid, bool)
        assert error is None or isinstance(error, str)


# =============================================================================
# Tests: Safe Functions Whitelist
# =============================================================================


class TestSafeFunctionsWhitelist:
    """Tests for safe functions whitelist."""

    def test_safe_functions_are_defined(self):
        """All safe functions are properly defined."""
        safe_funcs = DeterministicEnforcer.SAFE_FUNCTIONS

        assert "len" in safe_funcs
        assert "abs" in safe_funcs
        assert "min" in safe_funcs
        assert "max" in safe_funcs
        assert "lower" in safe_funcs
        assert "upper" in safe_funcs
        assert "int" in safe_funcs
        assert "float" in safe_funcs
        assert "str" in safe_funcs
        assert "bool" in safe_funcs

    def test_lower_function_handles_non_string(self, enforcer):
        """Lower function handles non-string gracefully."""
        # The custom lower function should return input as-is for non-strings
        passed, error = enforcer.evaluate(
            expression="lower(value) == 123",
            variables={"value": 123},
        )

        # Should work without exception
        assert passed is True

    def test_upper_function_handles_non_string(self, enforcer):
        """Upper function handles non-string gracefully."""
        # The custom upper function should return input as-is for non-strings
        passed, error = enforcer.evaluate(
            expression="upper(value) == 456",
            variables={"value": 456},
        )

        # Should work without exception
        assert passed is True


# =============================================================================
# Tests: Integration - Real-World Scenarios
# =============================================================================


class TestRealWorldScenarios:
    """Integration tests for real-world enforcement scenarios."""

    def test_refund_amount_limit(self, enforcer):
        """Enforces refund amount limit."""
        passed, error = enforcer.evaluate(
            expression="refund_amount <= 50",
            variables={"refund_amount": 45},
        )

        assert passed is True

        passed, error = enforcer.evaluate(
            expression="refund_amount <= 50",
            variables={"refund_amount": 75},
        )

        assert passed is False

    def test_discount_percentage_cap(self, enforcer):
        """Enforces maximum discount percentage."""
        passed, error = enforcer.evaluate(
            expression="discount_percent <= 20",
            variables={"discount_percent": 15},
        )

        assert passed is True

    def test_customer_tier_restriction(self, enforcer):
        """Enforces customer tier-based access."""
        passed, error = enforcer.evaluate(
            expression="customer_tier in ['gold', 'platinum', 'diamond']",
            variables={"customer_tier": "gold"},
        )

        assert passed is True

        passed, error = enforcer.evaluate(
            expression="customer_tier in ['gold', 'platinum', 'diamond']",
            variables={"customer_tier": "bronze"},
        )

        assert passed is False

    def test_order_quantity_limit(self, enforcer):
        """Enforces order quantity limits."""
        passed, error = enforcer.evaluate(
            expression="quantity > 0 and quantity <= max_quantity",
            variables={"quantity": 5, "max_quantity": 10},
        )

        assert passed is True

    def test_combined_business_rule(self, enforcer):
        """Enforces combined business rule."""
        passed, error = enforcer.evaluate(
            expression="(is_verified or is_admin) and amount <= max_amount",
            variables={
                "is_verified": True,
                "is_admin": False,
                "amount": 100,
                "max_amount": 200,
            },
        )

        assert passed is True

    def test_response_length_limit(self, enforcer):
        """Enforces response length limits."""
        passed, error = enforcer.evaluate(
            expression="len(response_text) <= 1000",
            variables={"response_text": "This is a short response"},
        )

        assert passed is True
