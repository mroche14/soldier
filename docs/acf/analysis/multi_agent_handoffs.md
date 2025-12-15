# Multi-Agent Handoffs - Future Planning

> **Status**: DEFERRED / FUTURE PLANNING
> **Date**: 2025-12-12
> **Principle**: Don't block this capability, but don't actively implement it now

---

## Current State

Multi-agent handoffs are **documented but not prioritized**. The basic mechanism exists in our architecture:

- `HandoffRequest` model in `BrainResult`
- `SessionStore.transfer_session()` interface
- ACF's `commit_and_respond` step handles the transfer

See [ACF_ARCHITECTURE.md Section 9](../architecture/ACF_ARCHITECTURE.md#9-multi-agent-handoffs) for the current design.

---

## What's Already Defined

### HandoffRequest Model

```python
class HandoffRequest(BaseModel):
    """Request to transfer session to another agent."""
    target_agent_id: UUID
    context_summary: dict
    reason: str | None = None
```

### Brain Returns Handoff

```python
# Inside Brain.run()
if self._should_handoff(ctx, target_agent_id):
    return BrainResult(
        response_segments=[
            ResponseSegment(text="Transferring you to our specialist...")
        ],
        handoff=HandoffRequest(
            target_agent_id=target_agent_id,
            context_summary=self._summarize_context(ctx),
        ),
    )
```

### ACF Handles Transfer

```python
@hatchet.step()
async def commit_and_respond(self, ctx: Context) -> dict:
    result = BrainResult(**ctx.step_output("run_pipeline")["result"])

    if result.handoff:
        await self._session_store.transfer_session(
            from_session=old_session_key,
            to_agent_id=result.handoff.target_agent_id,
            context_summary=result.handoff.context_summary,
        )
    # ...
```

### Session Transfer

```python
class SessionStore:
    async def transfer_session(
        self,
        from_session: str,
        to_agent_id: UUID,
        context_summary: dict,
    ) -> str:
        """
        Transfer session to new agent.
        - Creates new session_key with new agent_id
        - Copies relevant state
        - Stores context_summary for new agent
        """
        # ...
```

---

## Open Questions (For Future)

These questions are documented but **deferred** until multi-agent handoffs become a priority.

### 1. Context Transfer Richness

**Question**: What should `context_summary` contain?

| Option | Pros | Cons |
|--------|------|------|
| Structured summary only | Small payload, privacy-safe | Agent B lacks full context |
| Full conversation history | Complete context | Large payload, privacy concerns |
| Reference to history | Best of both | Requires Agent B to fetch |

**Current approach**: `dict` - flexible, schema TBD.

### 2. Handoff Failure Handling

**Question**: What happens when handoff fails?

| Failure | Possible Response |
|---------|-------------------|
| Target agent doesn't exist | Return error to user, stay with Agent A |
| Target agent is disabled | Same as above |
| Target agent can't handle channel | Block handoff or suggest channel switch |

**Current approach**: Not defined - happy path only.

### 3. Bi-directional Handoffs

**Question**: Can Agent B hand back to Agent A?

| Scenario | Consideration |
|----------|---------------|
| Simple return | New session_key again, context travels back |
| Ping-pong prevention | May need handoff cooldown or limit |
| "Escalation only" | Configure agents as terminal (no hand-back) |

**Current approach**: Not blocked, but not designed.

### 4. Warm vs Cold Handoff

**Question**: How does the transfer actually happen?

| Style | Description | Use Case |
|-------|-------------|----------|
| **Cold** | Agent A releases, Agent B picks up on next message | Simple, stateless |
| **Warm** | Agent A stays until Agent B confirms ready | Complex, better UX |

**Current approach**: Cold handoff (implicit).

### 5. Same-Turn vs Next-Turn Response

**Question**: When does Agent B first respond?

| Timing | Behavior |
|--------|----------|
| Same turn | Agent A hands off, Agent B immediately generates greeting |
| Next turn | User sends next message, Agent B responds |

**Current approach**: Next turn (simpler).

### 6. Channel Constraints

**Question**: What if agents have different channel availability?

| Agent A | Agent B | Action |
|---------|---------|--------|
| WhatsApp, webchat | webchat only | Block handoff? Suggest channel switch? |
| All channels | Restricted | Validate before handoff |

**Current approach**: Not validated.

---

## Design Principle

**Don't block multi-agent handoffs** - When making architectural decisions, ensure they don't prevent future multi-agent scenarios:

1. **Session keys include agent_id** - Already true, enables agent switching
2. **Context is serializable** - Don't rely on in-memory state that can't transfer
3. **Brain result supports handoff** - Already has `HandoffRequest`
4. **SessionStore is abstract** - Can implement transfer logic without ACF changes

---

## When to Revisit

Revisit this document when:

1. A customer requires agent specialization (e.g., sales → support → billing)
2. Building an "escalation to human" feature (human as special agent)
3. Implementing agent teams or hierarchies
4. Adding supervisor/observer agents

---

## References

- [ACF_ARCHITECTURE.md - Section 9](../architecture/ACF_ARCHITECTURE.md#9-multi-agent-handoffs)
- [AGENT_RUNTIME_SPEC.md - HandoffRequest](../architecture/AGENT_RUNTIME_SPEC.md)
