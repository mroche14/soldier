# Adaptive Accumulation

> **Topic**: Intelligent waiting for message completion
> **ACF Component**: Turn aggregation owned by Agent Conversation Fabric
> **Dependencies**: LogicalTurn model, Channel Capabilities
> **Impacts**: User experience, turn boundaries, response timing
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification

---

## ACF Context

Adaptive Accumulation is an **ACF component** that determines when a LogicalTurn is ready for processing. ACF owns the accumulation loop; Brain may provide hints that influence timing.

### ACF Ownership

| Aspect | Owner | Description |
|--------|-------|-------------|
| Accumulation Loop | ACF | Wait for timeout or new messages |
| Base Window Timing | ACF | From Channel Capabilities |
| Message Shape Analysis | ACF | Built-in heuristics |
| Plan Hints | Brain | Brain suggests expected inputs |

### Brain Hints (Previous-Turn Storage Pattern)

**Key insight**: Accumulation hints come from the PREVIOUS turn, not the current brain execution (no circular dependency).

**How it works**:
1. Turn N completes, brain returns `BrainResult.accumulation_hint`
2. ACF stores hint in `session.last_pipeline_result`
3. Turn N+1 accumulation loads `session.last_pipeline_result.accumulation_hint`
4. Uses hint to extend window if brain asked a question
5. First turn has no hint → falls back to channel defaults

```python
class AccumulationHint(BaseModel):
    """Hint from Brain to ACF about expected input."""
    awaiting_required_field: bool = False  # Extend window significantly
    expects_followup: bool = False         # Extend window moderately
    input_complete_confidence: float = 0.0  # May shorten window
    expected_input_type: str | None = None # "order_number", "confirmation", etc.
```

When brain is mid-scenario and has asked the user a question, it signals `awaiting_required_field=True`, and ACF extends the accumulation window on the NEXT turn.

---

## Overview

**Adaptive Accumulation** determines how long to wait before considering a user's input complete. Unlike fixed-window debouncing, it uses multiple signals to make intelligent decisions.

### The Problem

Fixed windows fail in real scenarios:

```
Fixed 200ms window:
  User: "Hello"     [wait 200ms] → Response: "Hi!"
  User: "How are you?"           → Response: "I'm doing well!"
  Result: TWO responses (bad UX)

Fixed 2000ms window:
  User: "Cancel my order #12345"  [wait 2000ms...] → Response
  Result: Unnecessary 2-second delay (bad UX)
```

### The Solution

Adaptive windows based on context:

```
Adaptive:
  User: "Hello"     [greeting detected, wait 800ms]
  User: "How are you?" [absorbed]
                    [timeout] → Response: "Hi! I'm doing well"
  Result: ONE natural response

  User: "Cancel my order #12345" [complete request detected, wait 300ms]
                                 [timeout] → Response: "Order cancelled"
  Result: Fast response to complete request
```

---

## Signal Hierarchy

Signals are evaluated in priority order:

### 1. Explicit Completion Signals (Highest Priority)

```python
EXPLICIT_COMPLETIONS = {
    ".",      # Period often indicates complete thought
    "?",      # Question mark indicates complete question
    "!",      # Exclamation indicates complete statement
    "please", # Politeness marker often ends requests
    "thanks", # Gratitude marker ends interactions
}

def has_explicit_completion(text: str) -> bool:
    text_lower = text.strip().lower()
    return (
        text.endswith((".", "?", "!"))
        or text_lower.endswith(("please", "thanks", "thank you"))
    )
```

### 2. Channel Characteristics

Different channels have different user behaviors:

```python
CHANNEL_DEFAULTS = {
    "whatsapp": 1200,   # Users send in bursts
    "telegram": 1000,   # Similar to WhatsApp
    "sms": 800,         # More deliberate due to cost/friction
    "web": 600,         # Fast typing expected
    "email": 0,         # Always complete (no accumulation)
    "voice": 0,         # Handled by speech recognition
    "slack": 800,       # Chat-style
    "teams": 800,       # Chat-style
}
```

