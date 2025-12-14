# Checkpoint Reuse (PhaseArtifact)

> **Topic**: Avoiding redundant computation on supersede
> **Boundary**: Pipeline-declared, ACF-enforced
> **Dependencies**: LogicalTurn, SideEffectPolicy
> **Impacts**: Performance, resource consumption, latency
> **See Also**: [ACF_SPEC.md](../ACF_SPEC.md) for complete specification

---

## ACF Context

Checkpoint Reuse involves **shared responsibility** between ACF and CognitivePipeline:

### Boundary Split

| Aspect | Owner | Description |
|--------|-------|-------------|
| Artifact Storage | ACF | Stores PhaseArtifacts in LogicalTurn |
| Fingerprint Computation | ACF | Computes input/dependency fingerprints |
| Reuse Validity Check | ACF | Compares fingerprints |
| **Reuse Policy Declaration** | **CognitivePipeline** | Declares what's safe to reuse |
| **Artifact Data** | **CognitivePipeline** | Produces artifact content |

### Key Insight: Pipeline Declares, ACF Enforces

ACF cannot know the semantics of phase outputs—only CognitivePipeline knows whether P4 retrieval results are still valid if the intent changed. Therefore:

1. **Pipeline declares** ReusePolicy for each phase artifact
2. **ACF stores** artifacts with fingerprints
3. **On restart**, ACF asks Pipeline which artifacts to reuse
4. **ACF validates** fingerprints match

```python
class ReusePolicy(str, Enum):
    """Pipeline-declared reuse semantics."""
    ALWAYS_SAFE = "always_safe"      # Can always reuse if fingerprint matches
    CONDITIONAL = "conditional"       # Reuse if specific conditions met
    NEVER = "never"                   # Never reuse (side effects, commits)

class PhaseArtifact(BaseModel):
    # ... existing fields ...

    # Pipeline-declared
    reuse_policy: ReusePolicy
    reuse_conditions: dict | None = None  # For CONDITIONAL
```

---

## Overview

**Checkpoint Reuse** prevents re-running expensive pipeline phases when a turn is superseded. If the inputs to a phase haven't changed, reuse its cached output.

### The Problem

Without checkpoint reuse:

```
Turn A: Message "Hello"
  P1: Load context       [500ms]
  P2: Situational sensor [300ms]
  P3: Customer data      [200ms]
  P4: Rule retrieval     [400ms]  ← New message "How are you?" arrives
  ... SUPERSEDED

Turn B: Message "Hello" + "How are you?"
  P1: Load context       [500ms]  ← SAME WORK, context unchanged!
  P2: Situational sensor [300ms]
  P3: Customer data      [200ms]
  P4: Rule retrieval     [400ms]  ← Maybe different now
  ...

Total P1-P3 work: 2000ms (duplicated 1000ms)
```

### The Solution

Cache phase outputs with fingerprints:

```
Turn A: Message "Hello"
  P1: Load context       [500ms] → Cache with fingerprint
  P2: Situational sensor [300ms] → Cache with fingerprint
  P3: Customer data      [200ms] → Cache with fingerprint
  P4: Rule retrieval     [400ms]  ← SUPERSEDED

Turn B: Message "Hello" + "How are you?"
  P1: ✓ Reuse (fingerprint matches)  [5ms]
  P2: Recompute (messages changed)   [300ms]
  P3: ✓ Reuse (customer data same)   [5ms]
  P4: Rule retrieval                  [400ms]
  ...

Total P1-P3 work: 1310ms (saved 690ms)
```

---

## PhaseArtifact Model

```python
from datetime import datetime
from pydantic import BaseModel
import hashlib
import json

class PhaseArtifact(BaseModel):
    """
    Cached output from a pipeline phase.

    Used to avoid redundant computation when turns are superseded.
    """

    phase: int  # Phase number (1-11)
    data: dict  # Phase output (serializable)

    # Fingerprints for validity checking
    input_fingerprint: str      # Hash of phase inputs
    dependency_fingerprint: str # Hash of external dependencies

    created_at: datetime
    reuse_count: int = 0  # How many times this was reused

    def is_valid(
        self,
        current_input_fp: str,
        current_dep_fp: str,
    ) -> bool:
        """
        Check if this artifact can be reused.

        Args:
            current_input_fp: Fingerprint of current inputs
            current_dep_fp: Fingerprint of current dependencies

        Returns:
            True if artifact is still valid
        """
        return (
            self.input_fingerprint == current_input_fp
            and self.dependency_fingerprint == current_dep_fp
        )

    def mark_reused(self) -> None:
        """Record that this artifact was reused."""
        self.reuse_count += 1
```

