"""WhatsApp formatter.

Converts markdown to WhatsApp-compatible format and handles message splitting.
"""

import re

from focal.alignment.generation.formatters import ChannelFormatter


class WhatsAppFormatter(ChannelFormatter):
    """Formatter for WhatsApp channel."""

    MAX_LENGTH = 4096

    @property
    def channel_name(self) -> str:
        """Channel name."""
        return "whatsapp"

    def format(self, response: str) -> str:
        """Format response for WhatsApp.

        Args:
            response: Raw LLM response

        Returns:
            WhatsApp-formatted response
        """
        # Convert markdown bold to WhatsApp format
        response = re.sub(r"\*\*(.+?)\*\*", r"*\1*", response)

        # Remove excessive line breaks (more than 2 consecutive)
        response = re.sub(r"\n{3,}", "\n\n", response)

        # Strip whitespace
        response = response.strip()

        # Split if too long
        if len(response) > self.MAX_LENGTH:
            response = self._split_message(response)

        return response

    def _split_message(self, message: str) -> str:
        """Split long message at natural boundaries.

        Args:
            message: Message to split

        Returns:
            First part of message with indicator
        """
        # Find last sentence boundary before limit
        truncate_at = self.MAX_LENGTH - 50  # Leave room for indicator

        # Try to split at sentence
        match = None
        for pattern in [r"\. ", r"\n\n", r"\n", r" "]:
            matches = list(re.finditer(pattern, message[:truncate_at]))
            if matches:
                match = matches[-1]
                break

        if match:
            split_point = match.end()
        else:
            split_point = truncate_at

        return message[:split_point] + "\n\n(message continues...)"
