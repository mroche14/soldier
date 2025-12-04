<a id="soldier.providers.llm.mock"></a>

# soldier.providers.llm.mock

Mock LLM provider for testing.

<a id="soldier.providers.llm.mock.MockLLMProvider"></a>

## MockLLMProvider Objects

```python
class MockLLMProvider(LLMProvider)
```

Mock LLM provider for testing.

Returns configurable responses without making actual API calls.
Useful for unit testing and development.

<a id="soldier.providers.llm.mock.MockLLMProvider.__init__"></a>

#### \_\_init\_\_

```python
def __init__(default_response: str = "Mock response",
             default_model: str = "mock-model",
             responses: dict[str, str] | None = None,
             stream_chunk_size: int = 10)
```

Initialize mock provider.

**Arguments**:

- `default_response` - Response to return when no match found
- `default_model` - Model name to report
- `responses` - Dict mapping message content to responses
- `stream_chunk_size` - Number of chars per stream chunk

<a id="soldier.providers.llm.mock.MockLLMProvider.provider_name"></a>

#### provider\_name

```python
@property
def provider_name() -> str
```

Return the provider name.

<a id="soldier.providers.llm.mock.MockLLMProvider.call_history"></a>

#### call\_history

```python
@property
def call_history() -> list[dict[str, Any]]
```

Return history of calls for testing assertions.

<a id="soldier.providers.llm.mock.MockLLMProvider.clear_history"></a>

#### clear\_history

```python
def clear_history() -> None
```

Clear call history.

<a id="soldier.providers.llm.mock.MockLLMProvider.set_response"></a>

#### set\_response

```python
def set_response(trigger: str, response: str) -> None
```

Set a response for a specific message content.

<a id="soldier.providers.llm.mock.MockLLMProvider.generate"></a>

#### generate

```python
async def generate(messages: list[LLMMessage],
                   *,
                   model: str | None = None,
                   max_tokens: int = 1024,
                   temperature: float = 0.7,
                   stop_sequences: list[str] | None = None,
                   **kwargs: Any) -> LLMResponse
```

Generate mock response.

<a id="soldier.providers.llm.mock.MockLLMProvider.generate_stream"></a>

#### generate\_stream

```python
async def generate_stream(messages: list[LLMMessage],
                          *,
                          model: str | None = None,
                          max_tokens: int = 1024,
                          temperature: float = 0.7,
                          stop_sequences: list[str] | None = None,
                          **kwargs: Any) -> AsyncIterator[str]
```

Stream mock response in chunks.

<a id="soldier.providers.llm.mock.MockLLMProvider.count_tokens"></a>

#### count\_tokens

```python
async def count_tokens(text: str) -> int
```

Count tokens (mock uses ~4 chars per token).

