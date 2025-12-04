<a id="soldier.conversation.models.session"></a>

# soldier.conversation.models.session

Session models for conversation domain.

<a id="soldier.conversation.models.session.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="soldier.conversation.models.session.PendingMigration"></a>

## PendingMigration Objects

```python
class PendingMigration(BaseModel)
```

Session marker for pending migration.

<a id="soldier.conversation.models.session.StepVisit"></a>

## StepVisit Objects

```python
class StepVisit(BaseModel)
```

Record of visiting a scenario step.

<a id="soldier.conversation.models.session.Session"></a>

## Session Objects

```python
class Session(BaseModel)
```

Runtime conversation state.

Sessions track the current state of a conversation including
scenario tracking, rule fires, variables, and customer profile link.

