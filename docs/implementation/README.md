# Implementation Planning

This folder contains the comprehensive plan to align the codebase with the architecture documentation.

## Contents

| Document | Purpose |
|----------|---------|
| **`master-plan.md`** | **Master orchestration document - START HERE** |
| `gap-analysis.md` | Exhaustive comparison of current codebase vs. documented architecture |
| `refactoring-plan.md` | Target folder structure and migration steps |
| `work-packages.md` | Independent work units for parallel execution |
| `subagent-protocol.md` | Protocol for Claude subagents to execute work |
| `tracking/` | Progress tracking per work package |
| `questions.md` | Ambiguities requiring human decision |

## Status

- **Created**: 2025-12-15
- **Status**: ALL DECISIONS COMPLETE - READY FOR EXECUTION

## User Decisions

| Question | Answer |
|----------|--------|
| Q1: FOCAL duplication | Keep both in brains/focal/ for review |
| Q2: Refactoring scope | (A) Full restructure |
| Q3: ConfigStore location | (C) Split - base limited to Agents+Tools |
| Q4: Terminology rename | (A) Now |
| Q5: IMPLEMENTATION_PLAN | (A) Moved to docs/focal_brain/ |
| Q6: ACF status | (B) Partially implemented |
| Q7: Hatchet status | (B) Partially integrated |
| Q8: Providers | (A) Delete ruche/providers/ |
| Q9: Subagent strategy | (B) Feature-based with tests |
| Q10: Testing | (B) Batch moves, fix after |
| Q11: Git strategy | One push when ready |
| Q12: gRPC | (B) Deferred |
| Q13: MCP | (B) Deferred |
| Q14: Alt stores | (B) Remove for now |

## Quick Links

- [Master Plan](master-plan.md) - Start here for execution
- [Work Packages](work-packages.md) - Detailed WP specifications
- [Tracking Overview](tracking/overview.md) - Current status
- [Questions](questions.md) - Pending decisions

## Related Documents

- [Architecture Readiness V6](../ARCHITECTURE_READINESS_REPORT_V6.md) - Current state assessment
- [CLAUDE.md](../../CLAUDE.md) - Development guidelines
- [FOCAL Brain Implementation Plan](../focal_brain/IMPLEMENTATION_PLAN.md) - Brain-specific phases
