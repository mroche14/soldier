## 6. Pipeline Execution Model

This section defines which pipeline operations can execute **in parallel** vs **sequentially**.

### 6.1 Dependency Graph

```
P1 (Identification & Context Loading)
│
├─── P1.1-P1.4: Sequential (tenant → agent → customer → session)
└─── P1.5-P1.6: Parallel (CustomerDataStore ‖ Config/Glossary)

        │
        ▼
P2 (Situational Sensor) ← MUST complete before P4
        │
        ▼
P3 (Customer Data Update) ← Uses P2 output
        │
        ▼
P4 (Retrieval & Selection)
│
├─── P4.1: Embedding generation (needs P2 SituationalSnapshot)
│
└─── P4.2-P4.5: PARALLEL per object type:
     ├── Rule retrieval + rerank + selection
     ├── Scenario retrieval + rerank + selection
     ├── Memory retrieval + rerank + selection
     └── Intent retrieval + rerank + selection

        │
        ▼
P5 (Rule Selection) ← Sequential (pre-filter → LLM filter → expand)
        │
        ▼
P6 (Scenario Orchestration) ← Sequential per scenario
        │
        ▼
P7 (Tool Execution) ← Sequential or parallel based on tool dependencies
        │
        ▼
P8 (Response Planning) ← Sequential
        │
        ▼
P9 (Generation) ← Sequential
        │
        ▼
P10 (Enforcement) ← Sequential (deterministic → LLM judge → remediation)
        │
        ├── retry loop back to P9 if needed
        │
        ▼
P11 (Persistence & Audit) ← PARALLEL:
     ├── SessionState persistence
     ├── CustomerDataStore persistence
     ├── TurnRecord write
     └── Memory ingestion (async)
```

### 6.2 Parallelism Opportunities

| Phase | Parallel Operations | Notes |
|-------|---------------------|-------|
| **P1** | CustomerDataStore load ‖ Config load | Independent data sources |
| **P4** | Rule/Scenario/Memory/Intent retrieval | After P4.1 (embedding), all retrievals can run in parallel |
| **P4** | Reranking per object type | Independent cross-encoder calls |
| **P7** | Tool execution | Only if tools have no dependencies on each other |
| **P11** | All persistence operations | Independent writes |

### 6.3 Critical Dependencies

These operations **MUST** be sequential:

| Dependency | Reason |
|------------|--------|
| **P2 → P4.1** | Embedding generation needs SituationalSnapshot context |
| **P3 → P4** | Customer data updates affect retrieval queries |
| **P4 → P5** | Rule selection needs retrieval results |
| **P5 → P6** | Scenario orchestration needs applied rules |
| **P6 → P7** | Tool execution needs scenario step context |
| **P8 → P9** | Generation needs response plan |
| **P9 → P10** | Enforcement needs generated response |

### 6.4 Async Background Operations

These operations run **asynchronously after the turn response is sent**:

| Operation | Trigger | Notes |
|-----------|---------|-------|
| Memory ingestion | P11 completion | Entity extraction, summarization |
| Analytics events | P11 completion | Metrics, traces |
| Webhook notifications | P11 completion | External integrations |

### 6.5 Implementation Pattern

```python
async def execute_retrieval_phase(context: TurnContext) -> RetrievalResults:
    """P4: Execute all retrievals in parallel after embedding."""

    # P4.1: Sequential - needs situational context
    embedding = await compute_embedding(context.situational_snapshot)

    # P4.2-P4.5: Parallel per object type
    rule_task = asyncio.create_task(retrieve_and_select_rules(embedding, context))
    scenario_task = asyncio.create_task(retrieve_and_select_scenarios(embedding, context))
    memory_task = asyncio.create_task(retrieve_and_select_memories(embedding, context))
    intent_task = asyncio.create_task(retrieve_and_select_intents(embedding, context))

    rules, scenarios, memories, intents = await asyncio.gather(
        rule_task, scenario_task, memory_task, intent_task
    )

    return RetrievalResults(
        rules=rules,
        scenarios=scenarios,
        memories=memories,
        intents=intents,
    )
```