### 3. Message Shape Analysis

```python
def analyze_message_shape(text: str) -> MessageShape:
    """Classify message completeness."""

    text_stripped = text.strip()
    text_lower = text_stripped.lower()

    # Greeting only - likely followed by actual request
    if text_lower in GREETINGS:
        return MessageShape.GREETING_ONLY

    # Fragment indicators
    if text_stripped.endswith(("...", ",", "-", ":")):
        return MessageShape.FRAGMENT

    # Incomplete entity reference
    if re.search(r"(order|ticket|case|id)\s*#?\s*$", text_lower):
        return MessageShape.INCOMPLETE_ENTITY

    # Very short messages often incomplete
    if len(text_stripped.split()) < 3 and not has_explicit_completion(text_stripped):
        return MessageShape.POSSIBLY_INCOMPLETE

    return MessageShape.LIKELY_COMPLETE

GREETINGS = {
    "hi", "hello", "hey", "hiya",
    "good morning", "good afternoon", "good evening",
    "morning", "afternoon", "evening",
}

class MessageShape(str, Enum):
    GREETING_ONLY = "greeting_only"           # +500ms
    FRAGMENT = "fragment"                      # +400ms
    INCOMPLETE_ENTITY = "incomplete_entity"   # +600ms
    POSSIBLY_INCOMPLETE = "possibly_incomplete" # +200ms
    LIKELY_COMPLETE = "likely_complete"        # +0ms
```

### 4. User Typing Cadence (Learned)

```python
@dataclass
class UserCadenceStats:
    """Historical typing statistics for a user."""
    inter_message_p50_ms: int  # Median time between messages
    inter_message_p95_ms: int  # 95th percentile
    sample_count: int          # How many samples

def adapt_to_user_cadence(
    base_wait_ms: int,
    cadence_stats: UserCadenceStats | None,
) -> int:
    """Adjust wait time based on user's historical behavior."""
    if cadence_stats is None or cadence_stats.sample_count < 5:
        return base_wait_ms  # Not enough data

    # Use 75th percentile of user's typical inter-message time
    user_typical = (cadence_stats.inter_message_p50_ms + cadence_stats.inter_message_p95_ms) // 2

    # Blend with base (60% base, 40% user history)
    return int(base_wait_ms * 0.6 + user_typical * 0.4)
```

### 5. Plan Hints (Context-Aware)

```python
def get_plan_hint_adjustment(current_plan: ResponsePlan | None) -> int:
    """
    Adjust wait time based on what we expect from user.

    If the plan indicates we're waiting for specific information,
    extend the window to allow user time to provide it.
    """
    if current_plan is None:
        return 0

    # Plan says we asked a question and await answer
    if current_plan.awaiting_required_field:
        return 1000  # Give user time to respond

    # Plan suggests multi-part response expected
    if current_plan.expects_followup:
        return 500

    return 0
```

---

## Main Algorithm

