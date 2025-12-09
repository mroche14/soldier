<a id="focal.alignment.engine"></a>

# focal.alignment.engine

Alignment Engine - Main pipeline orchestrator.

Coordinates all pipeline steps to process user messages through
context extraction, retrieval, filtering, generation, and enforcement.

Handles the complete turn lifecycle including:
- Session loading and persistence (via SessionStore)
- Conversation history retrieval (via AuditStore)
- Turn record creation for audit trail (via AuditStore)

<a id="focal.alignment.engine.AlignmentEngine"></a>

## AlignmentEngine Objects

```python
class AlignmentEngine()
```

Orchestrate the full alignment pipeline.

The AlignmentEngine coordinates all pipeline steps:
1. Context extraction - Understand the user message
2. Retrieval - Find candidate rules
3. Reranking - (Optional) Reorder candidates
4. Rule filtering - LLM judges which rules apply
5. Scenario filtering - (Optional) Navigate scenario graph
6. Tool execution - (Optional) Run tools from matched rules
7. Generation - Generate response
8. Enforcement - (Optional) Validate against hard constraints

Each step can be enabled/disabled via configuration.

<a id="focal.alignment.engine.AlignmentEngine.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config_store: ConfigStore,
             llm_provider: LLMProvider,
             embedding_provider: EmbeddingProvider,
             session_store: SessionStore | None = None,
             audit_store: AuditStore | None = None,
             rerank_provider: RerankProvider | None = None,
             pipeline_config: PipelineConfig | None = None,
             tool_executor: ToolExecutor | None = None,
             enforcement_validator: EnforcementValidator | None = None,
             fallback_handler: FallbackHandler | None = None,
             memory_store: MemoryStore | None = None,
             migration_config: ScenarioMigrationConfig | None = None) -> None
```

Initialize the alignment engine.

**Arguments**:

- `config_store` - Store for rules, scenarios, templates
- `llm_provider` - Provider for LLM operations
- `embedding_provider` - Provider for embeddings
- `session_store` - Store for session state (optional, enables persistence)
- `audit_store` - Store for turn records (optional, enables audit trail)
- `rerank_provider` - Provider for reranking retrieval results
- `pipeline_config` - Pipeline configuration
- `tool_executor` - Executor for tools attached to rules
- `enforcement_validator` - Validator for hard constraints
- `fallback_handler` - Handler for enforcement fallbacks
- `memory_store` - Store for memory episodes
- `migration_config` - Configuration for scenario migrations

<a id="focal.alignment.engine.AlignmentEngine.process_turn"></a>

#### process\_turn

```python
async def process_turn(message: str,
                       session_id: UUID,
                       tenant_id: UUID,
                       agent_id: UUID,
                       session: Session | None = None,
                       history: list[Turn] | None = None,
                       persist: bool = True) -> AlignmentResult
```

Process a user message through the alignment pipeline.

This method handles the complete turn lifecycle:
1. Load session from SessionStore (if not provided)
2. Load conversation history from AuditStore
3. Run all pipeline steps (context, retrieval, filtering, generation, enforcement)
4. Update session state (rule fires, scenario step, variables)
5. Persist session and turn record to stores

**Arguments**:

- `message` - The user's message
- `session_id` - Session identifier
- `tenant_id` - Tenant identifier
- `agent_id` - Agent identifier
- `session` - Optional pre-loaded session (skips SessionStore load)
- `history` - Optional conversation history (skips AuditStore load)
- `persist` - Whether to persist session and turn record (default True)
  

**Returns**:

  AlignmentResult with response and all intermediate results

