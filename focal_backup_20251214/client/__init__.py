"""Focal API client.

Usage:
    from uuid import uuid4
    from focal.client import FocalClient

    # For local development (generates JWT from FOCAL_JWT_SECRET)
    async with FocalClient.dev(tenant_id=uuid4()) as client:
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
    async with FocalClient(token="eyJ...") as client:
        ...

Note: tenant_id must be a valid UUID.
"""

from focal.client.client import FocalClient, FocalClientError

__all__ = ["FocalClient", "FocalClientError"]
