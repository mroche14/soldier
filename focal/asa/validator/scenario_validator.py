"""Scenario definition validator.

This module validates scenario definitions for structural correctness, reachability,
and proper checkpoint placement. This is specific to the alignment mechanic.
"""

from focal.asa.models import Issue, Severity, SideEffectPolicy, ValidationResult


class ScenarioValidator:
    """Validate scenario definitions for alignment-based mechanics.

    The ScenarioValidator checks scenario graph structure, step reachability,
    checkpoint placement, and tool binding safety.
    """

    def validate(self, scenario: dict) -> ValidationResult:
        """Validate a scenario definition.

        Args:
            scenario: Scenario definition dict with fields like name, steps

        Returns:
            ValidationResult with issues and suggestions
        """
        issues = []
        suggestions = []

        scenario_name = scenario.get("name", "unknown")
        steps = scenario.get("steps", [])

        if not steps:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="EMPTY_SCENARIO",
                    message=f"Scenario '{scenario_name}' has no steps",
                    fix="Add at least one step to the scenario",
                    location=scenario_name,
                )
            )
            return ValidationResult(valid=False, issues=issues, suggestions=suggestions)

        # Check for unreachable steps
        unreachable = self._find_unreachable_steps(scenario)
        for step_name in unreachable:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="UNREACHABLE_STEP",
                    message=f"Step '{step_name}' is not reachable from any other step in scenario '{scenario_name}'",
                    fix="Add a transition to this step or remove it if unnecessary",
                    location=f"{scenario_name}.{step_name}",
                )
            )

        # Check for infinite loops
        loops = self._detect_loops(scenario)
        for loop in loops:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    code="POTENTIAL_LOOP",
                    message=f"Potential infinite loop in scenario '{scenario_name}': {' -> '.join(loop)}",
                    fix="Add an exit condition or max iteration limit",
                    location=scenario_name,
                )
            )

        # Check checkpoint placement
        checkpoint_issues = self._validate_checkpoints(scenario)
        issues.extend(checkpoint_issues)

        # Check tool bindings
        for step in steps:
            step_name = step.get("name", "unknown")
            tool_bindings = step.get("tool_bindings", [])
            for binding in tool_bindings:
                tool_issues = self._validate_step_tool(scenario_name, step, binding)
                issues.extend(tool_issues)

        return ValidationResult(
            valid=len([i for i in issues if i.severity == Severity.ERROR]) == 0,
            issues=issues,
            suggestions=suggestions,
        )

    def _find_unreachable_steps(self, scenario: dict) -> list[str]:
        """Find steps that are not reachable from any other step.

        Args:
            scenario: Scenario definition dict

        Returns:
            List of unreachable step names
        """
        steps = scenario.get("steps", [])
        if not steps:
            return []

        # Build adjacency map
        reachable = set()
        first_step = steps[0].get("name")
        reachable.add(first_step)

        # BFS to find all reachable steps
        queue = [first_step]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            # Find the step definition
            current_step = next((s for s in steps if s.get("name") == current), None)
            if not current_step:
                continue

            # Check transitions
            transitions = current_step.get("transitions", [])
            for transition in transitions:
                target = transition.get("target_step")
                if target and target not in visited:
                    reachable.add(target)
                    queue.append(target)

        # Find unreachable steps
        all_step_names = {s.get("name") for s in steps if s.get("name")}
        return list(all_step_names - reachable)

    def _detect_loops(self, scenario: dict) -> list[list[str]]:
        """Detect potential infinite loops in scenario graph.

        Args:
            scenario: Scenario definition dict

        Returns:
            List of loop paths (each is a list of step names)
        """
        steps = scenario.get("steps", [])
        loops = []

        # Simple cycle detection using DFS
        def find_cycles_from(start: str, path: list[str], visited: set[str]):
            if start in visited:
                # Found a cycle
                cycle_start = path.index(start)
                loops.append(path[cycle_start:] + [start])
                return

            visited.add(start)
            path.append(start)

            # Find the step definition
            current_step = next((s for s in steps if s.get("name") == start), None)
            if current_step:
                transitions = current_step.get("transitions", [])
                for transition in transitions:
                    target = transition.get("target_step")
                    if target:
                        find_cycles_from(target, path.copy(), visited.copy())

        # Check for cycles from each step
        for step in steps:
            step_name = step.get("name")
            if step_name:
                find_cycles_from(step_name, [], set())

        return loops

    def _validate_checkpoints(self, scenario: dict) -> list[Issue]:
        """Validate checkpoint placement makes sense.

        Args:
            scenario: Scenario definition dict

        Returns:
            List of validation issues
        """
        issues = []
        scenario_name = scenario.get("name", "unknown")
        steps = scenario.get("steps", [])

        checkpoint_steps = [s for s in steps if s.get("is_checkpoint")]

        if not checkpoint_steps:
            # No checkpoints - might be fine for simple scenarios
            has_irreversible = any(
                any(
                    tb.get("tool", {}).get("side_effect_policy")
                    == SideEffectPolicy.IRREVERSIBLE.value
                    for tb in step.get("tool_bindings", [])
                )
                for step in steps
            )
            if has_irreversible:
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        code="MISSING_CHECKPOINT",
                        message=f"Scenario '{scenario_name}' has IRREVERSIBLE tools but no checkpoint steps",
                        fix="Add is_checkpoint=True to steps that collect confirmation before irreversible actions",
                        location=scenario_name,
                    )
                )

        return issues

    def _validate_step_tool(
        self, scenario_name: str, step: dict, binding: dict
    ) -> list[Issue]:
        """Validate tool binding on a step.

        Args:
            scenario_name: Name of the scenario
            step: Step definition dict
            binding: Tool binding dict

        Returns:
            List of validation issues
        """
        issues = []
        step_name = step.get("name", "unknown")
        tool = binding.get("tool", {})
        tool_name = tool.get("name", "unknown")
        side_effect_policy = tool.get("side_effect_policy")

        # IRREVERSIBLE tool on non-checkpoint step
        if side_effect_policy == SideEffectPolicy.IRREVERSIBLE.value:
            if not step.get("is_checkpoint"):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        code="IRREVERSIBLE_NO_CHECKPOINT",
                        message=f"Step '{step_name}' in scenario '{scenario_name}' has IRREVERSIBLE tool '{tool_name}' but is_checkpoint=False",
                        fix="Set is_checkpoint=True on this step to ensure confirmation before irreversible action",
                        location=f"{scenario_name}.{step_name}",
                    )
                )

        return issues
