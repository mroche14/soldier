# AG-UI Integration Considerations

> **Status**: ANALYSIS / FUTURE PLANNING
> **Date**: 2025-12-11
> **Context**: AG-UI is a potential webchat protocol, NOT an ACF core concern

---

## Important Clarification

This document was moved out of ACF_SPEC.md because **AG-UI does not belong in ACF's core specification**.

**Key principle**: AG-UI is a **channel adapter concern**, not an ACF concern. ACF should be channel-agnostic. AG-UI would be implemented as one possible `WebchatChannelAdapter`, not as ACF infrastructure.

See the deep analysis at the end of this document for the architectural rationale.

---

## What AG-UI Is

AG-UI (Agent-User Interaction Protocol) is a standardized event-based protocol for real-time agent-to-frontend communication.

AG-UI provides:
- **Event-based protocol** between agent backends and frontend apps
- **~16 standard event types** covering lifecycle, streaming, tools, state
- **Transport-agnostic**: SSE, WebSocket, HTTP binary
- **Framework integrations**: LangGraph, CrewAI, Microsoft Agent Framework already speak AG-UI

**Core abstraction**: `run(input: RunAgentInput) → Observable<BaseEvent>`

| Event Category | Event Types |
|---------------|-------------|
| Lifecycle | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` |
| Text streaming | `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` |
| Tool calls | `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END` |
| State sync | `STATE_SNAPSHOT`, `STATE_DELTA`, `MESSAGES_SNAPSHOT` |
| Custom | `RAW`, `CUSTOM` |

---

## Where AG-UI Actually Fits

AG-UI is **just one possible implementation** for a webchat channel adapter:

```
End Users
    │
    ▼
┌─────────────────────────────────────────────────┐
│  Channel Adapters (NOT ACF)                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ │
│  │WhatsApp │ │ Email   │ │ Voice   │ │Webchat│ │
│  │ Adapter │ │ Adapter │ │ Adapter │ │Adapter│ │  ← AG-UI is ONE option here
│  └────┬────┘ └────┬────┘ └────┬────┘ └───┬───┘ │
│       └──────────┬┴──────────┬┴──────────┘     │
└──────────────────┼────────────────────────────-┘
                   ▼
           Agent Conversation Fabric (ACF)
           - Logical turns, mutex, supersede
           - Channel-AGNOSTIC
                   │
                   ▼
           Brain
           - FOCAL 11 phases / Agno / LangGraph
```

**Key insight**: ACF doesn't need to know about AG-UI. Channel adapters handle protocol translation.

---

## Integration Options (Deferred Decision)

### Option A: Defer AG-UI Entirely

- Build webchat with your own simple protocol first
- Keep internal `FabricEvent` model (AG-UI-inspired but independent)
- Add AG-UI adapter later if/when needed

**Best for**: Maximum flexibility, avoiding premature dependency.

### Option B: AG-UI Adapter Only (No CopilotKit)

- Implement AG-UI protocol in webchat adapter
- Don't use CopilotKit runtime
- Build your own React UI

**Best for**: Protocol compatibility without CopilotKit dependency.

### Option C: CopilotKit Headless

- Use CopilotKit's hooks (`useCopilotChat`) for state management
- Build your own UI components
- Still locked into their protocol interpretation

**Best for**: Fast webchat delivery with visual control.

---

## Internal Event Model (Recommended)

Regardless of AG-UI decision, FOCAL should have its own internal event model:

```python
class FabricEventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    CONFIRMATION_REQUESTED = "confirmation_requested"
    CONFIRMATION_RESOLVED = "confirmation_resolved"
    STATUS_UPDATE = "status_update"  # "searching…", "calling bank…"

class FabricEvent(BaseModel):
    type: FabricEventType
    session_id: str
    payload: dict[str, Any]
    timestamp: datetime
```

This model:
- Is AG-UI-**inspired** but not AG-UI-**dependent**
- Lives in ACF (shared across all brains)
- Can be mapped to AG-UI by a webchat adapter if needed
- Can be mapped to plain text by WhatsApp/email adapters

---

## Confirmations as Tools (Critical Pattern)

**Key principle from architecture review**:

> User confirmations are **tools** from the brain's point of view, decided by scenarios—not "magic" in ACF or channel adapters.

```python
# Scenario step defines the tool
steps:
  - id: confirm_refund
    tool_binding:
      tool_id: "confirm_with_user"
      args_template: {"message": "Refund order {{order_id}}?"}

# Brain (P7.4) outputs PlannedToolExecution
planned = PlannedToolExecution(
    tool_name="confirm_with_user",
    args={"message": "Refund order 123?"},
)

# ToolHub decides HOW to execute based on channel
# - Webchat + AG-UI: render dialog via AG-UI tool event
# - WhatsApp: send text "Reply YES or NO to confirm"
```

**Where decisions live**:

| Decision | Who Makes It |
|----------|-------------|
| "We need user confirmation" | Brain (scenario step) |
| "Confirmation is a tool" | ToolHub configuration |
| "How to render on webchat" | WebchatChannelAdapter (maybe AG-UI) |
| "How to render on WhatsApp" | WhatsAppChannelAdapter (text fallback) |
| ACF | **Nothing about confirmations** |

---

## Why AG-UI Was Moved Out of ACF_SPEC

The original ACF_SPEC.md section suggested:
- "ACF maps to AG-UI UI card"
- "ACF translates FabricEvents to AG-UI"

**This was incorrect.** ACF should be channel-agnostic. The corrected architecture:

1. **Brain** decides *what* to do (confirm, ask, inform)
2. **ACF** handles *when* (mutex, supersede, turn boundaries)
3. **ToolHub + ChannelAdapters** handle *how* (AG-UI vs text vs email)

AG-UI is a channel concern, implemented in a specific adapter, not ACF infrastructure.

---

## Strategic Recommendation

**For now**: Design the internal `FabricEvent` model to be AG-UI-compatible but not AG-UI-dependent. Defer the AG-UI decision until webchat is an immediate priority.

**When webchat ships**: Implement AG-UI as a `WebchatChannelAdapter` option, not as ACF core. Keep the option to swap it out.

---

## References

- [AG-UI Protocol](https://docs.ag-ui.com/)
- [CopilotKit](https://github.com/CopilotKit/CopilotKit)
- [Channel Capabilities topic](../architecture/topics/10-channel-capabilities.md)
