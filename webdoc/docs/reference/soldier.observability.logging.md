<a id="focal.observability.logging"></a>

# focal.observability.logging

Structured logging configuration using structlog.

Provides JSON logging for production and console logging for development,
with automatic context binding and PII redaction.

<a id="focal.observability.logging.PIIRedactor"></a>

## PIIRedactor Objects

```python
class PIIRedactor()
```

Processor that redacts PII from log events.

Uses two-tier approach:
1. Key-name lookup via frozenset (O(1)) for known sensitive keys
2. Regex patterns on string values as fallback for accidental PII

<a id="focal.observability.logging.PIIRedactor.__call__"></a>

#### \_\_call\_\_

```python
def __call__(_logger: WrappedLogger, _method_name: str,
             event_dict: EventDict) -> EventDict
```

Redact PII from event dictionary.

<a id="focal.observability.logging.setup_logging"></a>

#### setup\_logging

```python
def setup_logging(level: str = "INFO",
                  format: str = "json",
                  redact_pii: bool = True,
                  _include_trace_id: bool = True) -> None
```

Configure structured logging.

**Arguments**:

- `level` - Minimum log level (DEBUG, INFO, WARNING, ERROR)
- `format` - Output format - "json" for production, "console" for development
- `redact_pii` - Whether to redact PII from logs
- `include_trace_id` - Whether to include trace_id in logs

<a id="focal.observability.logging.get_logger"></a>

#### get\_logger

```python
def get_logger(name: str) -> structlog.stdlib.BoundLogger
```

Get a logger instance bound to the given name.

**Arguments**:

- `name` - Logger name (typically __name__ of the module)
  

**Returns**:

  A bound structlog logger

