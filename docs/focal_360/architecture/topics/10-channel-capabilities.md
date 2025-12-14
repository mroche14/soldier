# Channel Capabilities

> **Topic**: Channel-aware behavior for accumulation, formatting, and routing
> **ACF Component**: Channel model with facts vs policies split
> **Dependencies**: LogicalTurn (accumulation), Adaptive Accumulation
> **Impacts**: Message formatting, turn timing, fallback routing, outbound delivery
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification

---

## ACF Context: ChannelPolicy as Single Source of Truth

**Decision §4.3**: ChannelPolicy is the **canonical model** for channel behavior, loaded from ConfigStore into `AgentContext.channel_policies`.

### Key Principle

**Everyone reads from the same ChannelPolicy object**:
- ACF (accumulation behavior, supersede decisions)
- Agent/Pipeline (response timing, formatting decisions)
- ChannelAdapter (capabilities, message splitting)

**No duplicate policy definitions**. ChannelPolicy combines both immutable facts and configurable behaviors.

### ChannelPolicy Model

```python
from enum import Enum
from pydantic import BaseModel

class SupersedeMode(str, Enum):
    """How to handle new messages during turn processing."""
    QUEUE = "queue"      # Queue new messages, finish current turn
    INTERRUPT = "interrupt"  # Cancel current turn, start new one
    IGNORE = "ignore"    # Discard new messages until turn completes

class ChannelPolicy(BaseModel):
    """
    Single source of truth for channel behavior.

    Loaded from ConfigStore into AgentContext.channel_policies.
    Used by: ACF (accumulation), Agent (pipeline), ChannelGateway (formatting).
    """
    channel: str  # "whatsapp", "webchat", "email", "voice"

    # === ACF Accumulation Behavior ===
    aggregation_window_ms: int = 3000
    """How long to wait for message bursts before processing."""

    supersede_default: SupersedeMode = SupersedeMode.QUEUE
    """Default behavior when new message arrives during turn."""

    # === ChannelAdapter Capabilities ===
    supports_typing_indicator: bool = True
    """Whether channel supports typing indicators."""

    supports_read_receipts: bool = True
    """Whether channel supports read receipts."""

    max_message_length: int | None = None
    """Maximum characters per message (None = unlimited)."""

    supports_markdown: bool = True
    """Whether channel renders markdown formatting."""

    supports_rich_media: bool = True
    """Whether channel supports images, buttons, etc."""

    # === Agent/Pipeline Behavior ===
    natural_response_delay_ms: int = 0
    """Delay before sending response (to feel more natural)."""

    # === Rate Limiting ===
    max_messages_per_minute: int = 60
    """Rate limit for outbound messages."""
```

### Ownership and Configuration

| Aspect | Owner | Description |
|--------|-------|-------------|
| ChannelPolicy Model | ACF | Canonical definition in AgentContext |
| Default Values | ConfigStore | Sensible defaults per channel |
| Overrides | Configuration | Tenant/agent-specific customization |
| Runtime Access | AgentContext | Loaded once, used by all components |

---

## Overview

**Channel Capabilities** describe what each communication channel can do. This information serves multiple purposes:

1. **Accumulation timing**: WhatsApp users burst; email is always complete
2. **Response formatting**: SMS has 160 chars; WhatsApp supports markdown
3. **Fallback routing**: If WhatsApp fails, try SMS
4. **Outbound delivery**: Which channels support proactive messaging

### The Problem

Without channel awareness:
```
WhatsApp user sends: "Hello" [wait 200ms] "How are you?"
Agent responds twice (bad UX)

SMS response: "Here's what I found:\n\n## Results\n\n1. **First item**..."
User sees: Garbled markdown (SMS doesn't render it)
```

### The Solution

Channel-aware behavior at every layer:
```
WhatsApp: 1200ms accumulation window, markdown OK, rich media OK
SMS: 800ms window, plain text only, 160 char segments
Email: 0ms window (always complete), full HTML, unlimited length
```

---

## Reference: ChannelPolicy Usage

ChannelPolicy is defined in **AGENT_RUNTIME_SPEC.md § 2.2** and loaded into `AgentContext.channel_policies`.

### How Components Access ChannelPolicy

