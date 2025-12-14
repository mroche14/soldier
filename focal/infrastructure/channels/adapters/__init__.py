"""Channel adapters for external messaging platforms.

Adapters for webchat, WhatsApp, email, SMS, etc.
"""

from focal.infrastructure.channels.adapters.agui_webchat import AGUIWebchatAdapter
from focal.infrastructure.channels.adapters.simple_webchat import SimpleWebchatAdapter
from focal.infrastructure.channels.adapters.smtp_email import SMTPEmailAdapter
from focal.infrastructure.channels.adapters.twilio_whatsapp import TwilioWhatsAppAdapter

__all__ = [
    "AGUIWebchatAdapter",
    "SimpleWebchatAdapter",
    "TwilioWhatsAppAdapter",
    "SMTPEmailAdapter",
]
