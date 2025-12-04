<a id="soldier.alignment.context.models"></a>

# soldier.alignment.context.models

Context models for alignment pipeline.

Contains enriched context models for understanding user messages,
including intent, entities, sentiment, and scenario navigation hints.

<a id="soldier.alignment.context.models.Sentiment"></a>

## Sentiment Objects

```python
class Sentiment(str, Enum)
```

Detected sentiment of the user message.

<a id="soldier.alignment.context.models.Urgency"></a>

## Urgency Objects

```python
class Urgency(str, Enum)
```

Urgency level detected from the message.

<a id="soldier.alignment.context.models.ScenarioSignal"></a>

## ScenarioSignal Objects

```python
class ScenarioSignal(str, Enum)
```

Signal about scenario navigation intent.

<a id="soldier.alignment.context.models.ScenarioSignal.START"></a>

#### START

User wants to begin a process

<a id="soldier.alignment.context.models.ScenarioSignal.CONTINUE"></a>

#### CONTINUE

Normal flow continuation

<a id="soldier.alignment.context.models.ScenarioSignal.EXIT"></a>

#### EXIT

User wants to leave/cancel

<a id="soldier.alignment.context.models.ScenarioSignal.UNKNOWN"></a>

#### UNKNOWN

Unclear intent

<a id="soldier.alignment.context.models.ExtractedEntity"></a>

## ExtractedEntity Objects

```python
class ExtractedEntity(BaseModel)
```

An entity extracted from the message.

<a id="soldier.alignment.context.models.Turn"></a>

## Turn Objects

```python
class Turn(BaseModel)
```

A single turn in the conversation history.

<a id="soldier.alignment.context.models.Context"></a>

## Context Objects

```python
class Context(BaseModel)
```

Extracted context from a user message.

This is the enriched understanding of what the user said,
including semantic analysis, entity extraction, and
navigation hints.

