# ACF Worker Setup Guide

## Overview

The ACF Worker (`ruche-worker`) is a Hatchet-based worker that processes LogicalTurn workflows. It has been wired with real store implementations and AgentRuntime.

## Components Wired

### 1. Store Layer

The worker creates three types of stores based on configuration:

#### SessionStore
- **Primary**: RedisSessionStore (configurable via `settings.storage.session.backend`)
- **Fallback**: InMemorySessionStore (if Redis connection fails)
- **Configuration**: `config/default.toml` → `[storage.session]`

#### MessageStore
- **Status**: Not yet implemented
- **Current**: Returns `None` placeholder
- **Future**: Will store message history for turn accumulation

#### AuditStore
- **Current**: InMemoryAuditStore (due to circular import issues with PostgreSQL implementation)
- **Configuration**: `config/default.toml` → `[storage.audit]`
- **Note**: PostgresAuditStore exists but causes circular imports

### 2. AgentRuntime

The worker creates a fully functional AgentRuntime with the following dependencies:

#### ConfigStore
- **Current**: InMemoryConfigStore (PostgresConfigStore is incomplete)
- **Note**: PostgresConfigStore missing implementations for:
  - `get_channel_bindings`
  - `get_channel_policies`
  - `get_tool_definitions`

#### ToolGateway
- **Implementation**: Created with empty provider dictionary
- **Idempotency Cache**: Simple in-memory implementation
- **Future**: Tool providers can be registered dynamically

#### BrainFactory
- **Registered Brains**: FOCAL (placeholder factory)
- **Factory Function**: Returns `None` (needs proper FOCAL brain wiring)
- **Extensible**: Additional brain types (LangGraph, Agno) can be registered

## Configuration

### Development (InMemory stores)

Set `RUCHE_ENV=development` or override in config:

```toml
[storage.session]
backend = "inmemory"

[storage.audit]
backend = "inmemory"

[storage.config]
backend = "inmemory"
```

### Production (Redis + PostgreSQL)

Default configuration in `config/default.toml`:

```toml
[storage.session]
backend = "redis"
host = "localhost"
port = 6379

[storage.audit]
backend = "postgres"
connection_url = "${DATABASE_URL}"

[storage.config]
backend = "postgres"
connection_url = "${DATABASE_URL}"
```

**Environment Variables**:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string (optional, will construct from host/port)

## Running the Worker

### Prerequisites

1. **Hatchet server running** (required):
   ```bash
   # See ruche/infrastructure/jobs/README.md for setup
   docker-compose up hatchet
   ```

2. **Redis running** (optional for development):
   ```bash
   docker-compose up redis
   ```

3. **Configuration**:
   ```bash
   export RUCHE_JOBS__HATCHET__ENABLED=true
   export RUCHE_JOBS__HATCHET__SERVER_URL=http://localhost:7077
   ```

### Start Worker

```bash
uv run ruche-worker
```

### Expected Output

```
2025-12-16 14:29:34 [info] acf_worker_starting server_url=http://localhost:7077 concurrency=4
2025-12-16 14:29:34 [info] hatchet_client_created server_url=http://localhost:7077 concurrency=4
2025-12-16 14:29:34 [info] redis_client_created url=redis://localhost:6379
2025-12-16 14:29:34 [info] session_store_created backend=redis url=redis://localhost:6379
2025-12-16 14:29:34 [info] audit_store_created backend=inmemory
2025-12-16 14:29:34 [info] stores_initialized session_backend=redis audit_backend=inmemory
2025-12-16 14:29:34 [info] config_store_created backend=inmemory
2025-12-16 14:29:34 [info] tool_gateway_created provider_count=0
2025-12-16 14:29:34 [info] brain_factory_created available_types=['focal']
2025-12-16 14:29:34 [info] agent_runtime_created max_cache_size=1000
2025-12-16 14:29:34 [info] logical_turn_workflow_created
2025-12-16 14:29:34 [info] workflow_registered workflow_name=logical-turn
2025-12-16 14:29:34 [info] acf_worker_ready workflow_count=1
2025-12-16 14:29:34 [info] starting_hatchet_worker
```

