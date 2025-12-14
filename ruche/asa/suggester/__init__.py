"""ASA suggestion components.

This package contains components that generate suggestions for improving
configurations, including policy suggestions and edge case rule generation.
"""

from ruche.asa.suggester.edge_case_generator import EdgeCaseGenerator
from ruche.asa.suggester.policy_suggester import PolicySuggester

__all__ = [
    "EdgeCaseGenerator",
    "PolicySuggester",
]
