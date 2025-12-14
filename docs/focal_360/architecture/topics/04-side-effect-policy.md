# Side-Effect Policy

> **Topic**: Classifying tool effects for safe interruption
> **Owner**: Toolbox (Agent Layer)
> **Architecture**: See [ACF_ARCHITECTURE.md](../ACF_ARCHITECTURE.md) for overall architecture
> **Implementation**: See [TOOLBOX_SPEC.md](../TOOLBOX_SPEC.md) for complete Toolbox specification
> **Dependencies**: LogicalTurn model
> **Impacts**: Tool execution, superseding decisions, cancellation safety

---

## Ownership Model (v3.0)

> **IMPORTANT**: Side-effect policy is now owned by **Toolbox** (Agent layer), not ACF.
> ACF only stores side effect records received via FabricEvents.

| Component | Owner | Description |
|-----------|-------|-------------|
| `SideEffectPolicy` enum | Toolbox | Classification of tool effects |
| `ToolDefinition` with policy | ConfigStore | Stored per-tenant |
| Policy checks before execution | Toolbox | Via `get_metadata()` |
| Side effect recording | Toolbox | Creates `SideEffectRecord`, emits FabricEvent |
| Side effect storage | ACF | Receives events, stores in `LogicalTurn.side_effects` |
| Supersede signal | ACF | Provides `has_pending_messages()` |
| Supersede decision | Pipeline | Uses metadata + signal to decide |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     AGENT LAYER (owns side effect semantics)                 │
│                                                                              │
│  CognitivePipeline                                                          │
│       │                                                                      │
│       │ 1. Get metadata: ctx.toolbox.get_metadata(tool_name)                │
│       │ 2. Check supersede if IRREVERSIBLE: await ctx.has_pending_messages()│
│       │ 3. Execute tool: await ctx.toolbox.execute(planned_tool, ctx)       │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Toolbox                                      │    │
│  │  - Knows tool's SideEffectPolicy (from ToolDefinition)              │    │
│  │  - Executes via ToolGateway                                         │    │
│  │  - Creates SideEffectRecord                                         │    │
│  │  - Emits FabricEvent(TOOL_SIDE_EFFECT_COMPLETED)                    │    │
│  └───────────────────────────────┬─────────────────────────────────────┘    │
│                                  │                                          │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
                                   │ FabricEvent
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ACF LAYER (stores events only)                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    TurnManager                                       │    │
│  │  - Receives TOOL_SIDE_EFFECT_* events                               │    │
│  │  - Stores in LogicalTurn.side_effects                               │    │
│  │  - Does NOT interpret policy semantics                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Overview

**SideEffectPolicy** classifies tools by what happens when they execute. This classification enables safe turn superseding—we know when it's safe to cancel and restart vs. when we must complete.

### The Problem

Without classification, we can't safely interrupt:

```
Turn A: Processing...
  P1-P6: ✓ Complete
  P7: Executing "issue_refund" tool...
           ← New message arrives: "Wait, wrong order!"

What should happen?
  - Can we cancel and restart? (DANGEROUS if refund already sent)
  - Must we finish? (BAD UX if user wants to cancel)
```

### The Solution

Classify every tool:

```
issue_refund: IRREVERSIBLE
  → Before P7 executes this tool, check for pending messages
  → If pending messages, Pipeline decides SUPERSEDE/ABSORB/CONTINUE

validate_order: PURE
  → Can supersede anytime, no state changed

update_cart: COMPENSATABLE
  → Can supersede, but must run compensation (restore_cart)
```

---

## Policy Levels

