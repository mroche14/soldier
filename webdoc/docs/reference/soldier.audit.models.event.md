<a id="soldier.audit.models.event"></a>

# soldier.audit.models.event

AuditEvent model for audit domain.

<a id="soldier.audit.models.event.utc_now"></a>

#### utc\_now

```python
def utc_now() -> datetime
```

Return current UTC time.

<a id="soldier.audit.models.event.AuditEvent"></a>

## AuditEvent Objects

```python
class AuditEvent(BaseModel)
```

Generic audit event.

A flexible audit event type that can capture various
system events for compliance and debugging.

