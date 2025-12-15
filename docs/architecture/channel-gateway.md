# ChannelGateway Interface Specification

> **Status**: PROPOSED
> **Date**: 2025-12-15
> **Scope**: Multi-channel message ingress and egress abstraction
> **Dependencies**: Channel Capabilities (`acf/architecture/topics/10-channel-capabilities.md`), API Layer (`api-layer.md`)
> **Implementation Note**: The ChannelGateway code may live in a separate service/repository. This spec defines the interface contract.

---

## Executive Summary

The **ChannelGateway** is the abstraction layer between external messaging channels (WhatsApp, SMS, Email, Web, Voice) and the Ruche platform. It handles:

1. **Inbound**: Receive messages from channels → normalize → route to Ruche
2. **Outbound**: Receive responses from Ruche → format → deliver to channels
3. **Identity Resolution**: Map channel-specific user IDs to platform interlocutors

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Interface abstraction** | Ruche is channel-agnostic; adapters implement channel-specific logic |
| **External to Ruche core** | Gateway handles rate limits, auth, retries for each provider |
| **Normalized message envelope** | All channels produce the same `InboundMessage` format |
| **ChannelPolicy-driven** | Formatting and routing respect tenant/agent channel configuration |
| **Cross-channel linking by default** | Same phone/email auto-links across channels; tenants can unlink or disable |

---

## 1. Architecture Position

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         External Channels                                │
│   WhatsApp  │   SMS   │   Email   │   Webchat   │   Voice   │   Slack   │
└──────┬──────┴────┬────┴─────┬─────┴──────┬──────┴─────┬─────┴─────┬─────┘
       │           │          │            │            │           │
       ▼           ▼          ▼            ▼            ▼           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ChannelGateway Service                            │
│                                                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │  WhatsApp   │ │    SMS      │ │   Email     │ │   Webchat   │  ...   │
│  │   Adapter   │ │   Adapter   │ │   Adapter   │ │   Adapter   │        │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘        │
│         │               │               │               │                │
│         └───────────────┴───────────────┴───────────────┘                │
│                                 │                                         │
│                         InboundMessage                                   │
│                        (normalized format)                               │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                      ┌───────────┴───────────┐
                      │   Message Router      │
                      │   (tenant + agent     │
                      │    resolution)        │
                      └───────────┬───────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            RUCHE (this repo)                             │
│                                                                          │
│   POST /v1/chat ← ACF → Brain → Response                                │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ OutboundMessage
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ChannelGateway Service                            │
│                        (outbound routing)                               │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         External Channels
```

**Boundary Clarification:**

| Responsibility | Owner |
|----------------|-------|
| Channel API integration | ChannelGateway (adapters) |
| Message normalization | ChannelGateway |
| Tenant/agent resolution | ChannelGateway or Message Router |
| Message processing | Ruche (ACF + Brain) |
| Response formatting | ChannelGateway (using ChannelPolicy) |

---

## 2. Core Interfaces

### 2.1 ChannelAdapter Protocol

```python
from abc import ABC, abstractmethod
from uuid import UUID
from datetime import datetime
from typing import AsyncIterator
from pydantic import BaseModel


