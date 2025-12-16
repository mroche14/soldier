# sb_agent_hub Deep Dive: Channels (Webchat/AG‑UI, WebSocket chat, Voice)

## 1) Webchat: CopilotKit + AG‑UI SSE

### 1.1 Current working architecture (docs)

From `sb_agent_hub/docs/COPILOTKIT_FINAL_ARCHITECTURE.md`:

```
CopilotKit Frontend → /api/copilotkit (proxy) → Backend AG‑UI SSE stream
```

Key property:
- CopilotKit can consume AG‑UI SSE directly when configured with a `runtimeUrl`.

### 1.2 Backend AG‑UI implementation (code)

`sb_agent_hub/3-backend/app/api/user/ag_ui_langgraph.py` implements:
- `POST /stream` that returns `text/event-stream`
- Emits AG‑UI-style events:
  - `RUN_STARTED`
  - `TEXT_MESSAGE_START`
  - `TEXT_MESSAGE_CHUNK` (word-by-word streaming)
  - `TOOL_CALL_CHUNK` (tool args)
  - `TEXT_MESSAGE_END`
  - `RUN_FINISHED`

The current “agent” behind this endpoint is a LangGraph workflow compiled in the same file.

### 1.3 Integration mapping to soldier

The key insight from soldier’s own docs:
- `docs/architecture/event-model.md` expects **ACFEvents** inside the runtime
- “AG‑UI mapping is handled by channel adapters”

So, sb_agent_hub can remain the webchat channel gateway and:

1) Accept CopilotKit requests (AG‑UI contract)
2) Translate them into the soldier ingress envelope (`tenant_id`, `agent_id`, `channel="webchat"`, `channel_user_id`, content)
3) Call soldier’s runtime (streaming preferred)
4) Map soldier outputs back into AG‑UI events (RUN_STARTED/…/RUN_FINISHED)

This lets sb_agent_hub keep the frontend + proxy architecture unchanged while swapping the cognitive engine.

## 2) WebSocket chat

`sb_agent_hub/3-backend/app/api/user/websocket.py` provides:
- `WS /agent/{agent_id}/chat` with a custom protocol:
  - client sends `{type:"message", content:"..."}`
  - server streams `{type:"stream_chunk", chunk:"..."}`

It invokes `AgentRuntimeService.execute_agent(..., stream=True)` to generate chunks.

### Integration mapping to soldier

This WebSocket can become another “channel adapter”:
- Instead of invoking LangGraph runtime directly, the WS handler can invoke soldier stream endpoints and forward chunks.

## 3) Voice: VAPI/Twilio webhook ingestion

### 3.1 API surface

`sb_agent_hub/3-backend/app/api/user/voice.py` includes:
- Management endpoints for voice assistants and calls
- `POST /webhooks/vapi` for provider event callbacks

### 3.2 Current webhook handling behavior

`sb_agent_hub/3-backend/app/services/voice_service.py`:
- Persists voice events and transcripts into Supabase tables
- On `event_type == "function-call"`: records a “tool execution” row, but does not execute or route the tool call yet

### Integration mapping to soldier

The “voice provider event” stream can be converted into the soldier ingress envelope in two common ways:

1) **Transcript-driven**: treat each finalized user transcript as an inbound message:
   - `channel="voice"`
   - `channel_user_id` = phone number or call ID
   - `content.text` = transcript
2) **Conversation-state-driven**: treat voice calls as continuous sessions and stream partial transcripts as “message absorption” candidates:
   - this aligns with soldier’s ACF “message ≠ turn” idea

Tool/function calls from VAPI can be handled by:
- soldier toolbox (if soldier runs the brain)
- or sb_agent_hub tool execution, with results returned to the provider via provider APIs

The cleanest boundary is:
- soldier decides *whether* to call a tool (semantics)
- sb_agent_hub executes the tool in the provider ecosystem (Composio/MCP/voice provider function) and returns results

## 4) Key Channel-Layer Responsibilities sb_agent_hub Already Owns

Relative to soldier’s ChannelGateway/MessageRouter specs, sb_agent_hub already has the right home for:
- Authentication / tenant resolution (WorkOS/Supabase)
- AG‑UI/webchat protocol handling
- Voice provider webhooks
- WebSocket transport for real-time UX
- Potentially: identity linking across channels (phone/email/web user) via its DB

So the primary integration work is not “rewrite the frontend”; it’s “connect these channel endpoints to soldier’s runtime contract and map events/streams”.