```python
from enum import Enum

class SideEffectPolicy(str, Enum):
    """
    Classification of tool side effects.

    Owned by Toolbox, stored in ToolDefinition.
    Pipeline uses this to decide supersede behavior.
    """

    PURE = "pure"
    """
    Read-only operation. No external state modified.

    Safe to:
    - Cancel at any time
    - Retry without concern
    - Skip during checkpoint reuse

    Examples:
    - get_order_status
    - lookup_customer
    - validate_input
    - search_products
    """

    IDEMPOTENT = "idempotent"
    """
    Can be safely retried with same result.

    Safe to:
    - Retry multiple times
    - Cancel and restart

    Examples:
    - set_preference (same value)
    - update_timestamp
    - increment_view_count (if idempotent by design)
    """

    COMPENSATABLE = "compensatable"
    """
    Modifies state but can be undone via compensation action.

    On supersede:
    - Must run compensation tool
    - Compensation may require confirmation

    Examples:
    - add_to_cart → remove_from_cart
    - reserve_inventory → release_inventory
    - create_draft_order → delete_draft_order
    """

    IRREVERSIBLE = "irreversible"
    """
    Point of no return. Cannot be undone.

    Before execution:
    - Pipeline should check has_pending_messages()
    - May require user confirmation
    - Side effect is final

    Examples:
    - issue_refund
    - send_email
    - process_payment
    - submit_order
    - delete_account
    """
```

---

## Tool Definition (ConfigStore)

Every tool declares its policy in `ToolDefinition`:

```python
class ToolDefinition(BaseModel):
    """
    Tool definition stored in ConfigStore.

    Owned by: ConfigStore (per tenant)
    Used by: Toolbox to build ToolMetadata
    """

    id: UUID
    tenant_id: UUID
    name: str
    description: str

    # Execution configuration
    gateway: str  # "composio", "http", "internal"
    gateway_config: dict = Field(default_factory=dict)

    # Side effect classification
    side_effect_policy: SideEffectPolicy = SideEffectPolicy.PURE

    # For COMPENSATABLE tools
    compensation_tool_id: UUID | None = None

    # User confirmation
    requires_confirmation: bool = False
    confirmation_prompt: str | None = None

    # Parameter schema
    parameter_schema: dict = Field(default_factory=dict)
```

### Example Tool Definitions

```python
# PURE: Read-only
ToolDefinition(
    name="get_order_status",
    description="Get current status of an order",
    gateway="http",
    gateway_config={"url": "https://api.example.com/orders/{order_id}/status"},
    side_effect_policy=SideEffectPolicy.PURE,
)

# IDEMPOTENT: Safe to retry
ToolDefinition(
    name="set_notification_preference",
    description="Set user notification preferences",
    gateway="http",
    side_effect_policy=SideEffectPolicy.IDEMPOTENT,
)

# COMPENSATABLE: Can undo
ToolDefinition(
    name="add_to_cart",
    description="Add item to shopping cart",
    gateway="http",
    side_effect_policy=SideEffectPolicy.COMPENSATABLE,
    compensation_tool_id=remove_from_cart_tool_id,
)

# IRREVERSIBLE: Point of no return
ToolDefinition(
    name="issue_refund",
    description="Issue a refund to customer",
    gateway="composio",
    gateway_config={"composio_action": "stripe_refund"},
    side_effect_policy=SideEffectPolicy.IRREVERSIBLE,
    requires_confirmation=True,
    confirmation_prompt="Are you sure you want to refund ${amount} for order {order_id}?",
)
```

---

## Toolbox: get_metadata()

Pipeline uses `Toolbox.get_metadata()` to check policy before execution:

```python
class Toolbox:
    def get_metadata(self, tool_name: str) -> ToolMetadata | None:
        """
        Get metadata for supersede/confirmation decisions.

        Called by Pipeline before execution to determine:
        - Should I check has_pending_messages()?
        - Does this require confirmation?
        """
        resolved = self._tools.get(tool_name)
        if not resolved:
            return None

        defn = resolved.definition
        activation = resolved.activation

        # Apply activation overrides
        requires_confirmation = defn.requires_confirmation
        if activation and "requires_confirmation" in activation.policy_overrides:
            requires_confirmation = activation.policy_overrides["requires_confirmation"]

        return ToolMetadata(
            name=defn.name,
            side_effect_policy=defn.side_effect_policy,
            requires_confirmation=requires_confirmation,
            compensation_tool=defn.compensation_tool_id,
        )


class ToolMetadata(BaseModel):
    """
    Tool metadata for Pipeline decisions.

    Does NOT include execution details (those stay in ToolDefinition).
    """

    name: str
    side_effect_policy: SideEffectPolicy
    requires_confirmation: bool = False
    compensation_tool: UUID | None = None

    @property
    def is_irreversible(self) -> bool:
        return self.side_effect_policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def is_safe_to_retry(self) -> bool:
        return self.side_effect_policy in [
            SideEffectPolicy.PURE,
            SideEffectPolicy.IDEMPOTENT,
        ]
```

