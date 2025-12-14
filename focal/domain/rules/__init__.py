"""Rule domain models.

This module contains all models related to behavioral rules:
- Rule: Behavioral policy (when X, then Y)
- MatchedRule: Rule that matched with scoring
- Scope: Rule scoping levels (GLOBAL, SCENARIO, STEP)
- ToolBinding: Tool execution scheduling
"""

from focal.domain.rules.models import (
    AgentScopedModel,
    MatchedRule,
    Rule,
    Scope,
    TenantScopedModel,
    ToolBinding,
)

__all__ = [
    "Rule",
    "MatchedRule",
    "Scope",
    "ToolBinding",
    "TenantScopedModel",
    "AgentScopedModel",
]
