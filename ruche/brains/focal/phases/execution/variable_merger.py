"""Variable merging from multiple sources."""

from typing import Any

from ruche.brains.focal.phases.execution.models import ToolResult
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class VariableMerger:
    """Merges variables from multiple sources into engine_variables."""

    def merge_tool_results(
        self,
        known_vars: dict[str, Any],
        tool_results: list[ToolResult],
    ) -> dict[str, Any]:
        """Merge tool results into engine_variables.

        Merge order:
        1. Start with known_vars (profile + session)
        2. Add variables_filled from each ToolResult
        3. Later tools override earlier tools if conflict

        Args:
            known_vars: Pre-resolved variables from profile/session
            tool_results: Tool execution results

        Returns:
            engine_variables: Merged dict[str, Any]
        """
        # Start with known variables
        engine_variables = dict(known_vars)
        provenance: dict[str, str] = dict.fromkeys(known_vars, "pre_resolved")

        # Merge successful tool results
        for result in tool_results:
            if not result.success:
                continue

            for var_name, value in result.variables_filled.items():
                if var_name in engine_variables and var_name in provenance:
                    # Conflict: log and override
                    logger.warning(
                        "variable_conflict",
                        variable=var_name,
                        previous_source=provenance[var_name],
                        new_source=result.tool_name,
                        overriding=True,
                    )

                engine_variables[var_name] = value
                provenance[var_name] = result.tool_name

        logger.info(
            "merged_tool_results",
            total_variables=len(engine_variables),
            from_known=len(known_vars),
            from_tools=len(engine_variables) - len(known_vars),
            successful_tools=sum(1 for r in tool_results if r.success),
        )

        return engine_variables
