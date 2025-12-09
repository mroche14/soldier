# Quickstart: API Layer - Core

**Feature**: 006-api-layer-core
**Date**: 2025-11-28

## Prerequisites

1. Python 3.11+ installed
2. Project dependencies installed: `uv sync`
3. Redis running (optional, for rate limiting and idempotency)

## Installation

Add the new dependencies to pyproject.toml:

```bash
uv add fastapi uvicorn python-jose sse-starlette httpx
uv add --optional api redis
```

## Running the API Server

### Development Mode

```bash
# Start with auto-reload
uv run uvicorn focal.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Or with the CLI (when implemented)
uv run focal serve --dev
```

### Production Mode

```bash
# Multiple workers with gunicorn
uv run gunicorn focal.api.app:create_app \
    --factory \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

## Configuration

Set environment variables or create `config/development.toml`:

```toml
[api]
host = "0.0.0.0"
port = 8000
workers = 4
cors_origins = ["http://localhost:3000"]

[api.rate_limit]
enabled = true
requests_per_minute = 60
burst_size = 10
```

### Required Environment Variables

```bash
# For JWT validation
export FOCAL_JWT_SECRET="your-secret-key"

# For Redis-backed rate limiting (optional)
export REDIS_URL="redis://localhost:6379/0"
```

## Quick API Test

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": [
    {"name": "config_store", "status": "healthy"},
    {"name": "session_store", "status": "healthy"}
  ],
  "timestamp": "2025-11-28T10:30:00Z"
}
```

### Send a Message

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "channel": "webchat",
    "user_channel_id": "user123",
    "message": "Hello, I need help with my order"
  }'
```

Expected response:
```json
{
  "response": "Hello! I'd be happy to help you with your order. Could you please provide your order number?",
  "session_id": "sess_abc123",
  "turn_id": "turn_xyz789",
  "matched_rules": ["rule_greeting", "rule_order_inquiry"],
  "tools_called": [],
  "tokens_used": 125,
  "latency_ms": 450
}
```

### Stream a Response

```bash
curl -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Accept: text/event-stream" \
  -d '{
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "channel": "webchat",
    "user_channel_id": "user123",
    "message": "Tell me about your return policy"
  }'
```

Expected SSE stream:
```
event: token
data: {"content": "Our "}

event: token
data: {"content": "return policy "}

event: token
data: {"content": "allows..."}

event: done
data: {"turn_id": "turn_xyz789", "session_id": "sess_abc123", "matched_rules": ["rule_returns"], "tokens_used": 200, "latency_ms": 800}
```

### Get Session State

```bash
curl http://localhost:8000/v1/sessions/sess_abc123 \
  -H "Authorization: Bearer <your-jwt-token>"
```

### Get Session History

```bash
curl "http://localhost:8000/v1/sessions/sess_abc123/turns?limit=10&offset=0" \
  -H "Authorization: Bearer <your-jwt-token>"
```

### End a Session

```bash
curl -X DELETE http://localhost:8000/v1/sessions/sess_abc123 \
  -H "Authorization: Bearer <your-jwt-token>"
```

## Prometheus Metrics

Available at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

Key metrics:
- `focal_api_requests_total{method, path, status}` - Request count
- `focal_api_request_duration_seconds{method, path}` - Request latency
- `focal_llm_tokens_total{provider, model}` - LLM token usage
- `focal_rate_limit_exceeded_total{tenant_tier}` - Rate limit hits

## Testing

```bash
# Run API unit tests
uv run pytest tests/unit/api/ -v

# Run API integration tests
uv run pytest tests/integration/api/ -v

# Run with coverage
uv run pytest tests/unit/api/ --cov=focal.api --cov-report=term-missing
```

## OpenAPI Documentation

When the server is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Troubleshooting

### Rate Limit Exceeded

If you see 429 errors, check:
1. Your tenant tier limits
2. Redis connection (if using distributed limiting)
3. X-RateLimit-* headers for limit info

### JWT Validation Errors

Ensure your JWT:
1. Has `tenant_id` claim
2. Is signed with the correct secret
3. Is not expired

### Session Not Found

Sessions may expire. Create a new one by omitting `session_id` in the chat request.