```python
# In ACF (accumulation)
def get_aggregation_window(agent_ctx: AgentContext, channel: str) -> int:
    """ACF reads aggregation_window_ms from ChannelPolicy."""
    policy = agent_ctx.channel_policies.get(channel)
    return policy.aggregation_window_ms if policy else 3000

# In ChannelAdapter (formatting)
def format_response(
    response: str,
    agent_ctx: AgentContext,
    channel: str,
) -> list[str]:
    """ChannelAdapter reads capabilities from ChannelPolicy."""
    policy = agent_ctx.channel_policies.get(channel)
    if not policy:
        return [response]

    # Strip markdown if not supported
    if not policy.supports_markdown:
        response = strip_markdown(response)

    # Split if exceeds max length
    if policy.max_message_length and len(response) > policy.max_message_length:
        return split_message(response, policy.max_message_length)

    return [response]

# In Agent/Pipeline (response timing)
async def send_response(
    response: str,
    agent_ctx: AgentContext,
    channel: str,
) -> None:
    """Agent uses natural_response_delay_ms from ChannelPolicy."""
    policy = agent_ctx.channel_policies.get(channel)
    if policy and policy.natural_response_delay_ms > 0:
        await asyncio.sleep(policy.natural_response_delay_ms / 1000)

    await channel_gateway.send(response)
```

---

## Default ChannelPolicy Values

These are the default ChannelPolicy configurations stored in ConfigStore:

```python
DEFAULT_CHANNEL_POLICIES: dict[str, ChannelPolicy] = {
    "whatsapp": ChannelPolicy(
        channel="whatsapp",
        aggregation_window_ms=1200,
        supersede_default=SupersedeMode.QUEUE,
        supports_typing_indicator=True,
        supports_read_receipts=True,
        max_message_length=4096,
        supports_markdown=True,
        supports_rich_media=True,
        natural_response_delay_ms=0,
        max_messages_per_minute=60,
    ),

    "sms": ChannelPolicy(
        channel="sms",
        aggregation_window_ms=800,
        supersede_default=SupersedeMode.QUEUE,
        supports_typing_indicator=False,
        supports_read_receipts=False,
        max_message_length=160,
        supports_markdown=False,
        supports_rich_media=False,
        natural_response_delay_ms=0,
        max_messages_per_minute=30,  # Cost control
    ),

    "email": ChannelPolicy(
        channel="email",
        aggregation_window_ms=0,  # Email is always complete
        supersede_default=SupersedeMode.QUEUE,
        supports_typing_indicator=False,
        supports_read_receipts=False,
        max_message_length=None,  # Unlimited
        supports_markdown=True,  # Rendered as HTML
        supports_rich_media=True,
        natural_response_delay_ms=0,
        max_messages_per_minute=10,
    ),

    "webchat": ChannelPolicy(
        channel="webchat",
        aggregation_window_ms=600,
        supersede_default=SupersedeMode.QUEUE,
        supports_typing_indicator=True,
        supports_read_receipts=True,
        max_message_length=10000,
        supports_markdown=True,
        supports_rich_media=True,
        natural_response_delay_ms=500,  # Slight delay for natural feel
        max_messages_per_minute=60,
    ),

    "voice": ChannelPolicy(
        channel="voice",
        aggregation_window_ms=0,  # Speech recognition handles this
        supersede_default=SupersedeMode.INTERRUPT,  # Voice should interrupt
        supports_typing_indicator=False,
        supports_read_receipts=False,
        max_message_length=500,  # TTS limits
        supports_markdown=False,
        supports_rich_media=False,
        natural_response_delay_ms=300,
        max_messages_per_minute=20,
    ),
}
```

---

## Integration Points

### 1. Adaptive Accumulation

```python
class AdaptiveAccumulator:
    def __init__(self, channel_profiles: dict[Channel, ChannelCapability]):
        self._profiles = channel_profiles

    def suggest_wait_ms(
        self,
        message_content: str,
        channel: str,
        **kwargs,
    ) -> int:
        profile = self._profiles.get(Channel(channel))
        if profile is None:
            return 800  # Default

        # Start with channel's default
        base = profile.default_turn_window_ms

        # Email is always complete
        if base == 0:
            return 0

        # Adjust for message shape, user cadence, etc.
        # ... (see 03-adaptive-accumulation.md)

        return base
```

### 2. Response Formatting

