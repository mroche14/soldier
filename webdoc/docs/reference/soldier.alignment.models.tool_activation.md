<a id="focal.alignment.models.tool_activation"></a>

# focal.alignment.models.tool\_activation

ToolActivation model for per-agent tool enablement.

<a id="focal.alignment.models.tool_activation.ToolActivation"></a>

## ToolActivation Objects

```python
class ToolActivation(AgentScopedModel)
```

Per-agent tool enablement status.

Controls which tools are available for a specific agent
and any policy overrides for those tools.

Unique constraint: (tenant_id, agent_id, tool_id)

<a id="focal.alignment.models.tool_activation.ToolActivation.is_enabled"></a>

#### is\_enabled

```python
@property
def is_enabled() -> bool
```

Check if tool is currently enabled.

<a id="focal.alignment.models.tool_activation.ToolActivation.enable"></a>

#### enable

```python
def enable() -> None
```

Enable this tool activation.

<a id="focal.alignment.models.tool_activation.ToolActivation.disable"></a>

#### disable

```python
def disable() -> None
```

Disable this tool activation.

<a id="focal.alignment.models.tool_activation.ToolActivation.create"></a>

#### create

```python
@classmethod
def create(cls,
           tenant_id: UUID,
           agent_id: UUID,
           tool_id: str,
           policy_override: dict[str, Any] | None = None) -> Self
```

Create a new enabled tool activation.

**Arguments**:

- `tenant_id` - Owning tenant
- `agent_id` - Agent this tool is activated for
- `tool_id` - External tool identifier
- `policy_override` - Optional policy overrides
  

**Returns**:

  New ToolActivation instance

