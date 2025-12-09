<a id="focal.alignment.context.extractor"></a>

# focal.alignment.context.extractor

Context extraction for alignment pipeline.

Extracts structured context from user messages including intent,
entities, sentiment, and scenario navigation signals.

<a id="focal.alignment.context.extractor.ContextExtractor"></a>

## ContextExtractor Objects

```python
class ContextExtractor()
```

Extract structured context from user messages.

Supports three extraction modes:
- llm: Full LLM-based extraction (highest quality, slowest)
- embedding_only: Vector embedding only (fast, no semantic analysis)
- disabled: Pass-through (fastest, message only)

<a id="focal.alignment.context.extractor.ContextExtractor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(llm_provider: LLMProvider,
             embedding_provider: EmbeddingProvider,
             prompt_template: str | None = None) -> None
```

Initialize the context extractor.

**Arguments**:

- `llm_provider` - Provider for LLM-based extraction
- `embedding_provider` - Provider for generating embeddings
- `prompt_template` - Optional custom prompt template

<a id="focal.alignment.context.extractor.ContextExtractor.extract"></a>

#### extract

```python
async def extract(message: str,
                  history: list[Turn],
                  mode: Literal["llm", "embedding_only", "disabled"] = "llm",
                  session_id: UUID | None = None,
                  tenant_id: UUID | None = None) -> Context
```

Extract structured context from a user message.

**Arguments**:

- `message` - The user's message to analyze
- `history` - Previous conversation turns for context
- `mode` - Extraction mode determining analysis depth
- `session_id` - Optional session ID for logging/tracing
- `tenant_id` - Optional tenant ID for logging/tracing
  

**Returns**:

  Context object with extracted information
  

**Raises**:

- `ValueError` - If message is empty or whitespace-only

