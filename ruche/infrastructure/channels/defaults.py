"""Default channel policies.

These are the baseline ChannelPolicy configurations per the spec in
docs/acf/architecture/topics/10-channel-capabilities.md
"""

from ruche.infrastructure.channels.models import ChannelPolicy, SupersedeMode

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
        max_messages_per_minute=30,
    ),
    "email": ChannelPolicy(
        channel="email",
        aggregation_window_ms=0,
        supersede_default=SupersedeMode.QUEUE,
        supports_typing_indicator=False,
        supports_read_receipts=False,
        max_message_length=None,
        supports_markdown=True,
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
        natural_response_delay_ms=500,
        max_messages_per_minute=60,
    ),
    "voice": ChannelPolicy(
        channel="voice",
        aggregation_window_ms=0,
        supersede_default=SupersedeMode.INTERRUPT,
        supports_typing_indicator=False,
        supports_read_receipts=False,
        max_message_length=500,
        supports_markdown=False,
        supports_rich_media=False,
        natural_response_delay_ms=300,
        max_messages_per_minute=20,
    ),
}