```python
class AdaptiveAccumulator:
    """
    Determines optimal wait time before processing accumulated messages.
    """

    def __init__(
        self,
        min_wait_ms: int = 200,
        max_wait_ms: int = 3000,
        channel_defaults: dict[str, int] | None = None,
    ):
        self._min_wait_ms = min_wait_ms
        self._max_wait_ms = max_wait_ms
        self._channel_defaults = channel_defaults or CHANNEL_DEFAULTS

    def suggest_wait_ms(
        self,
        message_content: str,
        channel: str,
        user_cadence: UserCadenceStats | None = None,
        current_plan: ResponsePlan | None = None,
        messages_in_turn: int = 1,
    ) -> int:
        """
        Calculate how long to wait for additional messages.

        Args:
            message_content: The latest message text
            channel: Channel identifier (whatsapp, web, etc.)
            user_cadence: Historical typing stats for this user
            current_plan: Current response plan (if mid-scenario)
            messages_in_turn: How many messages already accumulated

        Returns:
            Milliseconds to wait before processing
        """
        # Start with channel default
        base = self._channel_defaults.get(channel, 800)

        # Adjust for message shape
        shape = analyze_message_shape(message_content)
        shape_adjustments = {
            MessageShape.GREETING_ONLY: 500,
            MessageShape.FRAGMENT: 400,
            MessageShape.INCOMPLETE_ENTITY: 600,
            MessageShape.POSSIBLY_INCOMPLETE: 200,
            MessageShape.LIKELY_COMPLETE: 0,
        }
        base += shape_adjustments.get(shape, 0)

        # Explicit completion = shorter wait
        if has_explicit_completion(message_content):
            base = max(self._min_wait_ms, base - 300)

        # Adjust for user's historical cadence
        base = adapt_to_user_cadence(base, user_cadence)

        # Adjust for plan hints
        base += get_plan_hint_adjustment(current_plan)

        # Diminishing returns after multiple messages
        if messages_in_turn > 1:
            # Each additional message reduces wait (user is clearly typing)
            base = int(base * (0.8 ** (messages_in_turn - 1)))

        return self._clamp(base)

    def _clamp(self, value: int) -> int:
        return max(self._min_wait_ms, min(value, self._max_wait_ms))
```

---

## Advanced: AI-Predicted Completion

For highest quality, use a small model to predict completion:

```python
class CompletionPredictor:
    """
    Use lightweight model to predict if user is done typing.
    """

    PROMPT = """Given the conversation context and latest message(s),
    predict if the user has finished their current thought.

    Messages: {messages}

    Is the user likely done typing? Answer YES or NO with confidence 0-100."""

    async def predict_completion(
        self,
        messages: list[str],
        executor: LLMExecutor,
    ) -> tuple[bool, float]:
        """
        Predict if user input is complete.

        Returns:
            (is_complete, confidence)
        """
        response = await executor.generate(
            prompt=self.PROMPT.format(messages="\n".join(messages)),
            model="haiku",  # Fast, cheap model
            max_tokens=20,
        )

        # Parse response
        is_complete = "YES" in response.upper()
        confidence = extract_confidence(response)

        return is_complete, confidence
```

Usage in accumulation loop:

```python
async def accumulate_with_prediction(turn: LogicalTurn):
    while True:
        wait_ms = accumulator.suggest_wait_ms(...)

        # For longer waits, check AI prediction mid-wait
        if wait_ms > 1000:
            await asyncio.sleep(wait_ms / 2 / 1000)

            is_complete, confidence = await predictor.predict_completion(
                turn.messages
            )

            if is_complete and confidence > 0.8:
                turn.completion_reason = "ai_predicted"
                return  # Start processing early
            else:
                # Continue waiting remainder
                await asyncio.sleep(wait_ms / 2 / 1000)
        else:
            await asyncio.sleep(wait_ms / 1000)

        # Check for new message
        if no_new_message:
            turn.completion_reason = "timeout"
            return
```

---

## Configuration

```toml
[brain.accumulation]
enabled = true

# Global bounds
min_wait_ms = 200
max_wait_ms = 3000

# Channel-specific defaults
[brain.accumulation.channels]
whatsapp = 1200
telegram = 1000
sms = 800
web = 600
email = 0
voice = 0

# AI prediction (optional)
[brain.accumulation.prediction]
enabled = false
model = "haiku"
confidence_threshold = 0.8
check_after_ms = 500
```

---

## Observability

### Metrics

```python
# Accumulation window duration
accumulation_duration_ms = Histogram(
    "logical_turn_accumulation_duration_ms",
    "How long turns spent accumulating",
    buckets=[100, 200, 500, 1000, 2000, 3000],
)

# Messages per turn
messages_per_turn = Histogram(
    "logical_turn_message_count",
    "Number of messages accumulated per turn",
    buckets=[1, 2, 3, 4, 5, 10],
)

# Completion reasons
completion_reason_count = Counter(
    "logical_turn_completion_reason_total",
    "How turns were completed",
    ["reason"],  # timeout, ai_predicted, explicit_signal
)
```

