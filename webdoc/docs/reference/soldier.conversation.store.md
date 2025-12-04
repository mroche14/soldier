<a id="soldier.conversation.store"></a>

# soldier.conversation.store

SessionStore abstract interface.

<a id="soldier.conversation.store.SessionStore"></a>

## SessionStore Objects

```python
class SessionStore(ABC)
```

Abstract interface for session storage.

Manages session state with support for channel-based
lookup and status filtering.

<a id="soldier.conversation.store.SessionStore.get"></a>

#### get

```python
@abstractmethod
async def get(session_id: UUID) -> Session | None
```

Get a session by ID.

<a id="soldier.conversation.store.SessionStore.save"></a>

#### save

```python
@abstractmethod
async def save(session: Session) -> UUID
```

Save a session, returning its ID.

<a id="soldier.conversation.store.SessionStore.delete"></a>

#### delete

```python
@abstractmethod
async def delete(session_id: UUID) -> bool
```

Delete a session.

<a id="soldier.conversation.store.SessionStore.get_by_channel"></a>

#### get\_by\_channel

```python
@abstractmethod
async def get_by_channel(tenant_id: UUID, channel: Channel,
                         user_channel_id: str) -> Session | None
```

Get session by channel identity.

<a id="soldier.conversation.store.SessionStore.list_by_agent"></a>

#### list\_by\_agent

```python
@abstractmethod
async def list_by_agent(tenant_id: UUID,
                        agent_id: UUID,
                        *,
                        status: SessionStatus | None = None,
                        limit: int = 100) -> list[Session]
```

List sessions for an agent with optional status filter.

<a id="soldier.conversation.store.SessionStore.list_by_customer"></a>

#### list\_by\_customer

```python
@abstractmethod
async def list_by_customer(tenant_id: UUID,
                           customer_profile_id: UUID,
                           *,
                           limit: int = 100) -> list[Session]
```

List sessions for a customer profile.

<a id="soldier.conversation.store.SessionStore.find_sessions_by_step_hash"></a>

#### find\_sessions\_by\_step\_hash

```python
@abstractmethod
async def find_sessions_by_step_hash(
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None) -> list[Session]
```

Find sessions at a step matching the content hash.

Used for migration deployment to mark eligible sessions.

**Arguments**:

- `tenant_id` - Tenant identifier
- `scenario_id` - Scenario identifier
- `scenario_version` - Scenario version
- `step_content_hash` - Step content hash to match
- `scope_filter` - Optional filter for eligible sessions
  

**Returns**:

  List of matching sessions

