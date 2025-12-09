"""Tests for SituationSnapshot and CandidateVariableInfo models."""

import pytest
from pydantic import ValidationError

from focal.alignment.context.situation_snapshot import (
    CandidateVariableInfo,
    SituationSnapshot,
)


class TestCandidateVariableInfo:
    """Test suite for CandidateVariableInfo model."""

    def test_create_with_required_fields(self):
        """Test model creation with required fields."""
        var_info = CandidateVariableInfo(
            value="John Doe",
            scope="IDENTITY",
        )

        assert var_info.value == "John Doe"
        assert var_info.scope == "IDENTITY"
        assert var_info.is_update is False  # default

    def test_create_with_all_fields(self):
        """Test model creation with all fields."""
        var_info = CandidateVariableInfo(
            value="order_12345",
            scope="CASE",
            is_update=True,
        )

        assert var_info.value == "order_12345"
        assert var_info.scope == "CASE"
        assert var_info.is_update is True

    def test_scope_validation(self):
        """Test that only valid scopes are accepted."""
        # Valid scopes
        for scope in ["IDENTITY", "BUSINESS", "CASE", "SESSION"]:
            var_info = CandidateVariableInfo(value="test", scope=scope)
            assert var_info.scope == scope

        # Invalid scope
        with pytest.raises(ValidationError):
            CandidateVariableInfo(value="test", scope="INVALID")

    def test_value_can_be_any_type(self):
        """Test that value field accepts any type."""
        # String
        var1 = CandidateVariableInfo(value="text", scope="IDENTITY")
        assert var1.value == "text"

        # Number
        var2 = CandidateVariableInfo(value=42, scope="IDENTITY")
        assert var2.value == 42

        # Boolean
        var3 = CandidateVariableInfo(value=True, scope="IDENTITY")
        assert var3.value is True

        # Dict
        var4 = CandidateVariableInfo(value={"key": "val"}, scope="IDENTITY")
        assert var4.value == {"key": "val"}


class TestSituationSnapshot:
    """Test suite for SituationSnapshot model."""

    def test_create_with_required_fields(self):
        """Test model creation with required fields only."""
        snapshot = SituationSnapshot(message="test",
            language="en",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
        )

        assert snapshot.language == "en"
        assert snapshot.intent_changed is False
        assert snapshot.topic_changed is False
        assert snapshot.tone == "neutral"
        assert snapshot.previous_intent_label is None
        assert snapshot.new_intent_label is None
        assert snapshot.new_intent_text is None
        assert snapshot.frustration_level is None
        assert snapshot.situation_facts == []
        assert snapshot.candidate_variables == {}

    def test_create_with_all_fields(self):
        """Test model creation with all fields populated."""
        snapshot = SituationSnapshot(message="test",
            language="es",
            previous_intent_label="greeting",
            intent_changed=True,
            new_intent_label="refund_request",
            new_intent_text="User wants to request a refund",
            topic_changed=True,
            tone="frustrated",
            frustration_level="high",
            situation_facts=["User ordered product #123", "Product arrived damaged"],
            candidate_variables={
                "order_id": CandidateVariableInfo(
                    value="123",
                    scope="CASE",
                    is_update=False,
                )
            },
        )

        assert snapshot.language == "es"
        assert snapshot.previous_intent_label == "greeting"
        assert snapshot.intent_changed is True
        assert snapshot.new_intent_label == "refund_request"
        assert snapshot.new_intent_text == "User wants to request a refund"
        assert snapshot.topic_changed is True
        assert snapshot.tone == "frustrated"
        assert snapshot.frustration_level == "high"
        assert len(snapshot.situation_facts) == 2
        assert "order_id" in snapshot.candidate_variables

    def test_frustration_level_validation(self):
        """Test that only valid frustration levels are accepted."""
        # Valid levels
        for level in ["low", "medium", "high"]:
            snapshot = SituationSnapshot(message="test",
                language="en",
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
                frustration_level=level,
            )
            assert snapshot.frustration_level == level

        # None is also valid
        snapshot = SituationSnapshot(message="test",
            language="en",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            frustration_level=None,
        )
        assert snapshot.frustration_level is None

        # Invalid level
        with pytest.raises(ValidationError):
            SituationSnapshot(message="test",
                language="en",
                intent_changed=False,
                topic_changed=False,
                tone="neutral",
                frustration_level="extreme",
            )

    def test_candidate_variables_dict_parsing(self):
        """Test that candidate_variables dict is properly parsed."""
        snapshot = SituationSnapshot(message="test",
            language="en",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            candidate_variables={
                "name": CandidateVariableInfo(
                    value="John",
                    scope="IDENTITY",
                ),
                "email": CandidateVariableInfo(
                    value="john@example.com",
                    scope="IDENTITY",
                    is_update=True,
                ),
            },
        )

        assert len(snapshot.candidate_variables) == 2
        assert snapshot.candidate_variables["name"].value == "John"
        assert snapshot.candidate_variables["name"].scope == "IDENTITY"
        assert snapshot.candidate_variables["name"].is_update is False
        assert snapshot.candidate_variables["email"].value == "john@example.com"
        assert snapshot.candidate_variables["email"].is_update is True

    def test_empty_candidate_variables(self):
        """Test snapshot with no candidate variables."""
        snapshot = SituationSnapshot(message="test",
            language="en",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            candidate_variables={},
        )

        assert snapshot.candidate_variables == {}

    def test_situation_facts_list(self):
        """Test situation_facts as list of strings."""
        facts = [
            "User is a premium customer",
            "Order was placed yesterday",
            "Payment was successful",
        ]

        snapshot = SituationSnapshot(message="test",
            language="en",
            intent_changed=False,
            topic_changed=False,
            tone="neutral",
            situation_facts=facts,
        )

        assert snapshot.situation_facts == facts
        assert len(snapshot.situation_facts) == 3
