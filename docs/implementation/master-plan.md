# Master Implementation Plan

> **Status**: READY FOR EXECUTION
> **Created**: 2025-12-15
> **Purpose**: Orchestrate codebase restructuring via independent work packages

---

## Executive Summary

This plan restructures the Ruche codebase to match documented architecture. Work is split into 9 independent work packages (WPs) executed in waves by subagents.

**Key Goals**:
1. Consolidate FOCAL brain code in `brains/focal/`
2. Complete ACF implementation with Hatchet workflow
3. Full folder restructure to match documentation
4. Rename `customer_data` → `interlocutor_data`
5. Deduplicate providers
6. Align all documentation

---

## User Decisions Applied

| Decision | Choice | Impact |
|----------|--------|--------|
| Q1: FOCAL duplication | Keep both in brains/focal/ for review | WP-001 |
| Q2: Refactoring scope | Full restructure (A) | WP-004 |
| Q3: ConfigStore location | Pending | — |
| Q4: Terminology rename | Now (A) | WP-005 |
| Q5: IMPLEMENTATION_PLAN | Moved to docs/focal_brain/ | WP-007 |
| Q6: ACF status | Partially implemented (B) | WP-002 |
| Q7: Hatchet status | Partially integrated (B) | WP-002 |
| Q8: Providers | Delete root (A assumed) | WP-006 |
| Q9: Subagent strategy | Feature-based (B) | This plan |
| Q10: Testing strategy | Batch moves (B) | WP-004 |

---

## Execution Waves

### Wave 1: Planning (COMPLETE)
**Status**: WP-000 complete

| WP | Name | Status | Deliverables |
|----|------|--------|--------------|
| WP-000 | Planning & Questions | ✅ COMPLETE | This plan, questions answered |

### Wave 2: Core Consolidation (PARALLEL)
**Estimated**: 3-5 days
**Can start**: Now

| WP | Name | Status | Deliverables |
|----|------|--------|--------------|
| WP-001 | FOCAL Consolidation | ⚪ READY | Single FOCAL codebase in brains/focal/ |
| WP-002 | ACF Verification | ⚪ READY | Complete ACF + Hatchet workflow |

**Parallelization**: WP-001 and WP-002 have no overlap. Can run simultaneously.

### Wave 3: Wiring & Structure (SEQUENTIAL)
**Estimated**: 4-7 days
**Depends on**: Wave 2

| WP | Name | Status | Deliverables |
|----|------|--------|--------------|
| WP-003 | Enforcement Wiring | ⚪ PENDING | Two-lane dispatch, GLOBAL constraints |
| WP-004 | Folder Restructuring | ⚪ PENDING | All files in target locations |

**Order**: WP-003 depends on WP-001 (enforcement code moves). WP-004 depends on both WP-001 and WP-002.

### Wave 4: Cleanup (PARALLEL)
**Estimated**: 2-3 days
**Depends on**: Wave 3

| WP | Name | Status | Deliverables |
|----|------|--------|--------------|
| WP-005 | Terminology | ⚪ PENDING | customer → interlocutor rename |
| WP-006 | Provider Dedup | ⚪ PENDING | Single provider location |

**Parallelization**: Both cleanup tasks can run in parallel after structure is stable.

### Wave 5: Polish (PARALLEL)
**Estimated**: 4-5 days
**Depends on**: Wave 4

| WP | Name | Status | Deliverables |
|----|------|--------|--------------|
| WP-007 | Documentation | ⚪ PENDING | All docs updated |
| WP-008 | Test Coverage | ⚪ PENDING | 80%+ coverage |

---

## Subagent Protocol Summary

Each subagent:
1. **Receives** work package spec with scope boundaries
2. **Creates** feature branch `wp/{id}/{short-name}`
3. **Executes** tasks within allowed file scope
4. **Reports** progress to `tracking/WP-{id}.md`
5. **Escalates** if needs files outside scope
6. **Validates** tests pass, linting clean
7. **Creates** PR for human review

See `subagent-protocol.md` for full details.

---

## Scope Boundaries

| WP | Owns | Reads | Forbidden |
|----|------|-------|-----------|
| WP-001 | brains/focal/**, alignment/** | domain/**, config/** | runtime/**, api/** |
| WP-002 | runtime/acf/**, runtime/agent/**, jobs/** | domain/**, config/** | brains/**, api/** |
| WP-003 | brains/focal/phases/enforcement/** | domain/**, config/** | runtime/**, api/** |
| WP-004 | ruche/** (all restructuring) | docs/architecture/** | — |
| WP-005 | ruche/**, tests/** | docs/** | — |
| WP-006 | providers/**, infrastructure/providers/** | All importers | brains/**, runtime/** |
| WP-007 | docs/**, CLAUDE.md | ruche/** | ruche/**, tests/** |
| WP-008 | tests/** | ruche/** | ruche/** |

---

## Quality Gates

Before each WP completes:

1. **Tests**: `pytest {scope}` passes
2. **Types**: `mypy {scope}` passes (or warns only)
3. **Lint**: `ruff check {scope}` clean
4. **Coverage**: 80%+ for modified files

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Broken imports after restructure | HIGH | Automated refactoring, batch testing |
| Circular imports | MEDIUM | Dependency analysis before moves |
| Test failures | MEDIUM | Each WP fixes its own tests |
| Merge conflicts between WPs | LOW | Non-overlapping scopes |

---

## Tracking

- **Overview**: `tracking/overview.md` - Status of all WPs
- **Per-WP**: `tracking/WP-{id}.md` - Detailed progress
- **Questions**: `questions.md` - User decisions

---

## How to Start

1. **Human**: Answer Q3 (ConfigStore location) if not yet decided
2. **Claude**: Spawn WP-001 subagent for FOCAL consolidation
3. **Claude**: Spawn WP-002 subagent for ACF verification (parallel)
4. **Monitor**: Check `tracking/overview.md` for progress

---

## References

- `work-packages.md` - Full WP specifications
- `subagent-protocol.md` - Execution protocol
- `gap-analysis.md` - Initial analysis
- `refactoring-plan.md` - Target folder structure
- `questions.md` - User decisions

---

*This plan is the master orchestration document for the codebase restructuring effort.*
