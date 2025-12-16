"""Tool execution context.

Bridges Agent layer (Toolbox) to Infrastructure layer (ToolGateway).
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass
class ToolExecutionContext:
    """Context passed to ToolGateway for execution.

    Bridges Agent layer (Toolbox) to Infrastructure layer (ToolGateway).
    Carries turn_group_id from ACF for idempotency key construction.
    """

    tenant_id: UUID
    agent_id: UUID
    turn_group_id: UUID  # From LogicalTurn (ACF-provided)
    tool_name: str
    args: dict[str, Any]
    gateway: str  # "composio", "http", "internal"
    gateway_config: dict[str, Any]

    def build_idempotency_key(self, business_key: str) -> str:
        """Build idempotency key scoped to conversation attempt.

        Format: {tool_name}:{business_key}:turn_group:{turn_group_id}

        This ensures:
        - Supersede chain shares key -> one execution
        - QUEUE creates new turn_group_id -> allows re-execution

        Args:
            business_key: Business-level identifier for the operation

        Returns:
            Composite idempotency key
        """
        return f"{self.tool_name}:{business_key}:turn_group:{self.turn_group_id}"
