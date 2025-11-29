# Research: Scenario Migration System

**Feature**: 008-scenario-migration
**Date**: 2025-11-29
**Status**: Complete

## Overview

This document consolidates research findings for implementing the anchor-based scenario migration system. All technical unknowns have been resolved through codebase analysis.

---

## 1. Content Hashing Strategy

### Decision
Use SHA-256 hash of JSON-serialized semantic attributes, truncated to 16 characters.

### Rationale
- SHA-256 is cryptographically secure and collision-resistant
- JSON serialization with `sort_keys=True` ensures deterministic output
- 16-character truncation provides sufficient uniqueness (64 bits = ~18 quintillion combinations)
- Matches existing pattern: `Scenario.content_hash` field already exists in model

### Implementation
```python
import hashlib
import json

def compute_node_content_hash(step: ScenarioStep) -> str:
    """Compute semantic content hash for anchor identification."""
    hash_input = {
        "name": step.name,
        "description": step.description,
        "rule_ids": sorted(str(r) for r in step.rule_ids),
        "collects_profile_fields": sorted(step.collects_profile_fields),
        "is_checkpoint": step.is_checkpoint,
        "checkpoint_description": step.checkpoint_description,
        "performs_action": step.performs_action,
    }
    serialized = json.dumps(hash_input, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| MD5 | Cryptographically weak, though sufficient for non-security use |
| Full SHA-256 (64 chars) | Unnecessarily long for display/storage |
| Step ID matching | IDs may change across versions |

---

## 2. Graph Traversal Algorithm

### Decision
Use BFS (Breadth-First Search) for upstream/downstream analysis with visited set for cycle detection.

### Rationale
- BFS already used in codebase (`scenario_validation.py:detect_unreachable_steps`)
- Natural for finding shortest paths and all reachable nodes
- Visited set prevents infinite loops in cyclic graphs
- O(V + E) time complexity is acceptable for 100-step scenarios

### Implementation Pattern
```python
def find_upstream_path(scenario: Scenario, target_step_id: UUID) -> list[UUID]:
    """Find all steps upstream of target using reverse BFS."""
    # Build reverse adjacency list
    reverse_edges: dict[UUID, list[UUID]] = defaultdict(list)
    for step in scenario.steps:
        for transition in step.transitions:
            reverse_edges[transition.to_step_id].append(step.id)

    # BFS backwards from target
    visited: set[UUID] = set()
    queue = [target_step_id]
    upstream: list[UUID] = []

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        for predecessor in reverse_edges[current]:
            if predecessor not in visited:
                upstream.append(predecessor)
                queue.append(predecessor)

    return upstream
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| DFS | BFS provides more intuitive "closest first" ordering |
| Recursive | Risk of stack overflow for deep graphs |
| NetworkX library | Adds external dependency for simple traversal |

---

## 3. ConfigStore Extension for Migration Plans

### Decision
Extend existing `ConfigStore` interface with migration-specific methods.

### Rationale
- Migration plans are configuration data ("how should migration behave")
- Follows Four Stores principle: ConfigStore handles "how should it behave?"
- Existing pattern: ConfigStore already handles Rules, Scenarios, Templates

