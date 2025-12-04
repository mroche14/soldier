<a id="soldier.audit.store"></a>

# soldier.audit.store

AuditStore abstract interface.

<a id="soldier.audit.store.AuditStore"></a>

## AuditStore Objects

```python
class AuditStore(ABC)
```

Abstract interface for audit storage.

Manages turn records and audit events with support
for time-series queries.

<a id="soldier.audit.store.AuditStore.save_turn"></a>

#### save\_turn

```python
@abstractmethod
async def save_turn(turn: TurnRecord) -> UUID
```

Save a turn record.

<a id="soldier.audit.store.AuditStore.get_turn"></a>

#### get\_turn

```python
@abstractmethod
async def get_turn(turn_id: UUID) -> TurnRecord | None
```

Get a turn record by ID.

<a id="soldier.audit.store.AuditStore.list_turns_by_session"></a>

#### list\_turns\_by\_session

```python
@abstractmethod
async def list_turns_by_session(session_id: UUID,
                                *,
                                limit: int = 100,
                                offset: int = 0) -> list[TurnRecord]
```

List turn records for a session in chronological order.

<a id="soldier.audit.store.AuditStore.list_turns_by_tenant"></a>

#### list\_turns\_by\_tenant

```python
@abstractmethod
async def list_turns_by_tenant(tenant_id: UUID,
                               *,
                               start_time: datetime | None = None,
                               end_time: datetime | None = None,
                               limit: int = 100) -> list[TurnRecord]
```

List turn records for a tenant with optional time filter.

<a id="soldier.audit.store.AuditStore.save_event"></a>

#### save\_event

```python
@abstractmethod
async def save_event(event: AuditEvent) -> UUID
```

Save an audit event.

<a id="soldier.audit.store.AuditStore.get_event"></a>

#### get\_event

```python
@abstractmethod
async def get_event(event_id: UUID) -> AuditEvent | None
```

Get an audit event by ID.

<a id="soldier.audit.store.AuditStore.list_events_by_session"></a>

#### list\_events\_by\_session

```python
@abstractmethod
async def list_events_by_session(session_id: UUID,
                                 *,
                                 event_type: str | None = None,
                                 limit: int = 100) -> list[AuditEvent]
```

List audit events for a session.

