"""Enums for alignment domain."""

from enum import Enum


class Scope(str, Enum):
    """Rule and Template scoping levels.

    Determines when a rule or template is active:
    - GLOBAL: Always evaluated for the agent
    - SCENARIO: Only when the specified scenario is active
    - STEP: Only when in the specific step
    """

    GLOBAL = "global"
    SCENARIO = "scenario"
    STEP = "step"


class TemplateMode(str, Enum):
    """How templates are used in response generation.

    - SUGGEST: LLM can adapt the text as a suggestion
    - EXCLUSIVE: Use exactly, bypass LLM entirely
    - FALLBACK: Use if LLM fails or violates rules
    """

    SUGGEST = "suggest"
    EXCLUSIVE = "exclusive"
    FALLBACK = "fallback"


class VariableUpdatePolicy(str, Enum):
    """When to refresh variable values.

    - ON_EACH_TURN: Refresh every turn
    - ON_DEMAND: Refresh only when explicitly requested
    - ON_SCENARIO_ENTRY: Refresh when entering scenario
    - ON_SESSION_START: Refresh at session start only
    """

    ON_EACH_TURN = "on_each_turn"
    ON_DEMAND = "on_demand"
    ON_SCENARIO_ENTRY = "on_scenario_entry"
    ON_SESSION_START = "on_session_start"
