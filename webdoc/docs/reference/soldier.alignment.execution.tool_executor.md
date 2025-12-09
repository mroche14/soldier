<a id="focal.alignment.execution.tool_executor"></a>

# focal.alignment.execution.tool\_executor

Tool execution with timeout handling.

<a id="focal.alignment.execution.tool_executor.ToolExecutor"></a>

## ToolExecutor Objects

```python
class ToolExecutor()
```

Execute tools attached to matched rules.

Supports:
- Parallel execution with configurable concurrency
- Per-tool timeout handling
- Fail-fast mode for critical tool chains
- Result aggregation with success/failure tracking

<a id="focal.alignment.execution.tool_executor.ToolExecutor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(tools: dict[str, ToolCallable],
             timeout_ms: int = 5000,
             max_parallel: int = 5,
             fail_fast: bool = False) -> None
```

Initialize the tool executor.

**Arguments**:

- `tools` - Map of tool_id -> async callable
- `timeout_ms` - Maximum execution time per tool
- `max_parallel` - Maximum concurrent tool executions
- `fail_fast` - Stop on first tool failure

<a id="focal.alignment.execution.tool_executor.ToolExecutor.execute"></a>

#### execute

```python
async def execute(matched_rules: list[MatchedRule],
                  context: Context) -> list[ToolResult]
```

Execute all tools attached to matched rules.

**Arguments**:

- `matched_rules` - Rules with attached tool IDs
- `context` - User message context for tool input
  

**Returns**:

  List of ToolResult for each executed tool

