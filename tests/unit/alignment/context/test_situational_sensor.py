"""Tests for SituationSensor."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from ruche.brains.focal.phases.context.customer_schema_mask import (
    CustomerSchemaMask,
    CustomerSchemaMaskEntry,
)
from ruche.brains.focal.phases.context.models import Turn
from ruche.brains.focal.phases.context.situation_sensor import SituationSensor
from ruche.brains.focal.phases.context.situation_snapshot import (
    CandidateVariableInfo,
    SituationSnapshot,
)
from ruche.brains.focal.models.glossary import GlossaryItem
from ruche.config.models.pipeline import SituationSensorConfig
from ruche.interlocutor_data.models import (
    InterlocutorDataField,
    InterlocutorDataStore,
    VariableEntry,
)
from ruche.interlocutor_data.enums import VariableSource
from ruche.infrastructure.providers.llm.base import LLMResponse, TokenUsage


@pytest.fixture
def sensor_config():
    """Create a test sensor configuration."""
    return SituationSensorConfig(
        enabled=True,
        model="openrouter/openai/gpt-oss-120b",
        fallback_models=["anthropic/claude-3-5-haiku-20241022"],
        temperature=0.0,
        max_tokens=800,
        history_turns=5,
        include_glossary=True,
        include_schema_mask=True,
    )


@pytest.fixture
def mock_llm_executor():
    """Create a mock LLM executor."""
    executor = Mock()
    executor.generate = AsyncMock()
    return executor


@pytest.fixture
def customer_data_fields():
    """Create test customer data field definitions."""
    tenant_id = uuid4()
    agent_id = uuid4()

    return {
        "name": InterlocutorDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="name",
            display_name="Full Name",
            value_type="string",
            scope="IDENTITY",
            persist=True,
        ),
        "email": InterlocutorDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="email",
            display_name="Email Address",
            value_type="string",
            scope="IDENTITY",
            persist=True,
        ),
        "order_id": InterlocutorDataField(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="order_id",
            display_name="Order ID",
            value_type="string",
            scope="CASE",
            persist=True,
        ),
    }


@pytest.fixture
def customer_data_store():
    """Create test customer data store."""
    return InterlocutorDataStore(
        id=uuid4(),
        tenant_id=uuid4(),
        interlocutor_id=uuid4(),
        fields={
            "email": VariableEntry(
                id=uuid4(),
                name="email",
                value="john@example.com",
                value_type="string",
                source=VariableSource.USER_PROVIDED,
                collected_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        },
    )


@pytest.fixture
def glossary_items():
    """Create test glossary items."""
    tenant_id = uuid4()
    agent_id = uuid4()

    return {
        "CSAT": GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="CSAT",
            definition="Customer Satisfaction score from 1-5",
            usage_hint="Use when discussing survey results",
        ),
        "VIP": GlossaryItem(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            term="VIP",
            definition="Premium customer with special benefits",
        ),
    }


class TestSituationSensorBuildSchemaMask:
    """Test _build_schema_mask method."""

    def test_build_schema_mask_shows_existing_fields(
        self, sensor_config, mock_llm_executor, customer_data_fields, customer_data_store
    ):
        """Test that schema mask correctly shows which fields have values."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        mask = sensor._build_schema_mask(customer_data_store, customer_data_fields)

        # email has a value
        assert mask.variables["email"].exists is True
        assert mask.variables["email"].scope == "IDENTITY"
        assert mask.variables["email"].type == "string"

        # name and order_id don't have values
        assert mask.variables["name"].exists is False
        assert mask.variables["order_id"].exists is False

    def test_build_schema_mask_no_values_exposed(
        self, sensor_config, mock_llm_executor, customer_data_fields, customer_data_store
    ):
        """Test that actual values are NOT exposed in schema mask."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        mask = sensor._build_schema_mask(customer_data_store, customer_data_fields)

        # Check that mask doesn't contain actual values
        for entry in mask.variables.values():
            # CustomerSchemaMaskEntry has no value field
            assert not hasattr(entry, "value")

    def test_build_schema_mask_empty_store(
        self, sensor_config, mock_llm_executor, customer_data_fields
    ):
        """Test schema mask with empty customer data store."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        empty_store = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=uuid4(),
            interlocutor_id=uuid4(),
            fields={},
        )

        mask = sensor._build_schema_mask(empty_store, customer_data_fields)

        # All fields should show exists=False
        for entry in mask.variables.values():
            assert entry.exists is False


