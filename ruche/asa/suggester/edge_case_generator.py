"""Edge case rule generator.

This module generates suggested rules for common edge cases in scenarios,
such as cancellation handling, validation, and timeout scenarios.
Primarily used by alignment-based mechanics.
"""

from ruche.asa.models import SideEffectPolicy, SuggestedRule


class EdgeCaseGenerator:
    """Generate edge-case rules and scenarios based on scenario analysis."""

    def generate_edge_cases(
        self,
        scenario: dict,
        tools: list[dict],
    ) -> list[SuggestedRule]:
        """Generate edge-case rules for a scenario.

        Analyzes the scenario structure and tool usage to suggest rules for
        common edge cases like user cancellation, invalid input, and timeouts.

        Args:
            scenario: Scenario definition dict
            tools: List of available tool definitions

        Returns:
            List of suggested rules to handle edge cases
        """
        suggestions = []
        scenario_name = scenario.get("name", "unknown")
        steps = scenario.get("steps", [])

        # Build tool lookup map
        tool_map = {t.get("name"): t for t in tools if t.get("name")}

        # For each IRREVERSIBLE tool, suggest cancellation handling
        for step in steps:
            step_name = step.get("name", "unknown")
            tool_bindings = step.get("tool_bindings", [])

            for binding in tool_bindings:
                tool_name = binding.get("tool_name")
                tool = tool_map.get(tool_name, {})
                side_effect_policy = tool.get("side_effect_policy")

                if side_effect_policy == SideEffectPolicy.IRREVERSIBLE.value:
                    suggestions.append(
                        SuggestedRule(
                            name=f"handle_cancel_before_{step_name}",
                            description=f"Handle user cancellation before {tool_name}",
                            trigger_condition="User says 'cancel', 'stop', 'wait', or 'nevermind'",
                            trigger_scope=f"Before reaching step '{step_name}'",
                            suggested_action="Confirm cancellation, don't proceed to irreversible action",
                            priority=100,  # High priority to catch cancellations
                        )
                    )

        # For scenarios with data collection, suggest validation rules
        data_steps = [s for s in steps if self._is_data_collection_step(s)]
        for step in data_steps:
            step_name = step.get("name", "unknown")
            suggestions.append(
                SuggestedRule(
                    name=f"validate_{step_name}_input",
                    description=f"Validate user input at step '{step_name}'",
                    trigger_condition="User provides invalid or incomplete data",
                    suggested_action="Re-prompt with specific guidance on what format is expected",
                    priority=50,
                )
            )

        # Suggest timeout handling for multi-step scenarios
        if len(steps) > 3:
            suggestions.append(
                SuggestedRule(
                    name=f"handle_{scenario_name}_timeout",
                    description=f"Handle session timeout mid-scenario in {scenario_name}",
                    trigger_condition="No user response for configured timeout period",
                    suggested_action="Send reminder or gracefully close scenario with option to resume",
                    priority=30,
                )
            )

        # Suggest error handling for tools with external dependencies
        external_tools = [
            tool for tool in tools
            if self._is_external_tool(tool)
        ]
        if external_tools:
            for tool in external_tools:
                tool_name = tool.get("name", "unknown")
                suggestions.append(
                    SuggestedRule(
                        name=f"handle_{tool_name}_failure",
                        description=f"Handle failure of external tool {tool_name}",
                        trigger_condition=f"Tool '{tool_name}' returns error or times out",
                        suggested_action="Inform user of the issue and offer alternative or retry",
                        priority=40,
                    )
                )

        # Suggest confirmation for scenarios with multiple irreversible steps
        irreversible_steps = [
            s for s in steps
            if any(
                tool_map.get(tb.get("tool_name"), {}).get("side_effect_policy")
                == SideEffectPolicy.IRREVERSIBLE.value
                for tb in s.get("tool_bindings", [])
            )
        ]
        if len(irreversible_steps) > 1:
            suggestions.append(
                SuggestedRule(
                    name=f"confirm_multi_action_{scenario_name}",
                    description=f"Confirm with user before multiple irreversible actions in {scenario_name}",
                    trigger_condition="About to execute second or subsequent irreversible action",
                    suggested_action="Summarize what has been done and confirm next action",
                    priority=80,
                )
            )

        return suggestions

    def _is_data_collection_step(self, step: dict) -> bool:
        """Check if step collects user data.

        Args:
            step: Step definition dict

        Returns:
            True if step appears to collect data from user
        """
        prompt = (step.get("prompt") or "").lower()
        description = (step.get("description") or "").lower()
        combined = f"{prompt} {description}"

        # Heuristic: step prompts user for specific information
        data_collection_keywords = [
            "enter",
            "provide",
            "what is your",
            "please tell",
            "type",
            "input",
            "specify",
            "give me",
            "share your",
        ]

        return any(keyword in combined for keyword in data_collection_keywords)

    def _is_external_tool(self, tool: dict) -> bool:
        """Check if tool depends on external service.

        Args:
            tool: Tool definition dict

        Returns:
            True if tool appears to call external service
        """
        name = tool.get("name", "").lower()
        description = (tool.get("description") or "").lower()
        combined = f"{name} {description}"

        # Heuristic: tool name/description mentions external systems
        external_keywords = [
            "api",
            "http",
            "external",
            "service",
            "third-party",
            "integration",
            "webhook",
            "fetch",
            "call",
        ]

        return any(keyword in combined for keyword in external_keywords)
