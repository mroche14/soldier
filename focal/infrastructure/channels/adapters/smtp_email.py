"""SMTP email channel adapter.

Integrates with SMTP for email messaging.
Stub implementation - to be completed when email support is needed.
"""

from focal.infrastructure.channels.models import OutboundMessage
from focal.observability.logging import get_logger

logger = get_logger(__name__)


class SMTPEmailAdapter:
    """SMTP email channel adapter.

    Sends/receives messages via SMTP/IMAP.
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize SMTP adapter.

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            username: SMTP username
            password: SMTP password
        """
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password

    async def send(self, message: OutboundMessage) -> None:
        """Send a message via SMTP.

        Args:
            message: Message to send
        """
        logger.warning(
            "smtp_email_stub",
            message="SMTP email adapter not yet implemented",
        )
        # Stub - would send via SMTP