class ChannelAdapter(ABC):
    """
    Abstract interface for channel integrations.

    Each channel (WhatsApp, SMS, etc.) implements this interface.
    Adapters handle channel-specific authentication, formatting, and rate limits.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique channel identifier: 'whatsapp', 'sms', 'email', etc."""
        ...

    @abstractmethod
    async def receive_webhook(
        self,
        request_body: bytes,
        headers: dict[str, str],
    ) -> list["InboundMessage"]:
        """
        Parse incoming webhook from channel provider.

        Args:
            request_body: Raw HTTP body
            headers: HTTP headers (for signature verification)

        Returns:
            List of normalized InboundMessages (may be >1 for batched webhooks)

        Raises:
            WebhookValidationError: If signature/format invalid
        """
        ...

    @abstractmethod
    async def send_message(
        self,
        message: "OutboundMessage",
    ) -> "DeliveryResult":
        """
        Send message to channel.

        Args:
            message: Normalized outbound message

        Returns:
            DeliveryResult with provider message ID and status

        Raises:
            ChannelDeliveryError: If delivery fails
        """
        ...

    @abstractmethod
    async def send_typing_indicator(
        self,
        channel_user_id: str,
        tenant_id: UUID,
    ) -> None:
        """Send typing indicator if channel supports it."""
        ...

    @abstractmethod
    async def send_read_receipt(
        self,
        message_id: str,
        tenant_id: UUID,
    ) -> None:
        """Send read receipt if channel supports it."""
        ...

    @abstractmethod
    async def get_media(
        self,
        media_id: str,
        tenant_id: UUID,
    ) -> "MediaContent":
        """
        Retrieve media content from channel.

        Some channels (WhatsApp) require fetching media separately.
        """
        ...

    @abstractmethod
    async def healthcheck(self) -> "HealthStatus":
        """Check channel connectivity and credentials."""
        ...
```

### 2.2 InboundMessage (Normalized)

```python
from enum import Enum


class ContentType(str, Enum):
    """Type of message content."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    MIXED = "mixed"  # Text + media


class MediaAttachment(BaseModel):
    """Media content in a message."""
    type: ContentType
    url: str | None = None  # URL to fetch content
    media_id: str | None = None  # Channel-specific ID
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    size_bytes: int | None = None
    thumbnail_url: str | None = None


class LocationContent(BaseModel):
    """Location data."""
    latitude: float
    longitude: float
    name: str | None = None
    address: str | None = None


class InboundMessage(BaseModel):
    """
    Normalized inbound message from any channel.

    This is the canonical format that ChannelGateway produces
    and Ruche consumes via POST /v1/chat.
    """

    # ─────────────────────────────────────────────────────────────
    # Identity (resolved by ChannelGateway or Message Router)
    # ─────────────────────────────────────────────────────────────
    tenant_id: UUID
    agent_id: UUID
    channel: str  # "whatsapp", "sms", "email", etc.
    channel_user_id: str  # Phone number, email, etc.

    # ─────────────────────────────────────────────────────────────
    # Content (normalized from channel-specific format)
    # ─────────────────────────────────────────────────────────────
    content_type: ContentType
    text: str | None = None
    media: list[MediaAttachment] = []
    location: LocationContent | None = None

    # ─────────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────────
    provider_message_id: str  # Channel's message ID
    received_at: datetime  # When channel received it
    gateway_received_at: datetime  # When gateway received webhook

    # Channel-specific metadata (preserved for debugging)
    raw_metadata: dict = {}

    # ─────────────────────────────────────────────────────────────
    # Optional: Conversation context from channel
    # ─────────────────────────────────────────────────────────────
    reply_to_message_id: str | None = None  # If replying to specific message
    forwarded: bool = False
    is_status_update: bool = False  # Read receipt, delivery status, etc.
```

### 2.3 OutboundMessage

```python
class OutboundSegment(BaseModel):
    """A single segment of an outbound response."""
    type: ContentType
    text: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    buttons: list[dict] | None = None  # Interactive buttons
    quick_replies: list[str] | None = None


class OutboundMessage(BaseModel):
    """
    Outbound message from Ruche to a channel.

    May contain multiple segments (text + images, etc.)
    """

    # ─────────────────────────────────────────────────────────────
    # Routing
    # ─────────────────────────────────────────────────────────────
    tenant_id: UUID
    agent_id: UUID
    channel: str
    channel_user_id: str

    # ─────────────────────────────────────────────────────────────
    # Content
    # ─────────────────────────────────────────────────────────────
    segments: list[OutboundSegment]

    # ─────────────────────────────────────────────────────────────
    # Context
    # ─────────────────────────────────────────────────────────────
    logical_turn_id: UUID
    session_id: str
    reply_to_message_id: str | None = None  # For threaded replies

    # ─────────────────────────────────────────────────────────────
    # Delivery hints
    # ─────────────────────────────────────────────────────────────
    typing_indicator_ms: int = 0  # Show typing for N ms before sending
    priority: str = "normal"  # "high" for urgent messages
```

### 2.4 DeliveryResult

```python
class DeliveryStatus(str, Enum):
    """Delivery status from channel."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    QUEUED = "queued"


