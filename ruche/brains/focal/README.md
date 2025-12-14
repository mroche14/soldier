# FOCAL Cognitive Pipeline

The FOCAL (Focused Contextual Alignment) pipeline is the primary cognitive mechanic for processing conversational turns in the Focal platform.

## Overview

FOCAL implements a 12-phase processing flow that transforms user input into contextually-aligned agent responses while maintaining full observability and persistence.

## Architecture

### Pipeline Phases

1. **Identification & Context Loading** - Resolve customer identity from channel, load session state and conversation history
2. **Situational Sensor** - Extract intent, tone, sentiment, and candidate variables from user message
3. **Interlocutor Data Update** - Apply variable updates to in-memory customer profile
4. **Retrieval** - Parallel retrieval of rules, scenarios, intents, and memory episodes
5. **Reranking** - Improve ordering of retrieved candidates using semantic reranking
6. **LLM Filtering** - Use LLM to judge which rules and scenarios actually apply
7. **Scenario Orchestration** - Navigate scenario graph (start, transition, exit, relocalize)
8. **Response Planning** - Build response plan from scenario contributions and rule constraints
9. **Tool Execution** - Execute tools attached to matched rules
10. **Response Generation** - Generate natural language response using LLM
11. **Enforcement** - Validate response against hard constraints, apply fallbacks
12. **Persistence** - Parallel save to SessionStore, CustomerDataStore, and AuditStore

### Key Components

- **FocalCognitivePipeline** (`pipeline.py`) - Main orchestrator class
- **Models** (`models/`) - Domain models for turn context, snapshots, plans, results
- **Migration** (`migration/`) - Scenario version migration handling
- **Prompts** (`prompts/`) - Jinja2 templates for LLM tasks

## Usage

```python
from focal.mechanics.focal import FocalCognitivePipeline
from focal.config.models.pipeline import PipelineConfig

# Create pipeline
pipeline = FocalCognitivePipeline(
    config_store=config_store,
    embedding_provider=embedding_provider,
    session_store=session_store,
    audit_store=audit_store,
    pipeline_config=PipelineConfig(),
    # ... other dependencies
)

# Process a turn
result = await pipeline.process_turn(
    message="Hello, I need help",
    tenant_id=tenant_id,
    agent_id=agent_id,
    session_id=session_id,
    channel="whatsapp",
    channel_user_id="+1234567890"
)

print(result.response)  # The generated response
print(result.matched_rules)  # Rules that fired
print(result.total_time_ms)  # Processing time
```

## Configuration

Each phase can be enabled/disabled via `PipelineConfig`:

```toml
[pipeline.situation_sensor]
enabled = true

[pipeline.retrieval]
enabled = true

[pipeline.rule_filtering]
enabled = true
batch_size = 5

[pipeline.scenario_filtering]
enabled = true
max_loop_count = 10

[pipeline.tool_execution]
enabled = true

[pipeline.generation]
enabled = true

[pipeline.enforcement]
enabled = false
```

## Dependencies

The FOCAL pipeline depends on:

- **Stores**: AgentConfigStore, SessionStore, AuditStore, CustomerDataStore, MemoryStore
- **Providers**: EmbeddingProvider, RerankProvider, LLMExecutor
- **Components**: Various alignment components (context, retrieval, filtering, generation, enforcement)

See `pipeline.py` for the complete dependency graph.

## Observability

Every phase is instrumented with:

- **Structured Logging** - JSON logs with tenant/agent/session/turn context
- **Timing Metrics** - Per-phase duration tracking
- **Prometheus Metrics** - Counters and histograms for monitoring

## Migration System

FOCAL includes a comprehensive scenario migration system for handling version transitions:

- **MigrationPlanner** - Generates migration plans when scenarios are updated
- **MigrationDeployer** - Marks affected sessions for migration
- **MigrationExecutor** - Executes just-in-time migrations when customers return
- **GapFillService** - Attempts to fill missing required fields without asking users

See `migration/` directory for details.

## Testing

Tests for the FOCAL pipeline are located in `tests/mechanics/focal/`.

Run tests:
```bash
uv run pytest tests/mechanics/focal/
```

## Future Work

### Phase Extraction

Currently, all phase logic is embedded in `pipeline.py` as private methods. Future work will extract each phase to its own module in `phases/`:

- `p01_identification.py`
- `p02_situational.py`
- `p03_data_update.py`
- ... (see `phases/README.md`)

### Protocol Compliance

Add a wrapper method to implement the `CognitivePipeline` protocol:

```python
async def process_turn(...) -> PipelineResult:
    # Call existing implementation
    alignment_result = await self._process_turn_impl(...)

    # Convert to protocol format
    return PipelineResult(
        turn_id=alignment_result.turn_id,
        response=alignment_result.response,
        # ... map fields
    )
```

### Component Migration

Gradually move supporting components from `focal/alignment/` to `focal/mechanics/focal/`:

- Context extraction
- Retrieval
- Filtering
- Generation
- Enforcement

## Documentation

- `MIGRATION_NOTES.md` - Migration tracking and history
- `phases/README.md` - Phase extraction plan
- `../protocol.py` - CognitivePipeline protocol definition

## Related

- Main implementation plan: `IMPLEMENTATION_PLAN.md` (project root)
- Architecture docs: `docs/architecture/`
- Original alignment docs: `docs/focal_turn_pipeline/`
