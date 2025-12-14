# Archived FOCAL 360 Documents

> **Status**: These documents are historical and have been superseded by the new architecture in `../architecture/`

---

## Why These Documents Are Archived

The LogicalTurn architecture vision (December 2025) fundamentally changed how we approach FOCAL 360:

1. **"Debouncing" → Adaptive Accumulation**: Not a fixed window, but intelligent completion detection
2. **"Ingress Control" → Turn Gateway + LogicalTurn**: Integrated into the core model
3. **"Waves" → Phase-based Implementation**: New order based on LogicalTurn dependencies
4. **"ASA Meta-Agent" → ASA Validator**: Design-time tool, not runtime agent

---

## Archived Files

| File | Original Purpose | Status |
|------|------------------|--------|
| `WAVE_EXECUTION_GUIDE.md` | Wave-based implementation order | **SUPERSEDED** by `../WAVE_EXECUTION_GUIDE_V2.md` |
| `gap_analysis.md` | Mapping concepts to existing code | **HISTORICAL** - superseded |
| `gap_analysis_reassessment.md` | Re-evaluation after architecture changes | **HISTORICAL** - contained obsolete Mode 0/1/2 references |
| `wave_analysis_report.md` | Critical analysis of 6 waves | **HISTORICAL** - insights absorbed into topic files |
| `SUBAGENT_PROTOCOL.md` | Execution protocol for subagents | **HISTORICAL** - still useful patterns but references old docs |
| `chatgpt_last.md` | Draft architecture discussion | **HISTORICAL** - contained obsolete Mode 0/1/2 patterns |

---

## Current Authoritative Documentation

Use these instead:

| Document | Purpose |
|----------|---------|
| `../architecture/README.md` | Master index for all topics |
| `../architecture/ACF_ARCHITECTURE.md` | Canonical architecture (v3.0) |
| `../architecture/ACF_SPEC.md` | Detailed ACF mechanics |
| `../architecture/AGENT_RUNTIME_SPEC.md` | Agent lifecycle spec |
| `../architecture/TOOLBOX_SPEC.md` | Tool execution spec |
| `../architecture/LOGICAL_TURN_VISION.md` | Founding vision document |
| `../architecture/topics/*.md` | 13 detailed topic specifications |
| `../WAVE_EXECUTION_GUIDE_V2.md` | Current implementation guide |

---

## Historical Value

These documents may still be useful for:
- Understanding the evolution of thinking
- Reference for vocabulary that appeared in discussions
- Context for why certain decisions were made

But **do not use them for implementation decisions** - refer to the architecture folder instead.
