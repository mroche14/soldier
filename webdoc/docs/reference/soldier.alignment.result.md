<a id="soldier.alignment.result"></a>

# soldier.alignment.result

Pipeline result models for alignment engine.

Contains the main AlignmentResult and timing models.

<a id="soldier.alignment.result.PipelineStepTiming"></a>

## PipelineStepTiming Objects

```python
class PipelineStepTiming(BaseModel)
```

Timing information for a single pipeline step.

<a id="soldier.alignment.result.AlignmentResult"></a>

## AlignmentResult Objects

```python
class AlignmentResult(BaseModel)
```

Complete result of processing a turn through the alignment pipeline.

This is the primary output of the AlignmentEngine. It contains
all intermediate results for auditability and debugging.

