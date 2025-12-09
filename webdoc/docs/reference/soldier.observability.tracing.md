<a id="focal.observability.tracing"></a>

# focal.observability.tracing

OpenTelemetry distributed tracing setup.

Provides trace context propagation, span creation, and OTLP export.
Supports W3C Trace Context for cross-service correlation.

<a id="focal.observability.tracing.setup_tracing"></a>

#### setup\_tracing

```python
def setup_tracing(service_name: str = "focal",
                  otlp_endpoint: str | None = None,
                  console_export: bool = False,
                  _sample_rate: float = 1.0) -> Tracer
```

Initialize OpenTelemetry tracing.

**Arguments**:

- `service_name` - Name to identify this service in traces
- `otlp_endpoint` - OTLP gRPC endpoint (e.g., "localhost:4317")
  Falls back to OTEL_EXPORTER_OTLP_ENDPOINT env var
- `console_export` - Also export spans to console (for debugging)
- `sample_rate` - Fraction of traces to sample (0.0 to 1.0)
  

**Returns**:

  Configured Tracer instance

<a id="focal.observability.tracing.get_tracer"></a>

#### get\_tracer

```python
def get_tracer() -> Tracer
```

Get the configured tracer, or a no-op tracer if not initialized.

**Returns**:

  Tracer instance

<a id="focal.observability.tracing.extract_context"></a>

#### extract\_context

```python
def extract_context(headers: dict[str, str]) -> Context
```

Extract trace context from HTTP headers.

Supports W3C Trace Context (traceparent/tracestate headers).

**Arguments**:

- `headers` - HTTP headers dict
  

**Returns**:

  OpenTelemetry Context with extracted trace info

<a id="focal.observability.tracing.inject_context"></a>

#### inject\_context

```python
def inject_context(headers: dict[str, str],
                   context: Context | None = None) -> None
```

Inject trace context into HTTP headers.

Adds W3C Trace Context headers (traceparent/tracestate).

**Arguments**:

- `headers` - HTTP headers dict to inject into
- `context` - Context to inject (current if not specified)

<a id="focal.observability.tracing.get_current_trace_id"></a>

#### get\_current\_trace\_id

```python
def get_current_trace_id() -> str | None
```

Get the current trace ID as a hex string.

**Returns**:

  Trace ID or None if not in a trace

<a id="focal.observability.tracing.get_current_span_id"></a>

#### get\_current\_span\_id

```python
def get_current_span_id() -> str | None
```

Get the current span ID as a hex string.

**Returns**:

  Span ID or None if not in a span

<a id="focal.observability.tracing.create_span"></a>

#### create\_span

```python
@contextmanager
def create_span(name: str,
                kind: SpanKind = SpanKind.INTERNAL,
                attributes: dict[str, Any] | None = None,
                context: Context | None = None) -> Generator[Span, None, None]
```

Create a new span as a context manager.

**Arguments**:

- `name` - Span name
- `kind` - Span kind (INTERNAL, SERVER, CLIENT, etc.)
- `attributes` - Initial span attributes
- `context` - Parent context (current if not specified)
  

**Yields**:

  The created span

<a id="focal.observability.tracing.record_exception"></a>

#### record\_exception

```python
def record_exception(span: Span,
                     exception: Exception,
                     escaped: bool = True) -> None
```

Record an exception on a span.

**Arguments**:

- `span` - Span to record on
- `exception` - The exception that occurred
- `escaped` - Whether the exception escaped the span scope

<a id="focal.observability.tracing.set_span_attributes"></a>

#### set\_span\_attributes

```python
def set_span_attributes(span: Span, **attributes: Any) -> None
```

Set multiple attributes on a span.

**Arguments**:

- `span` - Span to set attributes on
- `**attributes` - Key-value pairs to set

<a id="focal.observability.tracing.TracingContext"></a>

## TracingContext Objects

```python
class TracingContext()
```

Context manager for traced operations with common patterns.

Provides convenient tracing for turn processing and pipeline steps.

<a id="focal.observability.tracing.TracingContext.__init__"></a>

#### \_\_init\_\_

```python
def __init__(tenant_id: str, agent_id: str, session_id: str)
```

Initialize tracing context.

**Arguments**:

- `tenant_id` - Tenant identifier
- `agent_id` - Agent identifier
- `session_id` - Session identifier

<a id="focal.observability.tracing.TracingContext.turn_span"></a>

#### turn\_span

```python
@contextmanager
def turn_span(
        turn_id: str,
        user_message_preview: str | None = None
) -> Generator[Span, None, None]
```

Create a span for a turn.

**Arguments**:

- `turn_id` - Turn identifier
- `user_message_preview` - First N chars of user message
  

**Yields**:

  Turn span

<a id="focal.observability.tracing.TracingContext.pipeline_step_span"></a>

#### pipeline\_step\_span

```python
@contextmanager
def pipeline_step_span(step_name: str,
                       turn_id: str) -> Generator[Span, None, None]
```

Create a span for a pipeline step.

**Arguments**:

- `step_name` - Pipeline step name (e.g., "context_extraction")
- `turn_id` - Turn identifier
  

**Yields**:

  Pipeline step span

<a id="focal.observability.tracing.TracingContext.llm_call_span"></a>

#### llm\_call\_span

```python
@contextmanager
def llm_call_span(provider: str, model: str,
                  purpose: str) -> Generator[Span, None, None]
```

Create a span for an LLM API call.

**Arguments**:

- `provider` - LLM provider name
- `model` - Model identifier
- `purpose` - Call purpose (e.g., "context_extraction", "generation")
  

**Yields**:

  LLM call span

