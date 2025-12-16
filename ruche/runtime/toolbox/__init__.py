"""Toolbox layer for tool execution.

The Toolbox layer handles tool execution for Agents, bridging the business
layer (Agent/Brain) with the infrastructure layer (ToolGateway/Providers).

Key Components:
- Toolbox - Agent-level facade (knows tool semantics)
- ToolGateway - Infrastructure-level execution (knows providers)
- ToolExecutionContext - Bridges ACF turn_group_id to tool idempotency
- ToolDefinition / ToolActivation - Configuration in ConfigStore

Key Principle: Toolbox owns tool semantics (reversible, compensatable).
ToolGateway owns execution mechanics (providers, idempotency).

Three-Tier Visibility Model:
- Tier 1 (Catalog): All tools in ecosystem
- Tier 2 (Tenant-Available): Tools tenant has connected
- Tier 3 (Agent-Enabled): Tools this agent can use
"""

from ruche.runtime.toolbox.context import ToolExecutionContext
from ruche.runtime.toolbox.gateway import (
    IdempotencyCache,
    ToolExecutionError,
    ToolGateway,
    ToolProvider,
)
from ruche.runtime.toolbox.models import (
    PlannedToolExecution,
    ResolvedTool,
    SideEffectPolicy,
    SideEffectRecord,
    ToolActivation,
    ToolDefinition,
    ToolMetadata,
    ToolResult,
)
from ruche.runtime.toolbox.toolbox import Toolbox

__all__ = [
    # Core classes
    "Toolbox",
    "ToolGateway",
    "ToolExecutionContext",
    # Models
    "ToolDefinition",
    "ToolActivation",
    "PlannedToolExecution",
    "ToolResult",
    "ToolMetadata",
    "SideEffectRecord",
    "SideEffectPolicy",
    "ResolvedTool",
    # Gateway
    "ToolProvider",
    "ToolExecutionError",
    "IdempotencyCache",
]
