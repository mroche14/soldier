"""Unit tests for TurnManager accumulation logic."""

import pytest

from ruche.runtime.acf.models import AccumulationHint, MessageShape
from ruche.runtime.acf.turn_manager import (
    CHANNEL_DEFAULTS,
    GREETINGS,
    TurnManager,
    UserCadenceStats,
)


@pytest.fixture
def turn_manager() -> TurnManager:
    """Create TurnManager with default settings."""
    return TurnManager()


@pytest.fixture
def custom_turn_manager() -> TurnManager:
    """Create TurnManager with custom settings."""
    return TurnManager(
        min_wait_ms=100,
        max_wait_ms=5000,
        channel_defaults={"custom": 1500},
    )


class TestChannelDefaults:
    """Tests for channel default constants."""

    def test_whatsapp_default(self) -> None:
        """WhatsApp has 1200ms default."""
        assert CHANNEL_DEFAULTS["whatsapp"] == 1200

    def test_web_default(self) -> None:
        """Web has 600ms default."""
        assert CHANNEL_DEFAULTS["web"] == 600

    def test_email_no_accumulation(self) -> None:
        """Email has 0ms (no accumulation)."""
        assert CHANNEL_DEFAULTS["email"] == 0

    def test_api_no_accumulation(self) -> None:
        """API has 0ms (no accumulation)."""
        assert CHANNEL_DEFAULTS["api"] == 0


class TestGreetings:
    """Tests for greeting detection."""

    def test_greeting_set_contains_common_greetings(self) -> None:
        """Greeting set contains common greetings."""
        assert "hi" in GREETINGS
        assert "hello" in GREETINGS
        assert "hey" in GREETINGS
        assert "good morning" in GREETINGS


class TestMessageShapeAnalysis:
    """Tests for message shape classification."""

    def test_analyze_message_shape_greeting_only(
        self, turn_manager: TurnManager
    ) -> None:
        """Single greeting is classified as GREETING_ONLY."""
        assert turn_manager._analyze_message_shape("hi") == MessageShape.GREETING_ONLY
        assert turn_manager._analyze_message_shape("hello") == MessageShape.GREETING_ONLY
        assert turn_manager._analyze_message_shape("Hey") == MessageShape.GREETING_ONLY

    def test_analyze_message_shape_fragment_ellipsis(
        self, turn_manager: TurnManager
    ) -> None:
        """Message ending with ellipsis is FRAGMENT."""
        assert turn_manager._analyze_message_shape("I need help with...") == MessageShape.FRAGMENT

    def test_analyze_message_shape_fragment_comma(
        self, turn_manager: TurnManager
    ) -> None:
        """Message ending with comma is FRAGMENT."""
        assert turn_manager._analyze_message_shape("I have a problem,") == MessageShape.FRAGMENT

    def test_analyze_message_shape_fragment_dash(
        self, turn_manager: TurnManager
    ) -> None:
        """Message ending with dash is FRAGMENT."""
        assert turn_manager._analyze_message_shape("My order number is-") == MessageShape.FRAGMENT

    def test_analyze_message_shape_fragment_colon(
        self, turn_manager: TurnManager
    ) -> None:
        """Message ending with colon is FRAGMENT."""
        assert turn_manager._analyze_message_shape("The issue:") == MessageShape.FRAGMENT

    def test_analyze_message_shape_incomplete_entity_order(
        self, turn_manager: TurnManager
    ) -> None:
        """Incomplete entity reference is detected."""
        assert turn_manager._analyze_message_shape("order #") == MessageShape.INCOMPLETE_ENTITY
        assert turn_manager._analyze_message_shape("my order") == MessageShape.INCOMPLETE_ENTITY

    def test_analyze_message_shape_incomplete_entity_ticket(
        self, turn_manager: TurnManager
    ) -> None:
        """Incomplete ticket reference is detected."""
        assert turn_manager._analyze_message_shape("ticket") == MessageShape.INCOMPLETE_ENTITY
        assert turn_manager._analyze_message_shape("case #") == MessageShape.INCOMPLETE_ENTITY

    def test_analyze_message_shape_possibly_incomplete_short(
        self, turn_manager: TurnManager
    ) -> None:
        """Short messages without completion markers are POSSIBLY_INCOMPLETE."""
        assert turn_manager._analyze_message_shape("help me") == MessageShape.POSSIBLY_INCOMPLETE

    def test_analyze_message_shape_likely_complete_with_period(
        self, turn_manager: TurnManager
    ) -> None:
        """Message with period is LIKELY_COMPLETE."""
        assert turn_manager._analyze_message_shape("I need help.") == MessageShape.LIKELY_COMPLETE

    def test_analyze_message_shape_likely_complete_with_question(
        self, turn_manager: TurnManager
    ) -> None:
        """Message with question mark is LIKELY_COMPLETE."""
        assert turn_manager._analyze_message_shape("Can you help me?") == MessageShape.LIKELY_COMPLETE

    def test_analyze_message_shape_likely_complete_longer_text(
        self, turn_manager: TurnManager
    ) -> None:
        """Longer messages are LIKELY_COMPLETE."""
        assert (
            turn_manager._analyze_message_shape("I need help with my account settings")
            == MessageShape.LIKELY_COMPLETE
        )


