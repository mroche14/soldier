"""Channel-specific response formatters.

Formats responses for different communication channels (WhatsApp, email, SMS, etc.).
"""

from abc import ABC, abstractmethod


class ChannelFormatter(ABC):
    """Formats responses for specific communication channels."""

    @abstractmethod
    def format(self, response: str) -> str:
        """Format response for the channel.

        Args:
            response: Raw LLM response

        Returns:
            Channel-formatted response
        """
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Name of the channel."""
        pass


# Import concrete formatters AFTER ChannelFormatter is defined
from ruche.brains.focal.phases.generation.formatters.default import DefaultFormatter
from ruche.brains.focal.phases.generation.formatters.email import EmailFormatter
from ruche.brains.focal.phases.generation.formatters.sms import SMSFormatter
from ruche.brains.focal.phases.generation.formatters.whatsapp import WhatsAppFormatter


def get_formatter(channel: str) -> ChannelFormatter:
    """Get formatter for channel name.

    Args:
        channel: Channel name (whatsapp, email, sms, web, slack)

    Returns:
        Appropriate formatter instance
    """
    formatters = {
        "whatsapp": WhatsAppFormatter(),
        "email": EmailFormatter(),
        "sms": SMSFormatter(),
        "web": DefaultFormatter(),
        "slack": DefaultFormatter(),
    }
    return formatters.get(channel.lower(), DefaultFormatter())


__all__ = [
    "ChannelFormatter",
    "get_formatter",
    "DefaultFormatter",
    "EmailFormatter",
    "SMSFormatter",
    "WhatsAppFormatter",
]
