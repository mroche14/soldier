"""Soldier API client.

Usage:
    from uuid import uuid4
    from soldier.client import SoldierClient

    # For local development (generates JWT from SOLDIER_JWT_SECRET)
    async with SoldierClient.dev(tenant_id=uuid4()) as client:
        agent = await client.create_agent(name="My Agent")
        rule = await client.create_rule(
            agent.id,
            name="Greeting",
            condition="user greets",
            action="respond warmly",
        )
        response = await client.chat(agent.id, "Hello!")
        print(response.response)

    # For production (with JWT token)
    async with SoldierClient(token="eyJ...") as client:
        ...

Note: tenant_id must be a valid UUID.
"""

from soldier.client.client import SoldierClient, SoldierClientError

__all__ = ["SoldierClient", "SoldierClientError"]
