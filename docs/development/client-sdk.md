# Focal Client SDK

**Version**: 1.0
**Last Updated**: 2025-12-15

## Overview

The Focal Client SDK provides a Python interface for interacting with the Focal API. It offers an async-first design with type-safe request/response models and built-in authentication support.

**Key Features**:
- Async/await interface for all operations
- Type-safe Pydantic models
- JWT authentication with dev mode for local testing
- Comprehensive CRUD operations for agents, rules, scenarios, templates, and variables
- Synchronous and streaming chat interfaces
- Context manager support for automatic resource cleanup

## Installation

The client is included in the Ruche package:

```python
from ruche.client import FocalClient
```

**Dependencies**:
- `httpx` - Async HTTP client
- `pydantic` - Type validation
- `python-jose` - JWT token generation (dev mode)

## Quick Start

### Basic Usage (Production)

```python
import asyncio
from ruche.client import FocalClient

async def main():
    # Create client with JWT token
    async with FocalClient(
        base_url="https://api.focal.example.com",
        tenant_id="your-tenant-id",
        token="your-jwt-token"
    ) as client:
        # Create an agent
        agent = await client.create_agent(
            name="Customer Support Bot",
            description="Handles customer inquiries"
        )

        # Chat with the agent
        response = await client.chat(
            agent_id=agent.id,
            message="Hello!",
            user_id="user-123"
        )

        print(f"Agent: {response.response}")

asyncio.run(main())
```

### Dev Mode (Local Testing)

For local development, use the `dev()` class method to automatically generate JWT tokens:

```python
import asyncio
from uuid import uuid4
from ruche.client import FocalClient

async def main():
    # Create client in dev mode (generates JWT automatically)
    async with FocalClient.dev(
        tenant_id=uuid4(),
        base_url="http://localhost:8000"
    ) as client:
        # Health check
        health = await client.health()
        print(f"API Status: {health.status}")

        # Create and use an agent
        agent = await client.create_agent(name="Test Agent")
        response = await client.chat(agent.id, "Hello!")
        print(f"Agent: {response.response}")

asyncio.run(main())
```

**Dev Mode Requirements**:
- Set the `RUCHE_JWT_SECRET` environment variable
- The secret must match the API server's JWT secret
- Only use for local testing - never in production

## Authentication

### Production Authentication

In production, obtain a JWT token from your authentication system and pass it to the client:

```python
client = FocalClient(
    base_url="https://api.focal.example.com",
    tenant_id="your-tenant-id",
    token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
)
```

**JWT Claims Required**:
- `tenant_id` - Tenant isolation
- `sub` - User identifier
- `roles` - User roles (e.g., admin, user)
- `tier` - Subscription tier (e.g., enterprise, pro)

### Dev Mode Authentication

For local testing, use the `dev()` class method:

```python
from uuid import uuid4

# Reads RUCHE_JWT_SECRET from environment
client = FocalClient.dev(
    tenant_id=uuid4(),
    base_url="http://localhost:8000"
)

# Or provide secret explicitly
client = FocalClient.dev(
    tenant_id=uuid4(),
    secret="your-dev-secret"
)
```

## API Methods

### Health Check

```python
health = await client.health()
print(f"Status: {health.status}")
print(f"Version: {health.version}")
```

**Returns**: `HealthResponse`

### Agents

#### List Agents

```python
agents = await client.list_agents()
for agent in agents:
    print(f"{agent.name}: {agent.id}")
```

**Returns**: `list[AgentResponse]`

#### Get Agent

```python
agent = await client.get_agent(agent_id="agent-id-here")
print(f"Agent: {agent.name}")
```

**Returns**: `AgentResponse`

#### Create Agent

```python
agent = await client.create_agent(
    name="Support Bot",
    description="Handles customer support inquiries"
)
```