class TestExplicitCompletion:
    """Tests for explicit completion signal detection."""

    def test_has_explicit_completion_period(self, turn_manager: TurnManager) -> None:
        """Period indicates completion."""
        assert turn_manager._has_explicit_completion("Help me.")

    def test_has_explicit_completion_question_mark(
        self, turn_manager: TurnManager
    ) -> None:
        """Question mark indicates completion."""
        assert turn_manager._has_explicit_completion("Can you help?")

    def test_has_explicit_completion_exclamation(
        self, turn_manager: TurnManager
    ) -> None:
        """Exclamation mark indicates completion."""
        assert turn_manager._has_explicit_completion("Thank you!")

    def test_has_explicit_completion_please(self, turn_manager: TurnManager) -> None:
        """'please' indicates completion."""
        assert turn_manager._has_explicit_completion("Help me please")

    def test_has_explicit_completion_thanks(self, turn_manager: TurnManager) -> None:
        """'thanks' indicates completion."""
        assert turn_manager._has_explicit_completion("Send it thanks")

    def test_has_explicit_completion_thank_you(self, turn_manager: TurnManager) -> None:
        """'thank you' indicates completion."""
        assert turn_manager._has_explicit_completion("Done thank you")

    def test_has_explicit_completion_no_signal(self, turn_manager: TurnManager) -> None:
        """No completion signals returns False."""
        assert not turn_manager._has_explicit_completion("I need help")


