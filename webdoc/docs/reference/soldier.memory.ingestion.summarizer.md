<a id="soldier.memory.ingestion.summarizer"></a>

# soldier.memory.ingestion.summarizer

Conversation summarization for long conversations.

<a id="soldier.memory.ingestion.summarizer.ConversationSummarizer"></a>

## ConversationSummarizer Objects

```python
class ConversationSummarizer()
```

Generate hierarchical conversation summaries.

<a id="soldier.memory.ingestion.summarizer.ConversationSummarizer.__init__"></a>

#### \_\_init\_\_

```python
def __init__(llm_provider: LLMProvider, memory_store: MemoryStore,
             config: SummarizationConfig)
```

Initialize conversation summarizer.

**Arguments**:

- `llm_provider` - LLM provider for summarization
- `memory_store` - Memory store
- `config` - Summarization configuration

<a id="soldier.memory.ingestion.summarizer.ConversationSummarizer.summarize_window"></a>

#### summarize\_window

```python
async def summarize_window(episodes: list[Episode], group_id: str) -> Episode
```

Create summary of conversation window.

Uses LLM to generate concise summary of N turns.
Summary is returned as Episode with content_type="summary".

**Arguments**:

- `episodes` - Window of episodes to summarize (typically 10-50)
- `group_id` - Tenant:session for the summary
  

**Returns**:

- `Episode` - Summary episode (NOT persisted, caller stores it)
  

**Raises**:

- `SummarizationError` - If LLM call fails

<a id="soldier.memory.ingestion.summarizer.ConversationSummarizer.create_meta_summary"></a>

#### create\_meta\_summary

```python
async def create_meta_summary(summaries: list[Episode],
                              group_id: str) -> Episode
```

Create meta-summary (summary of summaries).

For very long conversations, combines multiple window
summaries into higher-level overview.

**Arguments**:

- `summaries` - Window summaries to combine (typically 5-10)
- `group_id` - Tenant:session for the meta-summary
  

**Returns**:

- `Episode` - Meta-summary episode (NOT persisted)
  

**Raises**:

- `SummarizationError` - If LLM call fails

<a id="soldier.memory.ingestion.summarizer.ConversationSummarizer.check_and_summarize_if_needed"></a>

#### check\_and\_summarize\_if\_needed

```python
async def check_and_summarize_if_needed(group_id: str) -> Episode | None
```

Check if summarization threshold reached and summarize if needed.

Queries MemoryStore to count episodes, compares against thresholds,
and triggers window or meta-summary generation.

**Arguments**:

- `group_id` - Tenant:session to check
  

**Returns**:

- `Episode` - Created summary if threshold was reached, None otherwise
  (Summary is automatically persisted by this method)
  

**Raises**:

- `SummarizationError` - If summary generation or storage fails