### New Methods Required
```python
class ConfigStore(ABC):
    # ... existing methods ...

    # Migration Plan operations
    @abstractmethod
    async def get_migration_plan(
        self, tenant_id: UUID, plan_id: UUID
    ) -> MigrationPlan | None:
        """Get migration plan by ID."""
        pass

    @abstractmethod
    async def get_migration_plan_for_versions(
        self, tenant_id: UUID, scenario_id: UUID,
        from_version: int, to_version: int
    ) -> MigrationPlan | None:
        """Get migration plan for specific version transition."""
        pass

    @abstractmethod
    async def save_migration_plan(self, plan: MigrationPlan) -> UUID:
        """Save or update migration plan."""
        pass

    @abstractmethod
    async def list_migration_plans(
        self, tenant_id: UUID, scenario_id: UUID,
        status: str | None = None
    ) -> list[MigrationPlan]:
        """List migration plans for scenario."""
        pass

    # Scenario version archiving
    @abstractmethod
    async def archive_scenario_version(
        self, tenant_id: UUID, scenario: Scenario
    ) -> None:
        """Archive scenario version before update."""
        pass

    @abstractmethod
    async def get_archived_scenario(
        self, tenant_id: UUID, scenario_id: UUID, version: int
    ) -> Scenario | None:
        """Get archived scenario by version."""
        pass
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Separate MigrationStore | Over-engineering; plans are config data |
| AuditStore | AuditStore is for immutable event logs, not queryable config |

---

## 4. SessionStore Extension for Migration State

### Decision
Add `pending_migration` field and extend `step_history` with checkpoint tracking.

### Rationale
- Session already tracks `active_scenario_version` and `step_history`
- `pending_migration` is session-specific state ("what's happening now")
- StepVisit already has structure we can extend with `is_checkpoint`

### Model Changes
```python
class PendingMigration(BaseModel):
    """Marker indicating session needs migration at next turn."""
    target_version: int
    anchor_content_hash: str
    migration_plan_id: UUID
    marked_at: datetime

class StepVisit(BaseModel):
    """Record of visiting a scenario step."""
    step_id: UUID
    step_name: str  # NEW: for checkpoint description
    entered_at: datetime
    turn_number: int
    transition_reason: str | None
    confidence: float
    is_checkpoint: bool = False  # NEW
    checkpoint_description: str | None = None  # NEW

class Session(BaseModel):
    # ... existing fields ...
    pending_migration: PendingMigration | None = None  # NEW
    scenario_checksum: str | None = None  # NEW
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Separate migration state table | Session is the right place for per-session state |
| Store checkpoint history separately | StepVisit already tracks step history |

---

## 5. Gap Fill Extraction Pattern

### Decision
Use existing LLMProvider with JSON-formatted extraction prompt, following RuleFilter pattern.

### Rationale
- RuleFilter already demonstrates successful JSON extraction from LLM
- Existing providers (Anthropic, OpenAI) handle structured output well
- Temperature 0.0 for deterministic extraction
- Confidence scoring from LLM reasoning

### Implementation Pattern
```python
EXTRACTION_PROMPT = """
Extract the following field from the conversation history.

Field: {field_name}
Type: {field_type}
Hints: {extraction_hints}

Conversation:
{conversation}

Respond in JSON:
{{
    "found": true/false,
    "value": "extracted value or null",
    "confidence": 0.0-1.0,
    "source_quote": "relevant quote from conversation",
    "reasoning": "why this is the value"
}}
"""

async def extract_field_from_conversation(
    self,
    field_name: str,
    field_type: str,
    session: Session,
    max_turns: int = 20,
) -> ExtractionResult:
    """Extract field value from conversation history."""
    # Get recent conversation from AuditStore
    turns = await self._audit_store.get_turns(
        session.session_id, limit=max_turns
    )
    conversation = self._format_conversation(turns)

    prompt = EXTRACTION_PROMPT.format(
        field_name=field_name,
        field_type=field_type,
        extraction_hints=field_def.extraction_prompt_hint,
        conversation=conversation,
    )

    response = await self._llm_provider.generate(
        messages=[LLMMessage(role="user", content=prompt)],
        temperature=0.0,
        max_tokens=500,
    )

    return self._parse_extraction(response.content)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Regex extraction | Too brittle for natural language |
| Embedding similarity | Doesn't extract actual values |
| Fine-tuned model | Overkill for simple extraction |

---

## 6. Two-Phase Deployment Implementation

### Decision
Phase 1 marks sessions via batch query; Phase 2 applies at turn time via pre-turn reconciliation hook.

### Rationale
- Batch marking is efficient (single query per anchor)
- JIT application aligns with existing AlignmentEngine flow
- No live migration during deployment = no service disruption
- Pre-turn reconciliation fits naturally before context extraction

### Implementation Pattern
```python
# Phase 1: Deployment (batch mark)
async def deploy_migration(
    plan: MigrationPlan,
    session_store: SessionStore,
) -> int:
    """Mark eligible sessions for migration."""
    marked_count = 0

    for anchor in plan.transformation_map.anchors:
        policy = plan.anchor_policies.get(anchor.anchor_content_hash)

        # Query sessions at this anchor
        sessions = await session_store.find_sessions_by_step_hash(
            tenant_id=plan.tenant_id,
            scenario_id=plan.scenario_id,
            scenario_version=plan.from_version,
            step_content_hash=anchor.anchor_content_hash,
            scope_filter=policy.scope_filter,
        )

        for session in sessions:
            session.pending_migration = PendingMigration(
                target_version=plan.to_version,
                anchor_content_hash=anchor.anchor_content_hash,
                migration_plan_id=plan.id,
                marked_at=datetime.now(UTC),
            )
            await session_store.save(session)
            marked_count += 1

    return marked_count

