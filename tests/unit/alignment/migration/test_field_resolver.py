"""Tests for missing field resolver."""

from uuid import uuid4

import pytest

from ruche.brains.focal.migration.field_resolver import (
    NO_CONFIRM_THRESHOLD,
    USE_THRESHOLD,
    MissingFieldResolver,
)
from ruche.brains.focal.migration.models import ResolutionSource
from ruche.conversation.models import Channel, Session


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


def create_session(
    tenant_id,
    agent_id,
    variables: dict | None = None,
) -> Session:
    """Helper to create a session."""
    return Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables=variables or {},
    )


class TestMissingFieldResolverSessionFill:
    """Tests for session variable filling."""

    @pytest.mark.asyncio
    async def test_fill_from_session_variables(self, tenant_id, agent_id):
        """Test that existing session variables are used."""
        session = create_session(
            tenant_id, agent_id, variables={"email": "user@example.com"}
        )

        service = MissingFieldResolver()
        result = await service.fill_gap(field_name="email", session=session)

        assert result.filled is True
        assert result.value == "user@example.com"
        assert result.source == ResolutionSource.SESSION
        assert result.confidence == 1.0
        assert result.needs_confirmation is False

    @pytest.mark.asyncio
    async def test_session_fill_not_found(self, tenant_id, agent_id):
        """Test that missing fields return not found."""
        session = create_session(tenant_id, agent_id, variables={})

        service = MissingFieldResolver()
        result = await service.fill_gap(field_name="email", session=session)

        assert result.filled is False
        assert result.source == ResolutionSource.NOT_FOUND

    def test_try_session_fill_direct(self, tenant_id, agent_id):
        """Test direct session fill method."""
        session = create_session(
            tenant_id, agent_id, variables={"phone": "555-1234"}
        )

        service = MissingFieldResolver()
        result = service.try_session_fill(field_name="phone", session=session)

        assert result.filled is True
        assert result.value == "555-1234"
        assert result.source == ResolutionSource.SESSION


class TestMissingFieldResolverExtractionParsing:
    """Tests for extraction response parsing."""

    def test_parse_valid_extraction_found(self, tenant_id, agent_id):
        """Test parsing valid extraction response."""
        service = MissingFieldResolver()
        response = '{"found": true, "value": "user@example.com", "confidence": 0.95, "source_quote": "my email is user@example.com"}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is True
        assert result.value == "user@example.com"
        assert result.source == ResolutionSource.EXTRACTION
        assert result.confidence == 0.95
        assert result.needs_confirmation is False
        assert result.extraction_quote == "my email is user@example.com"

    def test_parse_extraction_not_found(self, tenant_id, agent_id):
        """Test parsing not found response."""
        service = MissingFieldResolver()
        response = '{"found": false, "value": null, "confidence": 0.0}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is False
        assert result.source == ResolutionSource.NOT_FOUND

    def test_parse_extraction_low_confidence(self, tenant_id, agent_id):
        """Test that low confidence results are rejected."""
        service = MissingFieldResolver()
        response = '{"found": true, "value": "maybe@example.com", "confidence": 0.5}'

        result = service._parse_extraction_response("email", response)

        # Below USE_THRESHOLD, treated as not found
        assert result.filled is False
        assert result.source == ResolutionSource.NOT_FOUND

    def test_parse_extraction_needs_confirmation(self, tenant_id, agent_id):
        """Test that medium confidence needs confirmation."""
        service = MissingFieldResolver()
        response = '{"found": true, "value": "user@example.com", "confidence": 0.90}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is True
        assert result.needs_confirmation is True  # Below NO_CONFIRM_THRESHOLD

    def test_parse_invalid_json(self, tenant_id, agent_id):
        """Test handling of invalid JSON response."""
        service = MissingFieldResolver()
        response = "Not valid JSON at all"

        result = service._parse_extraction_response("email", response)

        assert result.filled is False
        assert result.source == ResolutionSource.NOT_FOUND

    def test_parse_malformed_response(self, tenant_id, agent_id):
        """Test handling of malformed response."""
        service = MissingFieldResolver()
        response = '{"unexpected": "format"}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is False


class TestMissingFieldResolverMultipleFill:
    """Tests for filling multiple fields."""

    @pytest.mark.asyncio
    async def test_fill_multiple_all_in_session(self, tenant_id, agent_id):
        """Test filling multiple fields from session."""
        session = create_session(
            tenant_id,
            agent_id,
            variables={
                "email": "user@example.com",
                "phone": "555-1234",
            },
        )

        service = MissingFieldResolver()
        results = await service.fill_multiple(
            field_names=["email", "phone"],
            session=session,
        )

        assert len(results) == 2
        assert results["email"].filled is True
        assert results["phone"].filled is True

    @pytest.mark.asyncio
    async def test_fill_multiple_partial(self, tenant_id, agent_id):
        """Test filling multiple fields with partial success."""
        session = create_session(
            tenant_id,
            agent_id,
            variables={"email": "user@example.com"},
        )

        service = MissingFieldResolver()
        results = await service.fill_multiple(
            field_names=["email", "phone"],
            session=session,
        )

        assert results["email"].filled is True
        assert results["phone"].filled is False


