# Subagent Execution Protocol

> **Status**: DRAFT - Pending user decisions on questions.md
> **Purpose**: Define how Claude subagents should execute independent work packages

---

## Overview

Large-scale implementation work will be split into **Work Packages** executed by **Subagents**. This document defines the protocol for safe, parallel execution.

---

## 1. Work Package Definition

Each work package must specify:

```yaml
work_package:
  id: WP-001
  name: "ACF Implementation Completion"
  description: "Complete Phase 6.5 ACF implementation"

  # Scope boundaries
  files:
    owns:        # Files this WP can modify
      - "ruche/runtime/acf/**"
      - "tests/unit/runtime/acf/**"
    reads:       # Files this WP can read but not modify
      - "ruche/domain/**"
      - "ruche/config/**"
    forbidden:   # Files this WP must not touch
      - "ruche/brains/**"
      - "ruche/api/**"

  # Dependencies
  depends_on: []                    # WP IDs that must complete first
  blocks: ["WP-003", "WP-004"]      # WP IDs that depend on this

  # Validation
  success_criteria:
    - "All tests in tests/unit/runtime/acf/ pass"
    - "No new linting errors"
    - "Coverage > 80% for modified files"

  # Tracking
  status: pending | in_progress | blocked | complete | failed
  assignee: null  # Subagent ID when running
```

---

## 2. Subagent Capabilities

### What Subagents CAN Do

1. **Read any file** in the codebase (for context)
2. **Modify files** within their `owns` scope
3. **Create new files** within their `owns` directories
4. **Run tests** for their scope
5. **Create commits** for their work package
6. **Report status** to tracking system

### What Subagents CANNOT Do

1. **Modify files outside scope** - Will be rejected
2. **Merge to main** - Requires human review
3. **Make architectural decisions** - Must escalate
4. **Resolve questions.md items** - Human only
5. **Modify other WP's files** - Even if blocked

---

## 3. Execution Protocol

### Phase 1: Initialization

```
1. Subagent receives WP specification
2. Subagent reads all files in `reads` scope for context
3. Subagent creates feature branch: `wp/{id}/{short-name}`
4. Subagent logs start to tracking/WP-{id}.md
```

### Phase 2: Implementation

```
1. For each task in WP:
   a. Implement change
   b. Run relevant tests
   c. If tests fail, fix or escalate
   d. Commit with message: "[WP-{id}] {description}"
   e. Update tracking/WP-{id}.md with progress
```

### Phase 3: Validation

```
1. Run full test suite for `owns` scope
2. Run linter on modified files
3. Check coverage meets threshold
4. Generate summary of changes
```

### Phase 4: Completion

```
1. Create PR from branch
2. Update tracking/WP-{id}.md with:
   - Final status
   - Files changed
   - Tests added/modified
   - Any issues encountered
3. Notify coordinator (human) for review
```

---

## 4. Communication Protocol

### Status Updates

Subagents write status to `docs/implementation/tracking/WP-{id}.md`:

```markdown
# WP-001: ACF Implementation Completion

## Status: in_progress
## Last Updated: 2025-12-15T14:30:00Z
## Assignee: subagent-a1b2c3

### Progress
- [x] Task 1: Implement LogicalTurn model
- [x] Task 2: Add session mutex
- [ ] Task 3: Wire Hatchet workflow
- [ ] Task 4: Add unit tests

### Blockers
None

### Notes
- Found existing mutex implementation, extending it
- Created 3 new test files

### Files Modified
- ruche/runtime/acf/logical_turn.py (new)
- ruche/runtime/acf/mutex.py (modified)
- tests/unit/runtime/acf/test_logical_turn.py (new)
```

### Escalation

When subagent encounters issues outside its scope:

```markdown
### Escalation Required

**Issue**: Need to modify `ruche/domain/interlocutor/models.py` to add field
**Reason**: LogicalTurn needs InterlocutorID reference
**Proposed Solution**: Add `interlocutor_id: UUID` to TurnContext
**Blocking Tasks**: Task 3, Task 4

Awaiting coordinator decision.
```

---

## 5. Conflict Resolution

### File Conflicts

If two WPs need to modify the same file:

1. **Preferred**: Redesign WP boundaries to avoid overlap
2. **If unavoidable**: Establish order - one WP owns, other waits
3. **Never**: Both modify simultaneously

### Dependency Deadlocks

If WP-A depends on WP-B which depends on WP-A:

1. Identify the cycle
2. Extract shared dependency into WP-0
3. Both depend on WP-0

---

## 6. Rollback Protocol

If a work package fails:

```
1. Mark WP status as `failed` in tracking
2. Document failure reason
3. Revert branch (do not merge)
4. Escalate to coordinator
5. Do NOT attempt fixes outside scope
```

---

## 7. Commit Message Format

```
[WP-{id}] {type}: {description}

{body}

Work-Package: WP-{id}
Task: {task-number}
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring
- `test`: Test additions
- `docs`: Documentation

Example:
```
[WP-001] feat: Add LogicalTurn model with accumulation

Implements the LogicalTurn model per ACF_SPEC.md.
Includes message accumulation and status tracking.

Work-Package: WP-001
Task: 1
```

---

## 8. Parallel Execution Rules

### Safe to Run in Parallel

| WP-A Scope | WP-B Scope | Safe? |
|------------|------------|-------|
| `ruche/runtime/` | `ruche/brains/` | ✅ Yes |
| `ruche/runtime/acf/` | `ruche/runtime/agent/` | ⚠️ Maybe (check interfaces) |
| `ruche/brains/focal/` | `ruche/brains/focal/` | ❌ No |

### Coordination Required

When WPs share:
- Common interfaces (domain models)
- Shared utilities
- Configuration models

Create interface-lock in tracking:
```
interface_locks:
  - file: ruche/domain/interlocutor/models.py
    locked_by: WP-001
    until: WP-001 complete
```

---

## 9. Quality Gates

Before marking WP complete:

1. **Tests pass**: `pytest {scope} --tb=short`
2. **Types check**: `mypy {scope} --strict` (or project standard)
3. **Lint clean**: `ruff check {scope}`
4. **Coverage met**: `pytest --cov={scope} --cov-fail-under=80`
5. **No TODOs added**: Unless tracked in issues

---

## 10. Tracking Directory Structure

```
docs/implementation/tracking/
├── overview.md              # Summary of all WPs
├── WP-001.md               # ACF completion
├── WP-002.md               # Enforcement wiring
├── WP-003.md               # Folder restructuring
├── ...
└── completed/              # Archived completed WPs
    ├── WP-000.md
    └── ...
```

---

## Next Steps

1. User answers questions in `questions.md`
2. Create `work-packages.md` with specific WP definitions
3. Create tracking files for each WP
4. Begin parallel execution

---

*This protocol is a living document. Update as we learn from execution.*
