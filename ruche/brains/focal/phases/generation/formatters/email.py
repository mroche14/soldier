"""Email formatter.

Preserves markdown and adds proper structure for email.
"""

from ruche.brains.focal.phases.generation.formatters import ChannelFormatter


class EmailFormatter(ChannelFormatter):
    """Formatter for email channel."""

    @property
    def channel_name(self) -> str:
        """Channel name."""
        return "email"

    def format(self, response: str) -> str:
        """Format response for email.

        Args:
            response: Raw LLM response

        Returns:
            Email-formatted response
        """
        response = response.strip()

        # Add greeting if not present
        if not self._has_greeting(response):
            response = "Hello,\n\n" + response

        # Add signature placeholder if not present
        if not self._has_signature(response):
            response = response + "\n\nBest regards"

        return response

    def _has_greeting(self, text: str) -> bool:
        """Check if text has a greeting."""
        greetings = ["hello", "hi", "dear", "greetings"]
        first_line = text.split("\n")[0].lower()
        return any(greeting in first_line for greeting in greetings)

    def _has_signature(self, text: str) -> bool:
        """Check if text has a signature."""
        signatures = ["regards", "sincerely", "best", "thanks", "thank you"]
        last_lines = "\n".join(text.split("\n")[-3:]).lower()
        return any(sig in last_lines for sig in signatures)
