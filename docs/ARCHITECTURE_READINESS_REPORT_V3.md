# Ruche Architecture Readiness Report

> **Analysis Date**: 2025-12-15
> **Scope**: Implementation & Production Readiness Assessment
> **Status**: COMPREHENSIVE REVIEW COMPLETE
> **Version**: 3.0

---

## Executive Summary

This report assesses whether the Ruche architecture is **implementation-ready** and **production-ready**.

### Overall Verdict

| Dimension | Score | Status |
|-----------|-------|--------|
| **Architecture Completeness** | 85% | Core components well-defined |
| **Cross-Document Consistency** | 90% | Terminology standardized |
| **Implementation Readiness** | 80% | Key interfaces defined |
| **Production Readiness** | 70% | Scaling solutions defined |
| **Security Posture** | 70% | Good foundations |
| **Operational Readiness** | 45% | Infrastructure gaps remain |

### What's Ready

| Component | Status | Reference |
|-----------|--------|-----------|
| ACF Concurrency | ✅ Solved | Hatchet-native (`ACF_SCALABILITY_ANALYSIS.md`) |
| Event Model | ✅ Defined | AgentEvent + ACFEvent (`event-model.md`) |
| Tool Safety | ✅ Defined | SideEffectPolicy + 3-layer idempotency |
| Message Queuing | ✅ Solved | Hatchet RabbitMQ integration |
| Supersede Handling | ✅ Solved | `CANCEL_IN_PROGRESS` strategy |
| Documentation Structure | ✅ Clean | `focal_360/` → `acf/` rename complete |

### What's Needed

| Gap | Priority | Effort |
|-----|----------|--------|
| Kubernetes manifests | CRITICAL | 3 days |
| Operational runbooks | CRITICAL | 4 days |
| Webhook specification | HIGH | 2 days |
| ChannelGateway interface | HIGH | 2 days |
| Error handling spec | HIGH | 2 days |
| Backup/restore procedures | CRITICAL | 3 days |

---

## 1. Architecture Overview

### 1.1 Platform Structure

```
RUCHE PLATFORM
├── ACF (Agent Conversation Fabric)     → docs/acf/
│   ├── Session concurrency (Hatchet-native)
│   ├── LogicalTurn lifecycle
│   ├── Supersede coordination
│   └── ACFEvent routing
│
├── Brains (Cognitive Brains)        → ruche/brains/
│   └── FOCAL (Alignment brain)      → docs/focal_brain/
│
├── Toolbox                             → docs/acf/architecture/TOOLBOX_SPEC.md
│   ├── SideEffectPolicy enforcement
│   ├── Tool execution via ToolGateway
│   └── Idempotency management
│
└── Infrastructure
    ├── Stores (Config, Memory, Session, Audit)
    ├── Providers (LLM, Embedding, Rerank)
    └── Observability (structlog, OTEL, Prometheus)
```

### 1.2 Key Abstractions

| Abstraction | Purpose | Owner |
|-------------|---------|-------|
| **LogicalTurn** | Conversational beat (1+ messages → 1 response) | ACF |
| **ACFEvent** | Transport envelope for event routing | ACF |
| **AgentEvent** | Semantic event (what happened) | Brains/Toolbox |
| **Brain** | Brain interface (agent.process_turn() → brain.think()) | Platform |
| **SideEffectPolicy** | Tool safety classification | Toolbox |

### 1.3 Documentation Map

| Area | Location | Contents |
|------|----------|----------|
| **ACF** | `docs/acf/` | ACF_SPEC, TOOLBOX_SPEC, AGENT_RUNTIME_SPEC |
| **Events** | `docs/architecture/event-model.md` | AgentEvent + ACFEvent specification |
| **Scaling** | `docs/architecture/ACF_SCALABILITY_ANALYSIS.md` | Hatchet concurrency solution |
| **FOCAL Brain** | `docs/focal_brain/` | 11-phase alignment brain |
| **Core** | `docs/architecture/` | Overview, configuration, observability |
| **Design** | `docs/design/` | Domain models, decisions |

---

## 2. Resolved Issues

### 2.1 ACF Session Concurrency (SOLVED)

**Problem**: Redis mutex bottleneck at scale (lock contention, no queuing).

**Solution**: Hatchet-native concurrency controls.

```python
@hatchet.workflow()
class LogicalTurnWorkflow:
    @hatchet.concurrency(
        expression="input.session_key",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
    )
    @hatchet.step()
    async def process_turn(self, ctx: Context):
        # Hatchet guarantees single execution per session
        ...
```

| Strategy | Use Case |
|----------|----------|
| `GROUP_ROUND_ROBIN` | Queue messages, process in order (WhatsApp, SMS) |
| `CANCEL_IN_PROGRESS` | Supersede current turn (Web chat) |

