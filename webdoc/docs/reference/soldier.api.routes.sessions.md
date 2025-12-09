<a id="focal.api.routes.sessions"></a>

# focal.api.routes.sessions

Session management endpoints.

<a id="focal.api.routes.sessions.get_session"></a>

#### get\_session

```python
@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, tenant_context: TenantContextDep,
                      session_store: SessionStoreDep) -> SessionResponse
```

Get session state.

Retrieve the current state of a session including active scenario,
variables, and turn count.

**Arguments**:

- `session_id` - Session identifier
- `tenant_context` - Authenticated tenant context
- `session_store` - Session store
  

**Returns**:

  SessionResponse with session state
  

**Raises**:

- `SessionNotFoundError` - If session doesn't exist

<a id="focal.api.routes.sessions.delete_session"></a>

#### delete\_session

```python
@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, tenant_context: TenantContextDep,
                         session_store: SessionStoreDep) -> Response
```

End a session.

Terminate a session and clean up resources.

**Arguments**:

- `session_id` - Session identifier
- `tenant_context` - Authenticated tenant context
- `session_store` - Session store
  

**Returns**:

  204 No Content on success
  

**Raises**:

- `SessionNotFoundError` - If session doesn't exist

<a id="focal.api.routes.sessions.get_session_turns"></a>

#### get\_session\_turns

```python
@router.get("/{session_id}/turns", response_model=TurnListResponse)
async def get_session_turns(
    session_id: str,
    tenant_context: TenantContextDep,
    session_store: SessionStoreDep,
    audit_store: AuditStoreDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["asc", "desc"] = Query(default="desc")
) -> TurnListResponse
```

Get session conversation history.

Retrieve paginated turn history for a session.

**Arguments**:

- `session_id` - Session identifier
- `tenant_context` - Authenticated tenant context
- `session_store` - Session store
- `audit_store` - Audit store for turn records
- `limit` - Maximum number of turns to return (1-100)
- `offset` - Number of turns to skip
- `sort` - Sort order (asc=oldest first, desc=newest first)
  

**Returns**:

  TurnListResponse with paginated turns
  

**Raises**:

- `SessionNotFoundError` - If session doesn't exist

