<a id="focal.alignment.filtering.models"></a>

# focal.alignment.filtering.models

Filtering models for alignment pipeline.

Contains models for rule and scenario filtering results.

<a id="focal.alignment.filtering.models.MatchedRule"></a>

## MatchedRule Objects

```python
class MatchedRule(BaseModel)
```

A rule determined to apply to the current turn.

<a id="focal.alignment.filtering.models.RuleFilterResult"></a>

## RuleFilterResult Objects

```python
class RuleFilterResult(BaseModel)
```

Result of rule filtering.

<a id="focal.alignment.filtering.models.ScenarioAction"></a>

## ScenarioAction Objects

```python
class ScenarioAction(str, Enum)
```

Action to take regarding scenario navigation.

<a id="focal.alignment.filtering.models.ScenarioAction.NONE"></a>

#### NONE

No scenario action

<a id="focal.alignment.filtering.models.ScenarioAction.START"></a>

#### START

Start a new scenario

<a id="focal.alignment.filtering.models.ScenarioAction.CONTINUE"></a>

#### CONTINUE

Stay in current step

<a id="focal.alignment.filtering.models.ScenarioAction.TRANSITION"></a>

#### TRANSITION

Move to new step

<a id="focal.alignment.filtering.models.ScenarioAction.EXIT"></a>

#### EXIT

Exit scenario

<a id="focal.alignment.filtering.models.ScenarioAction.RELOCALIZE"></a>

#### RELOCALIZE

Recovery to valid step

<a id="focal.alignment.filtering.models.ScenarioFilterResult"></a>

## ScenarioFilterResult Objects

```python
class ScenarioFilterResult(BaseModel)
```

Result of scenario filtering/navigation.