class DeliveryResult(BaseModel):
    """Result of sending a message to a channel."""
    success: bool
    status: DeliveryStatus
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## 3. ChannelGateway Service Interface

### 3.1 Gateway Protocol

```python
class ChannelGateway(Protocol):
    """
    Main interface for the ChannelGateway service.

    This is what Ruche interacts with for outbound messages.
    Inbound messages come via HTTP webhook to Ruche's /v1/chat endpoint.
    """

    async def send(
        self,
        message: OutboundMessage,
        channel_policy: "ChannelPolicy",
    ) -> DeliveryResult:
        """
        Send message to appropriate channel.

        Applies channel policy for formatting (markdown stripping,
        message splitting, etc.) before delivery.
        """
        ...

    async def send_typing(
        self,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
        duration_ms: int,
    ) -> None:
        """Send typing indicator."""
        ...

    async def get_channel_status(
        self,
        tenant_id: UUID,
        channel: str,
    ) -> "ChannelHealthStatus":
        """Check channel health for a tenant."""
        ...

    async def resolve_interlocutor(
        self,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
    ) -> UUID | None:
        """
        Resolve channel identity to interlocutor ID.

        Returns None if no linked interlocutor exists.
        """
        ...

    async def link_interlocutor(
        self,
        interlocutor_id: UUID,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
        verified: bool = False,
    ) -> None:
        """Link a channel identity to an interlocutor."""
        ...

    async def unlink_interlocutor(
        self,
        interlocutor_id: UUID,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
    ) -> bool:
        """
        Unlink a channel identity from an interlocutor.

        Use when a user requests to separate identities across channels
        or when an incorrect auto-link needs correction.

        Returns:
            True if unlinked, False if link didn't exist
        """
        ...
```

### 3.2 Message Router (Optional)

If tenant/agent resolution happens outside Ruche:

```python
class MessageRouter(Protocol):
    """
    Routes inbound messages to correct tenant/agent.

    This may be part of ChannelGateway or a separate service.
    """

    async def route(
        self,
        channel: str,
        channel_user_id: str,
        channel_metadata: dict,
    ) -> "RoutingDecision":
        """
        Determine tenant and agent for incoming message.

        Resolution strategies:
        1. Channel account → tenant (WhatsApp Business Account)
        2. Phone number → tenant (dedicated numbers)
        3. Webhook URL → tenant/agent (path-based routing)
        """
        ...


class RoutingDecision(BaseModel):
    """Result of message routing."""
    tenant_id: UUID
    agent_id: UUID
    interlocutor_id: UUID | None = None  # If already known
    session_hint: str | None = None  # Suggested session
```

---

## 4. Channel Adapter Implementations

### 4.1 WhatsApp Adapter