**Reference**: `docs/architecture/ACF_SCALABILITY_ANALYSIS.md`

### 2.2 Event Model (SOLVED)

**Problem**: FabricEvent vs AgentEvent confusion; unclear separation of concerns.

**Solution**: Two-layer event model.

| Layer | Name | Purpose | Owner |
|-------|------|---------|-------|
| **Semantic** | `AgentEvent` | What happened | Brains, Toolbox |
| **Transport** | `ACFEvent` | Routing envelope | ACF |

**Reserved namespace**: `infra.*` events for ACF infrastructure (turn lifecycle, tool side effects, commit points).

**Reference**: `docs/architecture/event-model.md`

### 2.3 Tool Safety (SOLVED)

**Problem**: What happens if a tool executes mid-supersede?

**Solution**: Three-layer protection.

```
Layer 1: API Idempotency      (5 min TTL)  → Prevents duplicate API calls
Layer 2: Turn Idempotency     (60 sec TTL) → Prevents duplicate turn processing
Layer 3: Tool Idempotency     (24 hr TTL)  → Prevents duplicate side effects
```

**SideEffectPolicy**:

| Policy | Can Supersede? | Protection |
|--------|----------------|------------|
| `PURE` | Yes | None needed |
| `IDEMPOTENT` | Yes | Idempotency key |
| `COMPENSATABLE` | Yes* | Compensation workflow |
| `IRREVERSIBLE` | No | Requires confirmation |

**Reference**: `docs/acf/architecture/TOOLBOX_SPEC.md`

### 2.4 Documentation Structure (SOLVED)

**Problem**: `focal_360/` naming was confusing (legacy codename).

**Solution**: Renamed to `acf/` (Agent Conversation Fabric).

| Old | New |
|-----|-----|
| `docs/focal_360/` | `docs/acf/` |
| `FabricEvent` | `ACFEvent` |
| "FOCAL 360" | "ACF" / "Ruche Platform" |

---

## 3. Architecture Completeness

### 3.1 Component Status

| Component | Completeness | Notes |
|-----------|--------------|-------|
| ACF Core | 100% | Concurrency, turns, supersede |
| Event Model | 100% | AgentEvent + ACFEvent defined |
| Agent Runtime | 100% | Lifecycle, caching |
| Toolbox | 100% | SideEffectPolicy, idempotency |
| Configuration | 100% | TOML, hot-reload |
| Storage Interfaces | 100% | 4 stores defined |
| FOCAL Brain | 95% | 11 phases documented |
| Memory Layer | 90% | Entity/episode model |
| Selection Strategies | 100% | Elbow, threshold, etc. |
| Observability | 95% | structlog, OTEL, Prometheus |
| REST API | 90% | Core endpoints |
| Hatchet Integration | 90% | Workflow patterns |

### 3.2 Missing Specifications (Prioritized)

| Gap | Priority | Impact | Blocking? |
|-----|----------|--------|-----------|
| **Webhook System** | HIGH | Event delivery to tenants | Yes |
| **ChannelGateway Interface** | HIGH | Multi-channel support | Yes |
| **Error Handling Spec** | HIGH | Standardized errors, retries | Yes |
| **gRPC API Spec** | MEDIUM | High-perf streaming | No (future) |
| **MCP Server Spec** | MEDIUM | LLM tool discovery | No (future) |
| **Multimodal Providers** | LOW | STT/TTS/Vision | No (future) |

### 3.3 Documents to Create

**High Priority**:
1. `docs/architecture/webhooks.md` - Payload, delivery, retry logic
2. `docs/architecture/channel-gateway.md` - Channel adapter protocol
3. `docs/architecture/error-handling.md` - Error codes, circuit breakers

**Medium Priority**:
4. `docs/architecture/api-grpc.md` - Protobuf definitions
5. `docs/architecture/mcp-server.md` - Tool discovery protocol

---

## 4. Cross-Document Consistency

### 4.1 Terminology Status

| Term | Status | Standard |
|------|--------|----------|
| Platform name | ✅ Complete | Ruche |
| Event transport | ✅ Complete | ACFEvent |
| Event semantic | ✅ Complete | AgentEvent |
| Brains folder | ✅ Complete | `brains/` |
| ACF docs folder | ✅ Complete | `docs/acf/` |
| Interlocutor | ⚠️ Migrating | `interlocutor_id` (was `customer_id`) |
| Data store | ⚠️ Migrating | `InterlocutorDataStore` |

### 4.2 Remaining Cleanup

| Task | Files Affected | Effort |
|------|----------------|--------|
| `customer_id` → `interlocutor_id` | ~8 files | 1 day |
| Domain model alignment with Phase 2 | 2 files | 0.5 days |

