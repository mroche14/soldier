"""Jinja2 template loader for LLM prompts.

Centralized template loading and rendering for all LLM tasks.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateLoader:
    """Loads and renders Jinja2 templates for LLM tasks.

    Provides centralized Jinja2 template management following
    the LLM Task Pattern from CLAUDE.md.
    """

    def __init__(self, templates_dir: Path):
        """Initialize template loader.

        Args:
            templates_dir: Directory containing .jinja2 template files
        """
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context) -> str:
        """Render a template with context variables.

        Args:
            template_name: Template filename (e.g., "situation_sensor.jinja2")
            **context: Variables to pass to template

        Returns:
            Rendered template string

        Raises:
            jinja2.TemplateNotFound: If template doesn't exist
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
