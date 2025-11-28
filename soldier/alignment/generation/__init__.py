"""Alignment generation module.

Contains response generation components with template support.
"""

from soldier.alignment.generation.generator import ResponseGenerator
from soldier.alignment.generation.models import GenerationResult, TemplateMode
from soldier.alignment.generation.prompt_builder import PromptBuilder

__all__ = [
    "GenerationResult",
    "TemplateMode",
    "PromptBuilder",
    "ResponseGenerator",
]