```python
class WhatsAppAdapter(ChannelAdapter):
    """
    WhatsApp Business API adapter.

    Handles:
    - Webhook signature verification
    - Message type parsing (text, image, audio, etc.)
    - Template message sending
    - Interactive message buttons
    """

    channel_name = "whatsapp"

    def __init__(
        self,
        api_token: str,
        phone_number_id: str,
        webhook_verify_token: str,
        app_secret: str,  # For signature verification
    ):
        self._api_token = api_token
        self._phone_number_id = phone_number_id
        self._webhook_verify_token = webhook_verify_token
        self._app_secret = app_secret

    async def receive_webhook(
        self,
        request_body: bytes,
        headers: dict[str, str],
    ) -> list[InboundMessage]:
        # Verify signature
        signature = headers.get("X-Hub-Signature-256")
        if not self._verify_signature(request_body, signature):
            raise WebhookValidationError("Invalid signature")

        # Parse WhatsApp webhook format
        data = json.loads(request_body)
        messages = []

        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change["field"] == "messages":
                    for msg in change["value"].get("messages", []):
                        messages.append(self._parse_message(msg, change["value"]))

        return messages

    async def send_message(
        self,
        message: OutboundMessage,
    ) -> DeliveryResult:
        # Format for WhatsApp API
        payload = self._format_outbound(message)

        response = await self._http.post(
            f"https://graph.facebook.com/v17.0/{self._phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self._api_token}"},
            json=payload,
        )

        if response.status_code == 200:
            data = response.json()
            return DeliveryResult(
                success=True,
                status=DeliveryStatus.SENT,
                provider_message_id=data["messages"][0]["id"],
            )
        else:
            return DeliveryResult(
                success=False,
                status=DeliveryStatus.FAILED,
                error_code=str(response.status_code),
                error_message=response.text,
            )

    def _parse_message(
        self,
        msg: dict,
        context: dict,
    ) -> InboundMessage:
        """Parse WhatsApp message to normalized format."""
        msg_type = msg["type"]
        contact = context["contacts"][0]

        base = InboundMessage(
            tenant_id=UUID("00000000-0000-0000-0000-000000000000"),  # Set by router
            agent_id=UUID("00000000-0000-0000-0000-000000000000"),   # Set by router
            channel="whatsapp",
            channel_user_id=msg["from"],
            provider_message_id=msg["id"],
            received_at=datetime.fromtimestamp(int(msg["timestamp"])),
            gateway_received_at=datetime.utcnow(),
            raw_metadata={"contact_name": contact.get("profile", {}).get("name")},
        )

        if msg_type == "text":
            base.content_type = ContentType.TEXT
            base.text = msg["text"]["body"]
        elif msg_type == "image":
            base.content_type = ContentType.IMAGE
            base.text = msg.get("image", {}).get("caption")
            base.media = [MediaAttachment(
                type=ContentType.IMAGE,
                media_id=msg["image"]["id"],
                mime_type=msg["image"].get("mime_type"),
            )]
        # ... handle other types

        return base
```

### 4.2 SMS Adapter (Twilio)

```python
class TwilioSMSAdapter(ChannelAdapter):
    """Twilio SMS adapter."""

    channel_name = "sms"

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
    ):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number

    async def receive_webhook(
        self,
        request_body: bytes,
        headers: dict[str, str],
    ) -> list[InboundMessage]:
        # Parse form-encoded Twilio webhook
        params = parse_qs(request_body.decode())

        return [InboundMessage(
            tenant_id=UUID("00000000-0000-0000-0000-000000000000"),
            agent_id=UUID("00000000-0000-0000-0000-000000000000"),
            channel="sms",
            channel_user_id=params["From"][0],
            content_type=ContentType.TEXT,
            text=params["Body"][0],
            provider_message_id=params["MessageSid"][0],
            received_at=datetime.utcnow(),
            gateway_received_at=datetime.utcnow(),
        )]

    async def send_message(
        self,
        message: OutboundMessage,
    ) -> DeliveryResult:
        # SMS only supports text
        text = " ".join(
            seg.text for seg in message.segments
            if seg.text
        )

        response = await self._twilio_client.messages.create(
            to=message.channel_user_id,
            from_=self._from_number,
            body=text,
        )

        return DeliveryResult(
            success=True,
            status=DeliveryStatus.SENT,
            provider_message_id=response.sid,
        )
```

### 4.3 Email Adapter

