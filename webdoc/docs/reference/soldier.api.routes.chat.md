<a id="focal.api.routes.chat"></a>

# focal.api.routes.chat

Chat endpoints for message processing.

<a id="focal.api.routes.chat.process_message"></a>

#### process\_message

```python
@router.post("/chat", response_model=ChatResponse)
async def process_message(
    request: ChatRequest,
    _tenant_context: TenantContextDep,
    engine: AlignmentEngineDep,
    session_store: SessionStoreDep,
    _settings: SettingsDep,
    idempotency_key: Annotated[str | None,
                               Header(alias="Idempotency-Key")] = None
) -> ChatResponse
```

Process a user message and return agent response.

Takes a user message and processes it through the alignment engine,
returning the agent's response along with metadata about the turn.

**Arguments**:

- `request` - Chat request with message and context
- `tenant_context` - Authenticated tenant context
- `engine` - Alignment engine for processing
- `session_store` - Session store for session management
- `settings` - Application settings
- `idempotency_key` - Optional key for idempotent requests
  

**Returns**:

  ChatResponse with agent response and metadata
  

**Raises**:

- `AgentNotFoundError` - If agent_id doesn't exist
- `SessionNotFoundError` - If session_id provided but not found

<a id="focal.api.routes.chat.process_message_stream"></a>

#### process\_message\_stream

```python
@router.post("/chat/stream")
async def process_message_stream(
        request: ChatRequest, _tenant_context: TenantContextDep,
        engine: AlignmentEngineDep, session_store: SessionStoreDep,
        _settings: SettingsDep) -> EventSourceResponse
```

Process a user message with streaming response.

Takes a user message and processes it through the alignment engine,
streaming tokens back as Server-Sent Events as they are generated.

**Arguments**:

- `request` - Chat request with message and context
- `tenant_context` - Authenticated tenant context
- `engine` - Alignment engine for processing
- `session_store` - Session store for session management
- `settings` - Application settings
  

**Returns**:

  EventSourceResponse with SSE stream

