<a id="soldier.alignment.execution.variable_resolver"></a>

# soldier.alignment.execution.variable\_resolver

Variable resolution helper.

<a id="soldier.alignment.execution.variable_resolver.VariableResolver"></a>

## VariableResolver Objects

```python
class VariableResolver()
```

Resolve variables in template strings.

Supports standard Python format string syntax: {variable_name}
Unresolved variables are preserved as-is for later resolution.

<a id="soldier.alignment.execution.variable_resolver.VariableResolver.resolve"></a>

#### resolve

```python
def resolve(template: str, variables: dict[str, Any]) -> str
```

Resolve {var} placeholders in a template string.

Unknown variables remain unchanged; double braces are preserved.

**Raises**:

- `TypeError` - If template is not a string

