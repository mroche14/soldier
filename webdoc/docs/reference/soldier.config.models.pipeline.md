<a id="soldier.config.models.pipeline"></a>

# soldier.config.models.pipeline

Turn pipeline configuration models.

<a id="soldier.config.models.pipeline.ContextExtractionConfig"></a>

## ContextExtractionConfig Objects

```python
class ContextExtractionConfig(BaseModel)
```

Context extraction step configuration.

<a id="soldier.config.models.pipeline.RetrievalConfig"></a>

## RetrievalConfig Objects

```python
class RetrievalConfig(BaseModel)
```

Retrieval step configuration.

<a id="soldier.config.models.pipeline.RerankingConfig"></a>

## RerankingConfig Objects

```python
class RerankingConfig(BaseModel)
```

Reranking step configuration.

<a id="soldier.config.models.pipeline.RuleFilteringConfig"></a>

## RuleFilteringConfig Objects

```python
class RuleFilteringConfig(BaseModel)
```

Rule filtering step configuration.

<a id="soldier.config.models.pipeline.ScenarioFilteringConfig"></a>

## ScenarioFilteringConfig Objects

```python
class ScenarioFilteringConfig(BaseModel)
```

Scenario filtering step configuration.

<a id="soldier.config.models.pipeline.ToolExecutionConfig"></a>

## ToolExecutionConfig Objects

```python
class ToolExecutionConfig(BaseModel)
```

Tool execution step configuration.

<a id="soldier.config.models.pipeline.GenerationConfig"></a>

## GenerationConfig Objects

```python
class GenerationConfig(BaseModel)
```

Response generation step configuration.

<a id="soldier.config.models.pipeline.EnforcementConfig"></a>

## EnforcementConfig Objects

```python
class EnforcementConfig(BaseModel)
```

Enforcement step configuration.

<a id="soldier.config.models.pipeline.EntityExtractionConfig"></a>

## EntityExtractionConfig Objects

```python
class EntityExtractionConfig(BaseModel)
```

Entity extraction configuration.

<a id="soldier.config.models.pipeline.EntityDeduplicationConfig"></a>

## EntityDeduplicationConfig Objects

```python
class EntityDeduplicationConfig(BaseModel)
```

Entity deduplication configuration.

<a id="soldier.config.models.pipeline.WindowSummarizationConfig"></a>

## WindowSummarizationConfig Objects

```python
class WindowSummarizationConfig(BaseModel)
```

Window summarization configuration.

<a id="soldier.config.models.pipeline.MetaSummarizationConfig"></a>

## MetaSummarizationConfig Objects

```python
class MetaSummarizationConfig(BaseModel)
```

Meta-summarization configuration.

<a id="soldier.config.models.pipeline.SummarizationConfig"></a>

## SummarizationConfig Objects

```python
class SummarizationConfig(BaseModel)
```

Summarization configuration.

<a id="soldier.config.models.pipeline.MemoryIngestionConfig"></a>

## MemoryIngestionConfig Objects

```python
class MemoryIngestionConfig(BaseModel)
```

Memory ingestion system configuration.

<a id="soldier.config.models.pipeline.PipelineConfig"></a>

## PipelineConfig Objects

```python
class PipelineConfig(BaseModel)
```

Configuration for the turn pipeline.

<a id="soldier.config.models.pipeline.PipelineConfig.llm_filtering"></a>

#### llm\_filtering

```python
@property
def llm_filtering() -> RuleFilteringConfig
```

Alias for rule_filtering for backwards compatibility.

