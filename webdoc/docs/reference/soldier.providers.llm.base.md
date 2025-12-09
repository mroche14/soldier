<a id="focal.providers.llm.base"></a>

# focal.providers.llm.base

LLMProvider abstract interface.

<a id="focal.providers.llm.base.LLMMessage"></a>

## LLMMessage Objects

```python
class LLMMessage(BaseModel)
```

A message in a conversation.

<a id="focal.providers.llm.base.LLMResponse"></a>

## LLMResponse Objects

```python
class LLMResponse(BaseModel)
```

Response from an LLM provider.

<a id="focal.providers.llm.base.LLMProvider"></a>

## LLMProvider Objects

```python
class LLMProvider(ABC)
```

Abstract interface for LLM text generation.

Provides unified access to various LLM providers
(Anthropic, OpenAI, etc.) with streaming support.

<a id="focal.providers.llm.base.LLMProvider.provider_name"></a>

#### provider\_name

```python
@property
@abstractmethod
def provider_name() -> str
```

Return the provider name.

<a id="focal.providers.llm.base.LLMProvider.generate"></a>

#### generate

```python
@abstractmethod
async def generate(messages: list[LLMMessage],
                   *,
                   model: str | None = None,
                   max_tokens: int = 1024,
                   temperature: float = 0.7,
                   stop_sequences: list[str] | None = None,
                   **kwargs: Any) -> LLMResponse
```

Generate text from messages.

**Arguments**:

- `messages` - Conversation messages
- `model` - Model to use (provider default if not specified)
- `max_tokens` - Maximum tokens to generate
- `temperature` - Sampling temperature
- `stop_sequences` - Stop generation on these strings
- `**kwargs` - Provider-specific options
  

**Returns**:

  LLMResponse with generated content

<a id="focal.providers.llm.base.LLMProvider.generate_stream"></a>

#### generate\_stream

```python
@abstractmethod
def generate_stream(messages: list[LLMMessage],
                    *,
                    model: str | None = None,
                    max_tokens: int = 1024,
                    temperature: float = 0.7,
                    stop_sequences: list[str] | None = None,
                    **kwargs: Any) -> AsyncIterator[str]
```

Stream generated text.

**Arguments**:

- `messages` - Conversation messages
- `model` - Model to use (provider default if not specified)
- `max_tokens` - Maximum tokens to generate
- `temperature` - Sampling temperature
- `stop_sequences` - Stop generation on these strings
- `**kwargs` - Provider-specific options
  

**Yields**:

  Text chunks as they are generated

<a id="focal.providers.llm.base.LLMProvider.count_tokens"></a>

#### count\_tokens

```python
async def count_tokens(text: str) -> int
```

Count tokens in text.

Default implementation estimates ~4 chars per token.
Providers should override with accurate counts.

