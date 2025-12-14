"""Unit tests for VariableRequirementAnalyzer."""

import pytest

from ruche.alignment.execution.variable_requirement_analyzer import VariableRequirementAnalyzer
from ruche.alignment.filtering.models import MatchedRule
from ruche.alignment.models.tool_binding import ToolBinding
from tests.factories.alignment import RuleFactory


@pytest.fixture
def analyzer() -> VariableRequirementAnalyzer:
    return VariableRequirementAnalyzer()


def test_extract_from_tool_bindings(analyzer: VariableRequirementAnalyzer) -> None:
    """Test extracting required variables from tool bindings."""
    bindings = [
        ToolBinding(tool_id="tool_1", required_variables=["var_a", "var_b"]),
        ToolBinding(tool_id="tool_2", required_variables=["var_c"]),
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=bindings,
        applied_rules=[],
        current_step=None,
    )

    assert required == {"var_a", "var_b", "var_c"}


def test_extract_from_rule_action_text_placeholders(analyzer: VariableRequirementAnalyzer) -> None:
    """Test extracting variables from rule action_text placeholders."""
    rule1 = RuleFactory.create(action_text="Hello {name}, your age is {age}")
    rule2 = RuleFactory.create(action_text="Welcome {name}!")

    matched_rules = [
        MatchedRule(rule=rule1, match_score=1.0, relevance_score=1.0, reasoning="test"),
        MatchedRule(rule=rule2, match_score=1.0, relevance_score=1.0, reasoning="test"),
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=[],
        applied_rules=matched_rules,
        current_step=None,
    )

    assert required == {"name", "age"}


def test_extract_from_step_templates(analyzer: VariableRequirementAnalyzer) -> None:
    """Test extracting variables from step description templates."""
    from ruche.alignment.models.scenario import ScenarioStep
    from uuid import uuid4

    step = ScenarioStep(
        id=uuid4(),
        scenario_id=uuid4(),
        name="Test Step",
        description="Your order {order_id} will arrive on {delivery_date}",
    )

    required = analyzer.compute_required_variables(
        tool_bindings=[],
        applied_rules=[],
        current_step=step,
    )

    assert required == {"order_id", "delivery_date"}


def test_empty_requirements(analyzer: VariableRequirementAnalyzer) -> None:
    """Test when there are no required variables."""
    rule = RuleFactory.create(action_text="No variables here")

    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=[],
        applied_rules=matched_rules,
        current_step=None,
    )

    assert len(required) == 0


def test_duplicate_variable_names_deduplication(analyzer: VariableRequirementAnalyzer) -> None:
    """Test that duplicate variable names are deduplicated."""
    bindings = [
        ToolBinding(tool_id="tool_1", required_variables=["name", "email"]),
        ToolBinding(tool_id="tool_2", required_variables=["name", "phone"]),
    ]

    rule = RuleFactory.create(action_text="Hello {name}, your email is {email}")

    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=bindings,
        applied_rules=matched_rules,
        current_step=None,
    )

    # Should have unique values despite duplicates
    assert required == {"name", "email", "phone"}


def test_combined_sources(analyzer: VariableRequirementAnalyzer) -> None:
    """Test combining variables from all sources."""
    from ruche.alignment.models.scenario import ScenarioStep
    from uuid import uuid4

    bindings = [
        ToolBinding(tool_id="tool_1", required_variables=["api_key"]),
    ]

    rule = RuleFactory.create(action_text="User {user_id} requested {action}")

    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    step = ScenarioStep(
        id=uuid4(),
        scenario_id=uuid4(),
        name="Test Step",
        description="Session {session_id} active",
    )

    required = analyzer.compute_required_variables(
        tool_bindings=bindings,
        applied_rules=matched_rules,
        current_step=step,
    )

    assert required == {"api_key", "user_id", "action", "session_id"}


def test_no_placeholders_in_action_text(analyzer: VariableRequirementAnalyzer) -> None:
    """Test handling rules with action_text but no placeholders."""
    rule = RuleFactory.create(action_text="Plain text without any variables")

    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=[],
        applied_rules=matched_rules,
        current_step=None,
    )

    assert len(required) == 0


def test_complex_placeholder_patterns(analyzer: VariableRequirementAnalyzer) -> None:
    """Test extraction of various placeholder patterns."""
    rule = RuleFactory.create(
        action_text="Hello {user_name}, your {account_type} account has {balance} credits"
    )

    matched_rules = [
        MatchedRule(rule=rule, match_score=1.0, relevance_score=1.0, reasoning="test")
    ]

    required = analyzer.compute_required_variables(
        tool_bindings=[],
        applied_rules=matched_rules,
        current_step=None,
    )

    assert required == {"user_name", "account_type", "balance"}
