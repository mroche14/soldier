# ACF Hatchet Worker

This directory contains the Hatchet worker implementation for ACF (Agent Conversation Fabric) LogicalTurn processing.

## Overview

The ACF worker processes conversational turns through durable Hatchet workflows, providing:
- Session mutex management (single-writer rule)
- Message accumulation (turn boundary detection)
- Agent/Brain execution
- State persistence and response delivery

## Components

| File | Purpose |
|------|---------|
| `worker.py` | Worker entrypoint and CLI |
| `workflow.py` | LogicalTurnWorkflow implementation |
| `models.py` | ACF data models (LogicalTurn, events) |
| `mutex.py` | Session mutex for concurrency control |
| `turn_manager.py` | Adaptive accumulation timing |

## Prerequisites

### 1. Hatchet Server

You need a running Hatchet server. Options:

**Self-Hosted** (recommended for production):
```bash
# Using Docker Compose
docker-compose up -d hatchet

# Or using the Hatchet CLI
hatchet server start
```

**Hatchet Cloud**:
```bash
# Sign up at https://cloud.hatchet.run
# Get your API token from the dashboard
export HATCHET_CLIENT_TOKEN="your-jwt-token"
```

### 2. Redis

ACF uses Redis for session mutex:
```bash
docker run -d -p 6379:6379 redis:7
```

### 3. Configuration

Set required environment variables:
```bash
# Required for Hatchet connection
export HATCHET_CLIENT_TOKEN="your-jwt-token"  # JWT from Hatchet server

# Optional - override defaults
export RUCHE_JOBS__HATCHET__SERVER_URL="http://localhost:7077"
export RUCHE_STORAGE__SESSION__BACKEND="redis"
```

## Starting the Worker

### CLI

The simplest way to start the worker:

```bash
# Install the package
uv sync

# Start the worker
ruche-worker
```

The worker will:
1. Load configuration from `config/default.toml` and environment
2. Connect to Hatchet server
3. Register the LogicalTurnWorkflow
4. Start processing workflow runs

### Programmatic Usage

```python
from ruche.runtime.acf.worker import run_worker
import asyncio

# Start worker
asyncio.run(run_worker())
```

## Configuration

Configuration is loaded from:
1. `config/default.toml` (base defaults)
2. `config/{RUCHE_ENV}.toml` (environment overrides)
3. `RUCHE_*` environment variables (runtime overrides)

### Hatchet Configuration

```toml
[jobs.hatchet]
enabled = true
server_url = "http://localhost:7077"
# api_key loaded from HATCHET_CLIENT_TOKEN env var
worker_concurrency = 10
retry_max_attempts = 3
retry_backoff_seconds = 60
```

### Session Storage (Redis)

```toml
[storage.session]
backend = "redis"
# Redis connection details
```

## Workflow

The LogicalTurnWorkflow has 4 steps:

1. **acquire_mutex** - Get exclusive session lock
2. **accumulate** - Wait for message completion (adaptive timing)
3. **run_agent** - Execute Agent's Brain (FOCAL pipeline)
4. **commit_and_respond** - Persist state and send response

### Workflow Input

```python
{
    "tenant_id": "uuid-string",
    "agent_id": "uuid-string",
    "interlocutor_id": "uuid-string",
    "channel": "whatsapp",
    "message_id": "uuid-string",
    "message_content": "Hello!"
}
```

### Triggering Workflows

Workflows are triggered by the API layer or Channel Gateway when messages arrive:

```python
from hatchet_sdk import Hatchet

hatchet = Hatchet()  # Reads HATCHET_CLIENT_TOKEN from env

await hatchet.admin.run_workflow(
    "logical-turn",
    input={
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        # ... other fields
    }
)
```

## Development

### Running Without Hatchet

The workflow can be run directly without Hatchet for testing:

```python
from ruche.runtime.acf.workflow import LogicalTurnWorkflow, WorkflowInput
from redis.asyncio import Redis

redis = Redis.from_url("redis://localhost:6379")

workflow = LogicalTurnWorkflow(
    redis=redis,
    agent_runtime=agent_runtime,  # Your AgentRuntime instance
    session_store=session_store,
    message_store=message_store,
    audit_store=audit_store,
)

result = await workflow.run(
    WorkflowInput(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        interlocutor_id=str(interlocutor_id),
        channel="api",
        message_id=str(message_id),
        message_content="Test message",
    )
)
```

### Testing

```bash
# Unit tests (no Hatchet required)
uv run pytest tests/unit/runtime/acf/

# Integration tests (requires Hatchet + Redis)
uv run pytest tests/integration/runtime/acf/
```

## Monitoring

The worker logs structured JSON to stdout. Key events:

| Event | Description |
|-------|-------------|
| `acf_worker_starting` | Worker initialization |
| `hatchet_client_initialized` | Connected to Hatchet |
| `workflow_registered` | LogicalTurnWorkflow registered |
| `acf_worker_ready` | Worker ready for runs |
| `mutex_acquired` | Session lock acquired |
| `accumulation_complete` | Messages accumulated |
| `brain_starting` | Agent Brain execution starting |
| `brain_complete` | Agent Brain finished |
| `turn_committed` | State persisted |
| `mutex_released` | Session lock released |

## Troubleshooting

### "Failed to create Hatchet client"

- Ensure Hatchet server is running
- Check `HATCHET_CLIENT_TOKEN` is set and valid
- Verify `server_url` in configuration

### "mutex_acquisition_failed"

- Another workflow is holding the session lock
- Check Redis connectivity
- Review mutex timeout configuration

### "stores_placeholder" warning

- Full store implementations not yet complete
- Worker will use placeholder stores for now

## Architecture

See `docs/acf/architecture/` for complete ACF architecture documentation:
- `ACF_ARCHITECTURE.md` - Overall architecture
- `topics/06-hatchet-integration.md` - Workflow integration details
- `topics/02-session-mutex.md` - Mutex implementation
- `topics/03-adaptive-accumulation.md` - Turn boundaries

## Related

- AgentRuntime: `ruche/runtime/agent/`
- Brain implementations: `ruche/brains/`
- Toolbox (tool execution): `ruche/runtime/toolbox/`
- Channel Gateway: `ruche/runtime/channels/`