---

## 5. Implementation Readiness

### 5.1 Component Scores

| Component | Spec | Interface | Models | Algorithm | Score |
|-----------|------|-----------|--------|-----------|-------|
| REST API | 9/10 | ✅ | ✅ | N/A | **9/10** |
| ACF | 9/10 | ✅ | ✅ | ✅ | **9/10** |
| Toolbox | 9/10 | ✅ | ✅ | ✅ | **9/10** |
| Event Model | 10/10 | ✅ | ✅ | N/A | **10/10** |
| ConfigStore | 8/10 | ✅ | ✅ | ✅ | **8/10** |
| MemoryStore | 8/10 | ✅ | ✅ | ⚠️ | **8/10** |
| SessionStore | 8/10 | ✅ | ✅ | N/A | **8/10** |
| SelectionStrategy | 9/10 | ✅ | ✅ | ✅ | **9/10** |
| AlignmentEngine | 7/10 | ⚠️ | ✅ | ⚠️ | **7/10** |
| Rule Matching | 7/10 | ⚠️ | ✅ | ⚠️ | **7/10** |
| Scenario Orchestration | 6/10 | ⚠️ | ✅ | ⚠️ | **6/10** |

### 5.2 Remaining Interface Work

| Interface | Status | Needs |
|-----------|--------|-------|
| `AlignmentEngine.process_turn()` | ⚠️ Partial | Error handling contract |
| Session state machine | ⚠️ Partial | Formal state transitions |
| Scenario step skipping | ❌ Missing | Algorithm specification |
| Enforcement expressions | ❌ Missing | Language definition |

---

## 6. Production Readiness

### 6.1 Scalability

| Aspect | Status | Notes |
|--------|--------|-------|
| Stateless design | ✅ | No in-memory state |
| Horizontal scaling | ✅ | Any pod serves any request |
| Multi-tenant isolation | ✅ | `tenant_id` everywhere |
| Session concurrency | ✅ | Hatchet-native |
| Message queuing | ✅ | Hatchet RabbitMQ |
| Tool safety | ✅ | SideEffectPolicy + idempotency |
| Latency budgets | ⚠️ | Need P95 targets |
| Vector search scaling | ⚠️ | Need index tuning |

### 6.2 Redis Usage

| Purpose | Still Needed? |
|---------|---------------|
| SessionStore cache | ✅ Yes |
| Configuration bundles | ✅ Yes |
| Config hot-reload pub/sub | ✅ Yes |
| Idempotency cache | ✅ Yes |
| Workflow tracking | ✅ Yes |
| **Session mutex** | ❌ No (Hatchet replaces) |

### 6.3 Reliability Gaps

| Gap | Severity | Status |
|-----|----------|--------|
| Graceful degradation | HIGH | ❌ Not documented |
| Circuit breaker patterns | HIGH | ❌ Not documented |
| PostgreSQL failure handling | HIGH | ❌ Not documented |
| Hatchet failure handling | HIGH | ❌ Not documented |
| SLA/SLO definitions | MEDIUM | ❌ Not defined |

---

## 7. Security Posture

### 7.1 Strengths

| Area | Status |
|------|--------|
| JWT Authentication | ✅ Mandatory tenant_id claim |
| Multi-tenant Isolation | ✅ tenant_id on all entities |
| Secrets Management | ✅ SecretStr, secret manager |
| PII Privacy | ✅ Schema masking for LLMs |
| Tool Safety | ✅ SideEffectPolicy |
| Structured Logging | ✅ Auto-redaction |

### 7.2 Gaps

| Gap | Severity |
|-----|----------|
| Encryption at rest | HIGH |
| PostgreSQL RLS | HIGH |
| RBAC enforcement | HIGH |
| Prompt injection blocking | MEDIUM |
| Tool sandboxing | MEDIUM |
| Security headers | MEDIUM |

---

## 8. Operational Readiness

### 8.1 Maturity Matrix

| Dimension | Dev | Staging | Production |
|-----------|-----|---------|------------|
| Observability | ✅ | ✅ | ⚠️ Needs alerting |
| Deployment | ✅ Docker | ✅ Docker | ❌ No K8s |
| Configuration | ✅ | ✅ | ✅ |
| Testing | ✅ | ✅ | ⚠️ Security tests |
| Debugging | ⚠️ | ⚠️ | ❌ No runbooks |
| DR | ❌ | ❌ | ❌ CRITICAL |

### 8.2 Critical Gaps

| Gap | Severity | Effort |
|-----|----------|--------|
| Kubernetes manifests | CRITICAL | 3 days |
| Backup/restore procedures | CRITICAL | 3 days |
| Runbooks (top 9) | CRITICAL | 4 days |
| Deployment strategy | HIGH | 2 days |
| Alerting rules | HIGH | 2 days |
| Load testing | HIGH | 3 days |

