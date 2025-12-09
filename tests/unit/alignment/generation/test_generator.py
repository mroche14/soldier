"""Unit tests for ResponseGenerator."""

from typing import Any
from uuid import uuid4

import pytest

from soldier.alignment.context.situation_snapshot import SituationSnapshot
from soldier.alignment.context.models import Sentiment, Turn, Urgency
from soldier.alignment.execution.models import ToolResult
from soldier.alignment.filtering.models import MatchedRule
from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.generation.models import GenerationResult
from soldier.alignment.models.enums import TemplateResponseMode
from soldier.alignment.generation.prompt_builder import PromptBuilder
from soldier.alignment.models import Rule
from soldier.alignment.models.template import Template
from soldier.providers.llm import LLMExecutor, LLMMessage, LLMResponse


class MockLLMExecutor(LLMExecutor):
    """Mock LLM executor for testing response generation."""

    def __init__(
        self,
        response: str = "This is a test response.",
        model: str = "mock-model",
        raise_error: bool = False,
    ) -> None:
        super().__init__(model="mock/test", step_name="generation")
        self._response = response
        self._model_name = model
        self._raise_error = raise_error
        self.generate_calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        self.generate_calls.append(messages)

        if self._raise_error:
            raise RuntimeError("LLM error")

        return LLMResponse(
            content=self._response,
            model=self._model_name,
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )


def create_rule(
    name: str = "Test Rule",
    template_ids: list[str] | None = None,
) -> Rule:
    """Create a test rule."""
    return Rule(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name=name,
        condition_text="When user asks",
        action_text="Respond helpfully",
        attached_template_ids=template_ids or [],
    )


def create_matched_rule(
    name: str = "Test Rule",
    template_ids: list[str] | None = None,
) -> MatchedRule:
    """Create a test MatchedRule."""
    rule = create_rule(name=name, template_ids=template_ids)
    return MatchedRule(
        rule=rule,
        match_score=1.0,
        relevance_score=0.9,
        reasoning="Test match",
    )


def create_template(
    template_id: str | None = None,
    name: str = "Test Template",
    text: str = "Hello {name}, how can I help?",
    mode: TemplateResponseMode = TemplateResponseMode.SUGGEST,
) -> Template:
    """Create a test template."""
    tid = uuid4() if template_id is None else template_id
    return Template(
        id=tid,
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name=name,
        text=text,
        mode=mode,
    )


