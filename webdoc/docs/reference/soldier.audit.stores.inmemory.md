<a id="soldier.audit.stores.inmemory"></a>

# soldier.audit.stores.inmemory

In-memory implementation of AuditStore.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore"></a>

## InMemoryAuditStore Objects

```python
class InMemoryAuditStore(AuditStore)
```

In-memory implementation of AuditStore for testing and development.

Uses simple dict storage with linear scan for queries.
Not suitable for production use.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize empty storage.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.save_turn"></a>

#### save\_turn

```python
async def save_turn(turn: TurnRecord) -> UUID
```

Save a turn record.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.get_turn"></a>

#### get\_turn

```python
async def get_turn(turn_id: UUID) -> TurnRecord | None
```

Get a turn record by ID.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.list_turns_by_session"></a>

#### list\_turns\_by\_session

```python
async def list_turns_by_session(session_id: UUID,
                                *,
                                limit: int = 100,
                                offset: int = 0) -> list[TurnRecord]
```

List turn records for a session in chronological order.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.list_turns_by_tenant"></a>

#### list\_turns\_by\_tenant

```python
async def list_turns_by_tenant(tenant_id: UUID,
                               *,
                               start_time: datetime | None = None,
                               end_time: datetime | None = None,
                               limit: int = 100) -> list[TurnRecord]
```

List turn records for a tenant with optional time filter.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.save_event"></a>

#### save\_event

```python
async def save_event(event: AuditEvent) -> UUID
```

Save an audit event.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.get_event"></a>

#### get\_event

```python
async def get_event(event_id: UUID) -> AuditEvent | None
```

Get an audit event by ID.

<a id="soldier.audit.stores.inmemory.InMemoryAuditStore.list_events_by_session"></a>

#### list\_events\_by\_session

```python
async def list_events_by_session(session_id: UUID,
                                 *,
                                 event_type: str | None = None,
                                 limit: int = 100) -> list[AuditEvent]
```

List audit events for a session.