class TestSuggestWaitMs:
    """Tests for wait time calculation."""

    def test_suggest_wait_ms_uses_channel_default(
        self, turn_manager: TurnManager
    ) -> None:
        """Uses channel default as baseline."""
        wait = turn_manager.suggest_wait_ms("Hello", channel="whatsapp")
        assert wait > 0

    def test_suggest_wait_ms_greeting_only_increases_wait(
        self, turn_manager: TurnManager
    ) -> None:
        """Greeting-only messages increase wait time."""
        greeting_wait = turn_manager.suggest_wait_ms("hi", channel="web")
        normal_wait = turn_manager.suggest_wait_ms("I need help", channel="web")

        assert greeting_wait > normal_wait

    def test_suggest_wait_ms_explicit_completion_reduces_wait(
        self, turn_manager: TurnManager
    ) -> None:
        """Explicit completion markers reduce wait time."""
        incomplete_wait = turn_manager.suggest_wait_ms("I need help", channel="web")
        complete_wait = turn_manager.suggest_wait_ms("I need help.", channel="web")

        assert complete_wait < incomplete_wait

    def test_suggest_wait_ms_respects_min_wait(
        self, custom_turn_manager: TurnManager
    ) -> None:
        """Wait time respects minimum."""
        wait = custom_turn_manager.suggest_wait_ms(
            "Short complete message.",
            channel="api",
        )
        assert wait >= custom_turn_manager._min_wait_ms

    def test_suggest_wait_ms_respects_max_wait(
        self, turn_manager: TurnManager
    ) -> None:
        """Wait time respects maximum."""
        wait = turn_manager.suggest_wait_ms(
            "order #",
            channel="whatsapp",
            messages_in_turn=1,
        )
        assert wait <= turn_manager._max_wait_ms

    def test_suggest_wait_ms_multiple_messages_reduces_wait(
        self, turn_manager: TurnManager
    ) -> None:
        """Multiple messages reduce wait time (user is typing)."""
        first_wait = turn_manager.suggest_wait_ms(
            "I need", channel="web", messages_in_turn=1
        )
        second_wait = turn_manager.suggest_wait_ms(
            "help", channel="web", messages_in_turn=2
        )
        third_wait = turn_manager.suggest_wait_ms(
            "please", channel="web", messages_in_turn=3
        )

        assert second_wait < first_wait
        assert third_wait < second_wait

    def test_suggest_wait_ms_unknown_channel_uses_default(
        self, turn_manager: TurnManager
    ) -> None:
        """Unknown channel uses fallback default."""
        wait = turn_manager.suggest_wait_ms("Hello", channel="unknown_channel")
        assert wait > 0

    def test_suggest_wait_ms_custom_channel_default(
        self, custom_turn_manager: TurnManager
    ) -> None:
        """Custom channel defaults are used."""
        wait = custom_turn_manager.suggest_wait_ms("Hello", channel="custom")
        assert wait > 0


class TestAdaptToUserCadence:
    """Tests for user cadence adaptation."""

    def test_adapt_to_user_cadence_insufficient_samples(
        self, turn_manager: TurnManager
    ) -> None:
        """Returns base wait when insufficient samples."""
        stats = UserCadenceStats(
            inter_message_p50_ms=800,
            inter_message_p95_ms=1500,
            sample_count=3,  # Too few
        )

        base_wait = 1000
        adapted = turn_manager._adapt_to_user_cadence(base_wait, stats)
        assert adapted == base_wait

    def test_adapt_to_user_cadence_blends_with_user_history(
        self, turn_manager: TurnManager
    ) -> None:
        """Blends base wait with user history."""
        stats = UserCadenceStats(
            inter_message_p50_ms=500,
            inter_message_p95_ms=1500,
            sample_count=10,
        )

        base_wait = 1000
        adapted = turn_manager._adapt_to_user_cadence(base_wait, stats)

        user_typical = (500 + 1500) // 2  # 1000
        expected = int(base_wait * 0.6 + user_typical * 0.4)  # 1000
        assert adapted == expected

    def test_adapt_to_user_cadence_fast_typer(
        self, turn_manager: TurnManager
    ) -> None:
        """Fast typer reduces wait time."""
        stats = UserCadenceStats(
            inter_message_p50_ms=200,
            inter_message_p95_ms=400,
            sample_count=10,
        )

        base_wait = 1000
        adapted = turn_manager._adapt_to_user_cadence(base_wait, stats)

        user_typical = (200 + 400) // 2  # 300
        expected = int(base_wait * 0.6 + user_typical * 0.4)  # 720
        assert adapted < base_wait

    def test_adapt_to_user_cadence_slow_typer(
        self, turn_manager: TurnManager
    ) -> None:
        """Slow typer increases wait time."""
        stats = UserCadenceStats(
            inter_message_p50_ms=2000,
            inter_message_p95_ms=4000,
            sample_count=10,
        )

        base_wait = 1000
        adapted = turn_manager._adapt_to_user_cadence(base_wait, stats)

        user_typical = (2000 + 4000) // 2  # 3000
        expected = int(base_wait * 0.6 + user_typical * 0.4)  # 1800
        assert adapted > base_wait

    def test_adapt_to_user_cadence_no_stats(
        self, turn_manager: TurnManager
    ) -> None:
        """Returns base wait when no stats provided."""
        base_wait = 1000
        adapted = turn_manager._adapt_to_user_cadence(base_wait, None)
        assert adapted == base_wait


