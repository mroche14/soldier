"""Tool scheduling based on timing and dependencies."""

from typing import Literal
from uuid import UUID

from ruche.alignment.models.tool_binding import ToolBinding
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ToolScheduler:
    """Determines which tools to execute now based on timing and missing variables."""

    def schedule_tools(
        self,
        tool_bindings: list[ToolBinding],
        missing_vars: set[str],
        current_phase: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"],
    ) -> list[tuple[str, list[str]]]:
        """Determine tool calls allowed in current phase.

        Args:
            tool_bindings: All available tool bindings
            missing_vars: Variables still needed
            current_phase: Current execution phase

        Returns:
            List of (tool_id, vars_to_fill) tuples for execution
        """
        # Filter bindings by timing phase
        phase_bindings = [b for b in tool_bindings if b.when == current_phase]

        # Filter by which tools can fill missing variables
        relevant_bindings = []
        for binding in phase_bindings:
            # Check if this tool can fill any missing variables
            can_fill = any(var in missing_vars for var in binding.required_variables)
            if can_fill or not binding.required_variables:
                # Include tools with no required_variables (may have side effects)
                relevant_bindings.append(binding)

        # Build dependency graph and topologically sort
        scheduled = self._topological_sort(relevant_bindings)

        # Build result with variables each tool should fill
        result: list[tuple[str, list[str]]] = []
        for binding in scheduled:
            vars_to_fill = [v for v in binding.required_variables if v in missing_vars]
            result.append((binding.tool_id, vars_to_fill))

        logger.info(
            "scheduled_tools",
            phase=current_phase,
            total_bindings=len(tool_bindings),
            phase_bindings=len(phase_bindings),
            scheduled_count=len(result),
            missing_vars_count=len(missing_vars),
        )

        return result

    def _topological_sort(self, bindings: list[ToolBinding]) -> list[ToolBinding]:
        """Sort bindings by dependencies using topological sort.

        Args:
            bindings: Tool bindings to sort

        Returns:
            Sorted list respecting dependencies
        """
        # Build adjacency list
        tool_map = {b.tool_id: b for b in bindings}
        in_degree = {b.tool_id: 0 for b in bindings}
        adjacency = {b.tool_id: [] for b in bindings}

        for binding in bindings:
            for dep in binding.depends_on:
                if dep in tool_map:
                    adjacency[dep].append(binding.tool_id)
                    in_degree[binding.tool_id] += 1

        # Kahn's algorithm
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(tool_map[current])

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # If not all bindings processed, there's a cycle - return original order
        if len(result) < len(bindings):
            logger.warning(
                "dependency_cycle_detected",
                total_bindings=len(bindings),
                sorted_count=len(result),
            )
            return bindings

        return result


class FutureToolQueue:
    """Tracks tools scheduled for future execution (AFTER_STEP)."""

    def __init__(self) -> None:
        """Initialize the queue."""
        self._queues: dict[UUID, list[ToolBinding]] = {}

    def add_tools(
        self,
        tool_bindings: list[ToolBinding],
        session_id: UUID,
    ) -> None:
        """Add AFTER_STEP tools to queue.

        Args:
            tool_bindings: All tool bindings
            session_id: Session to queue for
        """
        after_step_tools = [b for b in tool_bindings if b.when == "AFTER_STEP"]

        if after_step_tools:
            if session_id not in self._queues:
                self._queues[session_id] = []
            self._queues[session_id].extend(after_step_tools)

            logger.info(
                "queued_after_step_tools",
                session_id=str(session_id),
                tool_count=len(after_step_tools),
            )

    def get_pending_tools(
        self,
        session_id: UUID,
    ) -> list[ToolBinding]:
        """Get tools waiting to execute after step completes.

        Args:
            session_id: Session to get tools for

        Returns:
            List of pending tool bindings
        """
        return self._queues.get(session_id, [])

    def clear_session(self, session_id: UUID) -> None:
        """Clear queue for session (step transition).

        Args:
            session_id: Session to clear
        """
        if session_id in self._queues:
            del self._queues[session_id]
            logger.debug("cleared_future_tool_queue", session_id=str(session_id))
