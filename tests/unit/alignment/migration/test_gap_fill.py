"""Tests for gap fill service."""

from uuid import uuid4

import pytest

from soldier.alignment.migration.gap_fill import (
    NO_CONFIRM_THRESHOLD,
    USE_THRESHOLD,
    GapFillService,
)
from soldier.alignment.migration.models import GapFillSource
from soldier.conversation.models import Channel, Session


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


class TestGapFillServiceSessionFill:
    """Tests for session variable filling."""

    @pytest.mark.asyncio
    async def test_fill_from_session_variables(self, tenant_id, agent_id):
        """Test that existing session variables are used."""
        session = create_session(
            tenant_id, agent_id, variables={"email": "user@example.com"}
        )

        service = GapFillService()
        result = await service.fill_gap(field_name="email", session=session)

        assert result.filled is True
        assert result.value == "user@example.com"
        assert result.source == GapFillSource.SESSION
        assert result.confidence == 1.0
        assert result.needs_confirmation is False

    @pytest.mark.asyncio
    async def test_session_fill_not_found(self, tenant_id, agent_id):
        """Test that missing fields return not found."""
        session = create_session(tenant_id, agent_id, variables={})

        service = GapFillService()
        result = await service.fill_gap(field_name="email", session=session)

        assert result.filled is False
        assert result.source == GapFillSource.NOT_FOUND

    def test_try_session_fill_direct(self, tenant_id, agent_id):
        """Test direct session fill method."""
        session = create_session(
            tenant_id, agent_id, variables={"phone": "555-1234"}
        )

        service = GapFillService()
        result = service.try_session_fill(field_name="phone", session=session)

        assert result.filled is True
        assert result.value == "555-1234"
        assert result.source == GapFillSource.SESSION


class TestGapFillServiceExtractionParsing:
    """Tests for extraction response parsing."""

    def test_parse_valid_extraction_found(self, tenant_id, agent_id):
        """Test parsing valid extraction response."""
        service = GapFillService()
        response = '{"found": true, "value": "user@example.com", "confidence": 0.95, "source_quote": "my email is user@example.com"}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is True
        assert result.value == "user@example.com"
        assert result.source == GapFillSource.EXTRACTION
        assert result.confidence == 0.95
        assert result.needs_confirmation is False
        assert result.extraction_quote == "my email is user@example.com"

    def test_parse_extraction_not_found(self, tenant_id, agent_id):
        """Test parsing not found response."""
        service = GapFillService()
        response = '{"found": false, "value": null, "confidence": 0.0}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is False
        assert result.source == GapFillSource.NOT_FOUND

    def test_parse_extraction_low_confidence(self, tenant_id, agent_id):
        """Test that low confidence results are rejected."""
        service = GapFillService()
        response = '{"found": true, "value": "maybe@example.com", "confidence": 0.5}'

        result = service._parse_extraction_response("email", response)

        # Below USE_THRESHOLD, treated as not found
        assert result.filled is False
        assert result.source == GapFillSource.NOT_FOUND

    def test_parse_extraction_needs_confirmation(self, tenant_id, agent_id):
        """Test that medium confidence needs confirmation."""
        service = GapFillService()
        response = '{"found": true, "value": "user@example.com", "confidence": 0.90}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is True
        assert result.needs_confirmation is True  # Below NO_CONFIRM_THRESHOLD

    def test_parse_invalid_json(self, tenant_id, agent_id):
        """Test handling of invalid JSON response."""
        service = GapFillService()
        response = "Not valid JSON at all"

        result = service._parse_extraction_response("email", response)

        assert result.filled is False
        assert result.source == GapFillSource.NOT_FOUND

    def test_parse_malformed_response(self, tenant_id, agent_id):
        """Test handling of malformed response."""
        service = GapFillService()
        response = '{"unexpected": "format"}'

        result = service._parse_extraction_response("email", response)

        assert result.filled is False


class TestGapFillServiceMultipleFill:
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

        service = GapFillService()
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

        service = GapFillService()
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

        service = GapFillService()
        history = service._build_conversation_history(session, max_turns=10)

        # Session without message_history attribute returns empty
        assert history == ""