```python
class EmailAdapter(ChannelAdapter):
    """Email adapter (SendGrid, SES, or SMTP)."""

    channel_name = "email"

    async def receive_webhook(
        self,
        request_body: bytes,
        headers: dict[str, str],
    ) -> list[InboundMessage]:
        # Parse inbound email (provider-specific format)
        # Convert HTML to text if needed
        ...

    async def send_message(
        self,
        message: OutboundMessage,
    ) -> DeliveryResult:
        # Convert markdown to HTML
        # Handle attachments
        # Send via email provider
        ...
```

### 4.4 Webchat Adapter

```python
class WebchatAdapter(ChannelAdapter):
    """
    Webchat adapter for embedded web widgets.

    Unlike other channels, webchat uses WebSocket for real-time.
    """

    channel_name = "webchat"

    async def receive_webhook(
        self,
        request_body: bytes,
        headers: dict[str, str],
    ) -> list[InboundMessage]:
        # Webchat messages typically come via WebSocket,
        # but can fall back to HTTP polling
        ...

    async def send_message(
        self,
        message: OutboundMessage,
    ) -> DeliveryResult:
        # Push via WebSocket connection
        # Fall back to message queue for offline users
        ...
```

---

## 5. Response Formatting

### 5.1 ChannelFormatter

The ChannelGateway applies ChannelPolicy rules before sending:

```python
class ChannelFormatter:
    """
    Format outbound messages according to channel capabilities.

    Uses ChannelPolicy loaded from Ruche's ConfigStore.
    """

    def format(
        self,
        message: OutboundMessage,
        policy: ChannelPolicy,
    ) -> list[OutboundSegment]:
        """
        Format message for channel delivery.

        Applies:
        - Markdown stripping (if not supported)
        - Message splitting (if exceeds max length)
        - Rich media conversion
        """
        formatted = []

        for segment in message.segments:
            if segment.type == ContentType.TEXT and segment.text:
                # Strip markdown if not supported
                text = segment.text
                if not policy.supports_markdown:
                    text = self._strip_markdown(text)

                # Split if too long
                if policy.max_message_length and len(text) > policy.max_message_length:
                    chunks = self._split_message(text, policy.max_message_length)
                    formatted.extend([
                        OutboundSegment(type=ContentType.TEXT, text=chunk)
                        for chunk in chunks
                    ])
                else:
                    formatted.append(OutboundSegment(type=ContentType.TEXT, text=text))

            elif segment.type in (ContentType.IMAGE, ContentType.VIDEO):
                if policy.supports_rich_media:
                    formatted.append(segment)
                else:
                    # Convert to link for channels without rich media
                    formatted.append(OutboundSegment(
                        type=ContentType.TEXT,
                        text=f"[Media: {segment.media_url}]",
                    ))

        return formatted

    def _strip_markdown(self, text: str) -> str:
        """Convert markdown to plain text."""
        import re
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove bold/italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        # Remove links, keep text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        # Remove code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        return text

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split long message at natural break points."""
        segments = []
        while text:
            if len(text) <= max_len:
                segments.append(text)
                break

            # Find break point (sentence > paragraph > word > hard)
            break_at = self._find_break_point(text, max_len)
            segments.append(text[:break_at].strip())
            text = text[break_at:].strip()

        return segments

    def _find_break_point(self, text: str, max_len: int) -> int:
        """Find natural break point."""
        # Try sentence break
        for punct in ['. ', '! ', '? ', '\n\n']:
            idx = text.rfind(punct, 0, max_len)
            if idx > max_len * 0.5:
                return idx + len(punct)

        # Try word break
        idx = text.rfind(' ', 0, max_len)
        if idx > 0:
            return idx

        # Hard break
        return max_len
```

---

## 6. Interlocutor Identity Resolution

### 6.1 ChannelIdentity Store

