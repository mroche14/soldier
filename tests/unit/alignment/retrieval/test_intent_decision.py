"""Tests for canonical intent decision logic."""

import pytest
from uuid import uuid4

from ruche.brains.focal.models.intent import IntentCandidate
from ruche.brains.focal.retrieval.intent_retriever import decide_canonical_intent


class TestDecideCanonicalIntent:
    """Test canonical intent decision merging."""

    def test_trusts_confident_sensor(self):
        """Test that confident LLM sensor intent is used."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.9
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.8,
                source="hybrid",
            )
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should trust confident sensor
        assert canonical == "order_cancellation"
        assert confidence == 0.9

    def test_prefers_hybrid_over_low_confidence_sensor(self):
        """Test that hybrid retrieval overrides low-confidence sensor."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.5  # Low confidence
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.85,  # High confidence
                source="hybrid",
            )
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should use hybrid candidate
        assert canonical == "refund_request"
        assert confidence == 0.85

    def test_fallback_to_sensor_when_both_low(self):
        """Test fallback to sensor when both sensor and hybrid are low confidence."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.5
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.6,  # Below threshold
                source="hybrid",
            )
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should fallback to sensor (even though low confidence)
        assert canonical == "order_cancellation"
        assert confidence == 0.5

    def test_no_sensor_uses_hybrid(self):
        """Test that hybrid is used when sensor has no intent."""
        sensor_intent = None
        sensor_confidence = None
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="order_status",
                score=0.75,
                source="hybrid",
            )
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should use hybrid candidate
        assert canonical == "order_status"
        assert confidence == 0.75

    def test_no_sensor_no_hybrid(self):
        """Test when neither sensor nor hybrid have results."""
        sensor_intent = None
        sensor_confidence = None
        hybrid_candidates = []

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should return None
        assert canonical is None
        assert confidence == 0.0

    def test_empty_hybrid_uses_sensor(self):
        """Test that sensor is used when hybrid has no results."""
        sensor_intent = "order_status"
        sensor_confidence = 0.6
        hybrid_candidates = []

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should use sensor (even below threshold)
        assert canonical == "order_status"
        assert confidence == 0.6

    def test_custom_threshold(self):
        """Test decision with custom threshold."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.8
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.85,
                source="hybrid",
            )
        ]

        # High threshold - sensor below it
        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.85,
        )

        # Should use hybrid since sensor below threshold
        assert canonical == "refund_request"
        assert confidence == 0.85

    def test_sensor_at_threshold(self):
        """Test sensor intent exactly at threshold."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.7
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.65,
                source="hybrid",
            )
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Sensor at threshold should be trusted
        assert canonical == "order_cancellation"
        assert confidence == 0.7

    def test_multiple_hybrid_candidates_uses_top(self):
        """Test that only top hybrid candidate is considered."""
        sensor_intent = "order_cancellation"
        sensor_confidence = 0.5
        hybrid_candidates = [
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="refund_request",
                score=0.85,
                source="hybrid",
            ),
            IntentCandidate(
                intent_id=uuid4(),
                intent_name="order_status",
                score=0.75,
                source="hybrid",
            ),
        ]

        canonical, confidence = decide_canonical_intent(
            sensor_intent=sensor_intent,
            sensor_confidence=sensor_confidence,
            hybrid_candidates=hybrid_candidates,
            threshold=0.7,
        )

        # Should use top hybrid candidate
        assert canonical == "refund_request"
        assert confidence == 0.85
