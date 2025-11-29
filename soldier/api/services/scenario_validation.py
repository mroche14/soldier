"""Scenario validation service."""

from uuid import UUID

from soldier.alignment.models import Scenario
from soldier.observability.logging import get_logger

logger = get_logger(__name__)


def detect_unreachable_steps(scenario: Scenario) -> list[UUID]:
    """Detect steps that cannot be reached from the entry point.

    Uses BFS from entry step to find all reachable steps,
    then returns any steps that weren't visited.

    Args:
        scenario: Scenario to analyze

    Returns:
        List of unreachable step IDs
    """
    if not scenario.steps:
        return []

    # Build step lookup
    step_map = {step.id: step for step in scenario.steps}

    # BFS from entry step
    reachable: set[UUID] = set()
    queue = [scenario.entry_step_id]

    while queue:
        step_id = queue.pop(0)
        if step_id in reachable:
            continue

        reachable.add(step_id)

        step = step_map.get(step_id)
        if step:
            for transition in step.transitions:
                if transition.to_step_id not in reachable:
                    queue.append(transition.to_step_id)

    # Find unreachable steps
    all_step_ids = {step.id for step in scenario.steps}
    unreachable = all_step_ids - reachable

    if unreachable:
        logger.warning(
            "unreachable_steps_detected",
            scenario_id=str(scenario.id),
            unreachable_count=len(unreachable),
        )

    return list(unreachable)


def validate_scenario_graph(scenario: Scenario) -> list[str]:
    """Validate scenario graph structure.

    Checks for:
    - Entry step exists in steps list
    - All transition targets exist
    - No orphaned steps (unreachable from entry)
    - At least one terminal step

    Args:
        scenario: Scenario to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors: list[str] = []

    if not scenario.steps:
        errors.append("Scenario has no steps")
        return errors

    step_ids = {step.id for step in scenario.steps}

    # Check entry step exists
    if scenario.entry_step_id not in step_ids:
        errors.append(f"Entry step {scenario.entry_step_id} not found in steps")

    # Check all transitions point to valid steps
    for step in scenario.steps:
        for transition in step.transitions:
            if transition.to_step_id not in step_ids:
                errors.append(
                    f"Step '{step.name}' has transition to unknown step {transition.to_step_id}"
                )

    # Check for unreachable steps
    unreachable = detect_unreachable_steps(scenario)
    if unreachable:
        errors.append(f"Found {len(unreachable)} unreachable step(s)")

    # Check for at least one terminal step
    has_terminal = any(step.is_terminal for step in scenario.steps)
    if not has_terminal:
        errors.append("Scenario has no terminal steps")

    return errors
