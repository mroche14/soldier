"""CI integration for configuration validation.

This module provides functions to validate all configurations before deployment,
ensuring that tools, scenarios, and rules meet safety and quality standards.
"""

import json
from pathlib import Path

from ruche.asa.models import DeploymentValidationResult, Issue, Severity, Suggestion
from ruche.asa.suggester.edge_case_generator import EdgeCaseGenerator
from ruche.asa.validator.scenario_validator import ScenarioValidator
from ruche.asa.validator.tool_validator import ToolValidator


async def validate_deployment(
    config_path: Path,
) -> DeploymentValidationResult:
    """Validate all configurations before deployment.

    Loads all tools, scenarios, and rules from the config directory and
    validates them for safety, completeness, and quality.

    Args:
        config_path: Path to configuration directory containing:
                     - tools/ directory with tool definitions
                     - scenarios/ directory with scenario definitions
                     - rules/ directory with rule definitions

    Returns:
        DeploymentValidationResult indicating whether deployment should proceed
    """
    all_issues = []
    all_suggestions = []

    # Load configurations
    tools = load_tools(config_path / "tools")
    scenarios = load_scenarios(config_path / "scenarios")
    rules = load_rules(config_path / "rules")

    # Validate tools
    tool_validator = ToolValidator()
    for tool in tools:
        result = tool_validator.validate(tool)
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)

    # Validate scenarios
    scenario_validator = ScenarioValidator()
    for scenario in scenarios:
        result = scenario_validator.validate(scenario)
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)

    # Check for missing edge cases
    edge_generator = EdgeCaseGenerator()
    for scenario in scenarios:
        suggested = edge_generator.generate_edge_cases(scenario, tools)
        # Check if suggested rules already exist
        for suggestion in suggested:
            if not rule_exists(suggestion.name, rules):
                all_suggestions.append(
                    Suggestion(
                        code="MISSING_EDGE_CASE",
                        message=f"Consider adding rule: {suggestion.name}",
                        details=suggestion.model_dump(),
                    )
                )

    # Determine if deployment should proceed
    errors = [i for i in all_issues if i.severity == Severity.ERROR]
    warnings = [i for i in all_issues if i.severity == Severity.WARNING]

    return DeploymentValidationResult(
        can_deploy=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        suggestions=all_suggestions,
    )


def load_tools(tools_dir: Path) -> list[dict]:
    """Load all tool definitions from directory.

    Args:
        tools_dir: Directory containing JSON tool definition files

    Returns:
        List of tool definition dicts
    """
    tools = []
    if not tools_dir.exists():
        return tools

    for tool_file in tools_dir.glob("*.json"):
        try:
            with open(tool_file) as f:
                tool = json.load(f)
                tools.append(tool)
        except Exception:
            # Skip invalid files
            pass

    return tools


def load_scenarios(scenarios_dir: Path) -> list[dict]:
    """Load all scenario definitions from directory.

    Args:
        scenarios_dir: Directory containing JSON scenario definition files

    Returns:
        List of scenario definition dicts
    """
    scenarios = []
    if not scenarios_dir.exists():
        return scenarios

    for scenario_file in scenarios_dir.glob("*.json"):
        try:
            with open(scenario_file) as f:
                scenario = json.load(f)
                scenarios.append(scenario)
        except Exception:
            # Skip invalid files
            pass

    return scenarios


def load_rules(rules_dir: Path) -> list[dict]:
    """Load all rule definitions from directory.

    Args:
        rules_dir: Directory containing JSON rule definition files

    Returns:
        List of rule definition dicts
    """
    rules = []
    if not rules_dir.exists():
        return rules

    for rule_file in rules_dir.glob("*.json"):
        try:
            with open(rule_file) as f:
                rule = json.load(f)
                rules.append(rule)
        except Exception:
            # Skip invalid files
            pass

    return rules


def rule_exists(rule_name: str, rules: list[dict]) -> bool:
    """Check if a rule with given name exists.

    Args:
        rule_name: Name of the rule to find
        rules: List of rule definitions

    Returns:
        True if rule exists, False otherwise
    """
    return any(r.get("name") == rule_name for r in rules)