```python
class ChannelIdentity(BaseModel):
    """
    Links a channel-specific user ID to a platform interlocutor.

    Stored in InterlocutorDataStore or a dedicated identity service.
    """
    interlocutor_id: UUID
    tenant_id: UUID
    channel: str
    channel_user_id: str  # Phone, email, etc.

    verified: bool = False
    verified_at: datetime | None = None

    opt_in_outbound: bool = False
    opt_in_at: datetime | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime | None = None


class IdentityResolver:
    """
    Resolve channel identities to interlocutors.

    **Default behavior: Cross-channel linking is ENABLED by default.**

    When a user messages from WhatsApp with +1234567890 and later from SMS
    with the same number, they are automatically linked to the same
    interlocutor. This provides seamless cross-channel experience.

    Tenants can:
    - Disable auto-linking via configuration (opt-out)
    - Unlink specific identities via API when needed
    - Users can request unlinking through the agent

    Resolution strategies (in order):
    1. Exact match: channel + channel_user_id → interlocutor
    2. Cross-channel auto-link: Same phone/email → same interlocutor (default ON)
    3. Create new: First message creates new interlocutor
    """

    def __init__(
        self,
        identity_store: "IdentityStore",
        interlocutor_store: "InterlocutorStore",
        auto_link_enabled: bool = True,  # Default: linked
    ):
        self._identity_store = identity_store
        self._interlocutor_store = interlocutor_store
        self._auto_link_enabled = auto_link_enabled

    async def resolve_or_create(
        self,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
    ) -> tuple[UUID, bool]:
        """
        Resolve or create interlocutor.

        Returns:
            (interlocutor_id, is_new)
        """
        # Try exact match
        identity = await self._identity_store.find(
            tenant_id=tenant_id,
            channel=channel,
            channel_user_id=channel_user_id,
        )
        if identity:
            return identity.interlocutor_id, False

        # Cross-channel auto-linking (default: enabled)
        if self._auto_link_enabled:
            cross_match = await self._try_cross_channel_link(
                tenant_id, channel, channel_user_id
            )
            if cross_match:
                return cross_match, False

        # Create new interlocutor
        interlocutor_id = await self._interlocutor_store.create(
            tenant_id=tenant_id,
        )
        await self._identity_store.link(
            interlocutor_id=interlocutor_id,
            tenant_id=tenant_id,
            channel=channel,
            channel_user_id=channel_user_id,
        )
        return interlocutor_id, True

    async def _try_cross_channel_link(
        self,
        tenant_id: UUID,
        channel: str,
        channel_user_id: str,
    ) -> UUID | None:
        """
        Attempt to link to existing interlocutor via shared identifier.

        Linkable identifiers:
        - Phone number: WhatsApp, SMS, Voice (+E.164 format)
        - Email: Email channel (lowercase normalized)
        """
        # Phone-based channels
        if channel in ("whatsapp", "sms", "voice") and channel_user_id.startswith("+"):
            cross_match = await self._identity_store.find_by_phone(
                tenant_id=tenant_id,
                phone=channel_user_id,
            )
            if cross_match:
                await self._identity_store.link(
                    interlocutor_id=cross_match.interlocutor_id,
                    tenant_id=tenant_id,
                    channel=channel,
                    channel_user_id=channel_user_id,
                )
                return cross_match.interlocutor_id

        # Email-based linking
        if channel == "email" and "@" in channel_user_id:
            normalized_email = channel_user_id.lower().strip()
            cross_match = await self._identity_store.find_by_email(
                tenant_id=tenant_id,
                email=normalized_email,
            )
            if cross_match:
                await self._identity_store.link(
                    interlocutor_id=cross_match.interlocutor_id,
                    tenant_id=tenant_id,
                    channel=channel,
                    channel_user_id=channel_user_id,
                )
                return cross_match.interlocutor_id

        return None

    async def unlink(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        channel: str,
        channel_user_id: str,
        create_new_interlocutor: bool = True,
    ) -> UUID | None:
        """
        Unlink a channel identity from an interlocutor.

        Args:
            tenant_id: Tenant context
            interlocutor_id: Current interlocutor
            channel: Channel to unlink
            channel_user_id: Channel-specific ID
            create_new_interlocutor: If True, create new interlocutor for this identity

        Returns:
            New interlocutor ID if created, None otherwise
        """
        await self._identity_store.unlink(
            tenant_id=tenant_id,
            interlocutor_id=interlocutor_id,
            channel=channel,
            channel_user_id=channel_user_id,
        )

        if create_new_interlocutor:
            new_interlocutor_id = await self._interlocutor_store.create(
                tenant_id=tenant_id,
            )
            await self._identity_store.link(
                interlocutor_id=new_interlocutor_id,
                tenant_id=tenant_id,
                channel=channel,
                channel_user_id=channel_user_id,
            )
            return new_interlocutor_id

        return None
```

