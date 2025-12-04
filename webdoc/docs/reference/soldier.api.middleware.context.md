<a id="soldier.api.middleware.context"></a>

# soldier.api.middleware.context

Request context middleware for observability.

<a id="soldier.api.middleware.context.get_request_context"></a>

#### get\_request\_context

```python
def get_request_context() -> RequestContext | None
```

Get the current request context.

**Returns**:

  The RequestContext for the current request, or None if not in a request.

<a id="soldier.api.middleware.context.set_request_context"></a>

#### set\_request\_context

```python
def set_request_context(context: RequestContext) -> None
```

Set the request context for the current request.

**Arguments**:

- `context` - The RequestContext to set

<a id="soldier.api.middleware.context.RequestContextMiddleware"></a>

## RequestContextMiddleware Objects

```python
class RequestContextMiddleware(BaseHTTPMiddleware)
```

Middleware that binds request context for observability.

Creates a RequestContext at the start of each request and makes it
available via context variable for logging and tracing.

<a id="soldier.api.middleware.context.RequestContextMiddleware.dispatch"></a>

#### dispatch

```python
async def dispatch(request: Request,
                   call_next: Callable[[Request], Response]) -> Response
```

Process request and bind context.

<a id="soldier.api.middleware.context.update_request_context"></a>

#### update\_request\_context

```python
def update_request_context(*,
                           tenant_id: str | None = None,
                           agent_id: str | None = None,
                           session_id: str | None = None,
                           turn_id: str | None = None) -> None
```

Update the current request context with additional identifiers.

Called during request processing to add context as it becomes available.

**Arguments**:

- `tenant_id` - Tenant identifier
- `agent_id` - Agent identifier
- `session_id` - Session identifier
- `turn_id` - Turn identifier