# Phase 2: JIT reconciliation (in AlignmentEngine.process_turn)
async def _pre_turn_reconciliation(self, session: Session) -> ReconciliationResult:
    """Check for and apply pending migration before processing turn."""
    if session.pending_migration is None:
        # Check for version mismatch without flag (late arrival)
        if session.active_scenario_version != current_scenario.version:
            return await self._fallback_reconciliation(session)
        return ReconciliationResult(action="continue")

    # Load plan and apply migration
    plan = await self._config_store.get_migration_plan(
        session.tenant_id,
        session.pending_migration.migration_plan_id,
    )

    if plan is None:
        return await self._fallback_reconciliation(session)

    return await self._executor.execute(session, plan)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Live migration during deployment | Service disruption, complex rollback |
| Background worker migration | Adds infrastructure complexity |
| Webhook-based notification | Requires customer to handle migration |

---

## 7. Checkpoint Blocking Algorithm

### Decision
Walk backwards through session.step_history to find last checkpoint; BFS from teleport target to check if upstream.

### Rationale
- step_history already ordered chronologically
- Simple reverse iteration to find checkpoints
- BFS determines reachability (is target upstream of checkpoint?)
- Explicit `is_checkpoint` flag on StepVisit avoids ambiguity

### Implementation Pattern
```python
def find_last_checkpoint(session: Session) -> CheckpointInfo | None:
    """Find most recent checkpoint in session history."""
    for visit in reversed(session.step_history):
        if visit.is_checkpoint:
            return CheckpointInfo(
                step_id=visit.step_id,
                step_name=visit.step_name,
                checkpoint_description=visit.checkpoint_description,
                passed_at=visit.entered_at,
            )
    return None

def is_upstream_of_checkpoint(
    target_step_id: UUID,
    checkpoint_step_id: UUID,
    scenario: Scenario,
) -> bool:
    """Check if target is upstream of checkpoint (would 'undo' checkpoint)."""
    # BFS from target to see if checkpoint is reachable
    step_map = {s.id: s for s in scenario.steps}
    visited: set[UUID] = set()
    queue = [target_step_id]

    while queue:
        current = queue.pop(0)
        if current == checkpoint_step_id:
            return True  # Checkpoint is downstream = target is upstream
        if current in visited:
            continue
        visited.add(current)

        step = step_map.get(current)
        if step:
            for t in step.transitions:
                queue.append(t.to_step_id)

    return False
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Store checkpoint status per session separately | Redundant with step_history |
| Use step order/index | Graph may not have linear ordering |
| Query ConfigStore for checkpoint status | Extra I/O; history already has info |

---

## 8. Composite Migration Strategy

### Decision
Chain plans in memory, simulate through versions, prune requirements not needed in final version.

### Rationale
- In-memory simulation is fast (no DB writes)
- Requirement pruning prevents "thrashing"
- Falls back gracefully if plan chain breaks

### Implementation Pattern
```python
async def execute_composite_migration(
    session: Session,
    start_version: int,
    end_version: int,
) -> ReconciliationResult:
    """Handle multi-version gap with requirement pruning."""
    # Get plan chain: V1→V2, V2→V3, etc.
    plans = await self._get_plan_chain(
        session.tenant_id,
        session.active_scenario_id,
        start_version,
        end_version,
    )

    if not plans:
        return await self._fallback_reconciliation(session)

    # Accumulate requirements through all versions
    accumulated_fields: set[str] = set()
    for plan in plans:
        for anchor in plan.transformation_map.anchors:
            for node in anchor.upstream_changes.inserted_nodes:
                accumulated_fields.update(node.collects_fields)

    # Prune: only keep fields needed in final version
    final_scenario = await self._config_store.get_scenario(
        session.tenant_id,
        session.active_scenario_id,
    )
    final_fields = {
        f for step in final_scenario.steps
        for f in step.collects_profile_fields
    }
    required_fields = accumulated_fields & final_fields

    # Gap fill only required fields
    missing = await self._gap_fill_fields(required_fields, session)

    if missing:
        return ReconciliationResult(action="collect", collect_fields=list(missing))

    return ReconciliationResult(action="teleport", ...)
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Apply each migration sequentially | Could ask for obsolete data (thrashing) |
| Pre-compute composite plans | Storage overhead, stale if versions change |
| Always fall back for multi-version | Loses customer data unnecessarily |