---

## 7. Configuration

### 7.1 Gateway Configuration

```toml
[channel_gateway]
# Service configuration
port = 8080
health_check_path = "/health"

# Default timeouts
send_timeout_ms = 10000
receive_timeout_ms = 5000

# Rate limiting (global)
max_inbound_per_second = 1000
max_outbound_per_second = 500

# Retry settings
max_retries = 3
retry_delays_ms = [1000, 5000, 15000]

# Identity resolution
[channel_gateway.identity]
# Cross-channel auto-linking: same phone/email = same interlocutor
# Default: true (linked by default, tenants can unlink via API)
auto_link_enabled = true

# Linkable identifier types
linkable_identifiers = ["phone", "email"]


[channel_gateway.adapters.whatsapp]
enabled = true
api_version = "v17.0"
webhook_verify_token = "${WHATSAPP_WEBHOOK_VERIFY_TOKEN}"
# Per-tenant credentials in secrets store


[channel_gateway.adapters.sms]
enabled = true
provider = "twilio"  # or "aws_sns", "vonage"
# Per-tenant credentials in secrets store


[channel_gateway.adapters.email]
enabled = true
provider = "sendgrid"  # or "ses", "smtp"
inbound_domain = "inbound.ruche.example.com"


[channel_gateway.adapters.webchat]
enabled = true
websocket_path = "/ws/chat"
cors_origins = ["*"]  # Configured per-tenant
```

### 7.2 Per-Tenant Channel Configuration

```toml
# Tenant-specific channel configuration (in ConfigStore)

# Tenant identity settings (overrides global defaults)
[[tenants.identity]]
tenant_id = "uuid"
# Disable auto-linking for this tenant (default: true = linked)
auto_link_enabled = false

[[tenants.channels]]
tenant_id = "uuid"
channel = "whatsapp"
phone_number_id = "123456789"
business_account_id = "987654321"
# Credentials reference secrets store

[[tenants.channels]]
tenant_id = "uuid"
channel = "sms"
from_numbers = ["+14155551234", "+14155551235"]
```

### 7.3 Identity Unlinking API

Tenants can unlink identities via the management API:

```http
DELETE /v1/interlocutors/{interlocutor_id}/identities/{channel}/{channel_user_id}
Authorization: Bearer <tenant_api_key>

# Response
{
  "unlinked": true,
  "new_interlocutor_id": "uuid"  // If create_new=true (default)
}
```

Use cases:
- User requests identity separation (privacy)
- Incorrect auto-link (shared phone number)
- Compliance requirements (GDPR right to be forgotten)

---

## 8. Observability

### 8.1 Metrics

```python
# Inbound metrics
channel_messages_received = Counter(
    "channel_messages_received_total",
    "Messages received by channel",
    ["channel", "tenant_id", "content_type"],
)

channel_webhook_latency = Histogram(
    "channel_webhook_latency_seconds",
    "Time to process inbound webhook",
    ["channel"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5],
)

# Outbound metrics
channel_messages_sent = Counter(
    "channel_messages_sent_total",
    "Messages sent by channel and status",
    ["channel", "tenant_id", "status"],
)

channel_send_latency = Histogram(
    "channel_send_latency_seconds",
    "Time to send message to channel",
    ["channel"],
    buckets=[0.1, 0.5, 1, 2, 5, 10],
)

# Identity metrics
identity_resolution_total = Counter(
    "identity_resolution_total",
    "Identity resolutions by result",
    ["result"],  # existing, new, cross_channel_linked
)

identity_unlink_total = Counter(
    "identity_unlink_total",
    "Identity unlinks by reason",
    ["reason"],  # user_request, admin_action, compliance
)
```

