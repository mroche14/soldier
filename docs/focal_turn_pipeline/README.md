# Focal Turn Pipeline Specification

## 1. Overview

This document specifies the **turn pipeline** for Focal – a production-grade cognitive engine for conversational AI. The pipeline processes a single user message through 11 phases, transforming it into a validated, policy-compliant response.

### 1.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Multi-tenant** | Every operation is scoped by `tenant_id` and `agent_id` |
| **Stateless pods** | All state lives in external stores; any pod can serve any request |
| **Deterministic control** | LLMs are sensors and judges, not policy engines |
| **Schema-driven** | Customer data, rules, and scenarios follow explicit schemas |
| **Observable** | Every turn produces a `TurnRecord` with full audit trail |

### 1.2 Pipeline Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FOCAL TURN PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────┐                                                                    │
│  │ User Message │                                                                    │
│  └──────┬──────┘                                                                    │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 1: IDENTIFICATION & CONTEXT LOADING                                    ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Resolve tenant/agent/customer/session                                  │ ║  │
│  ║  │ • Load SessionState, CustomerDataStore, Config, Glossary                 │ ║  │
│  ║  │ • Build TurnContext                                                      │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 2: SITUATIONAL SENSOR (LLM)                                            ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Schema-aware extraction (masked CustomerDataStore)                     │ ║  │
│  ║  │ • Intent detection, topic/tone analysis                                  │ ║  │
│  ║  │ • Extract candidate variables from conversation                          │ ║  │
│  ║  │ → Output: SituationalSnapshot                                            │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 3: CUSTOMER DATA UPDATE                                                ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Validate & coerce extracted variables against schema                   │ ║  │
│  ║  │ • Update in-memory CustomerDataStore                                     │ ║  │
│  ║  │ • Mark persistent updates for Phase 11                                   │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 4: RETRIEVAL & SELECTION                                               ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Compute embeddings + lexical features                                  │ ║  │
│  ║  │ • Hybrid retrieval: Intents → Rules → Scenarios                          │ ║  │
│  ║  │ • Apply selection strategies (adaptive_k, entropy, etc.)                 │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 5: RULE SELECTION                                                      ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Pre-filter by scope & lifecycle                                        │ ║  │
│  ║  │ • Optional LLM rule filter (APPLIES / NOT_RELATED / UNSURE)              │ ║  │
│  ║  │ • Expand via relationships (after certainty)                             │ ║  │
│  ║  │ → Output: applied_rules                                                  │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 6: SCENARIO ORCHESTRATION                                              ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Lifecycle decisions: START / CONTINUE / PAUSE / COMPLETE / CANCEL      │ ║  │
│  ║  │ • Step transitions within active scenarios                               │ ║  │
│  ║  │ • Determine scenario contributions (ASK / INFORM / CONFIRM)              │ ║  │
│  ║  │ → Output: ScenarioContributionPlan                                       │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 7: TOOL EXECUTION                                                      ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Collect tool bindings from rules + scenario steps                      │ ║  │
│  ║  │ • Resolve variables from CustomerDataStore / Session first               │ ║  │
│  ║  │ • Execute tools for missing variables                                    │ ║  │
│  ║  │ → Output: engine_variables                                               │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 8: RESPONSE PLANNING                                                   ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Determine global response type (ASK / ANSWER / MIXED / ESCALATE)       │ ║  │
│  ║  │ • Merge contributions from multiple scenarios                            │ ║  │
│  ║  │ • Inject constraints (must_include, must_avoid)                          │ ║  │
│  ║  │ → Output: ResponsePlan                                                   │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 9: GENERATION (LLM)                                                    ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Build prompt from ResponsePlan + rules + variables + glossary          │ ║  │
│  ║  │ • Generate response + LLM appends semantic categories                    │ ║  │
│  ║  │ • Post-format for channel (WhatsApp, email, webchat, etc.)               │ ║  │
│  ║  │ → Output: channel_answer, TurnOutcome (with categories)                  │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 10: ENFORCEMENT & GUARDRAILS                                           ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Collect rules: matched hard constraints + ALL GLOBAL hard constraints  │ ║  │
│  ║  │ • Lane 1: Deterministic (enforcement_expression via simpleeval)          │ ║  │
│  ║  │ • Lane 2: LLM-as-Judge (subjective rules without expressions)            │ ║  │
│  ║  │ • Optional: Relevance & Grounding checks (bypass for valid refusals)     │ ║  │
│  ║  │ • Remediation: Regenerate or fallback, append POLICY_RESTRICTION         │ ║  │
│  ║  │ → Output: EnforcementResult, final TurnOutcome                           │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ├─── if violations & can_retry ──→ [Back to Phase 9 with hints]            │
│         │                                                                           │
│         ▼                                                                           │
│  ╔═══════════════════════════════════════════════════════════════════════════════╗  │
│  ║  PHASE 11: PERSISTENCE, AUDIT & OUTPUT                                        ║  │
│  ║  ┌──────────────────────────────────────────────────────────────────────────┐ ║  │
│  ║  │ • Persist SessionState + CustomerDataStore                               │ ║  │
│  ║  │ • Record TurnRecord (full audit trail)                                   │ ║  │
│  ║  │ • Optional: Long-term memory ingestion                                   │ ║  │
│  ║  │ • Emit metrics & traces                                                  │ ║  │
│  ║  └──────────────────────────────────────────────────────────────────────────┘ ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════════╝  │
│         │                                                                           │
│         ▼                                                                           │
│  ┌──────────────────┐                                                               │
│  │ Final Response    │                                                               │
│  │ + TurnRecord      │                                                               │
│  └──────────────────┘                                                               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Phase Summary