class TestSituationSensorBuildGlossaryView:
    """Test _build_glossary_view method."""

    def test_build_glossary_view(
        self, sensor_config, mock_llm_executor, glossary_items
    ):
        """Test that glossary view is built correctly."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        glossary_view = sensor._build_glossary_view(glossary_items)

        assert "CSAT" in glossary_view
        assert "VIP" in glossary_view
        assert glossary_view["CSAT"].definition == "Customer Satisfaction score from 1-5"

    def test_build_glossary_view_empty(self, sensor_config, mock_llm_executor):
        """Test with empty glossary."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        glossary_view = sensor._build_glossary_view({})

        assert glossary_view == {}


class TestSituationSensorBuildConversationWindow:
    """Test _build_conversation_window method."""

    def test_build_conversation_window_configurable_k(
        self, sensor_config, mock_llm_executor
    ):
        """Test that conversation window respects config.history_turns."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        history = [
            Turn(role="user", content=f"Message {i}", timestamp=datetime.now(UTC))
            for i in range(10)
        ]

        # Config has history_turns=5
        window = sensor._build_conversation_window(history)

        assert len(window) == 5
        assert window[0].content == "Message 5"
        assert window[-1].content == "Message 9"

    def test_build_conversation_window_less_than_k(
        self, sensor_config, mock_llm_executor
    ):
        """Test with fewer history items than K."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        history = [
            Turn(role="user", content="Message 1", timestamp=datetime.now(UTC)),
            Turn(role="assistant", content="Response 1", timestamp=datetime.now(UTC)),
        ]

        window = sensor._build_conversation_window(history)

        # Should return all items when less than K
        assert len(window) == 2

    def test_build_conversation_window_empty_history(
        self, sensor_config, mock_llm_executor
    ):
        """Test with empty history."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        window = sensor._build_conversation_window([])

        assert window == []

    def test_build_conversation_window_zero_k(self, mock_llm_executor):
        """Test with history_turns=0."""
        config = SituationSensorConfig(history_turns=0)
        sensor = SituationSensor(mock_llm_executor, config)

        history = [
            Turn(role="user", content="Message", timestamp=datetime.now(UTC))
        ]

        window = sensor._build_conversation_window(history)

        assert window == []


class TestSituationSensorParseSnapshot:
    """Test _parse_snapshot method."""

    def test_parse_snapshot_valid_json(self, sensor_config, mock_llm_executor):
        """Test parsing valid JSON from LLM."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        llm_output = {
            "language": "en",
            "previous_intent_label": "greeting",
            "intent_changed": True,
            "new_intent_label": "refund_request",
            "new_intent_text": "User wants a refund",
            "topic_changed": True,
            "tone": "frustrated",
            "frustration_level": "medium",
            "situation_facts": ["User ordered product #123"],
            "candidate_variables": {
                "order_id": {
                    "value": "123",
                    "scope": "CASE",
                    "is_update": False,
                }
            },
        }

        snapshot = sensor._parse_snapshot(llm_output, message="test message")

        assert isinstance(snapshot, SituationSnapshot)
        assert snapshot.language == "en"
        assert snapshot.intent_changed is True
        assert snapshot.new_intent_label == "refund_request"
        assert snapshot.tone == "frustrated"
        assert len(snapshot.candidate_variables) == 1
        assert "order_id" in snapshot.candidate_variables
        assert snapshot.message == "test message"

    def test_parse_snapshot_missing_optional_fields(
        self, sensor_config, mock_llm_executor
    ):
        """Test parsing with missing optional fields."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        llm_output = {
            "language": "en",
            "intent_changed": False,
            "topic_changed": False,
            "tone": "neutral",
        }

        snapshot = sensor._parse_snapshot(llm_output, message="test message")

        assert snapshot.language == "en"
        assert snapshot.previous_intent_label is None
        assert snapshot.new_intent_label is None
        assert snapshot.frustration_level is None
        assert snapshot.situation_facts == []
        assert snapshot.candidate_variables == {}
        assert snapshot.message == "test message"

    def test_parse_snapshot_candidate_variables_parsing(
        self, sensor_config, mock_llm_executor
    ):
        """Test that candidate_variables are properly parsed into CandidateVariableInfo."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        llm_output = {
            "language": "en",
            "intent_changed": False,
            "topic_changed": False,
            "tone": "neutral",
            "candidate_variables": {
                "name": {
                    "value": "John Doe",
                    "scope": "IDENTITY",
                    "is_update": False,
                },
                "email": {
                    "value": "john@example.com",
                    "scope": "IDENTITY",
                    "is_update": True,
                },
            },
        }

        snapshot = sensor._parse_snapshot(llm_output, message="test message")

        assert len(snapshot.candidate_variables) == 2
        assert isinstance(snapshot.candidate_variables["name"], CandidateVariableInfo)
        assert snapshot.candidate_variables["name"].value == "John Doe"
        assert snapshot.candidate_variables["name"].scope == "IDENTITY"
        assert snapshot.candidate_variables["name"].is_update is False
        assert snapshot.candidate_variables["email"].is_update is True