---

## SideEffectRecord

When a tool executes, Toolbox creates a `SideEffectRecord`:

```python
class SideEffectRecord(BaseModel):
    """
    Record of an executed side effect.

    Created by: Toolbox (after tool execution)
    Stored by: ACF (via FabricEvent → TurnManager)
    """

    id: UUID = Field(default_factory=uuid4)
    tool_name: str
    policy: SideEffectPolicy
    executed_at: datetime
    args: dict
    result: dict | None = None
    status: str  # "executed", "failed", "compensated"
    idempotency_key: str | None = None

    # For compensation tracking
    compensation_id: UUID | None = None
    compensation_executed: bool = False
    compensation_result: dict | None = None

    @property
    def irreversible(self) -> bool:
        """Check if this effect is irreversible."""
        return self.policy == SideEffectPolicy.IRREVERSIBLE

    @property
    def needs_compensation(self) -> bool:
        """Check if compensation is needed but not yet done."""
        return (
            self.policy == SideEffectPolicy.COMPENSATABLE
            and not self.compensation_executed
        )
```

---

## Pipeline Integration: Supersede Check

Pipeline checks `has_pending_messages()` before IRREVERSIBLE tools:

```python
class FocalCognitivePipeline(CognitivePipeline):
    """Pipeline with supersede-aware tool execution."""

    async def _execute_tools(
        self,
        matched_rules: list[MatchedRule],
        ctx: AgentTurnContext,
    ) -> list[ToolResult]:
        """Execute tools with supersede checking."""
        results = []

        for rule in matched_rules:
            for tool_binding in rule.tool_bindings:
                planned = PlannedToolExecution(
                    tool_name=tool_binding.tool_id,
                    args=self._resolve_args(tool_binding, ctx),
                )

                # Get metadata for supersede decision
                metadata = ctx.toolbox.get_metadata(planned.tool_name)
                if not metadata:
                    continue

                # CHECK SUPERSEDE BEFORE IRREVERSIBLE
                if metadata.is_irreversible:
                    if await ctx.has_pending_messages():
                        # Pipeline decides: SUPERSEDE, ABSORB, QUEUE, or FORCE_COMPLETE
                        decision = await self._decide_supersede_action(ctx, planned)
                        if decision == SupersedeAction.SUPERSEDE:
                            raise SupersededError("New message before irreversible tool")
                        elif decision == SupersedeAction.ABSORB:
                            await self._absorb_pending_messages(ctx)
                        # FORCE_COMPLETE or QUEUE: continue execution

                # Execute tool via Toolbox
                result = await ctx.toolbox.execute(planned, ctx)
                results.append(result)

        return results
```

---

## Event Flow: Toolbox → ACF

When Toolbox executes a tool, it emits a FabricEvent that ACF stores:

```python
# In Toolbox.execute():
effect = SideEffectRecord(
    tool_name=tool.tool_name,
    policy=resolved.definition.side_effect_policy,
    executed_at=datetime.utcnow(),
    args=tool.args,
    result=result.data if result.success else None,
    status="executed" if result.success else "failed",
    idempotency_key=exec_ctx.build_idempotency_key(business_key),
)

# Emit to ACF
await turn_context.emit_event(FabricEvent(
    type=FabricEventType.TOOL_SIDE_EFFECT_COMPLETED,
    turn_id=turn_context.logical_turn.id,
    payload=effect.model_dump(),
))
```

```python
# In ACF EventRouter:
async def handle_side_effect_event(event: FabricEvent) -> None:
    if event.type == FabricEventType.TOOL_SIDE_EFFECT_COMPLETED:
        record = SideEffectRecord(**event.payload)
        await turn_manager.add_side_effect(event.turn_id, record)
```

