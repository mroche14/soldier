# %% [markdown]
# # Soldier Client Demo
#
# This notebook demonstrates how to use the Soldier API client to:
# 1. Create an agent
# 2. Add behavior rules
# 3. Chat with the agent

# %% [markdown]
# ## Setup
#
# First, make sure the API server is running:
# ```bash
# set -a && source .env && set +a && uv run uvicorn soldier.api.app:app --host 0.0.0.0 --port 8000
# ```

# %%
import asyncio
import os
from uuid import uuid4

# Load environment variables (for JWT secret)
from dotenv import load_dotenv
load_dotenv()

from soldier.client import SoldierClient

# %% [markdown]
# ## Create a Client
#
# Use `SoldierClient.dev()` for local development - it generates a JWT token automatically.

# %%
# Create a tenant ID (in production, this comes from your auth system)
TENANT_ID = uuid4()
print(f"Tenant ID: {TENANT_ID}")

# Create the client
client = SoldierClient.dev(tenant_id=TENANT_ID)

# %% [markdown]
# ## Helper function for async calls in Jupyter

# %%
def run(coro):
    """Run async coroutine in Jupyter."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

# %% [markdown]
# ## Check API Health

# %%
health = run(client.health())
print(f"API Status: {health.status}")
print(f"Version: {health.version}")

# %% [markdown]
# ## Create an Agent

# %%
agent = run(client.create_agent(
    name="Demo Assistant",
    description="A helpful assistant for testing the Soldier API"
))

print(f"Created agent: {agent.name}")
print(f"Agent ID: {agent.id}")

# %% [markdown]
# ## Add Behavior Rules
#
# Rules define how the agent should behave in different situations.

# %%
# Greeting rule
greeting_rule = run(client.create_rule(
    agent_id=agent.id,
    name="Greeting",
    condition="user greets, says hello, or starts conversation",
    action="respond with a warm, friendly greeting and offer to help",
))
print(f"✓ Created rule: {greeting_rule.name}")

# Help rule
help_rule = run(client.create_rule(
    agent_id=agent.id,
    name="Help Request",
    condition="user asks for help or assistance",
    action="explain your capabilities and ask what specific help they need",
))
print(f"✓ Created rule: {help_rule.name}")

# Farewell rule
farewell_rule = run(client.create_rule(
    agent_id=agent.id,
    name="Farewell",
    condition="user says goodbye or ends conversation",
    action="respond with a friendly farewell and invite them to return",
))
print(f"✓ Created rule: {farewell_rule.name}")

# %% [markdown]
# ## Chat with the Agent
#
# Now let's have a conversation!

# %%
async def chat(message: str, session_id: str = None):
    """Send a message and print the response."""
    print(f"\n👤 You: {message}")

    response = await client.chat(
        agent_id=agent.id,
        message=message,
        session_id=session_id,
    )

    print(f"🤖 Agent: {response.response}")
    print(f"   [Session: {response.session_id[:8]}... | Rules: {response.matched_rules}]")

    return response

# %%
# Start a conversation
response1 = run(chat("Hello!"))

# %%
# Continue the conversation (same session)
response2 = run(chat("What can you help me with?", session_id=response1.session_id))

# %%
# End the conversation
response3 = run(chat("Thanks, goodbye!", session_id=response1.session_id))

# %% [markdown]
# ## Cleanup

# %%
# Close the client when done
run(client.close())
print("✓ Client closed")

# %% [markdown]
# ## Quick Reference
#
# ```python
# # Create client
# client = SoldierClient.dev(tenant_id=uuid4())
#
# # Agents
# agent = await client.create_agent(name="My Agent")
# agents = await client.list_agents()
#
# # Rules
# rule = await client.create_rule(agent.id, name="...", condition="...", action="...")
# rules = await client.list_rules(agent.id)
#
# # Scenarios (conversation flows)
# scenario = await client.create_scenario(agent.id, name="...", steps=[...])
#
# # Chat
# response = await client.chat(agent.id, "Hello!")
#
# # Streaming chat
# async for token in client.chat_stream(agent.id, "Hello!"):
#     print(token, end="")
# ```
