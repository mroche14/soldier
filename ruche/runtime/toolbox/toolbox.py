"""Toolbox class - agent's facade for tool execution.

Agent-level tool facade. Knows tool semantics (reversible, compensatable).
"""

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from ruche.observability.logging import get_logger
from ruche.runtime.toolbox.context import ToolExecutionContext
from ruche.runtime.toolbox.gateway import ToolGateway
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

if TYPE_CHECKING:
    from ruche.runtime.acf.events import ACFEvent, ACFEventType

logger = get_logger(__name__)


class Toolbox:
    """Agent-level tool facade.

    Responsibilities:
    - Resolve tools from definitions + activations
    - Execute via ToolGateway
    - Record side effects via ACFEvents
    - Provide tool metadata for supersede decisions
    - Track unavailable tools for agent awareness

    Three-tier visibility:
    1. Catalog - all tools in ecosystem (marketplace)
    2. Tenant-available (Tier 2) - tools tenant has connected/purchased
    3. Agent-enabled (Tier 3) - tools this agent can use
    """

    def __init__(
        self,
        agent_id: UUID,
        tool_definitions: dict[UUID, ToolDefinition],
        tool_activations: dict[UUID, ToolActivation],
        gateway: ToolGateway,
    ):
        """Initialize toolbox.

        Args:
            agent_id: Agent identifier
            tool_definitions: All tenant-available tool definitions
            tool_activations: Agent-specific tool activations
            gateway: Gateway for tool execution
        """
        self._agent_id = agent_id
        self._gateway = gateway

        # Build resolved tool map (Tier 3: agent-enabled tools)
        self._enabled_tools: dict[str, ResolvedTool] = {}

        # Track all tenant-available tools (Tier 2: for discovery)
        self._available_tools: dict[str, ToolDefinition] = {}

        for tool_id, defn in tool_definitions.items():
            # All definitions are tenant-available (Tier 2)
            self._available_tools[defn.name] = defn

            # Check if enabled for this agent (Tier 3)
            activation = tool_activations.get(tool_id)
            if activation and activation.enabled:
                self._enabled_tools[defn.name] = ResolvedTool(
                    definition=defn,
                    activation=activation,
                )
            elif not activation:
                # No activation = use defaults (enabled)
                self._enabled_tools[defn.name] = ResolvedTool(
                    definition=defn,
                    activation=None,
                )

    async def execute(
        self,
        tool: PlannedToolExecution,
        turn_context: Any,  # AgentTurnContext - avoid circular import
    ) -> ToolResult:
        """Execute a single tool.

        Flow:
        1. Resolve tool from definitions
        2. Build ToolExecutionContext with turn_group_id
        3. Execute via ToolGateway
        4. Record side effect via ACFEvent
        5. Return result

        Args:
            tool: Planned tool execution
            turn_context: Agent turn context (contains emit_event callback)

        Returns:
            Tool execution result
        """
        resolved = self._enabled_tools.get(tool.tool_name)
        if not resolved:
            logger.warning(
                "tool_not_found",
                tool_name=tool.tool_name,
                agent_id=str(self._agent_id),
            )
            return ToolResult(
                status="error",
                error=f"Tool '{tool.tool_name}' not found or not enabled",
            )

        # Build execution context (bridges ACF turn_group_id to gateway)
        exec_ctx = ToolExecutionContext(
            tenant_id=resolved.definition.tenant_id,
            agent_id=self._agent_id,
            turn_group_id=turn_context.logical_turn.turn_group_id,
            tool_name=tool.tool_name,
            args=tool.args,
            gateway=resolved.definition.gateway,
            gateway_config=resolved.definition.gateway_config,
        )

        # Emit start event
        await self._emit_event(
            turn_context,
            "TOOL_SIDE_EFFECT_STARTED",
            {
                "tool_name": tool.tool_name,
                "side_effect_policy": resolved.definition.side_effect_policy.value,
            },
        )

        # Execute via gateway
        try:
            result = await self._gateway.execute(exec_ctx)
        except Exception as e:
            # Emit failure event
            await self._emit_event(
                turn_context,
                "TOOL_SIDE_EFFECT_FAILED",
                {
                    "tool_name": tool.tool_name,
                    "error": str(e),
                },
            )
            logger.error(
                "tool_execution_exception",
                tool_name=tool.tool_name,
                error=str(e),
                agent_id=str(self._agent_id),
            )
            return ToolResult(status="error", error=str(e))

        # Build and emit side effect record
        effect = SideEffectRecord(
            tool_name=tool.tool_name,
            policy=resolved.definition.side_effect_policy,
            executed_at=datetime.utcnow(),
            args=tool.args,
            result=result.data if result.success else None,
            status="executed" if result.success else "failed",
            idempotency_key=exec_ctx.build_idempotency_key(
                self._extract_business_key(tool.args, resolved.definition)
            ),
        )

        await self._emit_event(
            turn_context,
            "TOOL_SIDE_EFFECT_COMPLETED",
            effect.model_dump(),
        )

        return result

    async def execute_batch(
        self,
        tools: list[PlannedToolExecution],
        turn_context: Any,
    ) -> list[ToolResult]:
        """Execute multiple tools sequentially.

        Args:
            tools: List of planned tool executions
            turn_context: Agent turn context

        Returns:
            List of tool execution results
        """
        results = []
        for tool in tools:
            result = await self.execute(tool, turn_context)
            results.append(result)
            # Stop on first failure if tool is critical
            if not result.success and tool.critical:
                logger.info(
                    "tool_batch_stopped_on_failure",
                    tool_name=tool.tool_name,
                    agent_id=str(self._agent_id),
                )
                break
        return results

    def get_metadata(self, tool_name: str) -> ToolMetadata | None:
        """Get metadata for a tool.

        Used by Brain to decide supersede behavior before execution.

        Args:
            tool_name: Name of tool

        Returns:
            Tool metadata or None if not found
        """
        resolved = self._enabled_tools.get(tool_name)
        if not resolved:
            return None

        # Apply activation overrides
        defn = resolved.definition
        activation = resolved.activation

        requires_confirmation = defn.requires_confirmation
        if activation and "requires_confirmation" in activation.policy_overrides:
            requires_confirmation = activation.policy_overrides["requires_confirmation"]

        return ToolMetadata(
            name=defn.name,
            side_effect_policy=defn.side_effect_policy,
            requires_confirmation=requires_confirmation,
            compensation_tool=defn.compensation_tool_id,
            categories=defn.categories,
        )

    def is_available(self, tool_name: str) -> bool:
        """Check if tool is available for this agent.

        Args:
            tool_name: Name of tool

        Returns:
            True if tool is enabled for agent
        """
        return tool_name in self._enabled_tools

    def list_available(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of tool names enabled for agent
        """
        return list(self._enabled_tools.keys())

    def get_unavailable_tools(self) -> list[ToolDefinition]:
        """Get tools available to tenant but not enabled for this agent.

        This is Tier 2 (tenant-available) minus Tier 3 (agent-enabled).

        Enables agents to say:
        - "I could help you schedule a meeting if the Calendar tool is enabled"
        - "This requires the Email tool, which I don't have access to"

        Used by:
        - Agent response generation (suggest tool activations)
        - Agent Suggestion Agent (ASA) for recommendations
        - Admin UI (show what could be enabled)

        Returns:
            List of tools available to tenant but not agent
        """
        unavailable = []
        for tool_name, definition in self._available_tools.items():
            if tool_name not in self._enabled_tools:
                unavailable.append(definition)
        return unavailable

    def is_tenant_available(self, tool_name: str) -> bool:
        """Check if tool is available to the tenant (Tier 2).

        Returns True even if not enabled for this agent.

        Args:
            tool_name: Name of tool

        Returns:
            True if tool is available to tenant
        """
        return tool_name in self._available_tools

    def get_tool_definition(self, tool_name: str) -> ToolDefinition | None:
        """Get tool definition (Tier 2 lookup).

        Returns definition even if not enabled for this agent.
        Used for discovery and recommendation flows.

        Args:
            tool_name: Name of tool

        Returns:
            Tool definition or None if not found
        """
        return self._available_tools.get(tool_name)

    def _extract_business_key(
        self,
        args: dict[str, Any],
        definition: ToolDefinition,
    ) -> str:
        """Extract business key from args for idempotency.

        Uses tool's parameter_schema to identify key fields.
        Falls back to hashing all args.

        Args:
            args: Tool arguments
            definition: Tool definition

        Returns:
            Business key for idempotency
        """
        key_fields = definition.gateway_config.get("idempotency_key_fields", [])
        if key_fields:
            key_parts = [str(args.get(f, "")) for f in key_fields]
            return ":".join(key_parts)
        else:
            # Fallback: hash all args
            return hashlib.sha256(
                json.dumps(args, sort_keys=True).encode()
            ).hexdigest()[:16]

    async def _emit_event(
        self,
        turn_context: Any,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit ACF event.

        Args:
            turn_context: Agent turn context
            event_type: Event type name
            payload: Event payload
        """
        # Avoid circular import - call emit_event callback if available
        if hasattr(turn_context, "emit_event"):
            # Build event dict - actual ACFEvent creation happens in ACF
            await turn_context.emit_event(
                type=event_type,
                payload=payload,
            )