| Phase | Name | Primary Function | Key Output |
|:-----:|------|------------------|------------|
| **1** | Identification & Context Loading | Bootstrap turn context | `TurnContext` |
| **2** | Situational Sensor | Understand what's happening | `SituationalSnapshot` |
| **3** | Customer Data Update | Update customer profile | Updated `CustomerDataStore` |
| **4** | Retrieval & Selection | Find relevant rules/scenarios | Candidates with scores |
| **5** | Rule Selection | Determine which rules apply | `applied_rules` |
| **6** | Scenario Orchestration | Navigate scenario state machine | `ScenarioContributionPlan` |
| **7** | Tool Execution | Fetch external data, append `SYSTEM_ERROR` if failed | `engine_variables` |
| **8** | Response Planning | Plan what to say, append `AWAITING_USER_INPUT` if ASK | `ResponsePlan` |
| **9** | Generation | Produce response, LLM appends semantic categories | `channel_answer`, `TurnOutcome` |
| **10** | Enforcement & Guardrails | Validate, append `POLICY_RESTRICTION` if blocked | `EnforcementResult`, final `TurnOutcome` |
| **11** | Persistence & Output | Save state, emit response | `TurnRecord`, API response |

### 1.4 Key Data Flow

```
User Message
    │
    ├──→ TurnContext (Phase 1)
    │        │
    │        ├──→ SituationalSnapshot (Phase 2)
    │        │        │
    │        │        ├──→ CustomerDataStore updates (Phase 3)
    │        │        │
    │        │        └──→ Retrieval queries (Phase 4)
    │        │                 │
    │        │                 ├──→ applied_rules (Phase 5)
    │        │                 │
    │        │                 └──→ ScenarioContributionPlan (Phase 6)
    │        │                          │
    │        │                          └──→ engine_variables (Phase 7)
    │        │                                   │
    │        │                                   └──→ ResponsePlan (Phase 8)
    │        │                                            │
    │        │                                            └──→ channel_answer (Phase 9)
    │        │                                                     │
    │        │                                                     └──→ Validated response (Phase 10)
    │        │                                                              │
    │        │                                                              └──→ TurnRecord (Phase 11)
    │        │
    └────────┴──────────────────────────────────────────────────────────────────→ Final Response
```

---

## Contents

- [2. Pipeline (Phases 1–11)](focal_turn_pipeline/pipeline.md)
- [3. Data models & contracts](focal_turn_pipeline/data_models.md)
- [4. Pipeline Configuration](focal_turn_pipeline/configuration.md)
- [5. LLM Task Configuration Pattern](focal_turn_pipeline/llm_task_configuration.md)
- [6. Pipeline Execution Model](focal_turn_pipeline/execution_model.md)

Detailed sections live in `docs/focal_turn_pipeline/spec/` for easier navigation.