### Logging

```python
logger.info(
    "accumulation_complete",
    turn_id=turn.id,
    message_count=len(turn.messages),
    wait_ms=actual_wait_ms,
    suggested_wait_ms=suggested_wait_ms,
    completion_reason=turn.completion_reason,
    channel=channel,
    message_shape=shape.value,
)
```

---

## Testing Considerations

```python
# Test: Greeting extends window
def test_greeting_extends_window():
    acc = AdaptiveAccumulator()
    greeting_wait = acc.suggest_wait_ms("Hello", "web")
    request_wait = acc.suggest_wait_ms("Cancel my order #123", "web")

    assert greeting_wait > request_wait

# Test: Explicit completion reduces wait
def test_explicit_completion_reduces_wait():
    acc = AdaptiveAccumulator()
    incomplete = acc.suggest_wait_ms("I need help with", "web")
    complete = acc.suggest_wait_ms("I need help with my order.", "web")

    assert complete < incomplete

# Test: Channel affects base wait
def test_channel_affects_wait():
    acc = AdaptiveAccumulator()
    whatsapp = acc.suggest_wait_ms("Hello", "whatsapp")
    web = acc.suggest_wait_ms("Hello", "web")

    assert whatsapp > web  # WhatsApp users burst more

# Test: Multiple messages reduce wait
def test_multiple_messages_reduce_wait():
    acc = AdaptiveAccumulator()
    first = acc.suggest_wait_ms("Hello", "web", messages_in_turn=1)
    third = acc.suggest_wait_ms("How are you", "web", messages_in_turn=3)

    assert third < first  # User is clearly typing
```

---

## ACF Accumulation Step

In the LogicalTurnWorkflow, accumulation is a distinct step that loads hints from the previous turn:

```python
@hatchet.step()
async def accumulate(self, ctx: Context) -> dict:
    """
    ACF accumulation step.

    Waits for timeout or new_message events.
    Uses Channel Capabilities for base timing.
    Loads hints from PREVIOUS turn's brain result.
    """
    session_key = ctx.workflow_input()["session_key"]
    channel = ctx.workflow_input()["channel"]
    initial_message = RawMessage(**ctx.workflow_input()["initial_message"])

    # Load hint from previous turn (stored in session)
    session = await self._session_store.get(session_key)
    previous_hint = session.last_pipeline_result.accumulation_hint if session.last_pipeline_result else None

    # Initialize turn
    turn = LogicalTurn(
        session_key=session_key,
        messages=[initial_message.id],
        first_at=initial_message.timestamp,
        last_at=initial_message.timestamp,
    )

    while True:
        wait_ms = self._accumulator.suggest_wait_ms(
            message_content=initial_message.content,
            channel=channel,
            current_plan=previous_hint,  # From PREVIOUS turn
            messages_in_turn=len(turn.messages),
        )

        event = await ctx.wait_for_event(
            timeout_ms=wait_ms,
            event_types=["new_message"],
        )

        if event.timed_out:
            turn.completion_reason = "timeout"
            break

        # New message arrived
        new_message = RawMessage(**event.event_data)

        if turn.can_absorb_message():
            turn.absorb_message(new_message.id, new_message.timestamp)
            # Continue loop with updated message
        else:
            # Queue for next turn
            await self._message_queue.enqueue(session_key, new_message)
            break

    return {"turn": turn.model_dump()}
```

### Hint Storage in Session

```python
# At end of commit_and_respond step:
session.last_pipeline_result = LastBrainResult(
    turn_id=turn.id,
    completed_at=datetime.utcnow(),
    accumulation_hint=result.accumulation_hint,  # Store for next turn
)
await self._session_store.save(session)
```

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [01-logical-turn.md](01-logical-turn.md) - Turn model that accumulates (ACF core)
- [10-channel-capabilities.md](10-channel-capabilities.md) - Channel timing (ACF facts)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Event-based accumulation (ACF runtime)
