"""Alignment generation module.

Contains response generation components with template support.
"""

from focal.alignment.generation.generator import ResponseGenerator
from focal.alignment.generation.models import GenerationResult
from focal.alignment.generation.prompt_builder import PromptBuilder
from focal.alignment.models.enums import TemplateResponseMode

__all__ = [
    "GenerationResult",
    "TemplateResponseMode",
    "PromptBuilder",
    "ResponseGenerator",
]