### 8.2 Structured Logging

```python
logger.info(
    "inbound_message_received",
    channel=message.channel,
    channel_user_id=message.channel_user_id,
    content_type=message.content_type,
    provider_message_id=message.provider_message_id,
    tenant_id=str(message.tenant_id),
)

logger.info(
    "outbound_message_sent",
    channel=message.channel,
    channel_user_id=message.channel_user_id,
    segments=len(message.segments),
    logical_turn_id=str(message.logical_turn_id),
    provider_message_id=result.provider_message_id,
    status=result.status,
)

logger.warning(
    "channel_delivery_failed",
    channel=message.channel,
    channel_user_id=message.channel_user_id,
    error_code=result.error_code,
    error_message=result.error_message,
    will_retry=will_retry,
)

logger.info(
    "identity_resolved",
    channel=channel,
    result="cross_channel_linked",  # or "existing", "new"
    interlocutor_id=str(interlocutor_id),
    linked_from_channel=source_channel,  # Only for cross_channel_linked
    tenant_id=str(tenant_id),
)

logger.info(
    "identity_unlinked",
    channel=channel,
    channel_user_id=channel_user_id,
    previous_interlocutor_id=str(previous_id),
    new_interlocutor_id=str(new_id),
    reason="user_request",
    tenant_id=str(tenant_id),
)
```

---

## 9. Error Handling

### 9.1 Inbound Errors

| Error | Handling |
|-------|----------|
| Invalid webhook signature | Return 401, log warning |
| Malformed payload | Return 400, log error with payload sample |
| Unknown tenant/channel | Return 404, log warning |
| Rate limit exceeded | Return 429, queue for later |
| Internal error | Return 500, retry from channel |

### 9.2 Outbound Errors

| Error | Handling |
|-------|----------|
| Channel rate limit | Queue with backoff |
| Invalid recipient | Mark delivery failed, log |
| Channel API error | Retry with exponential backoff |
| Credential expired | Alert, pause channel |
| Network timeout | Retry up to max_retries |

---

## 10. Security Considerations

### 10.1 Webhook Security

- **Signature verification**: All channels must verify webhook signatures
- **IP allowlisting**: Optionally restrict webhook sources to known IPs
- **TLS required**: All webhook endpoints must be HTTPS

### 10.2 Credential Management

- Channel API credentials stored in secrets manager
- Per-tenant credential isolation
- Automatic rotation support where available

### 10.3 Data Handling

- PII (phone numbers, emails) logged only at DEBUG level
- Message content logged only at DEBUG level
- Media URLs have short-lived access tokens

---

## 11. Future Considerations

### 11.1 Additional Channels

- **Telegram**: Similar to WhatsApp adapter pattern
- **Slack**: Workspace-based routing
- **Discord**: Server/channel-based routing
- **Voice (Twilio/Vonage)**: Real-time transcription integration

### 11.2 Channel Orchestration

- **Smart channel selection**: Pick optimal channel for outbound based on user preferences and availability
- **Fallback chains**: WhatsApp → SMS → Email
- **A/B testing**: Test message variants across channels

### 11.3 Media Processing

- **Transcription**: Audio messages → text
- **OCR**: Image text extraction
- **Content moderation**: Scan media for prohibited content

---

## References

- [Channel Capabilities](../acf/architecture/topics/10-channel-capabilities.md) - ChannelPolicy model
- [API Layer](api-layer.md) - Ruche's /v1/chat endpoint
- [ACF Specification](../acf/architecture/ACF_SPEC.md) - Turn processing architecture
- [Interlocutor Data](../design/interlocutor-data.md) - Identity storage
