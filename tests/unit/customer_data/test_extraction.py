"""Unit tests for CustomerDataSchemaExtractor.

Tests extraction logic, confidence scoring, and field definition suggestions.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from focal.customer_data.extraction import (
    ExtractionResult,
    FieldDefinitionSuggestion,
    CustomerDataSchemaExtractor,
)
from focal.customer_data.enums import RequiredLevel


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return uuid4()


@pytest.fixture
def agent_id():
    """Test agent ID."""
    return uuid4()


@pytest.fixture
def scenario_id():
    """Test scenario ID."""
    return uuid4()


@pytest.fixture
def mock_llm():
    """Create a mock LLM executor."""
    return AsyncMock()


@pytest.fixture
def extractor_no_llm():
    """Create extractor without LLM (mock mode)."""
    return CustomerDataSchemaExtractor(llm_executor=None)


@pytest.fixture
def extractor_with_llm(mock_llm):
    """Create extractor with mock LLM."""
    return CustomerDataSchemaExtractor(llm_executor=mock_llm)


class TestExtractionFromScenarioConditions:
    """Tests for extraction from scenario conditions (T139)."""

    @pytest.mark.asyncio
    async def test_extract_no_llm_returns_empty(self, extractor_no_llm):
        """Test extraction without LLM returns empty result."""
        content = "if customer is over 18 years old"

        result = await extractor_no_llm.extract_requirements(
            content=content,
            content_type="scenario",
        )

        assert result.field_names == []
        assert result.confidence_scores == {}
        assert result.needs_human_review is True

    @pytest.mark.asyncio
    async def test_extract_with_llm_parses_response(self, extractor_with_llm, mock_llm):
        """Test extraction with LLM parses JSON response correctly."""
        mock_llm.generate.return_value = '''
        {
            "fields": [
                {"name": "date_of_birth", "display_name": "Date of Birth", "value_type": "date", "required_level": "hard", "confidence": 0.95, "reasoning": "age check requires birth date"},
                {"name": "email", "display_name": "Email", "value_type": "email", "required_level": "soft", "confidence": 0.7, "reasoning": "for notifications"}
            ]
        }
        '''

        result = await extractor_with_llm.extract_requirements(
            content="if customer is over 18, send email notification",
            content_type="scenario",
        )

        assert "date_of_birth" in result.field_names
        assert "email" in result.field_names
        assert result.confidence_scores["date_of_birth"] == 0.95
        assert result.confidence_scores["email"] == 0.7

    @pytest.mark.asyncio
    async def test_extract_handles_llm_error(self, extractor_with_llm, mock_llm):
        """Test extraction handles LLM errors gracefully."""
        mock_llm.generate.side_effect = Exception("LLM unavailable")

        result = await extractor_with_llm.extract_requirements(
            content="some content",
            content_type="scenario",
        )

        assert result.field_names == []
        assert result.needs_human_review is True


class TestExtractionFromRuleConditions:
    """Tests for extraction from rule conditions (T140)."""

    @pytest.mark.asyncio
    async def test_extract_from_rule(self, extractor_with_llm, mock_llm):
        """Test extraction from rule content."""
        mock_llm.generate.return_value = '''
        {
            "fields": [
                {"name": "membership_level", "display_name": "Membership Level", "value_type": "string", "confidence": 0.85}
            ]
        }
        '''

        result = await extractor_with_llm.extract_requirements(
            content="if membership_level == 'gold' then apply discount",
            content_type="rule",
        )

        assert "membership_level" in result.field_names


class TestConfidenceScoring:
    """Tests for confidence scoring (T141)."""

    @pytest.mark.asyncio
    async def test_high_confidence_no_review(self, extractor_with_llm, mock_llm):
        """Test high confidence doesn't trigger human review."""
        mock_llm.generate.return_value = '''
        {
            "fields": [
                {"name": "email", "confidence": 0.95}
            ]
        }
        '''

        result = await extractor_with_llm.extract_requirements(
            content="send email to customer",
            content_type="scenario",
        )

        assert result.needs_human_review is False

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_review(self, extractor_with_llm, mock_llm):
        """Test low confidence triggers human review."""
        mock_llm.generate.return_value = '''
        {
            "fields": [
                {"name": "custom_field", "confidence": 0.5}
            ]
        }
        '''

        result = await extractor_with_llm.extract_requirements(
            content="check something",
            content_type="scenario",
        )

        assert result.needs_human_review is True