class TestSituationSensorValidateLanguage:
    """Test _validate_language method."""

    def test_validate_language_valid_codes(self, sensor_config, mock_llm_executor):
        """Test validation with valid ISO 639-1 codes."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        for code in ["en", "es", "fr", "de", "it", "pt", "ja", "zh", "ar", "ru", "hi"]:
            result = sensor._validate_language(code, "test message")
            assert result == code

    def test_validate_language_uppercase(self, sensor_config, mock_llm_executor):
        """Test that uppercase codes are converted to lowercase."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        result = sensor._validate_language("EN", "test message")
        assert result == "en"

    def test_validate_language_invalid_code_fallback(self, sensor_config, mock_llm_executor):
        """Test that invalid codes trigger detection then fallback."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        # Invalid code with Latin text - should fallback to default
        result = sensor._validate_language("english", "Hello world")
        assert result == "en"

        # Invalid code with empty message - should fallback
        result = sensor._validate_language("xyz", "")
        assert result == "en"

    def test_validate_language_detects_chinese(self, sensor_config, mock_llm_executor):
        """Test detection of Chinese characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        # Invalid code but Chinese text
        result = sensor._validate_language("invalid", "你好世界")
        assert result == "zh"

    def test_validate_language_detects_japanese(self, sensor_config, mock_llm_executor):
        """Test detection of Japanese characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        # Hiragana
        result = sensor._validate_language("invalid", "こんにちは")
        assert result == "ja"

        # Katakana
        result = sensor._validate_language("invalid", "カタカナ")
        assert result == "ja"

    def test_validate_language_detects_korean(self, sensor_config, mock_llm_executor):
        """Test detection of Korean characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        result = sensor._validate_language("invalid", "안녕하세요")
        assert result == "ko"

    def test_validate_language_detects_arabic(self, sensor_config, mock_llm_executor):
        """Test detection of Arabic characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        result = sensor._validate_language("invalid", "مرحبا")
        assert result == "ar"

    def test_validate_language_detects_russian(self, sensor_config, mock_llm_executor):
        """Test detection of Cyrillic/Russian characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        result = sensor._validate_language("invalid", "Привет мир")
        assert result == "ru"

    def test_validate_language_detects_hebrew(self, sensor_config, mock_llm_executor):
        """Test detection of Hebrew characters."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        result = sensor._validate_language("invalid", "שלום")
        assert result == "he"

    def test_validate_language_custom_default(self, mock_llm_executor):
        """Test custom default language in config."""
        config = SituationSensorConfig(default_language="es")
        sensor = SituationSensor(mock_llm_executor, config)

        # Invalid code with undetectable text should use custom default
        result = sensor._validate_language("invalid", "Hello")
        assert result == "es"


class TestSituationSensorDetectLanguage:
    """Test _detect_language method."""

    def test_detect_language_chinese(self, sensor_config, mock_llm_executor):
        """Test Chinese character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("你好世界") == "zh"
        assert sensor._detect_language("中文测试") == "zh"

    def test_detect_language_japanese(self, sensor_config, mock_llm_executor):
        """Test Japanese character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("こんにちは") == "ja"
        assert sensor._detect_language("カタカナ") == "ja"
        assert sensor._detect_language("ひらがな") == "ja"

    def test_detect_language_korean(self, sensor_config, mock_llm_executor):
        """Test Korean character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("안녕하세요") == "ko"
        assert sensor._detect_language("한글") == "ko"

    def test_detect_language_arabic(self, sensor_config, mock_llm_executor):
        """Test Arabic character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("مرحبا") == "ar"
        assert sensor._detect_language("العربية") == "ar"

    def test_detect_language_cyrillic(self, sensor_config, mock_llm_executor):
        """Test Cyrillic/Russian character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("Привет") == "ru"
        assert sensor._detect_language("Русский") == "ru"

    def test_detect_language_hebrew(self, sensor_config, mock_llm_executor):
        """Test Hebrew character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("שלום") == "he"
        assert sensor._detect_language("עברית") == "he"

    def test_detect_language_thai(self, sensor_config, mock_llm_executor):
        """Test Thai character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("สวัสดี") == "th"
        assert sensor._detect_language("ภาษาไทย") == "th"

    def test_detect_language_hindi(self, sensor_config, mock_llm_executor):
        """Test Hindi/Devanagari character detection."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("नमस्ते") == "hi"
        assert sensor._detect_language("हिन्दी") == "hi"

    def test_detect_language_latin_returns_none(self, sensor_config, mock_llm_executor):
        """Test that Latin script returns None (no detection)."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("Hello world") is None
        assert sensor._detect_language("Bonjour") is None
        assert sensor._detect_language("Hola") is None

    def test_detect_language_empty_returns_none(self, sensor_config, mock_llm_executor):
        """Test that empty text returns None."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        assert sensor._detect_language("") is None

    def test_detect_language_mixed_scripts(self, sensor_config, mock_llm_executor):
        """Test detection with mixed scripts (first match wins)."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        # Chinese should be detected first
        assert sensor._detect_language("Hello 你好") == "zh"
        assert sensor._detect_language("Test こんにちは") == "ja"


