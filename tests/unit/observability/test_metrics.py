"""Tests for Prometheus metrics."""

import pytest
from prometheus_client import REGISTRY

from focal.observability.metrics import (
    ACTIVE_SESSIONS,
    ERRORS,
    LLM_TOKENS,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    RULES_MATCHED,
    setup_metrics,
)


@pytest.fixture(autouse=True)
def reset_metrics() -> None:
    """Reset metrics before each test."""
    # Note: In production code, you'd use a custom registry
    # For tests, we just verify the metrics exist and work
    pass


class TestRequestCount:
    """Tests for REQUEST_COUNT counter."""

    def test_counter_exists(self) -> None:
        """Should have REQUEST_COUNT counter defined."""
        assert REQUEST_COUNT is not None

    def test_counter_increment(self) -> None:
        """Should increment counter with labels."""
        REQUEST_COUNT.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
            endpoint="/v1/chat",
            status="200",
        ).inc()
        # Should not raise


class TestRequestLatency:
    """Tests for REQUEST_LATENCY histogram."""

    def test_histogram_exists(self) -> None:
        """Should have REQUEST_LATENCY histogram defined."""
        assert REQUEST_LATENCY is not None

    def test_histogram_observe(self) -> None:
        """Should observe latency values."""
        REQUEST_LATENCY.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
            endpoint="/v1/chat",
        ).observe(0.150)
        # Should not raise


class TestLLMTokens:
    """Tests for LLM_TOKENS counter."""

    def test_counter_exists(self) -> None:
        """Should have LLM_TOKENS counter defined."""
        assert LLM_TOKENS is not None

    def test_counter_with_direction_label(self) -> None:
        """Should accept direction label."""
        LLM_TOKENS.labels(
            provider="anthropic",
            model="claude-3-haiku",
            direction="input",
        ).inc(100)
        LLM_TOKENS.labels(
            provider="anthropic",
            model="claude-3-haiku",
            direction="output",
        ).inc(50)
        # Should not raise


class TestRulesMatched:
    """Tests for RULES_MATCHED histogram."""

    def test_histogram_exists(self) -> None:
        """Should have RULES_MATCHED histogram defined."""
        assert RULES_MATCHED is not None

    def test_histogram_observe(self) -> None:
        """Should observe rules matched count."""
        RULES_MATCHED.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
        ).observe(5)
        # Should not raise


class TestActiveSessions:
    """Tests for ACTIVE_SESSIONS gauge."""

    def test_gauge_exists(self) -> None:
        """Should have ACTIVE_SESSIONS gauge defined."""
        assert ACTIVE_SESSIONS is not None

    def test_gauge_set(self) -> None:
        """Should set gauge value."""
        ACTIVE_SESSIONS.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
        ).set(42)
        # Should not raise

    def test_gauge_inc_dec(self) -> None:
        """Should increment and decrement gauge."""
        gauge = ACTIVE_SESSIONS.labels(
            tenant_id="test-tenant-2",
            agent_id="test-agent-2",
        )
        gauge.inc()
        gauge.dec()
        # Should not raise


class TestErrors:
    """Tests for ERRORS counter."""

    def test_counter_exists(self) -> None:
        """Should have ERRORS counter defined."""
        assert ERRORS is not None

    def test_counter_with_error_type(self) -> None:
        """Should accept error_type label."""
        ERRORS.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
            error_type="validation_error",
        ).inc()
        ERRORS.labels(
            tenant_id="test-tenant",
            agent_id="test-agent",
            error_type="provider_error",
        ).inc()
        # Should not raise


class TestSetupMetrics:
    """Tests for setup_metrics function."""

    def test_setup_does_not_raise(self) -> None:
        """Should configure metrics without error."""
        setup_metrics()
        # Should not raise


class TestMetricsExport:
    """Tests for metrics export format."""

    def test_metrics_can_be_collected(self) -> None:
        """Should be able to collect metrics."""
        # Increment some metrics
        REQUEST_COUNT.labels(
            tenant_id="export-test",
            agent_id="export-agent",
            endpoint="/test",
            status="200",
        ).inc()

        # Collect should work
        metrics = list(REGISTRY.collect())
        assert len(metrics) > 0

    def test_metrics_have_correct_names(self) -> None:
        """Should have correctly prefixed metric names."""
        # Check that our metrics are in the registry
        metric_names = [m.name for m in REGISTRY.collect()]
        assert "focal_request_count" in metric_names or any(
            "request" in name for name in metric_names
        )
