"""SMS formatter.

Strips all formatting and enforces character limit.
"""

import re

from ruche.brains.focal.phases.generation.formatters import ChannelFormatter


class SMSFormatter(ChannelFormatter):
    """Formatter for SMS channel."""

    MAX_LENGTH = 160

    @property
    def channel_name(self) -> str:
        """Channel name."""
        return "sms"

    def format(self, response: str) -> str:
        """Format response for SMS.

        Args:
            response: Raw LLM response

        Returns:
            SMS-formatted response (max 160 chars)
        """
        # Strip all markdown formatting
        response = re.sub(r"\*\*(.+?)\*\*", r"\1", response)  # Bold
        response = re.sub(r"\*(.+?)\*", r"\1", response)  # Italic
        response = re.sub(r"__(.+?)__", r"\1", response)  # Underline
        response = re.sub(r"~~(.+?)~~", r"\1", response)  # Strikethrough

        # Remove multiple spaces
        response = re.sub(r"\s+", " ", response)

        # Strip and truncate
        response = response.strip()

        if len(response) > self.MAX_LENGTH:
            # Truncate at word boundary
            response = self._truncate_at_word(response, self.MAX_LENGTH - 3) + "..."

        return response

    def _truncate_at_word(self, text: str, max_length: int) -> str:
        """Truncate text at word boundary.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        # Find last space before max_length
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")

        if last_space > 0:
            return text[:last_space]

        return text[:max_length]
