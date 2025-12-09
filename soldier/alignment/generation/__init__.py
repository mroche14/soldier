"""Alignment generation module.

Contains response generation components with template support.
"""

from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.generation.models import GenerationResult
from soldier.alignment.generation.prompt_builder import PromptBuilder
from soldier.alignment.models.enums import TemplateResponseMode

__all__ = [
    "GenerationResult",
    "TemplateResponseMode",
    "PromptBuilder",
    "ResponseGenerator",
]
