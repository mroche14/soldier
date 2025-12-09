<a id="focal.conversation.models.turn"></a>

# focal.conversation.models.turn

Turn models for conversation domain.

<a id="focal.conversation.models.turn.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="focal.conversation.models.turn.ToolCall"></a>

## ToolCall Objects

```python
class ToolCall(BaseModel)
```

Record of tool execution.

<a id="focal.conversation.models.turn.Turn"></a>

## Turn Objects

```python
class Turn(BaseModel)
```

Single conversation exchange.

Represents one turn in a conversation with full metadata
about processing, matching, and execution.