## Testing

### Component Creation Test

```bash
uv run python -c "
import asyncio
from ruche.config import get_settings
from ruche.runtime.acf.worker import create_stores, create_agent_runtime

async def test():
    settings = get_settings()
    session_store, message_store, audit_store = await create_stores(settings)
    agent_runtime = await create_agent_runtime(settings)
    print('✅ All components wired successfully!')

asyncio.run(test())
"
```

## Known Limitations

### 1. FOCAL Brain Factory
The current FOCAL brain factory is a placeholder returning `None`. Full wiring requires:
- Embedding providers (Jina, OpenAI, Voyage)
- Rerank providers (Cohere, Voyage)
- LLM executors (Agno with OpenRouter)
- Additional stores (InterlocutorDataStore, MemoryStore)

### 2. Tool Providers
No tool providers are registered. The ToolGateway exists but cannot execute tools until providers are added.

### 3. PostgreSQL Stores
- **ConfigStore**: Incomplete implementation (missing channel/tool methods)
- **AuditStore**: Causes circular import issues

### 4. MessageStore
Not implemented yet. Required for message history and turn accumulation logic.

## Next Steps

To make the worker fully functional:

1. **Complete PostgresConfigStore** implementation:
   - Implement `get_channel_bindings`
   - Implement `get_channel_policies`
   - Implement `get_tool_definitions`

2. **Fix AuditStore circular imports**:
   - Restructure imports to avoid circular dependencies
   - Enable PostgresAuditStore usage

3. **Wire FOCAL brain factory**:
   - Create providers from settings
   - Wire all FOCAL dependencies
   - Return functional FocalCognitivePipeline

4. **Implement MessageStore**:
   - Design message history interface
   - Implement Redis-backed store
   - Wire into turn accumulation

5. **Register tool providers**:
   - HTTP provider for webhooks
   - Database provider for queries
   - Custom providers per tenant

## Files Modified

- `ruche/runtime/acf/worker.py` - Main worker implementation
  - `create_stores()` - Creates SessionStore, MessageStore, AuditStore
  - `create_agent_runtime()` - Creates ConfigStore, ToolGateway, BrainFactory, AgentRuntime
  - `create_worker()` - Orchestrates all component creation
  - `run_worker()` - Main entrypoint with graceful shutdown

## Architecture Notes

### Store Selection Logic

```python
# SessionStore: Redis with InMemory fallback
if backend == "redis":
    try:
        redis_client = Redis.from_url(redis_url)
        await redis_client.ping()  # Test connection
        return RedisSessionStore(redis_client)
    except Exception:
        logger.warning("redis_connection_failed", fallback="inmemory")
        return InMemorySessionStore()
```

### AgentRuntime Caching

- **Cache Key**: `(tenant_id, agent_id)`
- **Max Size**: 1000 agents (configurable)
- **Invalidation**: Version-based (detects config changes)
- **Eviction**: Simple LRU when cache is full

### BrainFactory Extensibility

```python
# Register additional brain types
brain_factory.register("langgraph", create_langgraph_brain)
brain_factory.register("agno", create_agno_brain)
brain_factory.register("custom", create_custom_brain)
```

## Troubleshooting

### Worker won't start

1. **Check Hatchet server**: `curl http://localhost:7077/health`
2. **Check configuration**: `uv run python -c "from ruche.config import get_settings; print(get_settings().jobs.hatchet)"`
3. **Check Redis** (if using): `redis-cli ping`

### Redis connection fails

Worker will fallback to InMemory stores automatically. Check logs for:
```
[warning] redis_connection_failed error=... fallback=inmemory
```

### Import errors

Circular import issues can occur if importing from `ruche.infrastructure` or `ruche.brains.focal`. Solution:
- Use lazy imports inside functions
- Avoid importing at module level

## References

- **ACF Architecture**: `docs/acf/architecture/ACF_ARCHITECTURE.md`
- **Agent Runtime**: `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- **Toolbox**: `docs/acf/architecture/TOOLBOX_SPEC.md`
- **LogicalTurn Workflow**: `ruche/runtime/acf/workflow.py`
