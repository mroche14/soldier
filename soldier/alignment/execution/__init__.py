"""Alignment execution module.

Contains tool execution and variable resolution components.
"""

from soldier.alignment.execution.models import ToolResult, VariableResolution
from soldier.alignment.execution.tool_executor import ToolExecutor
from soldier.alignment.execution.variable_resolver import VariableResolver

__all__ = [
    "ToolResult",
    "VariableResolution",
    "ToolExecutor",
    "VariableResolver",
]