```python
class ChannelFormatter:
    """Format responses for specific channels."""

    def __init__(self, capability: ChannelCapability):
        self._cap = capability

    def format(self, response: str) -> list[str]:
        """Format response, possibly splitting into segments."""

        # Strip markdown if not supported
        if not self._cap.supports_markdown:
            response = self._strip_markdown(response)

        # Split if needed
        if len(response) > self._cap.max_message_length:
            if self._cap.supports_message_segmentation:
                return self._split_message(response)
            else:
                return [response[:self._cap.max_message_length]]

        return [response]

    def _strip_markdown(self, text: str) -> str:
        """Convert markdown to plain text."""
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        # Remove links, keep text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        return text

    def _split_message(self, text: str) -> list[str]:
        """Split long message into segments."""
        max_len = self._cap.max_message_length
        segments = []

        while text:
            if len(text) <= max_len:
                segments.append(text)
                break

            # Find good break point
            break_point = self._find_break_point(text, max_len)
            segments.append(text[:break_point].strip())
            text = text[break_point:].strip()

        return segments

    def _find_break_point(self, text: str, max_len: int) -> int:
        """Find natural break point (sentence, paragraph)."""
        # Try paragraph break
        para_break = text.rfind('\n\n', 0, max_len)
        if para_break > max_len * 0.5:
            return para_break

        # Try sentence break
        for punct in ['. ', '! ', '? ']:
            sent_break = text.rfind(punct, 0, max_len)
            if sent_break > max_len * 0.5:
                return sent_break + len(punct)

        # Fall back to word break
        word_break = text.rfind(' ', 0, max_len)
        if word_break > 0:
            return word_break

        return max_len
```

### 3. Outbound Delivery

```python
class OutboundRouter:
    """Route outbound messages to appropriate channels."""

    def __init__(
        self,
        channel_profiles: dict[Channel, ChannelCapability],
        channel_adapters: dict[Channel, ChannelAdapter],
    ):
        self._profiles = channel_profiles
        self._adapters = channel_adapters

    async def send(
        self,
        customer_id: UUID,
        message: str,
        preferred_channel: Channel | None = None,
        context: dict | None = None,
    ) -> SendResult:
        """Send outbound message with fallback."""

        # Determine channel order
        channels = self._get_channel_order(customer_id, preferred_channel)

        for channel in channels:
            profile = self._profiles[channel]

            # Check if outbound is allowed
            if not profile.supports_outbound:
                continue

            # Check opt-in if required
            if profile.outbound_requires_opt_in:
                if not await self._check_opt_in(customer_id, channel):
                    continue

            # Check rate limits
            if not await self._check_rate_limit(customer_id, channel, profile):
                continue

            # Format message for channel
            formatter = ChannelFormatter(profile)
            segments = formatter.format(message)

            # Try to send
            try:
                adapter = self._adapters[channel]
                for segment in segments:
                    await adapter.send(customer_id, segment, context)

                return SendResult(
                    success=True,
                    channel=channel,
                    segments_sent=len(segments),
                )

            except ChannelError as e:
                logger.warning(
                    "channel_send_failed",
                    channel=channel.value,
                    error=str(e),
                )

                # Try fallback
                if profile.fallback_channel:
                    await asyncio.sleep(profile.fallback_delay_seconds)
                    continue

        return SendResult(success=False, error="All channels failed")

    def _get_channel_order(
        self,
        customer_id: UUID,
        preferred: Channel | None,
    ) -> list[Channel]:
        """Get ordered list of channels to try."""
        if preferred:
            channels = [preferred]
            profile = self._profiles.get(preferred)
            if profile and profile.fallback_channel:
                channels.append(profile.fallback_channel)
            return channels

        # Default order based on customer preferences
        # (would load from customer profile)
        return [Channel.WHATSAPP, Channel.SMS, Channel.EMAIL]
```

### 4. P1.6 Context Loading

```python
async def _load_channel_capability(
    self,
    turn_context: TurnContext,
) -> ChannelCapability:
    """Load channel capability in P1.6."""

    channel = Channel(turn_context.channel)

    # Start with default profile
    capability = CHANNEL_PROFILES.get(channel)
    if capability is None:
        capability = ChannelCapability(channel=channel)

    # Apply tenant overrides (if any)
    tenant_overrides = await self._config_store.get_channel_overrides(
        turn_context.tenant_id,
        channel,
    )
    if tenant_overrides:
        capability = self._merge_capability(capability, tenant_overrides)

    turn_context.channel_capability = capability
    return capability
```

---

## Customer Identity Across Channels

```python
class ChannelIdentity(BaseModel):
    """Customer identity on a specific channel."""

    customer_id: UUID
    channel: Channel
    channel_user_id: str  # WhatsApp phone, email address, etc.

    verified: bool = False
    verified_at: datetime | None = None

    opt_in_outbound: bool = False
    opt_in_at: datetime | None = None

    last_interaction: datetime | None = None

class CustomerIdentityStore(ABC):
    """Manage customer identities across channels."""

    @abstractmethod
    async def link_identity(
        self,
        customer_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> ChannelIdentity: ...

    @abstractmethod
    async def get_identities(
        self,
        customer_id: UUID,
    ) -> list[ChannelIdentity]: ...

    @abstractmethod
    async def find_customer_by_channel(
        self,
        channel: Channel,
        channel_user_id: str,
    ) -> UUID | None: ...

    @abstractmethod
    async def set_opt_in(
        self,
        customer_id: UUID,
        channel: Channel,
        opt_in: bool,
    ) -> None: ...
```

