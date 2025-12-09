<a id="focal.alignment.filtering.rule_filter"></a>

# focal.alignment.filtering.rule\_filter

Rule filtering for alignment pipeline.

Uses LLM-based judgment to determine which candidate rules apply
to the current user message and context.

<a id="focal.alignment.filtering.rule_filter.RuleFilter"></a>

## RuleFilter Objects

```python
class RuleFilter()
```

LLM-based rule relevance filtering.

Evaluates candidate rules against the current context to determine
which rules should apply to this turn.

<a id="focal.alignment.filtering.rule_filter.RuleFilter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(llm_provider: LLMProvider,
             prompt_template: str | None = None,
             relevance_threshold: float = 0.5) -> None
```

Initialize the rule filter.

**Arguments**:

- `llm_provider` - Provider for LLM-based filtering
- `prompt_template` - Optional custom prompt template
- `relevance_threshold` - Minimum relevance score to consider a match

<a id="focal.alignment.filtering.rule_filter.RuleFilter.filter"></a>

#### filter

```python
async def filter(context: Context,
                 candidates: list[Rule],
                 batch_size: int = 5) -> RuleFilterResult
```

Filter rules by relevance to the current context.

**Arguments**:

- `context` - Extracted context from user message
- `candidates` - Candidate rules to evaluate
- `batch_size` - Number of rules to evaluate per LLM call
  

**Returns**:

  RuleFilterResult with matched rules and metadata

