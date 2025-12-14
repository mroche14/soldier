"""Alignment generation module.

Contains response generation components with template support.
"""

from ruche.alignment.generation.generator import ResponseGenerator
from ruche.alignment.generation.models import GenerationResult
from ruche.alignment.generation.prompt_builder import PromptBuilder
from ruche.alignment.models.enums import TemplateResponseMode

__all__ = [
    "GenerationResult",
    "TemplateResponseMode",
    "PromptBuilder",
    "ResponseGenerator",
]
