<a id="focal.alignment.models.agent"></a>

# focal.alignment.models.agent

Agent model for conversational AI configuration.

<a id="focal.alignment.models.agent.AgentSettings"></a>

## AgentSettings Objects

```python
class AgentSettings(BaseModel)
```

Embedded settings for an agent's LLM configuration.

Controls the LLM provider and generation parameters for
the agent's responses.

<a id="focal.alignment.models.agent.Agent"></a>

## Agent Objects

```python
class Agent(TenantScopedModel)
```

Top-level container for conversational AI configuration.

An agent represents a complete conversational AI configuration,
including its rules, scenarios, templates, and variables.
All other configuration entities are scoped to an agent.

<a id="focal.alignment.models.agent.Agent.create"></a>

#### create

```python
@classmethod
def create(cls,
           tenant_id: UUID,
           name: str,
           description: str | None = None,
           settings: AgentSettings | None = None) -> Self
```

Create a new agent with defaults.

**Arguments**:

- `tenant_id` - Owning tenant identifier
- `name` - Agent display name
- `description` - Optional description
- `settings` - Optional LLM settings
  

**Returns**:

  New Agent instance