class TestGapFillThresholds:
    """Tests for confidence thresholds."""

    def test_use_threshold_value(self):
        """Verify USE_THRESHOLD is 0.85."""
        assert USE_THRESHOLD == 0.85

    def test_no_confirm_threshold_value(self):
        """Verify NO_CONFIRM_THRESHOLD is 0.95."""
        assert NO_CONFIRM_THRESHOLD == 0.95

    def test_threshold_ordering(self):
        """Verify thresholds are in correct order."""
        assert USE_THRESHOLD < NO_CONFIRM_THRESHOLD


class TestGapFillConversationHistory:
    """Tests for conversation history building."""

    def test_build_empty_history(self, tenant_id, agent_id):
        """Test building history from session without messages."""
        session = create_session(tenant_id, agent_id)

        service = MissingFieldResolver()
        history = service._build_conversation_history(session, max_turns=10)

        # Session without message_history attribute returns empty
        assert history == ""


class TestFieldResolutionResultMetadata:
    """Tests for FieldResolutionResult metadata fields."""

    def test_result_has_requirement_fields(self):
        """Test that FieldResolutionResult has requirement metadata fields."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        result = FieldResolutionResult(
            field_name="email",
            filled=False,
            source=ResolutionSource.NOT_FOUND,
            required_level="hard",
            fallback_action="ask",
            collection_order=1,
        )

        assert result.required_level == "hard"
        assert result.fallback_action == "ask"
        assert result.collection_order == 1

    def test_result_defaults_none_for_metadata(self):
        """Test that requirement metadata defaults to None/0."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        result = FieldResolutionResult(
            field_name="email",
            filled=False,
            source=ResolutionSource.NOT_FOUND,
        )

        assert result.required_level is None
        assert result.fallback_action is None
        assert result.collection_order == 0


class TestGetUnfilledHardRequirements:
    """Tests for get_unfilled_hard_requirements helper."""

    def test_returns_unfilled_hard_only(self):
        """Test filtering for unfilled hard requirements."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        results = {
            "email": FieldResolutionResult(
                field_name="email",
                filled=True,
                source=ResolutionSource.SESSION,
            ),
            "phone": FieldResolutionResult(
                field_name="phone",
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            ),
            "address": FieldResolutionResult(
                field_name="address",
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            ),
        }
        # Set requirement metadata
        results["email"].required_level = "hard"
        results["phone"].required_level = "hard"
        results["address"].required_level = "soft"

        service = MissingFieldResolver()
        unfilled = service.get_unfilled_hard_requirements(results)

        assert len(unfilled) == 1
        assert unfilled[0].field_name == "phone"

    def test_returns_empty_when_all_filled(self):
        """Test empty result when all hard requirements are filled."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        results = {
            "email": FieldResolutionResult(
                field_name="email",
                filled=True,
                source=ResolutionSource.SESSION,
            ),
        }
        results["email"].required_level = "hard"

        service = MissingFieldResolver()
        unfilled = service.get_unfilled_hard_requirements(results)

        assert len(unfilled) == 0


class TestGetFieldsToAsk:
    """Tests for get_fields_to_ask helper."""

    def test_returns_ask_fallback_only(self):
        """Test filtering for unfilled fields with ask fallback."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        results = {
            "email": FieldResolutionResult(
                field_name="email",
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            ),
            "phone": FieldResolutionResult(
                field_name="phone",
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            ),
            "nickname": FieldResolutionResult(
                field_name="nickname",
                filled=False,
                source=ResolutionSource.NOT_FOUND,
            ),
        }
        # Set fallback actions
        results["email"].fallback_action = "ask"
        results["email"].collection_order = 2
        results["phone"].fallback_action = "ask"
        results["phone"].collection_order = 1
        results["nickname"].fallback_action = "skip"

        service = MissingFieldResolver()
        to_ask = service.get_fields_to_ask(results)

        assert len(to_ask) == 2
        # Should be sorted by collection_order
        assert to_ask[0].field_name == "phone"  # order=1
        assert to_ask[1].field_name == "email"  # order=2

    def test_excludes_filled_fields(self):
        """Test that filled fields are excluded."""
        from ruche.brains.focal.migration.models import FieldResolutionResult

        results = {
            "email": FieldResolutionResult(
                field_name="email",
                filled=True,  # Already filled
                source=ResolutionSource.SESSION,
            ),
        }
        results["email"].fallback_action = "ask"

        service = MissingFieldResolver()
        to_ask = service.get_fields_to_ask(results)

        assert len(to_ask) == 0
