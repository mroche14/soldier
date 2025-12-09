<a id="focal.alignment.retrieval.models"></a>

# focal.alignment.retrieval.models

Retrieval models for alignment pipeline.

Contains models for scored rules, scenarios, and retrieval results.

<a id="focal.alignment.retrieval.models.RuleSource"></a>

## RuleSource Objects

```python
class RuleSource(str, Enum)
```

Source/scope of a retrieved rule.

<a id="focal.alignment.retrieval.models.RuleSource.GLOBAL"></a>

#### GLOBAL

Global scope

<a id="focal.alignment.retrieval.models.RuleSource.SCENARIO"></a>

#### SCENARIO

Scenario-scoped

<a id="focal.alignment.retrieval.models.RuleSource.STEP"></a>

#### STEP

Step-scoped

<a id="focal.alignment.retrieval.models.RuleSource.DIRECT"></a>

#### DIRECT

Directly referenced

<a id="focal.alignment.retrieval.models.ScoredRule"></a>

## ScoredRule Objects

```python
class ScoredRule(BaseModel)
```

A rule with its retrieval score.

<a id="focal.alignment.retrieval.models.ScoredScenario"></a>

## ScoredScenario Objects

```python
class ScoredScenario(BaseModel)
```

A scenario with its retrieval score.

<a id="focal.alignment.retrieval.models.ScoredEpisode"></a>

## ScoredEpisode Objects

```python
class ScoredEpisode(BaseModel)
```

A memory episode with its retrieval score.

<a id="focal.alignment.retrieval.models.RetrievalResult"></a>

## RetrievalResult Objects

```python
class RetrievalResult(BaseModel)
```

Result of the retrieval step.