class TestResponseGenerator:
    """Tests for ResponseGenerator class."""

    @pytest.fixture
    def llm_executor(self) -> MockLLMExecutor:
        return MockLLMExecutor(response="I can help you with that!")

    @pytest.fixture
    def generator(self, llm_executor: MockLLMExecutor) -> ResponseGenerator:
        return ResponseGenerator(llm_executor=llm_executor)

    @pytest.fixture
    def snapshot(self) -> SituationSnapshot:
        return SituationSnapshot(
            message="I want to return my order",
            new_intent_label="return order",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        )

    @pytest.fixture
    def matched_rules(self) -> list[MatchedRule]:
        return [
            create_matched_rule(name="Return Policy"),
            create_matched_rule(name="Order Info"),
        ]

    # Test initialization

    def test_generator_can_be_created(
        self,
        llm_executor: MockLLMExecutor,
    ) -> None:
        """Test that ResponseGenerator can be instantiated."""
        generator = ResponseGenerator(llm_executor=llm_executor)
        assert generator is not None

    def test_generator_with_custom_prompt_builder(
        self,
        llm_executor: MockLLMExecutor,
    ) -> None:
        """Test creating generator with custom prompt builder."""
        custom_builder = PromptBuilder(max_history_turns=5)
        generator = ResponseGenerator(
            llm_executor=llm_executor,
            prompt_builder=custom_builder,
        )
        assert generator._prompt_builder == custom_builder

    def test_generator_with_custom_defaults(
        self,
        llm_executor: MockLLMExecutor,
    ) -> None:
        """Test creating generator with custom defaults."""
        generator = ResponseGenerator(
            llm_executor=llm_executor,
            default_temperature=0.5,
            default_max_tokens=512,
        )
        assert generator._default_temperature == 0.5
        assert generator._default_max_tokens == 512

    # Test basic generation

    @pytest.mark.asyncio
    async def test_generate_returns_result(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
        matched_rules: list[MatchedRule],
    ) -> None:
        """Test that generate returns a GenerationResult."""
        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=matched_rules,
        )

        assert isinstance(result, GenerationResult)
        assert result.response == "I can help you with that!"

    @pytest.mark.asyncio
    async def test_generate_includes_model_info(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that result includes model information."""
        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
        )

        assert result.model == "mock-model"

    @pytest.mark.asyncio
    async def test_generate_includes_token_usage(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that result includes token usage."""
        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
        )

        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50

    @pytest.mark.asyncio
    async def test_generate_records_timing(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that generation time is recorded."""
        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
        )

        assert result.generation_time_ms > 0

    @pytest.mark.asyncio
    async def test_generate_includes_prompt_preview(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that result includes prompt preview."""
        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
        )

        assert result.prompt_preview is not None
        assert len(result.prompt_preview) <= 200

    # Test with history

    @pytest.mark.asyncio
    async def test_generate_with_history(
        self,
        generator: ResponseGenerator,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test generation includes history in messages."""
        history = [
            Turn(role="user", content="Hello"),
            Turn(role="assistant", content="Hi there!"),
        ]

        await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
            history=history,
        )

        # Check that LLM received history
        assert len(llm_executor.generate_calls) == 1
        messages = llm_executor.generate_calls[0]
        # Should have system + history + current message
        assert len(messages) >= 4

    # Test with tool results

    @pytest.mark.asyncio
    async def test_generate_with_tool_results(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test generation includes tool results."""
        tool_results = [
            ToolResult(
                tool_name="order_lookup",
                rule_id=uuid4(),
                success=True,
                outputs={"status": "shipped"},
                execution_time_ms=50.0,
            ),
        ]

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
            tool_results=tool_results,
        )

        # Tool results should be in the prompt (via prompt_preview)
        assert result.prompt_preview is not None

    # Test with memory context

    @pytest.mark.asyncio
    async def test_generate_with_memory_context(
        self,
        generator: ResponseGenerator,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test generation includes memory context."""
        memory_context = "User previously ordered item #123."

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[],
            memory_context=memory_context,
        )

        assert isinstance(result, GenerationResult)

    # Test template modes

    @pytest.mark.asyncio
    async def test_generate_exclusive_template_skips_llm(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that EXCLUSIVE template mode skips LLM."""
        template_id = str(uuid4())
        template = create_template(
            template_id=template_id,
            text="This is the exact template response.",
            mode=TemplateResponseMode.EXCLUSIVE,
        )

        matched_rule = create_matched_rule(
            name="Template Rule",
            template_ids=[template_id],
        )

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[matched_rule],
            templates=[template],
        )

        # Should use template, not LLM
        assert result.response == "This is the exact template response."
        assert result.template_mode == TemplateResponseMode.EXCLUSIVE
        assert str(result.template_used) == template_id
        # LLM should not have been called
        assert len(llm_executor.generate_calls) == 0

    @pytest.mark.asyncio
    async def test_generate_exclusive_template_resolves_variables(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that EXCLUSIVE template resolves variables."""
        template_id = str(uuid4())
        template = create_template(
            template_id=template_id,
            text="Hello {customer_name}, your order {order_id} is ready.",
            mode=TemplateResponseMode.EXCLUSIVE,
        )

        matched_rule = create_matched_rule(template_ids=[template_id])

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[matched_rule],
            templates=[template],
            variables={"customer_name": "John", "order_id": "12345"},
        )

        assert result.response == "Hello John, your order 12345 is ready."

    @pytest.mark.asyncio
    async def test_generate_suggest_template_uses_llm(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that SUGGEST template mode still uses LLM."""
        template_id = str(uuid4())
        template = create_template(
            template_id=template_id,
            text="Suggested response template.",
            mode=TemplateResponseMode.SUGGEST,
        )

        matched_rule = create_matched_rule(template_ids=[template_id])

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[matched_rule],
            templates=[template],
        )

        # Should use LLM response
        assert result.response == "I can help you with that!"
        # LLM should have been called
        assert len(llm_executor.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_generate_fallback_template_uses_llm(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Fallback templates are deferred to enforcement, not generation."""
        template_id = str(uuid4())
        template = create_template(
            template_id=template_id,
            text="Fallback response.",
            mode=TemplateResponseMode.FALLBACK,
        )

        matched_rule = create_matched_rule(template_ids=[template_id])

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[matched_rule],
            templates=[template],
        )

        assert result.response == "I can help you with that!"
        assert result.template_mode is None
        assert len(llm_executor.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_generate_no_matching_template(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test generation when rule has template ID but template not provided."""
        matched_rule = create_matched_rule(
            template_ids=[str(uuid4())],  # Non-existent template
        )

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[matched_rule],
            templates=[],  # No templates provided
        )

        # Should fall back to LLM
        assert result.response == "I can help you with that!"
        assert result.template_mode is None

    # Test multiple rules with templates

    @pytest.mark.asyncio
    async def test_generate_first_exclusive_template_wins(
        self,
        llm_executor: MockLLMExecutor,
        snapshot: SituationSnapshot,
    ) -> None:
        """Test that first exclusive template is used."""
        template1_id = str(uuid4())
        template2_id = str(uuid4())

        template1 = create_template(
            template_id=template1_id,
            text="First exclusive template.",
            mode=TemplateResponseMode.EXCLUSIVE,
        )
        template2 = create_template(
            template_id=template2_id,
            text="Second exclusive template.",
            mode=TemplateResponseMode.EXCLUSIVE,
        )

        rule1 = create_matched_rule(template_ids=[template1_id])
        rule2 = create_matched_rule(template_ids=[template2_id])

        generator = ResponseGenerator(llm_executor=llm_executor)

        result = await generator.generate(
            snapshot=snapshot,
            matched_rules=[rule1, rule2],
            templates=[template1, template2],
        )

        # First exclusive template should win
        assert result.response == "First exclusive template."


class TestGenerationResult:
    """Tests for GenerationResult model."""

    def test_basic_result(self) -> None:
        """Test creating a basic result."""
        result = GenerationResult(
            response="Hello there!",
            generation_time_ms=100.5,
        )
        assert result.response == "Hello there!"
        assert result.generation_time_ms == 100.5

    def test_result_with_all_fields(self) -> None:
        """Test result with all optional fields."""
        template_id = uuid4()
        result = GenerationResult(
            response="Template response",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
            generation_time_ms=200.0,
            template_used=template_id,
            template_mode=TemplateResponseMode.EXCLUSIVE,
            prompt_preview="System: You are...",
        )

        assert result.model == "gpt-4"
        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.template_used == template_id
        assert result.template_mode == TemplateResponseMode.EXCLUSIVE
        assert result.prompt_preview == "System: You are..."

    def test_result_defaults(self) -> None:
        """Test result default values."""
        result = GenerationResult(
            response="Test",
            generation_time_ms=0,
        )

        assert result.model is None
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.template_used is None
        assert result.template_mode is None
        assert result.prompt_preview is None


class TestTemplateResponseMode:
    """Tests for TemplateResponseMode enum."""

    def test_all_modes(self) -> None:
        """Test all template mode values."""
        assert TemplateResponseMode.EXCLUSIVE.value == "EXCLUSIVE"
        assert TemplateResponseMode.SUGGEST.value == "SUGGEST"
        assert TemplateResponseMode.FALLBACK.value == "FALLBACK"

    def test_mode_comparison(self) -> None:
        """Test mode enum comparison."""
        mode1 = TemplateResponseMode.EXCLUSIVE
        mode2 = TemplateResponseMode.EXCLUSIVE
        mode3 = TemplateResponseMode.SUGGEST

        assert mode1 == mode2
        assert mode1 != mode3