**Parameters**:
- `name` (str) - Agent name (required)
- `description` (str | None) - Agent description (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `AgentResponse`

#### Update Agent

```python
updated = await client.update_agent(
    agent_id=agent.id,
    name="Updated Name",
    description="New description",
    enabled=True
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to update (required)
- `name` (str | None) - New name (optional)
- `description` (str | None) - New description (optional)
- `enabled` (bool | None) - Enable/disable agent (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `AgentResponse`

#### Delete Agent

```python
await client.delete_agent(agent_id=agent.id)
```

**Returns**: None

### Rules

Rules define the agent's behavior patterns and constraints.

#### List Rules

```python
rules = await client.list_rules(agent_id=agent.id)
for rule in rules:
    print(f"{rule.name}: {rule.condition_text}")
```

**Returns**: `list[RuleResponse]`

#### Get Rule

```python
rule = await client.get_rule(
    agent_id=agent.id,
    rule_id="rule-id-here"
)
```

**Returns**: `RuleResponse`

#### Create Rule

```python
rule = await client.create_rule(
    agent_id=agent.id,
    name="Greeting Rule",
    condition="user says hello or greets",
    action="respond with a warm greeting",
    priority=100,
    enabled=True,
    is_hard_constraint=False
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to attach rule to (required)
- `name` (str) - Rule name (required)
- `condition` (str) - When the rule applies (required)
- `action` (str) - What the agent should do (required)
- `priority` (int) - Rule priority (default: 0)
- `enabled` (bool) - Whether rule is active (default: True)
- `is_hard_constraint` (bool) - Whether rule is enforceable (default: False)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `RuleResponse`

#### Update Rule

```python
updated = await client.update_rule(
    agent_id=agent.id,
    rule_id=rule.id,
    name="Updated Name",
    priority=200,
    enabled=False
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent ID (required)
- `rule_id` (str | UUID) - Rule to update (required)
- `name` (str | None) - New name (optional)
- `condition` (str | None) - New condition (optional)
- `action` (str | None) - New action (optional)
- `priority` (int | None) - New priority (optional)
- `enabled` (bool | None) - Enable/disable (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `RuleResponse`

#### Delete Rule

```python
await client.delete_rule(
    agent_id=agent.id,
    rule_id=rule.id
)
```

**Returns**: None

### Scenarios

Scenarios define structured conversation flows with multiple steps.

#### List Scenarios

```python
scenarios = await client.list_scenarios(agent_id=agent.id)
for scenario in scenarios:
    print(f"{scenario.name}: {len(scenario.steps)} steps")
```

**Returns**: `list[ScenarioResponse]`

#### Get Scenario

```python
scenario = await client.get_scenario(
    agent_id=agent.id,
    scenario_id="scenario-id-here"
)
```

**Returns**: `ScenarioResponse`

#### Create Scenario

```python
scenario = await client.create_scenario(
    agent_id=agent.id,
    name="Onboarding Flow",
    description="Guides new users through setup",
    entry_condition="user is new and requests onboarding",
    steps=[
        {
            "step_id": "welcome",
            "prompt": "Welcome! Let's get you set up.",
            "next_step_id": "collect_name"
        },
        {
            "step_id": "collect_name",
            "prompt": "What's your name?",
            "next_step_id": "confirm"
        }
    ]
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to attach scenario to (required)
- `name` (str) - Scenario name (required)
- `description` (str | None) - Scenario description (optional)
- `entry_condition` (str | None) - When to enter this scenario (optional)
- `steps` (list[dict] | None) - Scenario steps (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `ScenarioResponse`

#### Delete Scenario

```python
await client.delete_scenario(
    agent_id=agent.id,
    scenario_id=scenario.id
)
```

**Returns**: None

### Templates

Templates are reusable text patterns for agent responses.

#### List Templates

```python
templates = await client.list_templates(agent_id=agent.id)
for template in templates:
    print(f"{template.name}: {template.text[:50]}...")
```

**Returns**: `list[TemplateResponse]`

#### Create Template

```python
template = await client.create_template(
    agent_id=agent.id,
    name="greeting_template",
    text="Hello {user_name}! How can I help you today?"
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to attach template to (required)
- `name` (str) - Template name (required)
- `text` (str) - Template text with optional variables (required)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `TemplateResponse`

### Variables

Variables define extractable data fields from conversations.

#### List Variables

```python
variables = await client.list_variables(agent_id=agent.id)
for variable in variables:
    print(f"{variable.name}: {variable.description}")
```

**Returns**: `list[VariableResponse]`

#### Create Variable

```python
variable = await client.create_variable(
    agent_id=agent.id,
    name="user_email",
    description="User's email address"
)
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to attach variable to (required)
- `name` (str) - Variable name (required)
- `description` (str | None) - Variable description (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `VariableResponse`

### Chat

#### Synchronous Chat

Send a message and receive a complete response:

```python
response = await client.chat(
    agent_id=agent.id,
    message="What's the weather like?",
    channel="api",
    user_id="user-123",
    session_id="optional-session-id",
    metadata={"source": "web"}
)

print(f"Agent: {response.response}")
print(f"Session: {response.session_id}")
print(f"Matched rules: {response.matched_rules}")
```

**Parameters**:
- `agent_id` (str | UUID) - Agent to chat with (required)
- `message` (str) - User message (required)
- `channel` (str) - Channel identifier (default: "api")
- `user_id` (str) - User identifier (default: "anonymous")
- `session_id` (str | None) - Continue existing session (optional)
- `metadata` (dict[str, Any] | None) - Additional context (optional)
- `tenant_id` (str | UUID | None) - Override default tenant (optional)

**Returns**: `ChatResponse` with:
- `response` (str) - Agent's reply
- `session_id` (str) - Session identifier for continuation
- `matched_rules` (list[str]) - Rules that fired during processing

#### Streaming Chat

Stream response tokens as they are generated:

```python
async for token in client.chat_stream(
    agent_id=agent.id,
    message="Tell me a story",
    channel="api",
    user_id="user-123"
):
    print(token, end="", flush=True)

print()  # Newline after stream completes
```

**Parameters**: Same as synchronous chat

**Yields**: `str` - Response tokens as they arrive

**Error Handling**: Raises `FocalClientError` if stream encounters errors

## Error Handling

The client raises `FocalClientError` for all API errors:

```python
from ruche.client import FocalClientError

try:
    agent = await client.get_agent("nonexistent-id")
except FocalClientError as e:
    print(f"Error: {e.message}")
    print(f"Status: {e.status_code}")
    print(f"Details: {e.details}")
```

**FocalClientError attributes**:
- `message` (str) - Human-readable error message
- `status_code` (int | None) - HTTP status code (if applicable)
- `details` (Any) - Additional error details from API

**Common HTTP Status Codes**:
- 400 - Validation error (invalid request data)
- 401 - Authentication error (invalid/missing token)
- 403 - Permission denied
- 404 - Resource not found
- 409 - Conflict (duplicate resource)
- 429 - Rate limit exceeded
- 500 - Internal server error

## Usage Patterns

### Context Manager Pattern (Recommended)

Use async context managers for automatic resource cleanup:

```python
async with FocalClient.dev(tenant_id=tenant_id) as client:
    agent = await client.create_agent(name="Bot")
    # Client is automatically closed when exiting context
```

### Manual Resource Management

If not using a context manager, close the client explicitly:

```python
client = FocalClient.dev(tenant_id=tenant_id)
try:
    agent = await client.create_agent(name="Bot")
finally:
    await client.close()
```

### Session Continuation

Maintain conversation state across multiple messages:

```python
# First message creates a session
response1 = await client.chat(
    agent_id=agent.id,
    message="Hello!",
    user_id="user-123"
)

# Subsequent messages continue the session
response2 = await client.chat(
    agent_id=agent.id,
    message="What's the weather?",
    user_id="user-123",
    session_id=response1.session_id  # Continue conversation
)
```

### Multi-Tenant Usage

Handle multiple tenants with a single client instance:

```python
client = FocalClient(token="your-token")

# Create agents for different tenants
agent1 = await client.create_agent(
    name="Bot A",
    tenant_id="tenant-1"
)

agent2 = await client.create_agent(
    name="Bot B",
    tenant_id="tenant-2"
)
```

### Bulk Operations

Process multiple operations efficiently:

```python
# Create multiple rules for an agent
rule_configs = [
    ("Greeting", "user says hello", "greet warmly"),
    ("Help", "user asks for help", "offer assistance"),
    ("Farewell", "user says goodbye", "say goodbye")
]

rules = []
for name, condition, action in rule_configs:
    rule = await client.create_rule(
        agent_id=agent.id,
        name=name,
        condition=condition,
        action=action
    )
    rules.append(rule)

print(f"Created {len(rules)} rules")
```

## Complete Example

```python
import asyncio
from uuid import uuid4
from ruche.client import FocalClient

async def create_and_test_agent():
    """Create an agent, configure it, and test chat."""

    # Create client in dev mode
    async with FocalClient.dev(tenant_id=uuid4()) as client:
        # Check API health
        health = await client.health()
        print(f"API Status: {health.status}\n")

        # Create agent
        agent = await client.create_agent(
            name="Customer Support Bot",
            description="Handles basic customer inquiries"
        )
        print(f"Created agent: {agent.name} ({agent.id})\n")

        # Add behavior rules
        greeting_rule = await client.create_rule(
            agent_id=agent.id,
            name="Greeting",
            condition="user greets or says hello",
            action="respond with a warm, professional greeting",
            priority=100
        )

        help_rule = await client.create_rule(
            agent_id=agent.id,
            name="Help Request",
            condition="user asks for help or assistance",
            action="explain available services and ask how to help",
            priority=90
        )

        print(f"Added {len(await client.list_rules(agent.id))} rules\n")

        # Test conversation
        print("Starting conversation:")

        response1 = await client.chat(
            agent_id=agent.id,
            message="Hello!",
            user_id="demo-user"
        )
        print(f"User: Hello!")
        print(f"Bot: {response1.response}")
        print(f"Rules matched: {response1.matched_rules}\n")

        response2 = await client.chat(
            agent_id=agent.id,
            message="I need help",
            user_id="demo-user",
            session_id=response1.session_id
        )
        print(f"User: I need help")
        print(f"Bot: {response2.response}")
        print(f"Rules matched: {response2.matched_rules}\n")

        # Test streaming
        print("User: Tell me more (streaming)")
        print("Bot: ", end="")
        async for token in client.chat_stream(
            agent_id=agent.id,
            message="Tell me more",
            user_id="demo-user",
            session_id=response2.session_id
        ):
            print(token, end="", flush=True)
        print("\n")

        # Cleanup
        await client.delete_agent(agent.id)
        print("Agent deleted")

if __name__ == "__main__":
    asyncio.run(create_and_test_agent())
```

## Configuration

### Client Initialization Options

```python
client = FocalClient(
    base_url="http://localhost:8000",  # API server URL
    tenant_id="your-tenant-id",        # Default tenant for requests
    token="jwt-token",                 # Authentication token
    timeout=30.0                       # Request timeout in seconds
)
```

### Environment Variables

The client respects these environment variables:

- `RUCHE_JWT_SECRET` - JWT secret for dev mode token generation

## Testing

### Unit Testing with Mock Client

```python
from unittest.mock import AsyncMock
from ruche.client import FocalClient

async def test_create_agent():
    client = FocalClient.dev(tenant_id="test-tenant")
    client._client.request = AsyncMock(return_value=AsyncMock(
        status_code=200,
        json=lambda: {
            "id": "agent-id",
            "name": "Test Agent",
            "tenant_id": "test-tenant"
        }
    ))

    agent = await client.create_agent(name="Test Agent")
    assert agent.name == "Test Agent"
```

### Integration Testing

```python
import pytest
from uuid import uuid4
from ruche.client import FocalClient

@pytest.mark.asyncio
async def test_agent_lifecycle():
    """Test creating, using, and deleting an agent."""
    async with FocalClient.dev(tenant_id=uuid4()) as client:
        # Create
        agent = await client.create_agent(name="Test Agent")
        assert agent.id is not None

        # Use
        response = await client.chat(agent.id, "Hello")
        assert response.response is not None

        # Delete
        await client.delete_agent(agent.id)

        # Verify deleted
        with pytest.raises(FocalClientError) as exc:
            await client.get_agent(agent.id)
        assert exc.value.status_code == 404
```

## Troubleshooting

### Common Issues

**Authentication Errors (401)**:
```python
# Problem: Missing or invalid JWT token
client = FocalClient()  # No token provided

# Solution: Provide valid token or use dev mode
client = FocalClient.dev(tenant_id=tenant_id)
```

**Tenant ID Missing**:
```python
# Problem: Chat requires tenant_id but none provided
response = await client.chat(agent_id, "Hello")

# Solution: Set tenant_id on client or per-request
client = FocalClient.dev(tenant_id=tenant_id)
# OR
response = await client.chat(agent_id, "Hello", tenant_id=tenant_id)
```

**Connection Errors**:
```python
# Problem: Can't connect to API server
# Solution: Verify server is running and URL is correct
health = await client.health()  # Will raise connection error if unreachable
```

**Timeout Errors**:
```python
# Problem: Request takes too long
# Solution: Increase timeout
client = FocalClient(timeout=60.0)  # 60 seconds
```

## API Reference Summary

| Resource | List | Get | Create | Update | Delete |
|----------|------|-----|--------|--------|--------|
| Agents | `list_agents()` | `get_agent(id)` | `create_agent(name, ...)` | `update_agent(id, ...)` | `delete_agent(id)` |
| Rules | `list_rules(agent_id)` | `get_rule(agent_id, id)` | `create_rule(agent_id, ...)` | `update_rule(agent_id, id, ...)` | `delete_rule(agent_id, id)` |
| Scenarios | `list_scenarios(agent_id)` | `get_scenario(agent_id, id)` | `create_scenario(agent_id, ...)` | - | `delete_scenario(agent_id, id)` |
| Templates | `list_templates(agent_id)` | - | `create_template(agent_id, ...)` | - | - |
| Variables | `list_variables(agent_id)` | - | `create_variable(agent_id, ...)` | - | - |

**Additional Operations**:
- `health()` - Check API health
- `chat(agent_id, message, ...)` - Send message, get response
- `chat_stream(agent_id, message, ...)` - Stream response tokens

## Version History

- **1.0** (2025-12-15) - Initial documentation of existing client SDK

## See Also

- API Documentation: `docs/design/api-crud.md`
- Authentication: `docs/architecture/api-layer.md`
- Error Handling: `docs/architecture/error-handling.md`
