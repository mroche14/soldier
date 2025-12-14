"""Default formatter for web and Slack channels.

Passes through markdown with minimal transformations.
"""

from focal.alignment.generation.formatters import ChannelFormatter


class DefaultFormatter(ChannelFormatter):
    """Default formatter for web/Slack - passes through markdown."""

    @property
    def channel_name(self) -> str:
        """Channel name."""
        return "default"

    def format(self, response: str) -> str:
        """Format response (minimal changes).

        Args:
            response: Raw LLM response

        Returns:
            Formatted response with minimal transformations
        """
        # Just strip extra whitespace
        return response.strip()