---

## Integration with LogicalTurn

ACF stores side effects in `LogicalTurn`:

```python
class LogicalTurn(BaseModel):
    # ... other fields ...
    side_effects: list[SideEffectRecord] = Field(default_factory=list)

    def has_irreversible_effects(self) -> bool:
        """Check if any irreversible effects have executed."""
        return any(se.irreversible for se in self.side_effects)

    def get_pending_compensations(self) -> list[SideEffectRecord]:
        """Get effects that need compensation on supersede."""
        return [se for se in self.side_effects if se.needs_compensation]
```

---

## Configuration

```toml
[tools.side_effects]
# Require confirmation for all IRREVERSIBLE tools
require_irreversible_confirmation = true

# Allow superseding during COMPENSATABLE execution
allow_compensatable_supersede = true

# Timeout for compensation execution
compensation_timeout_seconds = 30
```

---

## Observability

### Metrics

```python
# Side effects by policy (Toolbox emits)
side_effect_count = Counter(
    "tool_side_effect_total",
    "Tools executed by policy",
    ["tenant_id", "agent_id", "policy", "tool_name"],
)

# Compensations triggered
compensation_count = Counter(
    "tool_compensation_total",
    "Compensation tools executed",
    ["tenant_id", "tool_name", "compensation_tool"],
)

# Supersede decisions (Pipeline emits)
supersede_decision_count = Counter(
    "pipeline_supersede_decision_total",
    "Supersede decisions by type",
    ["tenant_id", "agent_id", "decision", "trigger"],
)
```

### Logging

```python
logger.info(
    "tool_executed",
    tenant_id=ctx.tenant_id,
    agent_id=ctx.agent_id,
    tool_name=tool.tool_name,
    policy=metadata.side_effect_policy.value,
)

logger.warning(
    "supersede_check_before_irreversible",
    turn_id=turn.id,
    tool_name=tool.tool_name,
    has_pending=True,
    decision=decision.value,
)
```

---

## Testing Considerations

```python
# Test: Pipeline checks supersede before IRREVERSIBLE
async def test_irreversible_checks_supersede(pipeline, mock_toolbox, mock_fabric_ctx):
    mock_toolbox.get_metadata.return_value = ToolMetadata(
        name="issue_refund",
        side_effect_policy=SideEffectPolicy.IRREVERSIBLE,
    )
    mock_fabric_ctx.has_pending_messages.return_value = True

    # Pipeline should check and handle supersede
    with pytest.raises(SupersededError):
        await pipeline._execute_tools([...], mock_turn_ctx)


# Test: PURE tools don't check supersede
async def test_pure_skips_supersede_check(pipeline, mock_toolbox, mock_fabric_ctx):
    mock_toolbox.get_metadata.return_value = ToolMetadata(
        name="get_status",
        side_effect_policy=SideEffectPolicy.PURE,
    )

    await pipeline._execute_tools([...], mock_turn_ctx)

    # has_pending_messages should NOT be called for PURE tools
    mock_fabric_ctx.has_pending_messages.assert_not_called()


# Test: Toolbox emits FabricEvent on execution
async def test_toolbox_emits_side_effect_event(toolbox, mock_turn_ctx):
    await toolbox.execute(planned_tool, mock_turn_ctx)

    mock_turn_ctx.emit_event.assert_called_once()
    event = mock_turn_ctx.emit_event.call_args[0][0]
    assert event.type == FabricEventType.TOOL_SIDE_EFFECT_COMPLETED
```

---

## Related Topics

- [../ACF_ARCHITECTURE.md](../ACF_ARCHITECTURE.md) - Canonical architecture
- [../TOOLBOX_SPEC.md](../TOOLBOX_SPEC.md) - Complete Toolbox specification
- [../ACF_SPEC.md](../ACF_SPEC.md) - ACF mechanics
- [01-logical-turn.md](01-logical-turn.md) - Turn model that stores effects
- [05-checkpoint-reuse.md](05-checkpoint-reuse.md) - Skipping PURE phases
