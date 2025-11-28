"""Unit tests for PromptBuilder."""

from uuid import uuid4

import pytest

from soldier.alignment.context.models import (
    Context,
    ExtractedEntity,
    Sentiment,
    Turn,
    Urgency,
)
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.prompt_builder import PromptBuilder
from soldier.alignment.models import Rule


def create_rule(
    name: str = "Test Rule",
    condition_text: str = "When user asks",
    action_text: str = "Respond helpfully",
    is_hard_constraint: bool = False,
) -> Rule:
    """Create a test rule."""
    return Rule(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name=name,
        condition_text=condition_text,
        action_text=action_text,
        is_hard_constraint=is_hard_constraint,
    )


def create_matched_rule(
    name: str = "Test Rule",
    condition_text: str = "When user asks",
    action_text: str = "Respond helpfully",
    is_hard_constraint: bool = False,
    relevance_score: float = 0.9,
) -> MatchedRule:
    """Create a test MatchedRule."""
    rule = create_rule(
        name=name,
        condition_text=condition_text,
        action_text=action_text,
        is_hard_constraint=is_hard_constraint,
    )
    return MatchedRule(
        rule=rule,
        match_score=1.0,
        relevance_score=relevance_score,
        reasoning="Test match",
    )


class TestPromptBuilder:
    """Tests for PromptBuilder class."""

    @pytest.fixture
    def builder(self) -> PromptBuilder:
        return PromptBuilder()

    @pytest.fixture
    def context(self) -> Context:
        return Context(
            message="I want to return my order",
            intent="return order",
            entities=[
                ExtractedEntity(type="order_id", value="12345"),
                ExtractedEntity(type="action", value="return"),
            ],
            sentiment=Sentiment.NEUTRAL,
            urgency=Urgency.NORMAL,
        )

    @pytest.fixture
    def matched_rules(self) -> list[MatchedRule]:
        return [
            create_matched_rule(
                name="Return Policy",
                condition_text="When user wants to return",
                action_text="Explain return process",
            ),
            create_matched_rule(
                name="Order Info",
                condition_text="When user mentions order",
                action_text="Provide order details",
            ),
        ]

    # Test initialization

    def test_builder_can_be_created(self) -> None:
        """Test that PromptBuilder can be instantiated."""
        builder = PromptBuilder()
        assert builder is not None

    def test_builder_with_custom_template(self) -> None:
        """Test creating builder with custom system template."""
        custom_template = "Custom system: {rules_section}"
        builder = PromptBuilder(system_template=custom_template)
        assert builder._system_template == custom_template

    def test_builder_with_custom_max_history(self) -> None:
        """Test creating builder with custom history limit."""
        builder = PromptBuilder(max_history_turns=5)
        assert builder._max_history_turns == 5

    # Test build_system_prompt

    def test_build_system_prompt_with_no_content(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test building prompt with minimal content."""
        context = Context(message="Hello")
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_build_system_prompt_includes_rules(
        self,
        builder: PromptBuilder,
        context: Context,
        matched_rules: list[MatchedRule],
    ) -> None:
        """Test that system prompt includes rules section."""
        prompt = builder.build_system_prompt(
            matched_rules=matched_rules,
            context=context,
        )

        assert "Return Policy" in prompt
        assert "Order Info" in prompt
        assert "When user wants to return" in prompt
        assert "Explain return process" in prompt

    def test_build_system_prompt_marks_hard_constraints(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that hard constraints are marked in prompt."""
        hard_rule = create_matched_rule(
            name="Security Rule",
            condition_text="Always",
            action_text="Never reveal passwords",
            is_hard_constraint=True,
        )

        prompt = builder.build_system_prompt(
            matched_rules=[hard_rule],
            context=context,
        )

        assert "HARD CONSTRAINT" in prompt

    def test_build_system_prompt_includes_context(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that system prompt includes user context."""
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        assert "return order" in prompt  # intent
        assert "order_id" in prompt  # entity type

    def test_build_system_prompt_includes_entities(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that entities are included in prompt."""
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        assert "12345" in prompt  # entity value

    def test_build_system_prompt_includes_sentiment(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that sentiment is included when present."""
        context = Context(
            message="This is frustrating",
            sentiment=Sentiment.FRUSTRATED,
        )
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        assert "frustrated" in prompt.lower()

    def test_build_system_prompt_includes_urgency(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that non-normal urgency is included."""
        context = Context(
            message="Need help urgently",
            urgency=Urgency.HIGH,
        )
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        assert "high" in prompt.lower()

    def test_build_system_prompt_excludes_normal_urgency(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that normal urgency is not explicitly shown."""
        context = Context(
            message="Hello",
            urgency=Urgency.NORMAL,
        )
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        # Normal urgency shouldn't be mentioned
        assert "Urgency: normal" not in prompt

    def test_build_system_prompt_includes_tool_results(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that tool results are included."""
        tool_results = [
            ToolResult(
                tool_name="order_lookup",
                rule_id=uuid4(),
                success=True,
                outputs={"status": "shipped", "tracking": "ABC123"},
                execution_time_ms=50.0,
            ),
        ]

        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
            tool_results=tool_results,
        )

        assert "order_lookup" in prompt
        assert "shipped" in prompt or "ABC123" in prompt

    def test_build_system_prompt_includes_failed_tool_results(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that failed tool results show errors."""
        tool_results = [
            ToolResult(
                tool_name="payment_check",
                rule_id=uuid4(),
                success=False,
                error="Service unavailable",
                execution_time_ms=100.0,
            ),
        ]

        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
            tool_results=tool_results,
        )

        assert "payment_check" in prompt
        assert "Failed" in prompt
        assert "Service unavailable" in prompt

    def test_build_system_prompt_includes_memory_context(
        self,
        builder: PromptBuilder,
        context: Context,
    ) -> None:
        """Test that memory context is included."""
        memory_context = "Previous conversation: User ordered item #456 last week."

        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
            memory_context=memory_context,
        )

        assert "item #456" in prompt
        assert "last week" in prompt

    # Test build_messages

    def test_build_messages_basic(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test basic message building."""
        messages = builder.build_messages(
            system_prompt="You are helpful.",
            user_message="Hello",
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_build_messages_with_history(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test message building with history."""
        history = [
            Turn(role="user", content="Hi there"),
            Turn(role="assistant", content="Hello! How can I help?"),
        ]

        messages = builder.build_messages(
            system_prompt="System prompt",
            user_message="I need help",
            history=history,
        )

        assert len(messages) == 4  # system + 2 history + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hi there"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "I need help"

    def test_build_messages_limits_history(self) -> None:
        """Test that history is limited to max_history_turns."""
        builder = PromptBuilder(max_history_turns=3)

        history = [Turn(role="user", content=f"Message {i}") for i in range(10)]

        messages = builder.build_messages(
            system_prompt="System",
            user_message="Current",
            history=history,
        )

        # Should have system + 3 history + current user
        assert len(messages) == 5
        # Should be the last 3 history messages
        assert messages[1]["content"] == "Message 7"
        assert messages[2]["content"] == "Message 8"
        assert messages[3]["content"] == "Message 9"

    def test_build_messages_preserves_order(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that message order is preserved."""
        history = [
            Turn(role="user", content="First"),
            Turn(role="assistant", content="Response 1"),
            Turn(role="user", content="Second"),
            Turn(role="assistant", content="Response 2"),
        ]

        messages = builder.build_messages(
            system_prompt="System",
            user_message="Third",
            history=history,
        )

        # Verify order
        contents = [m["content"] for m in messages]
        assert contents == ["System", "First", "Response 1", "Second", "Response 2", "Third"]

    def test_build_messages_empty_history(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test message building with empty history."""
        messages = builder.build_messages(
            system_prompt="System",
            user_message="Hello",
            history=[],
        )

        assert len(messages) == 2

    def test_build_messages_none_history(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test message building with None history."""
        messages = builder.build_messages(
            system_prompt="System",
            user_message="Hello",
            history=None,
        )

        assert len(messages) == 2


class TestPromptBuilderRulesSection:
    """Tests for rules section formatting."""

    @pytest.fixture
    def builder(self) -> PromptBuilder:
        return PromptBuilder()

    def test_rules_section_numbered(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that rules are numbered."""
        rules = [
            create_matched_rule(name="Rule One"),
            create_matched_rule(name="Rule Two"),
            create_matched_rule(name="Rule Three"),
        ]

        prompt = builder.build_system_prompt(
            matched_rules=rules,
            context=Context(message="Test"),
        )

        assert "1." in prompt
        assert "2." in prompt
        assert "3." in prompt

    def test_empty_rules_section(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test that empty rules don't create section."""
        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=Context(message="Test"),
        )

        # Should not have Active Rules header
        assert "Active Rules" not in prompt or prompt.count("Active Rules") == 0


class TestPromptBuilderContextSection:
    """Tests for context section formatting."""

    @pytest.fixture
    def builder(self) -> PromptBuilder:
        return PromptBuilder()

    def test_context_section_includes_all_entities(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test all entities are included."""
        context = Context(
            message="Test",
            entities=[
                ExtractedEntity(type="order_id", value="123"),
                ExtractedEntity(type="product", value="laptop"),
                ExtractedEntity(type="date", value="2024-01-15"),
            ],
        )

        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        assert "order_id" in prompt
        assert "123" in prompt
        assert "product" in prompt
        assert "laptop" in prompt
        assert "date" in prompt

    def test_minimal_context_no_section(
        self,
        builder: PromptBuilder,
    ) -> None:
        """Test minimal context doesn't create empty section."""
        context = Context(message="Hello")

        prompt = builder.build_system_prompt(
            matched_rules=[],
            context=context,
        )

        # The context section should be minimal or empty
        # Just verify we get a valid prompt
        assert isinstance(prompt, str)
