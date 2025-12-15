"""Alignment generation module.

Contains response generation components with template support.
"""

from ruche.brains.focal.phases.generation.generator import ResponseGenerator
from ruche.brains.focal.phases.generation.models import GenerationResult
from ruche.brains.focal.phases.generation.prompt_builder import PromptBuilder
from ruche.brains.focal.models.enums import TemplateResponseMode

__all__ = [
    "GenerationResult",
    "TemplateResponseMode",
    "PromptBuilder",
    "ResponseGenerator",
]
