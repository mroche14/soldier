"""MCP (Model Context Protocol) server for tool discovery.

This module provides read-only tool catalog access for LLMs and AI agents
to discover what tools are available at three visibility tiers:

- Tier 1: Catalog (all tools in ecosystem) - Not yet implemented
- Tier 2: Tenant-available (tools tenant has connected/purchased)
- Tier 3: Agent-enabled (tools this agent can use)

The MCP server is for discovery only. Tool execution happens through
the Toolbox layer, not via MCP.
"""

from ruche.api.mcp.handlers import router
from ruche.api.mcp.server import MCPToolServer

__all__ = ["MCPToolServer", "router"]