---

## Configuration

```toml
[channels]
# Default channel for outbound if no preference
default_outbound = "whatsapp"

# Enable/disable channels globally
[channels.enabled]
whatsapp = true
sms = true
email = true
web = true
voice = false
telegram = false

# Per-channel overrides
[channels.whatsapp]
default_turn_window_ms = 1200
max_messages_per_minute = 60

[channels.sms]
default_turn_window_ms = 800
max_messages_per_day = 100

[channels.email]
supports_outbound = true
```

---

## Observability

### Metrics

```python
# Channel usage
channel_messages_received = Counter(
    "channel_messages_received_total",
    "Messages received by channel",
    ["channel"],
)

channel_messages_sent = Counter(
    "channel_messages_sent_total",
    "Messages sent by channel",
    ["channel", "status"],
)

# Fallback tracking
channel_fallback_count = Counter(
    "channel_fallback_total",
    "Fallback from one channel to another",
    ["from_channel", "to_channel"],
)

# Formatting
message_segments_count = Histogram(
    "message_segments_count",
    "Number of segments per message",
    ["channel"],
    buckets=[1, 2, 3, 5, 10],
)
```

### Logging

```python
logger.info(
    "outbound_sent",
    customer_id=str(customer_id),
    channel=channel.value,
    segments=len(segments),
    fallback_used=fallback_used,
)
```

---

## Testing

```python
# Test: SMS strips markdown
def test_sms_strips_markdown():
    cap = CHANNEL_PROFILES[Channel.SMS]
    formatter = ChannelFormatter(cap)

    result = formatter.format("**Bold** and *italic*")

    assert result == ["Bold and italic"]

# Test: Long message splits correctly
def test_long_message_splits():
    cap = ChannelCapability(
        channel=Channel.SMS,
        max_message_length=160,
        supports_message_segmentation=True,
    )
    formatter = ChannelFormatter(cap)

    long_message = "Hello. " * 50  # ~350 chars

    segments = formatter.format(long_message)

    assert len(segments) > 1
    assert all(len(s) <= 160 for s in segments)

# Test: WhatsApp has longer accumulation window
def test_whatsapp_longer_window():
    accumulator = AdaptiveAccumulator(CHANNEL_PROFILES)

    whatsapp_wait = accumulator.suggest_wait_ms("Hello", "whatsapp")
    web_wait = accumulator.suggest_wait_ms("Hello", "web")

    assert whatsapp_wait > web_wait
```

---

## Tenant/Agent Overrides

Tenants and agents can override default ChannelPolicy values in ConfigStore:

### ConfigStore Schema

```python
class ChannelPolicyOverride(BaseModel):
    """Tenant or agent-specific override for a channel policy."""
    tenant_id: UUID
    agent_id: UUID | None = None  # None = tenant-wide override
    channel: str

    # Override any field from ChannelPolicy
    aggregation_window_ms: int | None = None
    supersede_default: SupersedeMode | None = None
    supports_typing_indicator: bool | None = None
    max_message_length: int | None = None
    # ... etc

class ConfigStore(Protocol):
    """ConfigStore provides ChannelPolicy loading."""

    async def get_channel_policies(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> list[ChannelPolicy]:
        """
        Load channel policies for an agent.

        Resolution order:
        1. Start with DEFAULT_CHANNEL_POLICIES
        2. Apply tenant-wide overrides
        3. Apply agent-specific overrides

        Returns: List of ChannelPolicy (one per channel)
        """
        ...
```

### Example Configuration

```toml
# Tenant-wide override (applies to all agents)
[[tenants.overrides.channel_policies]]
channel = "whatsapp"
aggregation_window_ms = 2000  # Longer than default 1200ms

# Agent-specific override
[[agents.channel_policies]]
agent_id = "a1b2c3d4-..."
channel = "webchat"
natural_response_delay_ms = 1000  # Slower for this agent
supports_typing_indicator = false  # Disable typing indicator
```

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [03-adaptive-accumulation.md](03-adaptive-accumulation.md) - Uses channel timing (ACF component)
- [07-turn-gateway.md](07-turn-gateway.md) - Ingress channel handling (ACF component)
- [09-agenda-goals.md](09-agenda-goals.md) - Outbound channel selection (CognitivePipeline)