---

## Fingerprint Computation

### Input Fingerprints

Each phase has specific inputs that determine its output:

```python
class FingerprintComputer:
    """Compute fingerprints for phase inputs and dependencies."""

    def compute_phase_input_fingerprint(
        self,
        phase: int,
        turn: LogicalTurn,
        context: TurnContext,
    ) -> str:
        """
        Compute fingerprint for phase inputs.

        Different phases have different relevant inputs.
        """

        if phase == 1:  # Context Loading
            # P1 depends on: tenant, agent, customer, channel
            data = {
                "tenant_id": str(context.tenant_id),
                "agent_id": str(context.agent_id),
                "customer_id": str(context.customer_id),
                "channel": context.channel,
            }

        elif phase == 2:  # Situational Sensor
            # P2 depends on: messages, conversation history
            data = {
                "messages": [str(m) for m in turn.messages],
                "history_hash": self._hash_history(context.history),
            }

        elif phase == 3:  # Customer Data Update
            # P3 depends on: candidate variables from P2
            data = {
                "candidate_variables": context.candidate_variables,
            }

        elif phase == 4:  # Retrieval
            # P4 depends on: intent, entities, customer data
            data = {
                "intent": context.intent,
                "entities": context.entities,
                "customer_data_hash": self._hash_customer_data(context.customer_data),
            }

        elif phase in [5, 6]:  # Reranking, Filtering
            # Depends on retrieval results
            data = {
                "candidates_hash": self._hash_candidates(context.candidates),
            }

        elif phase == 7:  # Tool Execution
            # P7 depends on: bound tools from filtering
            data = {
                "tool_bindings": [tb.model_dump() for tb in context.tool_bindings],
            }

        elif phase in [8, 9]:  # Generation, Enforcement
            data = {
                "response_plan_hash": self._hash_plan(context.response_plan),
            }

        elif phase == 10:  # Formatting
            data = {
                "raw_response_hash": hashlib.md5(
                    context.raw_response.encode()
                ).hexdigest(),
                "channel": context.channel,
            }

        elif phase == 11:  # Persistence
            # P11 should never be reused (always commit)
            return "never_reuse"

        else:
            data = {"phase": phase, "turn_id": str(turn.id)}

        return self._hash_dict(data)

    def compute_dependency_fingerprint(
        self,
        phase: int,
        context: TurnContext,
    ) -> str:
        """
        Compute fingerprint for external dependencies.

        These are things outside the turn that affect phase output.
        """

        data = {
            # Config version affects all phases
            "config_version": context.config_version,
        }

        if phase in [4, 5, 6]:  # Retrieval phases
            # Rule/scenario versions matter
            data["ruleset_version"] = context.ruleset_version
            data["scenario_version"] = context.scenario_version

        if phase in [8, 9]:  # Generation phases
            # Template versions matter
            data["template_version"] = context.template_version

        return self._hash_dict(data)

    def _hash_dict(self, data: dict) -> str:
        """Create deterministic hash of dict."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _hash_history(self, history: list) -> str:
        return hashlib.md5(
            json.dumps([h.model_dump() for h in history], default=str).encode()
        ).hexdigest()[:12]

    def _hash_customer_data(self, data: CustomerDataStore) -> str:
        return hashlib.md5(
            json.dumps(data.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()[:12]

    def _hash_candidates(self, candidates: list) -> str:
        return hashlib.md5(
            json.dumps([c.id for c in candidates], default=str).encode()
        ).hexdigest()[:12]

    def _hash_plan(self, plan: ResponsePlan) -> str:
        return hashlib.md5(
            json.dumps(plan.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()[:12]
```

---

## Phase Reusability (Pipeline-Declared)

CognitivePipeline declares reusability for each phase. This is **not hardcoded in ACF**—the pipeline knows its own semantics:

```python
class ReusePolicy(str, Enum):
    """Pipeline-declared reuse semantics."""
    ALWAYS_SAFE = "always_safe"    # Can always reuse if fingerprint matches
    CONDITIONAL = "conditional"     # Reuse if specific conditions met
    NEVER = "never"                 # Never reuse (side effects, commits)


# Example: CognitivePipeline declares reuse policies
# (This is pipeline code, not ACF code)
class FOCALPipeline(CognitivePipeline):
    def get_reuse_policies(self) -> dict[int, ReusePolicy]:
        return {
            1: ReusePolicy.ALWAYS_SAFE,    # P1 context loading - identity doesn't change
            2: ReusePolicy.CONDITIONAL,     # P2 sensor - depends on messages
            3: ReusePolicy.CONDITIONAL,     # P3 customer data - depends on P2
            4: ReusePolicy.CONDITIONAL,     # P4 retrieval - depends on intent fingerprint
            5: ReusePolicy.CONDITIONAL,     # P5 reranking
            6: ReusePolicy.CONDITIONAL,     # P6 filtering
            7: ReusePolicy.NEVER,           # P7 tool execution - side effects!
            8: ReusePolicy.CONDITIONAL,     # P8 generation
            9: ReusePolicy.CONDITIONAL,     # P9 enforcement
            10: ReusePolicy.ALWAYS_SAFE,    # P10 formatting - deterministic
            11: ReusePolicy.NEVER,          # P11 persistence - must commit
        }
```

### ACF's Role

ACF enforces the declared policies by:
1. Storing artifacts with fingerprints
2. On restart, checking fingerprints against pipeline declarations
3. Only reusing artifacts where policy allows AND fingerprints match

---

## Integration with Pipeline

```python
class AlignmentEngine:
    """Engine with checkpoint reuse support."""

    async def process_logical_turn(
        self,
        turn: LogicalTurn,
        interrupt_check: Callable[[], Awaitable[bool]],
        reuse_artifacts: bool = True,
    ) -> TurnResult:
        """
        Process turn with optional artifact reuse.
        """

        context = TurnContext(...)
        fingerprinter = FingerprintComputer()

        for phase in self.phases:
            # Check reusability
            reusability = PHASE_REUSABILITY.get(phase.number, PhaseReusability.CONDITIONAL_REUSE)

            if reusability == PhaseReusability.NEVER_REUSE:
                # Must execute (e.g., P7 tools, P11 persistence)
                result = await phase.execute(turn, context)
                continue

            if reuse_artifacts and phase.number in turn.phase_artifacts:
                artifact = turn.phase_artifacts[phase.number]

                # Compute current fingerprints
                input_fp = fingerprinter.compute_phase_input_fingerprint(
                    phase.number, turn, context
                )
                dep_fp = fingerprinter.compute_dependency_fingerprint(
                    phase.number, context
                )

                if artifact.is_valid(input_fp, dep_fp):
                    # Reuse cached output
                    logger.debug(
                        "phase_reused",
                        phase=phase.number,
                        artifact_age_ms=(datetime.utcnow() - artifact.created_at).total_seconds() * 1000,
                    )
                    artifact.mark_reused()
                    context.apply_phase_output(phase.number, artifact.data)
                    continue

            # Execute phase
            result = await phase.execute(turn, context)

            # Cache output
            input_fp = fingerprinter.compute_phase_input_fingerprint(
                phase.number, turn, context
            )
            dep_fp = fingerprinter.compute_dependency_fingerprint(
                phase.number, context
            )

            turn.phase_artifacts[phase.number] = PhaseArtifact(
                phase=phase.number,
                data=result.to_dict(),
                input_fingerprint=input_fp,
                dependency_fingerprint=dep_fp,
                created_at=datetime.utcnow(),
            )

        return TurnResult(response=context.final_response)
```

---

## Storage Considerations

### Where to Store Artifacts

```python
# Option 1: In-memory on LogicalTurn (simplest)
turn.phase_artifacts[phase] = artifact

# Option 2: Redis with TTL (for distributed)
await redis.setex(
    f"artifact:{turn.id}:{phase}",
    ttl=300,  # 5 minutes
    value=artifact.model_dump_json(),
)

# Option 3: Turn store (for durability)
await turn_store.save_artifact(turn.id, phase, artifact)
```

### TTL Considerations

Artifacts should have short TTL:
- Typical turn processing: < 10 seconds
- Supersede window: < 5 seconds
- Safe TTL: 30-60 seconds

```toml
[pipeline.checkpoint_reuse]
enabled = true
artifact_ttl_seconds = 60
max_artifacts_per_turn = 10
```

---

## When Reuse Fails

Sometimes fingerprints match but reuse is wrong:

```python
class ArtifactReuseFailed(Exception):
    """Raised when reused artifact produces invalid state."""
    pass

async def execute_with_fallback(phase, turn, context, artifact):
    """Try reuse, fall back to execution on failure."""
    try:
        context.apply_phase_output(phase.number, artifact.data)
        # Validate the applied output
        if not context.is_valid_after_phase(phase.number):
            raise ArtifactReuseFailed("Invalid state after reuse")
    except ArtifactReuseFailed:
        logger.warning(
            "artifact_reuse_failed",
            phase=phase.number,
            falling_back=True,
        )
        # Clear invalid artifact
        del turn.phase_artifacts[phase.number]
        # Execute fresh
        return await phase.execute(turn, context)
```

---

## Observability

### Metrics

```python
# Reuse rate by phase
artifact_reuse_rate = Gauge(
    "phase_artifact_reuse_rate",
    "Rate of artifact reuse by phase",
    ["phase"],
)

# Time saved through reuse
time_saved_by_reuse_ms = Counter(
    "phase_artifact_time_saved_ms_total",
    "Milliseconds saved through artifact reuse",
    ["phase"],
)

# Reuse failures
artifact_reuse_failures = Counter(
    "phase_artifact_reuse_failure_total",
    "Failed artifact reuse attempts",
    ["phase", "reason"],
)
```

### Logging

```python
logger.info(
    "phase_completed",
    phase=phase.number,
    reused=was_reused,
    duration_ms=duration,
    fingerprint=input_fp[:8],
)
```

---

## Testing Considerations

```python
# Test: Artifact reused when fingerprint matches
async def test_artifact_reused_on_match():
    turn = LogicalTurn(...)

    # First execution
    result1 = await engine.process_logical_turn(turn, reuse_artifacts=True)
    assert 1 in turn.phase_artifacts

    # Same inputs = same fingerprint
    result2 = await engine.process_logical_turn(turn, reuse_artifacts=True)
    assert turn.phase_artifacts[1].reuse_count == 1

# Test: Artifact not reused when fingerprint changes
async def test_artifact_not_reused_on_change():
    turn = LogicalTurn(...)

    # First execution
    await engine.process_logical_turn(turn, reuse_artifacts=True)
    original_artifact = turn.phase_artifacts[2]

    # Add message (changes P2 input fingerprint)
    turn.messages.append(new_message_id)

    # Should recompute P2
    await engine.process_logical_turn(turn, reuse_artifacts=True)
    assert turn.phase_artifacts[2].created_at > original_artifact.created_at

# Test: P7 never reused
async def test_p7_never_reused():
    turn = LogicalTurn(...)
    turn.phase_artifacts[7] = PhaseArtifact(...)

    await engine.process_logical_turn(turn, reuse_artifacts=True)

    # P7 should have been executed, not reused
    assert turn.phase_artifacts[7].reuse_count == 0
```

---

## ACF Artifact Reuse Flow

When a turn is superseded and restarts:

```python
# ACF code for handling restart with artifact reuse
async def restart_with_reuse(
    self,
    old_turn: LogicalTurn,
    new_turn: LogicalTurn,
    pipeline: CognitivePipeline,
):
    """ACF: Handle restart after SUPERSEDE or ABSORB."""

    # Get pipeline's reuse declarations
    reuse_policies = pipeline.get_reuse_policies()

    for phase, artifact in old_turn.phase_artifacts.items():
        policy = reuse_policies.get(phase, ReusePolicy.NEVER)

        if policy == ReusePolicy.NEVER:
            continue  # Don't copy

        if policy == ReusePolicy.ALWAYS_SAFE:
            # Copy artifact to new turn
            new_turn.phase_artifacts[phase] = artifact

        elif policy == ReusePolicy.CONDITIONAL:
            # Check fingerprints
            new_fp = compute_fingerprint(phase, new_turn)
            if artifact.input_fingerprint == new_fp:
                new_turn.phase_artifacts[phase] = artifact
```

---

## Related Topics

- [../ACF_SPEC.md](../ACF_SPEC.md) - Complete ACF specification
- [01-logical-turn.md](01-logical-turn.md) - Turn model that holds artifacts (ACF core)
- [04-side-effect-policy.md](04-side-effect-policy.md) - Why P7 can't be reused (ACF component)
- [06-hatchet-integration.md](06-hatchet-integration.md) - Durable artifact storage (ACF runtime)
