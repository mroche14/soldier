"""Unit tests for ContextExtractor."""

from datetime import datetime
from typing import Any

import pytest

from soldier.alignment.context.extractor import ContextExtractor
from soldier.alignment.context.models import (
    Context,
    ExtractedEntity,
    ScenarioSignal,
    Sentiment,
    Turn,
    Urgency,
)
from soldier.providers.embedding import EmbeddingProvider, EmbeddingResponse
from soldier.providers.llm import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing context extraction."""

    def __init__(
        self,
        response_json: dict[str, Any] | None = None,
        raise_error: bool = False,
    ) -> None:
        self._response_json = response_json or {
            "intent": "get help",
            "entities": [],
            "sentiment": "neutral",
            "topic": "support",
            "urgency": "normal",
            "scenario_signal": "continue",
        }
        self._raise_error = raise_error
        self.generate_calls: list[list[LLMMessage]] = []

    @property
    def provider_name(self) -> str:
        return "mock_llm"

    async def generate(
        self,
        messages: list[LLMMessage],
        **kwargs: Any,
    ) -> LLMResponse:
        self.generate_calls.append(messages)
        if self._raise_error:
            raise RuntimeError("LLM error")

        import json

        return LLMResponse(
            content=json.dumps(self._response_json),
            model="mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )

    def generate_stream(self, messages: list[LLMMessage], **kwargs: Any):
        raise NotImplementedError("Streaming not needed for tests")


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dims: int = 1536) -> None:
        self._dims = dims
        self.embed_calls: list[list[str]] = []

    @property
    def provider_name(self) -> str:
        return "mock_embedding"

    @property
    def dimensions(self) -> int:
        return self._dims

    async def embed(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> EmbeddingResponse:
        self.embed_calls.append(texts)
        embeddings = [[0.1 * (i + 1)] * self._dims for i, _ in enumerate(texts)]
        return EmbeddingResponse(
            embeddings=embeddings,
            model="mock-embedding-model",
            dimensions=self._dims,
        )

    async def embed_single(self, text: str, **kwargs: Any) -> list[float]:
        response = await self.embed([text], **kwargs)
        return response.embeddings[0]


class TestContextExtractor:
    """Tests for ContextExtractor class."""

    @pytest.fixture
    def llm_provider(self) -> MockLLMProvider:
        return MockLLMProvider(
            response_json={
                "intent": "return damaged order",
                "entities": [{"type": "order_id", "value": "12345"}],
                "sentiment": "negative",
                "topic": "returns",
                "urgency": "high",
                "scenario_signal": "start",
            }
        )

    @pytest.fixture
    def embedding_provider(self) -> MockEmbeddingProvider:
        return MockEmbeddingProvider(dims=1536)

    @pytest.fixture
    def extractor(
        self,
        llm_provider: MockLLMProvider,
        embedding_provider: MockEmbeddingProvider,
    ) -> ContextExtractor:
        return ContextExtractor(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )

    @pytest.fixture
    def sample_history(self) -> list[Turn]:
        return [
            Turn(role="assistant", content="Hello! How can I help you today?"),
            Turn(role="user", content="I have a problem with my order"),
            Turn(role="assistant", content="I'm sorry to hear that. What's wrong?"),
        ]

    # Test initialization

    def test_extractor_can_be_created(
        self,
        llm_provider: MockLLMProvider,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test that ContextExtractor can be instantiated."""
        extractor = ContextExtractor(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
        )
        assert extractor is not None

    def test_extractor_with_custom_template(
        self,
        llm_provider: MockLLMProvider,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test creating extractor with custom prompt template."""
        custom_template = "Custom template: {message} {history}"
        extractor = ContextExtractor(
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            prompt_template=custom_template,
        )
        assert extractor._prompt_template == custom_template

    # Test disabled mode

    @pytest.mark.asyncio
    async def test_extract_disabled_mode_returns_minimal_context(
        self,
        extractor: ContextExtractor,
    ) -> None:
        """Test extraction in disabled mode returns message only."""
        context = await extractor.extract(
            message="Hello world",
            history=[],
            mode="disabled",
        )

        assert context.message == "Hello world"
        assert context.embedding is None
        assert context.intent is None
        assert context.entities == []
        assert context.turn_count == 0

    @pytest.mark.asyncio
    async def test_extract_disabled_mode_counts_history(
        self,
        extractor: ContextExtractor,
        sample_history: list[Turn],
    ) -> None:
        """Test disabled mode includes turn count."""
        context = await extractor.extract(
            message="Test",
            history=sample_history,
            mode="disabled",
        )

        assert context.turn_count == len(sample_history)

    # Test embedding_only mode

    @pytest.mark.asyncio
    async def test_extract_embedding_only_mode_returns_embedding(
        self,
        extractor: ContextExtractor,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test embedding_only mode generates embedding."""
        context = await extractor.extract(
            message="I need help",
            history=[],
            mode="embedding_only",
        )

        assert context.message == "I need help"
        assert context.embedding is not None
        assert len(context.embedding) == embedding_provider.dimensions
        assert context.intent is None  # No LLM extraction

    @pytest.mark.asyncio
    async def test_extract_embedding_only_mode_does_not_call_llm(
        self,
        extractor: ContextExtractor,
        llm_provider: MockLLMProvider,
    ) -> None:
        """Test embedding_only mode doesn't use LLM."""
        await extractor.extract(
            message="Test",
            history=[],
            mode="embedding_only",
        )

        assert len(llm_provider.generate_calls) == 0

    # Test LLM mode

    @pytest.mark.asyncio
    async def test_extract_llm_mode_full_extraction(
        self,
        extractor: ContextExtractor,
    ) -> None:
        """Test LLM mode performs full extraction."""
        context = await extractor.extract(
            message="I want to return my damaged order #12345",
            history=[],
            mode="llm",
        )

        assert context.message == "I want to return my damaged order #12345"
        assert context.embedding is not None
        assert context.intent == "return damaged order"
        assert len(context.entities) == 1
        assert context.entities[0].type == "order_id"
        assert context.entities[0].value == "12345"
        assert context.sentiment == Sentiment.NEGATIVE
        assert context.urgency == Urgency.HIGH
        assert context.scenario_signal == ScenarioSignal.START

    @pytest.mark.asyncio
    async def test_extract_llm_mode_calls_both_providers(
        self,
        extractor: ContextExtractor,
        llm_provider: MockLLMProvider,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test LLM mode calls both embedding and LLM providers."""
        await extractor.extract(
            message="Test message",
            history=[],
            mode="llm",
        )

        assert len(embedding_provider.embed_calls) == 1
        assert len(llm_provider.generate_calls) == 1

    @pytest.mark.asyncio
    async def test_extract_llm_mode_with_history(
        self,
        extractor: ContextExtractor,
        sample_history: list[Turn],
    ) -> None:
        """Test LLM mode includes history in extraction."""
        context = await extractor.extract(
            message="It's broken",
            history=sample_history,
            mode="llm",
        )

        assert context.turn_count == len(sample_history)
        # recent_topics should be extracted from history
        assert "order" in context.recent_topics

    # Test validation

    @pytest.mark.asyncio
    async def test_extract_empty_message_raises_error(
        self,
        extractor: ContextExtractor,
    ) -> None:
        """Test that empty message raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await extractor.extract(message="", history=[], mode="llm")

    @pytest.mark.asyncio
    async def test_extract_whitespace_message_raises_error(
        self,
        extractor: ContextExtractor,
    ) -> None:
        """Test that whitespace-only message raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            await extractor.extract(message="   \n\t  ", history=[], mode="llm")

    # Test parsing edge cases

    @pytest.mark.asyncio
    async def test_extract_handles_invalid_sentiment(
        self,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test that invalid sentiment defaults gracefully."""
        llm = MockLLMProvider(
            response_json={
                "intent": "test",
                "sentiment": "invalid_sentiment",
                "urgency": "normal",
            }
        )
        extractor = ContextExtractor(
            llm_provider=llm,
            embedding_provider=embedding_provider,
        )

        context = await extractor.extract(message="Test", history=[], mode="llm")
        assert context.sentiment is None

    @pytest.mark.asyncio
    async def test_extract_handles_invalid_urgency(
        self,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test that invalid urgency defaults to NORMAL."""
        llm = MockLLMProvider(
            response_json={
                "intent": "test",
                "urgency": "invalid_urgency",
            }
        )
        extractor = ContextExtractor(
            llm_provider=llm,
            embedding_provider=embedding_provider,
        )

        context = await extractor.extract(message="Test", history=[], mode="llm")
        assert context.urgency == Urgency.NORMAL

    @pytest.mark.asyncio
    async def test_extract_handles_malformed_entities(
        self,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test that malformed entities are skipped."""
        llm = MockLLMProvider(
            response_json={
                "intent": "test",
                "entities": [
                    {"type": "valid", "value": "123"},
                    {"missing": "fields"},  # Invalid - missing type/value
                    "not_a_dict",  # Invalid - not a dict
                ],
            }
        )
        extractor = ContextExtractor(
            llm_provider=llm,
            embedding_provider=embedding_provider,
        )

        context = await extractor.extract(message="Test", history=[], mode="llm")
        assert len(context.entities) == 1
        assert context.entities[0].type == "valid"

    @pytest.mark.asyncio
    async def test_extract_handles_json_in_code_block(
        self,
        embedding_provider: MockEmbeddingProvider,
    ) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""

        class MarkdownLLMProvider(MockLLMProvider):
            async def generate(self, messages, **kwargs):
                return LLMResponse(
                    content='```json\n{"intent": "code_block_test"}\n```',
                    model="mock",
                    usage={},
                )

        extractor = ContextExtractor(
            llm_provider=MarkdownLLMProvider(),
            embedding_provider=embedding_provider,
        )

        context = await extractor.extract(message="Test", history=[], mode="llm")
        assert context.intent == "code_block_test"


class TestTurn:
    """Tests for Turn model."""

    def test_create_user_turn(self) -> None:
        """Test creating a user turn."""
        turn = Turn(role="user", content="Hello")
        assert turn.role == "user"
        assert turn.content == "Hello"

    def test_create_assistant_turn(self) -> None:
        """Test creating an assistant turn."""
        turn = Turn(role="assistant", content="How can I help?")
        assert turn.role == "assistant"

    def test_turn_with_timestamp(self) -> None:
        """Test turn with explicit timestamp."""
        ts = datetime.utcnow()
        turn = Turn(role="user", content="Test", timestamp=ts)
        assert turn.timestamp == ts

    def test_turn_default_timestamp_is_none(self) -> None:
        """Test that turn timestamp defaults to None."""
        turn = Turn(role="user", content="Test")
        # timestamp is optional and defaults to None
        assert turn.timestamp is None


class TestExtractedEntity:
    """Tests for ExtractedEntity model."""

    def test_create_entity(self) -> None:
        """Test creating an extracted entity."""
        entity = ExtractedEntity(type="order_id", value="12345")
        assert entity.type == "order_id"
        assert entity.value == "12345"
        assert entity.confidence == 1.0

    def test_entity_with_confidence(self) -> None:
        """Test entity with explicit confidence."""
        entity = ExtractedEntity(type="product", value="laptop", confidence=0.85)
        assert entity.confidence == 0.85

    def test_entity_confidence_validation_high(self) -> None:
        """Test that confidence above 1 raises error."""
        with pytest.raises(ValueError):
            ExtractedEntity(type="test", value="test", confidence=1.5)

    def test_entity_confidence_validation_low(self) -> None:
        """Test that confidence below 0 raises error."""
        with pytest.raises(ValueError):
            ExtractedEntity(type="test", value="test", confidence=-0.1)

    def test_entity_boundary_confidence(self) -> None:
        """Test boundary confidence values."""
        zero = ExtractedEntity(type="t", value="v", confidence=0.0)
        one = ExtractedEntity(type="t", value="v", confidence=1.0)
        assert zero.confidence == 0.0
        assert one.confidence == 1.0


class TestContext:
    """Tests for Context model."""

    def test_context_model_creation(self) -> None:
        """Test creating a Context model directly."""
        context = Context(
            message="I want to return my order",
            intent="return order",
            entities=[ExtractedEntity(type="action", value="return")],
            sentiment=Sentiment.NEUTRAL,
            urgency=Urgency.NORMAL,
        )
        assert context.message == "I want to return my order"
        assert context.intent == "return order"
        assert len(context.entities) == 1

    def test_context_with_embedding(self) -> None:
        """Test creating context with embedding."""
        embedding = [0.1] * 1536
        context = Context(
            message="Test message",
            embedding=embedding,
        )
        assert context.embedding is not None
        assert len(context.embedding) == 1536

    def test_context_with_scenario_signal(self) -> None:
        """Test creating context with scenario signal."""
        context = Context(
            message="I want to start a return",
            scenario_signal=ScenarioSignal.START,
        )
        assert context.scenario_signal == ScenarioSignal.START

    def test_context_timestamps(self) -> None:
        """Test that context gets a timestamp."""
        before = datetime.utcnow()
        context = Context(message="Test")
        after = datetime.utcnow()

        assert before <= context.timestamp <= after

    def test_context_default_values(self) -> None:
        """Test default values for optional fields."""
        context = Context(message="Test")

        assert context.embedding is None
        assert context.intent is None
        assert context.entities == []
        assert context.sentiment is None
        assert context.topic is None
        assert context.urgency == Urgency.NORMAL
        assert context.scenario_signal is None
        assert context.turn_count == 0
        assert context.recent_topics == []

    def test_context_all_sentiments(self) -> None:
        """Test all sentiment enum values."""
        for sentiment in Sentiment:
            context = Context(message="Test", sentiment=sentiment)
            assert context.sentiment == sentiment

    def test_context_all_urgencies(self) -> None:
        """Test all urgency enum values."""
        for urgency in Urgency:
            context = Context(message="Test", urgency=urgency)
            assert context.urgency == urgency

    def test_context_all_scenario_signals(self) -> None:
        """Test all scenario signal enum values."""
        for signal in ScenarioSignal:
            context = Context(message="Test", scenario_signal=signal)
            assert context.scenario_signal == signal