class TestFieldDefinitionSuggestions:
    """Tests for field definition suggestions (T142)."""

    @pytest.mark.asyncio
    async def test_suggest_email_field(self, extractor_no_llm, tenant_id, agent_id):
        """Test suggestion for email field."""
        suggestions = await extractor_no_llm.suggest_field_definitions(
            field_names=["email_address"],
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(suggestions) == 1
        assert suggestions[0].name == "email_address"
        assert suggestions[0].value_type == "email"
        assert suggestions[0].validation_regex is not None

    @pytest.mark.asyncio
    async def test_suggest_phone_field(self, extractor_no_llm, tenant_id, agent_id):
        """Test suggestion for phone field."""
        suggestions = await extractor_no_llm.suggest_field_definitions(
            field_names=["phone_number"],
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(suggestions) == 1
        assert suggestions[0].value_type == "phone"

    @pytest.mark.asyncio
    async def test_suggest_date_field(self, extractor_no_llm, tenant_id, agent_id):
        """Test suggestion for date field."""
        suggestions = await extractor_no_llm.suggest_field_definitions(
            field_names=["date_of_birth"],
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(suggestions) == 1
        assert suggestions[0].value_type == "date"

    @pytest.mark.asyncio
    async def test_suggest_generates_display_name(self, extractor_no_llm, tenant_id, agent_id):
        """Test suggestion generates human-readable display name."""
        suggestions = await extractor_no_llm.suggest_field_definitions(
            field_names=["customer_first_name"],
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert suggestions[0].display_name == "Customer First Name"

    @pytest.mark.asyncio
    async def test_suggest_generates_collection_prompt(self, extractor_no_llm, tenant_id, agent_id):
        """Test suggestion generates collection prompt."""
        suggestions = await extractor_no_llm.suggest_field_definitions(
            field_names=["email"],
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert suggestions[0].collection_prompt is not None
        assert "email" in suggestions[0].collection_prompt.lower()


class TestNeedsHumanReviewFlag:
    """Tests for needs_human_review flag (T143)."""

    def test_create_requirements_high_confidence(self, extractor_no_llm, tenant_id, agent_id, scenario_id):
        """Test high confidence requirements don't need review."""
        extraction = ExtractionResult(
            field_names=["email"],
            confidence_scores={"email": 0.95},
            needs_human_review=False,
        )

        requirements = extractor_no_llm.create_requirements(
            extraction_result=extraction,
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
        )

        assert len(requirements) == 1
        assert requirements[0].needs_human_review is False

    def test_create_requirements_low_confidence(self, extractor_no_llm, tenant_id, agent_id, scenario_id):
        """Test low confidence requirements need review."""
        extraction = ExtractionResult(
            field_names=["unknown_field"],
            confidence_scores={"unknown_field": 0.5},
            needs_human_review=True,
        )

        requirements = extractor_no_llm.create_requirements(
            extraction_result=extraction,
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
        )

        assert len(requirements) == 1
        assert requirements[0].needs_human_review is True

    def test_create_requirements_sets_required_level(self, extractor_no_llm, tenant_id, agent_id, scenario_id):
        """Test required level based on confidence."""
        extraction = ExtractionResult(
            field_names=["high_conf", "low_conf"],
            confidence_scores={"high_conf": 0.9, "low_conf": 0.5},
            needs_human_review=True,
        )

        requirements = extractor_no_llm.create_requirements(
            extraction_result=extraction,
            tenant_id=tenant_id,
            agent_id=agent_id,
            scenario_id=scenario_id,
        )

        high_conf_req = next(r for r in requirements if r.field_name == "high_conf")
        low_conf_req = next(r for r in requirements if r.field_name == "low_conf")

        assert high_conf_req.required_level == RequiredLevel.HARD
        assert low_conf_req.required_level == RequiredLevel.SOFT


class TestTypeInference:
    """Tests for type inference from field names."""

    def test_infer_email_type(self, extractor_no_llm):
        """Test email type inference."""
        assert extractor_no_llm._infer_type_from_name("email") == "email"
        assert extractor_no_llm._infer_type_from_name("customer_email") == "email"
        assert extractor_no_llm._infer_type_from_name("email_address") == "email"

    def test_infer_phone_type(self, extractor_no_llm):
        """Test phone type inference."""
        assert extractor_no_llm._infer_type_from_name("phone") == "phone"
        assert extractor_no_llm._infer_type_from_name("phone_number") == "phone"
        assert extractor_no_llm._infer_type_from_name("mobile") == "phone"
        assert extractor_no_llm._infer_type_from_name("cell_phone") == "phone"

    def test_infer_date_type(self, extractor_no_llm):
        """Test date type inference."""
        assert extractor_no_llm._infer_type_from_name("date_of_birth") == "date"
        assert extractor_no_llm._infer_type_from_name("dob") == "date"
        assert extractor_no_llm._infer_type_from_name("birth_date") == "date"

    def test_infer_number_type(self, extractor_no_llm):
        """Test number type inference."""
        assert extractor_no_llm._infer_type_from_name("age") == "number"
        assert extractor_no_llm._infer_type_from_name("order_count") == "number"

    def test_infer_boolean_type(self, extractor_no_llm):
        """Test boolean type inference."""
        assert extractor_no_llm._infer_type_from_name("is_verified") == "boolean"
        assert extractor_no_llm._infer_type_from_name("has_subscription") == "boolean"

    def test_infer_default_string_type(self, extractor_no_llm):
        """Test default to string type."""
        assert extractor_no_llm._infer_type_from_name("first_name") == "string"
        assert extractor_no_llm._infer_type_from_name("company") == "string"


class TestCreateFieldDefinitions:
    """Tests for creating field definitions from suggestions."""

    def test_create_definitions(self, extractor_no_llm, tenant_id, agent_id):
        """Test creating CustomerDataField objects."""
        suggestions = [
            FieldDefinitionSuggestion(
                name="email",
                display_name="Email Address",
                value_type="email",
                validation_regex=r"^[\w.-]+@[\w.-]+\.\w+$",
                collection_prompt="What is your email?",
                confidence=0.9,
            )
        ]

        definitions = extractor_no_llm.create_field_definitions(
            suggestions=suggestions,
            tenant_id=tenant_id,
            agent_id=agent_id,
        )

        assert len(definitions) == 1
        assert definitions[0].name == "email"
        assert definitions[0].tenant_id == tenant_id
        assert definitions[0].agent_id == agent_id
        assert definitions[0].value_type == "email"
