<a id="focal.conversation.stores.inmemory"></a>

# focal.conversation.stores.inmemory

In-memory implementation of SessionStore.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore"></a>

## InMemorySessionStore Objects

```python
class InMemorySessionStore(SessionStore)
```

In-memory implementation of SessionStore for testing and development.

Uses simple dict storage with linear scan for queries.
Not suitable for production use.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize empty storage.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.get"></a>

#### get

```python
async def get(session_id: UUID) -> Session | None
```

Get a session by ID.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.save"></a>

#### save

```python
async def save(session: Session) -> UUID
```

Save a session, returning its ID.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.delete"></a>

#### delete

```python
async def delete(session_id: UUID) -> bool
```

Delete a session.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.get_by_channel"></a>

#### get\_by\_channel

```python
async def get_by_channel(tenant_id: UUID, channel: Channel,
                         user_channel_id: str) -> Session | None
```

Get session by channel identity.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.list_by_agent"></a>

#### list\_by\_agent

```python
async def list_by_agent(tenant_id: UUID,
                        agent_id: UUID,
                        *,
                        status: SessionStatus | None = None,
                        limit: int = 100) -> list[Session]
```

List sessions for an agent with optional status filter.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.list_by_customer"></a>

#### list\_by\_customer

```python
async def list_by_customer(tenant_id: UUID,
                           customer_profile_id: UUID,
                           *,
                           limit: int = 100) -> list[Session]
```

List sessions for a customer profile.

<a id="focal.conversation.stores.inmemory.InMemorySessionStore.find_sessions_by_step_hash"></a>

#### find\_sessions\_by\_step\_hash

```python
async def find_sessions_by_step_hash(
        tenant_id: UUID,
        scenario_id: UUID,
        scenario_version: int,
        step_content_hash: str,
        scope_filter: ScopeFilter | None = None) -> list[Session]
```

Find sessions at a step matching the content hash.

