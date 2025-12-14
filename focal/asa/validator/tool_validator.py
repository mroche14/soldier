"""Tool definition validator.

This module validates tool definitions for safety, completeness, and proper
side-effect policy declarations. This is primarily used by alignment-based
mechanics that use the Side-Effect Policy system.
"""

from focal.asa.models import (
    Issue,
    Severity,
    SideEffectPolicy,
    Suggestion,
    ValidationResult,
)


class ToolValidator:
    """Validate tool definitions for safety and completeness.

    The ToolValidator ensures that tools have proper side-effect declarations
    and that the declared policy is consistent with the tool's semantics.
    """

    # Tools that should probably be IRREVERSIBLE
    IRREVERSIBLE_INDICATORS = [
        "send",
        "email",
        "sms",
        "notify",
        "refund",
        "payment",
        "charge",
        "delete",
        "remove permanently",
        "submit",
        "finalize",
        "transfer",
        "withdraw",
    ]

    # Tools that should probably be PURE
    PURE_INDICATORS = [
        "get",
        "fetch",
        "read",
        "list",
        "search",
        "validate",
        "check",
        "find",
        "lookup",
        "query",
        "view",
    ]

    def validate(self, tool: dict) -> ValidationResult:
        """Validate a single tool definition.

        Args:
            tool: Tool definition dict with fields like name, description,
                  side_effect_policy, compensation_tool, confirmation_required

        Returns:
            ValidationResult with issues and suggestions
        """
        issues = []
        suggestions = []

        tool_name = tool.get("name", "unknown")

        # REQUIRED: Side-effect policy
        if not tool.get("side_effect_policy"):
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="MISSING_SIDE_EFFECT_POLICY",
                    message=f"Tool '{tool_name}' must declare side_effect_policy",
                    fix="Add side_effect_policy field (PURE, IDEMPOTENT, COMPENSATABLE, or IRREVERSIBLE)",
                    location=tool_name,
                )
            )
        else:
            # Check policy consistency with tool semantics
            policy_issues = self._check_policy_consistency(tool)
            issues.extend(policy_issues)

        # COMPENSATABLE must have compensation tool
        if tool.get("side_effect_policy") == SideEffectPolicy.COMPENSATABLE.value:
            if not tool.get("compensation_tool"):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="MISSING_COMPENSATION",
                        message=f"COMPENSATABLE tool '{tool_name}' must specify compensation_tool",
                        fix="Add compensation_tool field with the name of the compensating tool",
                        location=tool_name,
                    )
                )

        # IRREVERSIBLE should have confirmation
        if tool.get("side_effect_policy") == SideEffectPolicy.IRREVERSIBLE.value:
            if not tool.get("confirmation_required"):
                suggestions.append(
                    Suggestion(
                        code="RECOMMEND_CONFIRMATION",
                        message=f"IRREVERSIBLE tool '{tool_name}' should require confirmation",
                        recommended_change={"confirmation_required": True},
                    )
                )

        # Check for missing description
        if not tool.get("description"):
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="MISSING_DESCRIPTION",
                    message=f"Tool '{tool_name}' should have a description",
                    fix="Add description field to document what the tool does",
                    location=tool_name,
                )
            )

        return ValidationResult(
            valid=len([i for i in issues if i.severity == Severity.ERROR]) == 0,
            issues=issues,
            suggestions=suggestions,
        )

    def _check_policy_consistency(self, tool: dict) -> list[Issue]:
        """Check if declared policy matches tool semantics.

        Args:
            tool: Tool definition dict

        Returns:
            List of validation issues
        """
        issues = []
        name = tool.get("name", "").lower()
        desc = (tool.get("description") or "").lower()
        policy = tool.get("side_effect_policy")

        # Tools that should probably be IRREVERSIBLE
        if policy == SideEffectPolicy.PURE.value:
            for indicator in self.IRREVERSIBLE_INDICATORS:
                if indicator in name or indicator in desc:
                    issues.append(
                        Issue(
                            severity=Severity.WARNING,
                            code="POSSIBLE_POLICY_MISMATCH",
                            message=f"Tool '{tool.get('name')}' marked PURE but contains '{indicator}' - verify this is correct",
                            fix=f"Consider changing side_effect_policy to IRREVERSIBLE if this tool has side effects",
                            location=tool.get("name"),
                        )
                    )

        # Tools that should probably be PURE
        if policy in [
            SideEffectPolicy.COMPENSATABLE.value,
            SideEffectPolicy.IRREVERSIBLE.value,
        ]:
            for indicator in self.PURE_INDICATORS:
                if name.startswith(indicator):
                    issues.append(
                        Issue(
                            severity=Severity.WARNING,
                            code="POSSIBLE_POLICY_MISMATCH",
                            message=f"Tool '{tool.get('name')}' starts with '{indicator}' but marked {policy} - verify this is correct",
                            fix="Consider changing side_effect_policy to PURE if this tool only reads data",
                            location=tool.get("name"),
                        )
                    )

        return issues