### 8.3 Required Runbooks

1. High error rate (>5% turns failing)
2. Response latency degradation
3. Database connection pool exhausted
4. LLM provider outage
5. Hatchet workflow backlog
6. Redis unavailable
7. Vector search latency spike
8. Scenario migration stuck
9. Tool execution timeouts

---

## 9. Recommendations

### Phase 1: Pre-Production (Weeks 1-2)

**Documentation**:
- [ ] Create webhook specification
- [ ] Create ChannelGateway interface
- [ ] Create error handling specification
- [ ] Define session state machine
- [ ] Define enforcement expression language

**Security**:
- [ ] Enable PostgreSQL Row-Level Security
- [ ] Implement encryption at rest
- [ ] Add role-based authorization
- [ ] Add prompt injection detection

**Operations**:
- [ ] Create Kubernetes manifests
- [ ] Create backup/restore procedures
- [ ] Create top 5 runbooks
- [ ] Define alerting rules

### Phase 2: Hardening (Weeks 3-4)

**Scalability**:
- [ ] Define per-tenant limits
- [ ] Configure channel-specific strategies
- [ ] Add workflow queue monitoring
- [ ] Document circuit breakers

**Reliability**:
- [ ] Define SLO/SLI framework
- [ ] Implement graceful degradation
- [ ] Document failure scenarios
- [ ] Add health checks for all backends

**Testing**:
- [ ] Load test at 10k concurrent sessions
- [ ] Security testing (injection, isolation)
- [ ] Chaos engineering tests

### Phase 3: Production Launch (Weeks 5-6)

- [ ] Blue/Green deployment procedure
- [ ] Canary deployment process
- [ ] Rollback procedures
- [ ] Grafana dashboards
- [ ] On-call rotation
- [ ] Monthly DR drills

---

## 10. Architecture Decision Records

| Decision | Choice | Reference |
|----------|--------|-----------|
| Session Concurrency | Hatchet-native | `ACF_SCALABILITY_ANALYSIS.md` |
| Message Queue | Hatchet RabbitMQ | `ACF_SCALABILITY_ANALYSIS.md` |
| Supersede Strategy | Channel-specific | `ACF_SCALABILITY_ANALYSIS.md` |
| Event Model | AgentEvent + ACFEvent | `event-model.md` |
| Event Naming | FabricEvent → ACFEvent | `event-model.md` |
| Reserved Events | `infra.*` namespace | `event-model.md` |
| Tool Safety | SideEffectPolicy + 3-layer idempotency | `TOOLBOX_SPEC.md` |
| Doc Structure | `focal_360/` → `acf/` | This document |

---

## 11. Summary

### What's Complete

| Area | Status |
|------|--------|
| Core architecture | ✅ Well-designed |
| ACF concurrency | ✅ Hatchet-native solution |
| Event model | ✅ Two-layer (AgentEvent + ACFEvent) |
| Tool safety | ✅ SideEffectPolicy + idempotency |
| Documentation structure | ✅ Clean (`acf/`, `brains/`) |
| Multi-tenancy | ✅ tenant_id everywhere |
| Observability foundations | ✅ structlog, OTEL, Prometheus |

### What's Needed

| Area | Priority | Effort |
|------|----------|--------|
| Operational infrastructure | CRITICAL | 2-3 weeks |
| Security hardening | HIGH | 1-2 weeks |
| Missing specifications | HIGH | 1 week |
| Terminology cleanup | LOW | 2 days |

### Estimated Effort to Production

**4-6 weeks** with dedicated DevOps/SRE support.

---

## Appendix A: File References

### Core Architecture
- `docs/architecture/overview.md`
- `docs/architecture/event-model.md`
- `docs/architecture/ACF_SCALABILITY_ANALYSIS.md`
- `docs/architecture/configuration-*.md`
- `docs/architecture/architecture_reconsideration.md`

### ACF
- `docs/acf/README.md`
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/TOOLBOX_SPEC.md`
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- `docs/acf/architecture/topics/*.md`

### FOCAL Brain
- `docs/focal_brain/spec/brain.md`
- `docs/focal_brain/spec/data_models.md`

### Design
- `docs/design/domain-model.md`
- `docs/design/decisions/*.md`

---

## Appendix B: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-15 | Initial assessment |
| 2.0 | 2025-12-15 | Added Hatchet-native solution, tool safety model |
| 3.0 | 2025-12-15 | Event model (AgentEvent + ACFEvent), folder restructure |

---

*Report generated: 2025-12-15*
*Platform: Ruche*
*Version: 3.0*
