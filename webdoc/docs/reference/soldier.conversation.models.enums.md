<a id="soldier.conversation.models.enums"></a>

# soldier.conversation.models.enums

Enums for conversation domain.

<a id="soldier.conversation.models.enums.Channel"></a>

## Channel Objects

```python
class Channel(str, Enum)
```

Communication channels.

Represents the medium through which the conversation
is taking place.

<a id="soldier.conversation.models.enums.SessionStatus"></a>

## SessionStatus Objects

```python
class SessionStatus(str, Enum)
```

Session lifecycle states.

- ACTIVE: Session is in active use
- IDLE: Session is idle, waiting for input
- PROCESSING: Currently processing a message
- INTERRUPTED: Session was interrupted (e.g., by handoff)
- CLOSED: Session is closed and no longer accepting messages

