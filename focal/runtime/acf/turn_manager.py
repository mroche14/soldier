"""Turn manager for accumulation and boundary detection.

Implements adaptive accumulation logic to determine when a LogicalTurn
is ready for processing.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from focal.runtime.acf.models import AccumulationHint, MessageShape


# Greeting patterns
GREETINGS = {
    "hi",
    "hello",
    "hey",
    "hiya",
    "good morning",
    "good afternoon",
    "good evening",
    "morning",
    "afternoon",
    "evening",
}

# Channel-specific defaults (milliseconds)
CHANNEL_DEFAULTS = {
    "whatsapp": 1200,  # Users send in bursts
    "telegram": 1000,  # Similar to WhatsApp
    "sms": 800,  # More deliberate due to cost/friction
    "web": 600,  # Fast typing expected
    "webchat": 600,  # Same as web
    "email": 0,  # Always complete (no accumulation)
    "voice": 0,  # Handled by speech recognition
    "slack": 800,  # Chat-style
    "teams": 800,  # Chat-style
    "api": 0,  # Direct API calls are complete
}


@dataclass
class UserCadenceStats:
    """Historical typing statistics for a user."""

    inter_message_p50_ms: int  # Median time between messages
    inter_message_p95_ms: int  # 95th percentile
    sample_count: int  # How many samples


class TurnManager:
    """Manages turn accumulation and boundary detection.

    Implements adaptive accumulation using multiple signals:
    1. Explicit completion signals (punctuation, politeness markers)
    2. Channel characteristics
    3. Message shape analysis
    4. User typing cadence (learned)
    5. Plan hints from previous turn
    """

    def __init__(
        self,
        min_wait_ms: int = 200,
        max_wait_ms: int = 3000,
        channel_defaults: dict[str, int] | None = None,
    ):
        """Initialize turn manager.

        Args:
            min_wait_ms: Minimum accumulation window
            max_wait_ms: Maximum accumulation window
            channel_defaults: Override channel-specific defaults
        """
        self._min_wait_ms = min_wait_ms
        self._max_wait_ms = max_wait_ms
        self._channel_defaults = channel_defaults or CHANNEL_DEFAULTS

    def suggest_wait_ms(
        self,
        message_content: str,
        channel: str,
        user_cadence: UserCadenceStats | None = None,
        previous_hint: AccumulationHint | None = None,
        messages_in_turn: int = 1,
    ) -> int:
        """Calculate how long to wait for additional messages.

        Args:
            message_content: The latest message text
            channel: Channel identifier (whatsapp, web, etc.)
            user_cadence: Historical typing stats for this user
            previous_hint: Hint from previous turn's pipeline result
            messages_in_turn: How many messages already accumulated

        Returns:
            Milliseconds to wait before processing
        """
        # Start with channel default
        base = self._channel_defaults.get(channel, 800)

        # Adjust for message shape
        shape = self._analyze_message_shape(message_content)
        shape_adjustments = {
            MessageShape.GREETING_ONLY: 500,
            MessageShape.FRAGMENT: 400,
            MessageShape.INCOMPLETE_ENTITY: 600,
            MessageShape.POSSIBLY_INCOMPLETE: 200,
            MessageShape.LIKELY_COMPLETE: 0,
        }
        base += shape_adjustments.get(shape, 0)

        # Explicit completion = shorter wait
        if self._has_explicit_completion(message_content):
            base = max(self._min_wait_ms, base - 300)

        # Adjust for user's historical cadence
        base = self._adapt_to_user_cadence(base, user_cadence)

        # Adjust for previous turn's hint
        base += self._get_hint_adjustment(previous_hint)

        # Diminishing returns after multiple messages
        if messages_in_turn > 1:
            # Each additional message reduces wait (user is clearly typing)
            base = int(base * (0.8 ** (messages_in_turn - 1)))

        return self._clamp(base)

    def _analyze_message_shape(self, text: str) -> MessageShape:
        """Classify message completeness.

        Args:
            text: Message content

        Returns:
            MessageShape classification
        """
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Greeting only - likely followed by actual request
        if text_lower in GREETINGS:
            return MessageShape.GREETING_ONLY

        # Fragment indicators
        if text_stripped.endswith(("...", ",", "-", ":")):
            return MessageShape.FRAGMENT

        # Incomplete entity reference
        if re.search(r"(order|ticket|case|id)\s*#?\s*$", text_lower):
            return MessageShape.INCOMPLETE_ENTITY

        # Very short messages often incomplete
        if len(text_stripped.split()) < 3 and not self._has_explicit_completion(
            text_stripped
        ):
            return MessageShape.POSSIBLY_INCOMPLETE

        return MessageShape.LIKELY_COMPLETE

    def _has_explicit_completion(self, text: str) -> bool:
        """Check for explicit completion signals.

        Args:
            text: Message content

        Returns:
            True if text has explicit completion markers
        """
        text_lower = text.strip().lower()
        return text.endswith((".", "?", "!")) or text_lower.endswith(
            ("please", "thanks", "thank you")
        )

    def _adapt_to_user_cadence(
        self, base_wait_ms: int, cadence_stats: UserCadenceStats | None
    ) -> int:
        """Adjust wait time based on user's historical behavior.

        Args:
            base_wait_ms: Base wait time from other signals
            cadence_stats: Historical typing statistics

        Returns:
            Adjusted wait time
        """
        if cadence_stats is None or cadence_stats.sample_count < 5:
            return base_wait_ms  # Not enough data

        # Use 75th percentile of user's typical inter-message time
        user_typical = (
            cadence_stats.inter_message_p50_ms + cadence_stats.inter_message_p95_ms
        ) // 2

        # Blend with base (60% base, 40% user history)
        return int(base_wait_ms * 0.6 + user_typical * 0.4)

    def _get_hint_adjustment(self, hint: AccumulationHint | None) -> int:
        """Adjust wait time based on previous turn's pipeline hint.

        Args:
            hint: Accumulation hint from previous turn

        Returns:
            Adjustment in milliseconds (can be negative)
        """
        if hint is None:
            return 0

        # Pipeline asked a question and awaits answer
        if hint.awaiting_required_field:
            return 1000  # Give user time to respond

        # Pipeline suggests multi-part response expected
        if hint.expects_followup:
            return 500

        # Pipeline thinks input was complete - reduce wait
        if hint.input_complete_confidence > 0.8:
            return -200

        return 0

    def _clamp(self, value: int) -> int:
        """Clamp value to min/max bounds.

        Args:
            value: Value to clamp

        Returns:
            Clamped value
        """
        return max(self._min_wait_ms, min(value, self._max_wait_ms))
