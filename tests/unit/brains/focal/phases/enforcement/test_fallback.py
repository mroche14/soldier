"""Unit tests for fallback enforcement handler."""

import pytest
from uuid import uuid4

from ruche.brains.focal.phases.enforcement.fallback import FallbackHandler
from ruche.brains.focal.phases.enforcement.models import (
    ConstraintViolation,
    EnforcementResult,
)
from ruche.brains.focal.models import Template
from ruche.brains.focal.models.enums import TemplateResponseMode


@pytest.fixture
def fallback_handler():
    """Create FallbackHandler instance."""
    return FallbackHandler()


@pytest.fixture
def fallback_template():
    """Create a fallback template."""
    return Template(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Error Fallback",
        content="I apologize, but I cannot assist with that request.",
        mode=TemplateResponseMode.FALLBACK,
    )


@pytest.fixture
def regular_template():
    """Create a regular (non-fallback) template."""
    return Template(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="Regular Response",
        content="Here is your answer.",
        mode=TemplateResponseMode.SUGGEST,
    )


@pytest.fixture
def failed_enforcement_result():
    """Create an enforcement result that failed."""
    return EnforcementResult(
        passed=False,
        violations=[
            ConstraintViolation(
                rule_id=uuid4(),
                rule_name="Test Rule",
                violation_type="contains_prohibited",
                details="Contains prohibited content",
                severity="hard",
            )
        ],
        regeneration_attempted=True,
        regeneration_succeeded=False,
        fallback_used=False,
        fallback_template_id=None,
        final_response="Original problematic response",
        enforcement_time_ms=100.0,
    )


class TestSelectFallback:
    """Tests for select_fallback method."""

    def test_selects_fallback_template_when_present(
        self, fallback_handler, fallback_template, regular_template
    ):
        """Selects template with FALLBACK mode."""
        templates = [regular_template, fallback_template]

        result = fallback_handler.select_fallback(templates)

        assert result == fallback_template

    def test_returns_none_when_no_fallback_template(
        self, fallback_handler, regular_template
    ):
        """Returns None when no fallback template available."""
        templates = [regular_template]

        result = fallback_handler.select_fallback(templates)

        assert result is None

    def test_returns_none_for_empty_list(self, fallback_handler):
        """Returns None for empty template list."""
        result = fallback_handler.select_fallback([])

        assert result is None

    def test_returns_first_fallback_when_multiple(
        self, fallback_handler, fallback_template
    ):
        """Returns first fallback template when multiple present."""
        fallback2 = Template(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="Second Fallback",
            content="Another fallback",
            mode=TemplateResponseMode.FALLBACK,
        )

        templates = [fallback_template, fallback2]

        result = fallback_handler.select_fallback(templates)

        assert result == fallback_template


class TestApplyFallback:
    """Tests for apply_fallback method."""

    def test_applies_fallback_template_to_result(
        self, fallback_handler, fallback_template, failed_enforcement_result
    ):
        """Applies fallback template to failed enforcement result."""
        result = fallback_handler.apply_fallback(
            fallback_template, failed_enforcement_result
        )

        assert result.passed is True
        assert result.fallback_used is True
        assert result.fallback_template_id == fallback_template.id
        assert result.final_response == fallback_template.content
        assert result.violations == failed_enforcement_result.violations
        assert result.regeneration_attempted is True
        assert result.regeneration_succeeded is False

    def test_returns_original_result_when_no_template(
        self, fallback_handler, failed_enforcement_result
    ):
        """Returns original result when no fallback template provided."""
        result = fallback_handler.apply_fallback(None, failed_enforcement_result)

        assert result == failed_enforcement_result
        assert result.passed is False
        assert result.fallback_used is False

    def test_preserves_enforcement_time(
        self, fallback_handler, fallback_template, failed_enforcement_result
    ):
        """Preserves enforcement timing information."""
        result = fallback_handler.apply_fallback(
            fallback_template, failed_enforcement_result
        )

        assert result.enforcement_time_ms == 100.0
