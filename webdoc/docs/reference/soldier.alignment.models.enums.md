<a id="soldier.alignment.models.enums"></a>

# soldier.alignment.models.enums

Enums for alignment domain.

<a id="soldier.alignment.models.enums.Scope"></a>

## Scope Objects

```python
class Scope(str, Enum)
```

Rule and Template scoping levels.

Determines when a rule or template is active:
- GLOBAL: Always evaluated for the agent
- SCENARIO: Only when the specified scenario is active
- STEP: Only when in the specific step

<a id="soldier.alignment.models.enums.TemplateMode"></a>

## TemplateMode Objects

```python
class TemplateMode(str, Enum)
```

How templates are used in response generation.

- SUGGEST: LLM can adapt the text as a suggestion
- EXCLUSIVE: Use exactly, bypass LLM entirely
- FALLBACK: Use if LLM fails or violates rules

<a id="soldier.alignment.models.enums.VariableUpdatePolicy"></a>

## VariableUpdatePolicy Objects

```python
class VariableUpdatePolicy(str, Enum)
```

When to refresh variable values.

- ON_EACH_TURN: Refresh every turn
- ON_DEMAND: Refresh only when explicitly requested
- ON_SCENARIO_ENTRY: Refresh when entering scenario
- ON_SESSION_START: Refresh at session start only

