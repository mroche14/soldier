<a id="soldier.config.models.agent"></a>

# soldier.config.models.agent

Agent-level configuration models.

<a id="soldier.config.models.agent.AgentConfig"></a>

## AgentConfig Objects

```python
class AgentConfig(BaseModel)
```

Per-agent configuration overrides.

Agent configuration allows overriding default settings at the agent level.
These settings take precedence over global configuration when processing
requests for a specific agent.

