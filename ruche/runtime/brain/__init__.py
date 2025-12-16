"""Brain protocol and abstractions.

This module defines the Brain protocol that all thinking units implement.
"""

from ruche.runtime.brain.factory import BrainFactory
from ruche.runtime.brain.protocol import Brain, SupersedeCapable, SupersedeDecision

__all__ = [
    "Brain",
    "BrainFactory",
    "SupersedeCapable",
    "SupersedeDecision",
]
