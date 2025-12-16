"""Tests for Toolbox class."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ruche.runtime.toolbox.models import (
    PlannedToolExecution,
    SideEffectPolicy,
    ToolActivation,
    ToolDefinition,
    ToolResult,
)
from ruche.runtime.toolbox.toolbox import Toolbox


class TestToolbox:
    """Tests for Toolbox class."""

    @pytest.fixture
    def agent_id(self):
        """Create agent ID."""
        return uuid4()

    @pytest.fixture
    def tenant_id(self):
        """Create tenant ID."""
        return uuid4()

    @pytest.fixture
    def tool_definition(self, tenant_id):
        """Create a sample tool definition."""
        return ToolDefinition(
            id=uuid4(),
            tenant_id=tenant_id,
            name="send_email",
            description="Send an email",
            gateway="http",
            gateway_config={"url": "https://api.example.com/email"},
            side_effect_policy=SideEffectPolicy.IDEMPOTENT,
            parameter_schema={
                "type": "object",
                "properties": {"to": {"type": "string"}, "subject": {"type": "string"}},
            },
        )

    @pytest.fixture
    def tool_definitions(self, tool_definition):
        """Create tool definitions map."""
        return {tool_definition.id: tool_definition}

    @pytest.fixture
    def tool_activations(self):
        """Create empty tool activations map."""
        return {}

    @pytest.fixture
    def gateway(self):
        """Create mock gateway."""
        mock = AsyncMock()
        mock.execute = AsyncMock(return_value=ToolResult(status="success", data={"sent": True}))
        return mock

    @pytest.fixture
    def toolbox(self, agent_id, tool_definitions, tool_activations, gateway):
        """Create toolbox instance."""
        return Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_definitions,
            tool_activations=tool_activations,
            gateway=gateway,
        )

    @pytest.fixture
    def turn_context(self):
        """Create mock turn context."""
        mock = MagicMock()
        mock.logical_turn.turn_group_id = "turn-group-123"
        mock.emit_event = AsyncMock()
        return mock

    def test_toolbox_initialization(self, agent_id, tool_definitions, tool_activations, gateway):
        """Should initialize toolbox with tools."""
        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_definitions,
            tool_activations=tool_activations,
            gateway=gateway,
        )

        assert toolbox._agent_id == agent_id
        assert "send_email" in toolbox._enabled_tools
        assert "send_email" in toolbox._available_tools

    def test_tool_enabled_by_default(self, agent_id, tool_definitions, gateway):
        """Should enable tools by default when no activation exists."""
        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_definitions,
            tool_activations={},
            gateway=gateway,
        )

        assert toolbox.is_available("send_email")

    def test_tool_disabled_via_activation(self, agent_id, tool_definitions, gateway, tool_definition):
        """Should disable tool when activation sets enabled=False."""
        activation = ToolActivation(
            id=uuid4(),
            tenant_id=tool_definition.tenant_id,
            agent_id=agent_id,
            tool_id=tool_definition.id,
            enabled=False,
        )

        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_definitions,
            tool_activations={tool_definition.id: activation},
            gateway=gateway,
        )

        assert not toolbox.is_available("send_email")
        assert toolbox.is_tenant_available("send_email")

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, toolbox, turn_context, gateway):
        """Should execute tool successfully."""
        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com", "subject": "Test"},
        )

        result = await toolbox.execute(tool, turn_context)

        assert result.status == "success"
        assert result.data["sent"] is True
        gateway.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, toolbox, turn_context):
        """Should return error when tool not found."""
        tool = PlannedToolExecution(
            tool_name="nonexistent_tool",
            args={},
        )

        result = await toolbox.execute(tool, turn_context)

        assert result.status == "error"
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_emits_start_event(self, toolbox, turn_context):
        """Should emit start event before execution."""
        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com"},
        )

        await toolbox.execute(tool, turn_context)

        # Check that emit_event was called with start event
        calls = turn_context.emit_event.call_args_list
        assert any("TOOL_SIDE_EFFECT_STARTED" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_execute_emits_completed_event(self, toolbox, turn_context):
        """Should emit completed event after execution."""
        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com"},
        )

        await toolbox.execute(tool, turn_context)

        # Check that emit_event was called with completed event
        calls = turn_context.emit_event.call_args_list
        assert any("TOOL_SIDE_EFFECT_COMPLETED" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_execute_emits_failed_event_on_exception(self, toolbox, turn_context, gateway):
        """Should emit failed event when execution raises exception."""
        gateway.execute = AsyncMock(side_effect=Exception("Network error"))

        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com"},
        )

        result = await toolbox.execute(tool, turn_context)

        assert result.status == "error"
        calls = turn_context.emit_event.call_args_list
        assert any("TOOL_SIDE_EFFECT_FAILED" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_execute_batch(self, toolbox, turn_context, gateway):
        """Should execute multiple tools sequentially."""
        tools = [
            PlannedToolExecution(tool_name="send_email", args={"to": "user1@example.com"}),
            PlannedToolExecution(tool_name="send_email", args={"to": "user2@example.com"}),
        ]

        results = await toolbox.execute_batch(tools, turn_context)

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        assert gateway.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_batch_stops_on_critical_failure(self, toolbox, turn_context, gateway):
        """Should stop batch execution on critical tool failure."""
        gateway.execute = AsyncMock(side_effect=[
            ToolResult(status="success", data={"sent": True}),
            ToolResult(status="error", error="Failed"),
        ])

        tools = [
            PlannedToolExecution(tool_name="send_email", args={"to": "user1@example.com"}),
            PlannedToolExecution(
                tool_name="send_email",
                args={"to": "user2@example.com"},
                critical=True,
            ),
            PlannedToolExecution(tool_name="send_email", args={"to": "user3@example.com"}),
        ]

        results = await toolbox.execute_batch(tools, turn_context)

        # Should stop after second tool fails
        assert len(results) == 2
        assert gateway.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_batch_continues_on_non_critical_failure(self, toolbox, turn_context, gateway):
        """Should continue batch execution on non-critical tool failure."""
        gateway.execute = AsyncMock(side_effect=[
            ToolResult(status="success", data={"sent": True}),
            ToolResult(status="error", error="Failed"),
            ToolResult(status="success", data={"sent": True}),
        ])

        tools = [
            PlannedToolExecution(tool_name="send_email", args={"to": "user1@example.com"}),
            PlannedToolExecution(
                tool_name="send_email",
                args={"to": "user2@example.com"},
                critical=False,
            ),
            PlannedToolExecution(tool_name="send_email", args={"to": "user3@example.com"}),
        ]

        results = await toolbox.execute_batch(tools, turn_context)

        # Should execute all tools
        assert len(results) == 3
        assert gateway.execute.call_count == 3

    def test_get_metadata(self, toolbox):
        """Should return tool metadata."""
        metadata = toolbox.get_metadata("send_email")

        assert metadata is not None
        assert metadata.name == "send_email"
        assert metadata.side_effect_policy == SideEffectPolicy.IDEMPOTENT

    def test_get_metadata_not_found(self, toolbox):
        """Should return None for nonexistent tool."""
        metadata = toolbox.get_metadata("nonexistent")
        assert metadata is None

    def test_get_metadata_with_activation_override(self, agent_id, tool_definitions, gateway, tool_definition):
        """Should apply activation overrides to metadata."""
        activation = ToolActivation(
            id=uuid4(),
            tenant_id=tool_definition.tenant_id,
            agent_id=agent_id,
            tool_id=tool_definition.id,
            enabled=True,
            policy_overrides={"requires_confirmation": True},
        )

        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions=tool_definitions,
            tool_activations={tool_definition.id: activation},
            gateway=gateway,
        )

        metadata = toolbox.get_metadata("send_email")
        assert metadata.requires_confirmation is True

    def test_is_available(self, toolbox):
        """Should check if tool is available."""
        assert toolbox.is_available("send_email")
        assert not toolbox.is_available("nonexistent")

    def test_list_available(self, toolbox):
        """Should list all available tools."""
        available = toolbox.list_available()
        assert "send_email" in available

    def test_get_unavailable_tools(self, agent_id, tenant_id, gateway):
        """Should return tools available to tenant but not agent."""
        tool1 = ToolDefinition(
            id=uuid4(),
            tenant_id=tenant_id,
            name="enabled_tool",
            description="Enabled",
            gateway="http",
        )
        tool2 = ToolDefinition(
            id=uuid4(),
            tenant_id=tenant_id,
            name="disabled_tool",
            description="Disabled",
            gateway="http",
        )

        activation = ToolActivation(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            tool_id=tool2.id,
            enabled=False,
        )

        toolbox = Toolbox(
            agent_id=agent_id,
            tool_definitions={tool1.id: tool1, tool2.id: tool2},
            tool_activations={tool2.id: activation},
            gateway=gateway,
        )

        unavailable = toolbox.get_unavailable_tools()
        assert len(unavailable) == 1
        assert unavailable[0].name == "disabled_tool"

    def test_is_tenant_available(self, toolbox):
        """Should check if tool is available to tenant."""
        assert toolbox.is_tenant_available("send_email")
        assert not toolbox.is_tenant_available("nonexistent")

    def test_get_tool_definition(self, toolbox, tool_definition):
        """Should get tool definition."""
        defn = toolbox.get_tool_definition("send_email")
        assert defn is not None
        assert defn.name == "send_email"

    def test_extract_business_key_with_key_fields(self, toolbox, tool_definition):
        """Should extract business key from specified fields."""
        tool_definition.gateway_config["idempotency_key_fields"] = ["to", "subject"]

        args = {"to": "user@example.com", "subject": "Test", "body": "Hello"}
        key = toolbox._extract_business_key(args, tool_definition)

        assert key == "user@example.com:Test"

    def test_extract_business_key_fallback_to_hash(self, toolbox, tool_definition):
        """Should hash all args when no key fields specified."""
        args = {"to": "user@example.com", "subject": "Test"}
        key = toolbox._extract_business_key(args, tool_definition)

        # Should be a hash
        assert len(key) == 16
        assert isinstance(key, str)

    def test_extract_business_key_deterministic(self, toolbox, tool_definition):
        """Should produce same key for same args."""
        args = {"to": "user@example.com", "subject": "Test"}
        key1 = toolbox._extract_business_key(args, tool_definition)
        key2 = toolbox._extract_business_key(args, tool_definition)

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_execute_builds_correct_context(self, toolbox, turn_context, gateway):
        """Should build ToolExecutionContext with correct parameters."""
        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com"},
        )

        await toolbox.execute(tool, turn_context)

        # Check gateway was called with ToolExecutionContext
        call_args = gateway.execute.call_args
        ctx = call_args[0][0]
        assert ctx.tool_name == "send_email"
        assert ctx.args == {"to": "user@example.com"}
        assert ctx.turn_group_id == "turn-group-123"
        assert ctx.gateway == "http"

    @pytest.mark.asyncio
    async def test_execute_with_emit_event_callback(self, toolbox, gateway):
        """Should use emit_event callback when available."""
        turn_context = MagicMock()
        turn_context.logical_turn.turn_group_id = "turn-123"
        turn_context.emit_event = AsyncMock()

        tool = PlannedToolExecution(
            tool_name="send_email",
            args={"to": "user@example.com"},
        )

        result = await toolbox.execute(tool, turn_context)
        assert result.status == "success"
        # emit_event should have been called
        assert turn_context.emit_event.call_count > 0