---

## 9. Integration Points

### AlignmentEngine Integration
Pre-turn reconciliation fits at the start of `process_turn`:

```python
async def process_turn(self, ...):
    # Step 0: Pre-turn reconciliation (NEW)
    reconciliation = await self._pre_turn_reconciliation(session)
    if reconciliation.action == "collect":
        # Return collection prompt, don't proceed with normal turn
        return AlignmentResult(
            response=reconciliation.user_message,
            collecting_data=True,
            collect_fields=reconciliation.collect_fields,
        )
    if reconciliation.action == "teleport":
        # Update session position, then proceed normally
        session.active_step_id = reconciliation.target_step_id
        session.pending_migration = None
        await self._session_store.save(session)

    # Step 1: Context extraction (existing)
    ...
```

### API Integration
New endpoints under `/api/v1/migrations/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/scenarios/{id}/migration-plan` | POST | Generate plan for pending version |
| `/migration-plans/{id}` | GET | Get plan details |
| `/migration-plans/{id}/approve` | POST | Approve plan for deployment |
| `/migration-plans/{id}/deploy` | POST | Deploy approved plan |
| `/migration-plans/{id}/summary` | GET | Get operator review summary |

---

## 10. Testing Strategy

### Unit Tests
| Module | Focus |
|--------|-------|
| `test_diff.py` | Content hashing, anchor detection, transformation map |
| `test_planner.py` | Plan generation, policy application, summary building |
| `test_executor.py` | Clean Graft, Gap Fill, Re-Route scenarios |
| `test_gap_fill.py` | Profile/session/extraction fallback chain |
| `test_composite.py` | Multi-version chaining, requirement pruning |

### Integration Tests
| Scenario | Validates |
|----------|-----------|
| Clean Graft flow | Session marked → customer returns → silent teleport |
| Gap Fill flow | Missing data → extraction → profile persist |
| Re-Route with checkpoint | Fork condition true but checkpoint blocks |
| Multi-version gap | V1→V4 with intermediate requirement pruning |

### Contract Tests
Migration plan storage must pass `ConfigStoreContract` tests for:
- `get_migration_plan` / `save_migration_plan`
- `get_archived_scenario` / `archive_scenario_version`

---

## Summary

All technical unknowns have been resolved. The implementation can proceed using:

1. **SHA-256 content hashing** for anchor identification
2. **BFS graph traversal** for upstream/downstream analysis
3. **ConfigStore extension** for migration plan storage
4. **SessionStore extension** for pending_migration and checkpoint tracking
5. **LLM JSON extraction** for gap fill (following RuleFilter pattern)
6. **Two-phase deployment** with batch marking and JIT reconciliation
7. **Backward history walk + BFS** for checkpoint blocking
8. **In-memory plan chaining** for composite migration
