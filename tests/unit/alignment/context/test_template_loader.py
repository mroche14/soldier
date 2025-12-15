"""Tests for Jinja2 TemplateLoader."""

import tempfile
from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from ruche.brains.focal.phases.context.template_loader import TemplateLoader


class TestTemplateLoader:
    """Test suite for TemplateLoader."""

    def test_render_simple_template(self, tmp_path):
        """Test rendering a simple template."""
        # Create a test template
        template_file = tmp_path / "test.jinja2"
        template_file.write_text("Hello {{ name }}!")

        # Load and render
        loader = TemplateLoader(tmp_path)
        result = loader.render("test.jinja2", name="World")

        assert result == "Hello World!"

    def test_render_with_multiple_variables(self, tmp_path):
        """Test rendering with multiple context variables."""
        template_file = tmp_path / "multi.jinja2"
        template_file.write_text(
            "{{ greeting }} {{ name }}, you have {{ count }} messages."
        )

        loader = TemplateLoader(tmp_path)
        result = loader.render(
            "multi.jinja2",
            greeting="Hi",
            name="Alice",
            count=5,
        )

        assert result == "Hi Alice, you have 5 messages."

    def test_render_with_conditionals(self, tmp_path):
        """Test rendering with Jinja2 conditionals."""
        template_file = tmp_path / "conditional.jinja2"
        template_file.write_text(
            """{% if user %}
Hello {{ user }}!
{% else %}
Hello Guest!
{% endif %}"""
        )

        loader = TemplateLoader(tmp_path)

        # With user
        result_with_user = loader.render("conditional.jinja2", user="Bob")
        assert "Hello Bob!" in result_with_user

        # Without user
        result_no_user = loader.render("conditional.jinja2")
        assert "Hello Guest!" in result_no_user

    def test_render_with_loops(self, tmp_path):
        """Test rendering with Jinja2 loops."""
        template_file = tmp_path / "loop.jinja2"
        template_file.write_text(
            """Items:
{% for item in items %}
- {{ item }}
{% endfor %}"""
        )

        loader = TemplateLoader(tmp_path)
        result = loader.render("loop.jinja2", items=["Apple", "Banana", "Cherry"])

        assert "- Apple" in result
        assert "- Banana" in result
        assert "- Cherry" in result

    def test_render_with_dict(self, tmp_path):
        """Test rendering with dictionary variables."""
        template_file = tmp_path / "dict.jinja2"
        template_file.write_text(
            """User: {{ user.name }}
Email: {{ user.email }}"""
        )

        loader = TemplateLoader(tmp_path)
        result = loader.render(
            "dict.jinja2",
            user={"name": "Charlie", "email": "charlie@example.com"},
        )

        assert "User: Charlie" in result
        assert "Email: charlie@example.com" in result

    def test_trim_blocks_enabled(self, tmp_path):
        """Test that trim_blocks is enabled (removes newlines after blocks)."""
        template_file = tmp_path / "trim.jinja2"
        template_file.write_text(
            """{% if true %}
Line 1
{% endif %}
Line 2"""
        )

        loader = TemplateLoader(tmp_path)
        result = loader.render("trim.jinja2")

        # trim_blocks should remove the newline after {% endif %}
        assert "Line 1\nLine 2" in result

    def test_lstrip_blocks_enabled(self, tmp_path):
        """Test that lstrip_blocks is enabled (removes leading whitespace)."""
        template_file = tmp_path / "lstrip.jinja2"
        template_file.write_text(
            """{% for i in range(2) %}
    Item {{ i }}
{% endfor %}"""
        )

        loader = TemplateLoader(tmp_path)
        result = loader.render("lstrip.jinja2")

        # lstrip_blocks should remove leading whitespace before block tags
        # But preserve content indentation
        assert "Item 0" in result
        assert "Item 1" in result

    def test_template_not_found(self, tmp_path):
        """Test that TemplateNotFound is raised for missing templates."""
        loader = TemplateLoader(tmp_path)

        with pytest.raises(TemplateNotFound):
            loader.render("nonexistent.jinja2")

    def test_render_actual_situation_sensor_template(self):
        """Test rendering the actual situation_sensor.jinja2 template."""
        # Get the actual prompts directory
        templates_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "focal"
            / "alignment"
            / "context"
            / "prompts"
        )

        if not templates_dir.exists():
            pytest.skip("Templates directory not found")

        loader = TemplateLoader(templates_dir)

        # Render with minimal context
        result = loader.render(
            "situation_sensor.jinja2",
            message="Hello, I need help",
            schema_mask=None,
            glossary=None,
            conversation_window=[],
            previous_intent_label="none",
        )

        # Check that key sections are present
        assert "User: Hello, I need help" in result
        assert "Task" in result
        assert "language" in result
        assert "candidate_variables" in result

    def test_templates_dir_type(self, tmp_path):
        """Test that templates_dir can be a Path object."""
        template_file = tmp_path / "test.jinja2"
        template_file.write_text("Test")

        # Should work with Path object
        loader = TemplateLoader(tmp_path)
        result = loader.render("test.jinja2")
        assert result == "Test"
