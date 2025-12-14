"""Twilio WhatsApp channel adapter.

Integrates with Twilio for WhatsApp messaging.
Stub implementation - to be completed when WhatsApp support is needed.
"""

from focal.infrastructure.channels.models import OutboundMessage
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class TwilioWhatsAppAdapter:
    """Twilio WhatsApp channel adapter.

    Sends/receives messages via Twilio WhatsApp API.
    """

    def __init__(self, account_sid: str | None = None, auth_token: str | None = None) -> None:
        """Initialize Twilio adapter.

        Args:
            account_sid: Twilio account SID
            auth_token: Twilio auth token
        """
        self._account_sid = account_sid
        self._auth_token = auth_token

    async def send(self, message: OutboundMessage) -> None:
        """Send a message via Twilio WhatsApp.

        Args:
            message: Message to send
        """
        logger.warning(
            "twilio_whatsapp_stub",
            message="Twilio WhatsApp adapter not yet implemented",
        )
        # Stub - would send via Twilio API