class TestSituationSensorExtractJson:
    """Test _extract_json method."""

    def test_extract_json_from_markdown_code_block(
        self, sensor_config, mock_llm_executor
    ):
        """Test extracting JSON from markdown code block."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        content = '''Here is the analysis:

```json
{
  "language": "en",
  "intent_changed": true
}
```

Hope this helps!'''

        result = sensor._extract_json(content)

        assert result["language"] == "en"
        assert result["intent_changed"] is True

    def test_extract_json_from_plain_code_block(
        self, sensor_config, mock_llm_executor
    ):
        """Test extracting JSON from plain code block (no json marker)."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        content = '''```
{
  "language": "es"
}
```'''

        result = sensor._extract_json(content)

        assert result["language"] == "es"

    def test_extract_json_from_raw_text(self, sensor_config, mock_llm_executor):
        """Test extracting JSON from raw text without code block."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        content = '{"language": "fr", "tone": "neutral"}'

        result = sensor._extract_json(content)

        assert result["language"] == "fr"
        assert result["tone"] == "neutral"

    def test_extract_json_no_json_found(self, sensor_config, mock_llm_executor):
        """Test that ValueError is raised when no JSON found."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        content = "This is just plain text with no JSON"

        with pytest.raises(ValueError, match="No JSON found"):
            sensor._extract_json(content)

    def test_extract_json_invalid_json(self, sensor_config, mock_llm_executor):
        """Test that ValueError is raised for invalid JSON."""
        sensor = SituationSensor(mock_llm_executor, sensor_config)

        content = '''```json
{
  "language": "en",
  "missing_comma"
  "tone": "neutral"
}
```'''

        with pytest.raises(ValueError, match="Failed to parse JSON"):
            sensor._extract_json(content)


@pytest.mark.asyncio
class TestSituationSensorSense:
    """Test the main sense() method."""

    async def test_sense_full_flow(
        self,
        sensor_config,
        mock_llm_executor,
        customer_data_fields,
        customer_data_store,
        glossary_items,
    ):
        """Test full sense() flow with mocked LLM."""
        # Mock LLM response
        llm_response_content = '''```json
{
  "language": "en",
  "previous_intent_label": null,
  "intent_changed": true,
  "new_intent_label": "refund_request",
  "new_intent_text": "User wants to request a refund",
  "topic_changed": true,
  "tone": "frustrated",
  "frustration_level": "medium",
  "situation_facts": ["User ordered product #12345", "Product arrived damaged"],
  "candidate_variables": {
    "order_id": {
      "value": "12345",
      "scope": "CASE",
      "is_update": false
    },
    "name": {
      "value": "John Doe",
      "scope": "IDENTITY",
      "is_update": false
    }
  }
}
```'''

        mock_llm_executor.generate.return_value = LLMResponse(
            content=llm_response_content,
            model="openrouter/openai/gpt-oss-120b",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            finish_reason="stop",
        )

        sensor = SituationSensor(mock_llm_executor, sensor_config)

        # Call sense
        snapshot = await sensor.sense(
            message="My order #12345 arrived damaged, I want a refund",
            history=[],
            customer_data_store=customer_data_store,
            customer_data_fields=customer_data_fields,
            glossary_items=glossary_items,
        )

        # Verify LLM was called
        assert mock_llm_executor.generate.called

        # Verify snapshot
        assert isinstance(snapshot, SituationSnapshot)
        assert snapshot.language == "en"
        assert snapshot.intent_changed is True
        assert snapshot.new_intent_label == "refund_request"
        assert snapshot.tone == "frustrated"
        assert snapshot.frustration_level == "medium"
        assert len(snapshot.situation_facts) == 2
        assert len(snapshot.candidate_variables) == 2
        assert "order_id" in snapshot.candidate_variables
        assert "name" in snapshot.candidate_variables

    async def test_sense_with_empty_inputs(
        self, sensor_config, mock_llm_executor
    ):
        """Test sense() with minimal/empty inputs."""
        llm_response_content = '''{"language": "en", "intent_changed": false, "topic_changed": false, "tone": "neutral"}'''

        mock_llm_executor.generate.return_value = LLMResponse(
            content=llm_response_content,
            model="openrouter/openai/gpt-oss-120b",
            usage=TokenUsage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
            finish_reason="stop",
        )

        sensor = SituationSensor(mock_llm_executor, sensor_config)

        empty_store = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=uuid4(),
            interlocutor_id=uuid4(),
            fields={},
        )

        snapshot = await sensor.sense(
            message="Hello",
            history=[],
            customer_data_store=empty_store,
            customer_data_fields={},
            glossary_items={},
        )

        assert isinstance(snapshot, SituationSnapshot)
        assert snapshot.language == "en"