class TestGetHintAdjustment:
    """Tests for hint-based adjustments."""

    def test_get_hint_adjustment_no_hint(self, turn_manager: TurnManager) -> None:
        """No hint returns 0 adjustment."""
        adjustment = turn_manager._get_hint_adjustment(None)
        assert adjustment == 0

    def test_get_hint_adjustment_awaiting_required_field(
        self, turn_manager: TurnManager
    ) -> None:
        """Awaiting required field increases wait significantly."""
        hint = AccumulationHint(awaiting_required_field=True)
        adjustment = turn_manager._get_hint_adjustment(hint)
        assert adjustment == 1000

    def test_get_hint_adjustment_expects_followup(
        self, turn_manager: TurnManager
    ) -> None:
        """Expecting followup increases wait moderately."""
        hint = AccumulationHint(expects_followup=True)
        adjustment = turn_manager._get_hint_adjustment(hint)
        assert adjustment == 500

    def test_get_hint_adjustment_high_confidence_complete(
        self, turn_manager: TurnManager
    ) -> None:
        """High confidence of completion reduces wait."""
        hint = AccumulationHint(input_complete_confidence=0.9)
        adjustment = turn_manager._get_hint_adjustment(hint)
        assert adjustment == -200

    def test_get_hint_adjustment_low_confidence_complete(
        self, turn_manager: TurnManager
    ) -> None:
        """Low confidence of completion doesn't adjust."""
        hint = AccumulationHint(input_complete_confidence=0.5)
        adjustment = turn_manager._get_hint_adjustment(hint)
        assert adjustment == 0

    def test_get_hint_adjustment_combined_signals(
        self, turn_manager: TurnManager
    ) -> None:
        """First matching signal takes precedence."""
        hint = AccumulationHint(
            awaiting_required_field=True,
            input_complete_confidence=0.9,
        )
        # awaiting_required_field checked first
        adjustment = turn_manager._get_hint_adjustment(hint)
        assert adjustment == 1000


class TestClamp:
    """Tests for value clamping."""

    def test_clamp_below_min(self, turn_manager: TurnManager) -> None:
        """Values below min are clamped to min."""
        clamped = turn_manager._clamp(100)
        assert clamped == turn_manager._min_wait_ms

    def test_clamp_above_max(self, turn_manager: TurnManager) -> None:
        """Values above max are clamped to max."""
        clamped = turn_manager._clamp(5000)
        assert clamped == turn_manager._max_wait_ms

    def test_clamp_within_range(self, turn_manager: TurnManager) -> None:
        """Values within range are unchanged."""
        value = 1000
        clamped = turn_manager._clamp(value)
        assert clamped == value


class TestIntegration:
    """Integration tests for TurnManager."""

    def test_suggest_wait_ms_greeting_followed_by_request(
        self, turn_manager: TurnManager
    ) -> None:
        """Greeting increases wait, multiple messages reduce it."""
        greeting_wait = turn_manager.suggest_wait_ms("hi", channel="whatsapp")
        second_wait = turn_manager.suggest_wait_ms(
            "I need help", channel="whatsapp", messages_in_turn=2
        )

        assert greeting_wait > second_wait

    def test_suggest_wait_ms_with_all_signals(
        self, turn_manager: TurnManager
    ) -> None:
        """All signals combine correctly."""
        hint = AccumulationHint(awaiting_required_field=True)
        stats = UserCadenceStats(
            inter_message_p50_ms=800,
            inter_message_p95_ms=1200,
            sample_count=10,
        )

        wait = turn_manager.suggest_wait_ms(
            "What is your order number?",
            channel="whatsapp",
            user_cadence=stats,
            previous_hint=hint,
        )

        assert wait > 0
        assert wait <= turn_manager._max_wait_ms
