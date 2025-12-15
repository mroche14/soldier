# Ruche Architecture Readiness Report

> **Analysis Date**: 2025-12-15
> **Scope**: Implementation & Production Readiness Assessment
> **Status**: COMPREHENSIVE REVIEW COMPLETE
> **Version**: 2.0

---

## Executive Summary

This report presents findings from an exhaustive analysis of the Ruche architecture documentation. The assessment evaluates whether the architecture is **implementation-ready** (can developers build it?) and **production-ready** (can it run reliably at scale?).

### Overall Verdict

| Dimension | Score | Status | Change from v1 |
|-----------|-------|--------|----------------|
| **Architecture Completeness** | 75-80% | Core components well-defined | +5% |
| **Cross-Document Consistency** | 80% | Terminology standardizing | +5% |
| **Implementation Readiness** | 75% | Models complete; key interfaces defined | +5% |
| **Production Readiness** | 65% | Scaling bottleneck resolved | +15% |
| **Security Posture** | 70% | Good foundations; encryption gaps | — |
| **Operational Readiness** | 45% | Development-ready; production infra missing | +5% |

### Key Changes in v2

**Resolved Issues:**
- **ACF Session Mutex** - Solution defined: Hatchet-native concurrency (see `ACF_SCALABILITY_ANALYSIS.md`)
- **Tool Side Effects** - Three-layer protection: SideEffectPolicy + Idempotency + Supersede Guards
- **Message Queuing** - Handled natively by Hatchet's RabbitMQ integration

**Strengths:**
- Well-designed multi-tenant architecture (tenant_id everywhere)
- Complete data models (Pydantic schemas for all core entities)
- Strong observability foundation (structlog, OpenTelemetry, Prometheus)
- Comprehensive FOCAL brain specification (11 phases documented)
- Good secrets management (SecretStr, secret manager integration)
- Robust tool safety model (SideEffectPolicy enum, idempotency layers)

**Remaining Gaps:**
- No Kubernetes deployment manifests
- No disaster recovery procedures
- Missing webhook specifications
- No operational runbooks
- Encryption at rest not implemented

---

## 1. Architecture Completeness Analysis

### Component Coverage

| Component | Status | Completeness | Notes |
|-----------|--------|--------------|-------|
| ACF (Agent Conversation Fabric) | Complete | 100% | Concurrency solution defined |
| Agent Runtime | Complete | 100% | |
| Toolbox | Complete | 100% | SideEffectPolicy specified |
| Configuration System | Complete | 100% | |
| Storage Interfaces (4 stores) | Complete | 100% | |
| FOCAL Brain (11 Phases) | Complete | 95% | |
| Memory Layer | Complete | 90% | |
| Selection Strategies | Complete | 100% | |
| Observability | Complete | 95% | |
| API Layer (REST) | Complete | 90% | |
| Idempotency System | Complete | 95% | Three-layer design |
| Hatchet Integration | Complete | 90% | Concurrency patterns documented |

### Missing Components (Prioritized)

| Gap | Severity | Impact | Blocking? |
|-----|----------|--------|-----------|
| **Webhook System** | HIGH | Event delivery to tenant systems | Yes |
| **ChannelGateway Interface** | HIGH | Multi-channel support | Yes |
| **Error Handling Spec** | HIGH | Standardized error codes, retry strategies | Yes |
| **gRPC API Spec** | MEDIUM | High-performance streaming clients | No (future) |
| **MCP Server Spec** | MEDIUM | LLM tool discovery integration | No (future) |
| **Multimodal Providers** | LOW | STT/TTS/Vision interfaces | No (future) |

**Note**: Authentication is out of scope for this phase.

### Documents Needed

**High Priority (Implementation Blockers):**
1. `docs/architecture/api-webhooks.md` - Webhook payload, delivery, retry logic
2. `docs/architecture/channel-gateway.md` - Channel adapter protocol
3. `docs/architecture/error-handling.md` - Error codes, retry strategies, circuit breakers

**Medium Priority (Future Capabilities):**
4. `docs/architecture/api-grpc.md` - gRPC/protobuf definitions
5. `docs/architecture/mcp-server.md` - MCP tool discovery
6. `docs/architecture/providers-multimodal.md` - STT/TTS/Vision interfaces

---

## 2. Cross-Document Consistency Analysis

### Terminology Status

| Term | Old | New (Authoritative) | Status |
|------|-----|---------------------|--------|
| Customer/User | `customer_id` | `interlocutor_id` | Migrating |
| Data Store | `InterlocutorDataStore` | `InterlocutorDataStore` | Migrating |
| Brain folder | `mechanics/`, `brains/` | `brains/` | Complete |
| Platform name | Focal | Ruche | Complete |

### Remaining Inconsistencies

| Issue | Severity | Affected Documents | Status |
|-------|----------|-------------------|--------|
| **Interlocutor vs Customer terminology** | MEDIUM | ~8 files need update | Pending |
| **FabricEvent → ACFEvent rename** | MEDIUM | ~10 files need update | Defined (see below) |
| **Phase 1 context loading detail** | LOW | Overview vs spec minor mismatch | Pending |

### Resolution Required

1. Execute `customer_id` → `interlocutor_id` refactoring across documentation
2. ~~Create EVENT_MODEL.md specifying FabricEvent + AgentEvent relationship~~ ✅ DONE
3. Execute `FabricEvent` → `ACFEvent` rename across documentation (see `docs/architecture/event-model.md` §9.3)
4. Align domain-model.md with Phase 2 spec (add scopes, history, presence)

### Event Model Clarification (RESOLVED)

The event model confusion has been resolved with a two-layer design:

| Layer | Name | Purpose | Reference |
|-------|------|---------|-----------|
| **Semantic** | `AgentEvent` | What happened (business meaning) | `docs/architecture/event-model.md` |
| **Transport** | `ACFEvent` | Routing envelope (replaces FabricEvent) | `docs/architecture/event-model.md` |

**Key Decision**: ACF routes all events but only interprets `infra.*` namespace events.

---

## 3. Implementation Readiness Analysis

### Component Readiness Scores

| Component | Spec | Interface | Models | Algorithm | State Machine | **Score** |
|-----------|------|-----------|--------|-----------|---------------|-----------|
| REST API | 9/10 | ✅ | ✅ | N/A | N/A | **9/10** |
| AlignmentEngine | 7/10 | ⚠️ | ✅ | ⚠️ | ❌ | **7/10** |
| ConfigStore | 8/10 | ✅ | ✅ | ✅ | ✅ | **8/10** |
| MemoryStore | 8/10 | ✅ | ✅ | ⚠️ | ✅ | **8/10** |
| SessionStore | 7/10 | ✅ | ✅ | N/A | ⚠️ | **7/10** |
| SelectionStrategy | 9/10 | ✅ | ✅ | ✅ | N/A | **9/10** |
| Rule Matching | 7/10 | ⚠️ | ✅ | ⚠️ | ❌ | **7/10** |
| Scenario Orchestration | 6/10 | ⚠️ | ✅ | ⚠️ | ❌ | **6/10** |
| ACF | 8/10 | ✅ | ✅ | ✅ | ⚠️ | **8/10** |
| Toolbox | 9/10 | ✅ | ✅ | ✅ | ✅ | **9/10** |
| Idempotency | 9/10 | ✅ | ✅ | ✅ | N/A | **9/10** |

### Blocking Implementation Items

**Must define before implementation:**

1. **AlignmentEngine.process_turn() interface** with error handling contract
2. **Session state machine** (ACTIVE → IDLE → PROCESSING → CLOSED transitions)
3. **Scenario step skipping algorithm** (required field detection)
4. **Enforcement expression language** (Python? Jinja2? Custom DSL?)

**Already Resolved:**
- ~~ACF supersede response~~ → Hatchet `CANCEL_IN_PROGRESS` strategy
- ~~Message queuing~~ → Hatchet `GROUP_ROUND_ROBIN` strategy
- ~~Tool safety during cancellation~~ → SideEffectPolicy + Idempotency

### Recommended Implementation Sequence

```
Phase 0-3: ✅ DONE (Skeleton, Config, Observability, Models)
    ↓
Phase 4: SPECIFY MISSING INTERFACES
    - AlignmentEngine (process_turn contract)
    - Session state machine
    ↓
Phase 5: Implement Selection Strategies (ElbowSelection first)
    ↓
Phase 6: P1 + P2 (Identification + Situational Sensor)
    ↓
Phase 7: Stores (ConfigStore, SessionStore in-memory)
    ↓
Phase 8: P4 Retrieval (with selection strategies)
    ↓
Phase 9: Rule Matching (P5) + Enforcement (P10)
    ↓
Phase 10: Scenario Orchestration (P6) - most complex
    ↓
Phase 11: ACF + Hatchet Integration + Tool Execution
```

---

## 4. Production Readiness Analysis

### Scalability Assessment

| Aspect | Status | Risk | Notes |
|--------|--------|------|-------|
| Stateless design | ✅ Strong | Low | |
| Horizontal scaling | ✅ Designed | Low | |
| Multi-tenant isolation | ✅ Enforced | Low | |
| **ACF Session Concurrency** | ✅ Solved | Low | Hatchet-native concurrency |
| **Message Queuing** | ✅ Solved | Low | Hatchet RabbitMQ integration |
| **Tool Safety** | ✅ Solved | Low | SideEffectPolicy + Idempotency |
| **Latency budgets** | ⚠️ Undefined | MEDIUM | Need P95 targets |
| **Vector search scaling** | ⚠️ Untuned | MEDIUM | Need index tuning |

### ACF Concurrency Solution (IMPLEMENTED)

```
SOLUTION: Hatchet-Native Concurrency
┌─────────────────────────────────────────────────────────────────┐
│  @hatchet.concurrency(                                          │
│      expression="input.session_key",                            │
│      max_runs=1,                                                 │
│      limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN  │
│  )                                                               │
└─────────────────────────────────────────────────────────────────┘

Benefits:
├─ No custom Redis lock code
├─ Automatic message queuing via RabbitMQ
├─ Native supersede via CANCEL_IN_PROGRESS strategy
├─ Built-in observability (Hatchet dashboard)
└─ Automatic retry handling

Strategies by Channel:
├─ WhatsApp/SMS/Telegram → GROUP_ROUND_ROBIN (queue messages)
├─ Web/Mobile App → CANCEL_IN_PROGRESS (supersede behavior)
└─ Default → GROUP_ROUND_ROBIN
```

**Reference**: `docs/architecture/ACF_SCALABILITY_ANALYSIS.md`

### Tool Safety Model (THREE-LAYER PROTECTION)

```
Layer 1: API Idempotency (5 min TTL)
├─ Prevents duplicate API calls
└─ Key: idem:{tenant_id}:{idempotency_key}

Layer 2: Turn/Beat Idempotency (60 sec TTL)
├─ Prevents duplicate turn processing
└─ Key: idempotency:{tenant_id}:{beat_id}

Layer 3: Tool Idempotency (24 hour TTL)
├─ Prevents duplicate side effects
└─ Key: tool_idem:{tenant_id}:{tool}:{business_key}
```

**SideEffectPolicy Classification:**

| Policy | Description | Can Supersede? | Protection |
|--------|-------------|----------------|------------|
| `PURE` | No side effects | Yes | None needed |
| `IDEMPOTENT` | Has effects, key protects | Yes | Idempotency key |
| `COMPENSATABLE` | Can be rolled back | Yes* | Compensation workflow |
| `IRREVERSIBLE` | Cannot be undone | No | Requires confirmation |

*With compensation execution

**Supersede Guard:**
```python
def can_supersede(turn: LogicalTurn) -> bool:
    return not any(se.irreversible for se in turn.side_effects)
```

### Redis Usage Clarification

**Redis is STILL REQUIRED for:**

| Usage | Purpose | Removable? |
|-------|---------|------------|
| SessionStore cache | Fast session reads | No |
| Configuration bundles | Publisher → Focal config | No |
| Config hot-reload pub/sub | `cfg-updated` channel | No |
| Idempotency cache | Three-layer protection | No |
| Workflow run ID tracking | Session → workflow mapping | No |

**Redis is NO LONGER NEEDED for:**

| Usage | Replacement |
|-------|-------------|
| Session mutex/locks | Hatchet concurrency controls |
| Message queuing | Hatchet RabbitMQ integration |

### Reliability Gaps

| Gap | Impact | Severity |
|-----|--------|----------|
| No graceful degradation strategy | Cascading failures | HIGH |
| No circuit breaker pattern | Provider outages propagate | HIGH |
| PostgreSQL failure = undefined | Service unavailable | HIGH |
| No SLA/SLO definitions | Can't measure reliability | MEDIUM |

### Fault Tolerance Scenarios

| Failure | Current Behavior | Documented? |
|---------|------------------|-------------|
| Redis down | SessionStore degraded, idempotency fails | ⚠️ Partial |
| PostgreSQL down | Service fails | ❌ No |
| LLM provider down | Fallback chain | ✅ Yes |
| All providers down | Unknown | ❌ No |
| Hatchet down | Workflow processing stops | ❌ No |
| RabbitMQ down | Message queuing fails | ❌ No |

### Multi-Tenancy Gaps

| Gap | Impact |
|-----|--------|
| No resource limits per tenant | Tenant A can exhaust shared resources |
| No per-tenant rate limiting | Beyond global limiter |
| No storage quotas | Disk exhaustion |
| No LLM token quotas | Cost overrun |

---

## 5. Security Posture Analysis

### Security Strengths

| Area | Implementation | Status |
|------|----------------|--------|
| JWT Authentication | Mandatory tenant_id claim | ✅ Strong |
| Multi-tenant Isolation | tenant_id on all entities | ✅ Strong |
| Secrets Management | SecretStr, secret manager | ✅ Strong |
| PII Privacy | CustomerSchemaMask | ✅ Strong |
| Structured Logging | Auto-redaction patterns | ✅ Good |
| Soft Deletes | Audit trail preservation | ✅ Good |
| Tool Safety | SideEffectPolicy classification | ✅ Strong |

### Security Gaps

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| **No encryption at rest** | HIGH | Enable pgcrypto for customer data |
| **No DB-level RLS** | HIGH | Add PostgreSQL Row-Level Security |
| **No RBAC enforcement** | HIGH | Add per-endpoint role checks |
| **No real-time prompt injection blocking** | MEDIUM | Add pre-LLM filtering |
| **No tool sandboxing** | MEDIUM | Add timeouts, resource limits |
| **No agent ownership validation** | MEDIUM | Verify tenant owns agent_id |
| **No security headers** | MEDIUM | Add CSP, HSTS, X-Frame-Options |
| **No data retention policy** | MEDIUM | Implement auto-deletion |

### Priority Security Fixes

**Critical (Do First):**
1. Add PostgreSQL Row-Level Security (RLS)
2. Encrypt customer data at rest
3. Implement real-time prompt injection blocking
4. Add role-based authorization checks

**High (Do Soon):**
5. Implement agent ownership validation
6. Add GDPR data export/deletion mechanisms
7. Encrypt audit logs
8. Add tool execution sandboxing (timeouts)

---

## 6. Operational Readiness Analysis

### Operational Maturity Matrix

| Dimension | Development | Staging | Production |
|-----------|-------------|---------|------------|
| Observability | ✅ Ready | ✅ Ready | ⚠️ Needs alerting |
| Deployment | ✅ Docker | ✅ Docker | ❌ No K8s |
| Configuration | ✅ Ready | ✅ Ready | ✅ Ready |
| Testing | ✅ Complete | ✅ Ready | ⚠️ Needs security |
| Debugging | ⚠️ Basic | ⚠️ Basic | ❌ No runbooks |
| Disaster Recovery | ❌ Missing | ❌ Missing | ❌ CRITICAL |
| On-Call Support | ❌ Missing | ⚠️ Partial | ❌ Missing |

### Critical Operational Gaps

| Gap | Severity | Effort |
|-----|----------|--------|
| **No Kubernetes manifests** | CRITICAL | 3 days |
| **No backup/restore procedures** | CRITICAL | 3 days |
| **No runbooks** | CRITICAL | 4 days |
| **No deployment strategy** | HIGH | 2 days |
| **No alerting rules** | HIGH | 2 days |
| **No load testing** | HIGH | 3 days |
| **Incomplete health checks** | MEDIUM | 1 day |

### Required Runbooks

1. "High error rate (>5% of turns failing)"
2. "Response latency degradation"
3. "Out of memory errors"
4. "Database connection pool exhausted"
5. "LLM provider outage"
6. "Vector search latency spike"
7. "Hatchet workflow backlog growing"
8. "Scenario migration stuck"
9. "Tool execution timeouts"

---

## 7. Consolidated Recommendations

### Phase 1: Pre-Production (Weeks 1-2)

**Documentation & Specs:**
- [ ] Create webhook payload specifications
- [ ] Create ChannelGateway interface specification
- [ ] Define AlignmentEngine.process_turn() contract
- [ ] Define session state machine transitions
- [ ] Define enforcement expression language
- [ ] Create gRPC protobuf specifications (future reference)
- [ ] Create MCP server specification (future reference)

**Security:**
- [ ] Enable PostgreSQL Row-Level Security
- [ ] Implement encryption at rest for customer data
- [ ] Add role-based authorization enforcement
- [ ] Add real-time prompt injection detection

**Operations:**
- [ ] Create Kubernetes deployment manifests
- [ ] Create backup/restore procedures (RTO < 1h, RPO < 15min)
- [ ] Create top 5 runbooks
- [ ] Define alerting rules

### Phase 2: Hardening (Weeks 3-4)

**Scalability:**
- [ ] Define per-tenant concurrency limits
- [ ] Configure Hatchet concurrency per channel type
- [ ] Add workflow queue depth monitoring
- [ ] Document circuit breaker patterns

**Reliability:**
- [ ] Define SLO/SLI framework
- [ ] Implement graceful degradation modes
- [ ] Document all failure scenarios with recovery
- [ ] Add health checks for Hatchet/RabbitMQ

**Testing:**
- [ ] Run load tests at 10k concurrent sessions
- [ ] Implement security testing (injection, isolation)
- [ ] Create chaos engineering test suite (Redis, PostgreSQL, Hatchet failures)

### Phase 3: Production Launch (Weeks 5-6)

**Deployment:**
- [ ] Blue/Green deployment procedure
- [ ] Canary deployment process
- [ ] Rollback procedure with testing
- [ ] Database migration playbook

**Operations:**
- [ ] Grafana dashboards (including Hatchet metrics)
- [ ] On-call rotation setup
- [ ] Incident response procedures
- [ ] Monthly DR drills

---

## 8. Summary of Resolved Issues (v1 → v2)

| Issue | v1 Status | v2 Status | Resolution |
|-------|-----------|-----------|------------|
| ACF Session Mutex Bottleneck | CRITICAL | ✅ RESOLVED | Hatchet-native concurrency |
| Message Queuing Strategy | Missing | ✅ RESOLVED | Hatchet GROUP_ROUND_ROBIN |
| Supersede Handling | Undefined | ✅ RESOLVED | Hatchet CANCEL_IN_PROGRESS |
| Tool Safety During Cancel | Concern | ✅ RESOLVED | SideEffectPolicy + Idempotency |
| Redis Lock Contention | CRITICAL | ✅ RESOLVED | No longer using Redis locks |
| FabricEvent vs AgentEvent | Unclear | ✅ RESOLVED | Two-layer model defined (event-model.md) |

---

## Conclusion

The Ruche architecture represents a **well-designed cognitive engine** with strong foundations in multi-tenancy, observability, and configuration management. Version 2.0 of this assessment reflects significant improvements:

**Major Improvements:**
1. **Scaling bottleneck resolved** - Hatchet-native concurrency eliminates Redis lock contention
2. **Tool safety model complete** - SideEffectPolicy + three-layer idempotency
3. **Message queuing handled** - Hatchet's RabbitMQ integration
4. **Supersede behavior defined** - Channel-specific strategies

**Remaining Work:**

1. **Interface specifications** needed for webhooks, ChannelGateway, error handling
2. **State machines** need formal definition (session lifecycle, scenario orchestration)
3. **Security hardening** required (encryption, RLS, authorization)
4. **Operational infrastructure** missing (Kubernetes, runbooks, DR)

**Estimated effort to production-ready: 4-6 weeks** with dedicated DevOps/SRE support.

---

## Appendix A: Architecture Decision Records

| Decision | Choice | Rationale | Document |
|----------|--------|-----------|----------|
| Session Concurrency | Hatchet-native | Simplest, leverages existing infra | ACF_SCALABILITY_ANALYSIS.md |
| Message Queue | Hatchet RabbitMQ | Built-in, no separate system | ACF_SCALABILITY_ANALYSIS.md |
| Supersede Strategy | Channel-specific | WhatsApp queues, Web supersedes | ACF_SCALABILITY_ANALYSIS.md |
| Tool Safety | SideEffectPolicy | Clear classification, enables automation | TOOLBOX_SPEC.md |
| Idempotency | Three-layer | Defense in depth | WAVE_EXECUTION_GUIDE_V2.md |
| Event Model | AgentEvent + ACFEvent | Separation of concerns | event-model.md |
| Event Naming | FabricEvent → ACFEvent | Clarity, ACF ownership | event-model.md |
| Reserved Events | `infra.*` namespace | ACF interprets only infrastructure | event-model.md |

## Appendix B: Files Analyzed

### Core Architecture
- `docs/architecture/overview.md`
- `docs/architecture/api-layer.md`
- `docs/architecture/observability.md`
- `docs/architecture/configuration-*.md`
- `docs/architecture/architecture_reconsideration.md`
- `docs/architecture/ACF_SCALABILITY_ANALYSIS.md`
- `docs/architecture/event-model.md` (new - AgentEvent + ACFEvent specification)

### ACF Architecture
- `docs/acf/architecture/ACF_ARCHITECTURE.md`
- `docs/acf/architecture/ACF_SPEC.md`
- `docs/acf/architecture/AGENT_RUNTIME_SPEC.md`
- `docs/acf/architecture/TOOLBOX_SPEC.md`
- `docs/acf/architecture/topics/*.md`
- `docs/acf/WAVE_EXECUTION_GUIDE_V2.md`

### FOCAL Brain
- `docs/focal_brain/spec/data_models.md`
- `docs/focal_brain/spec/brain.md`
- `docs/focal_brain/spec/configuration.md`

### Design
- `docs/design/domain-model.md`
- `docs/design/interlocutor-data.md`
- `docs/design/decisions/001-storage-choice.md`

### Code
- `ruche/api/middleware/auth.py`
- `ruche/api/middleware/rate_limit.py`
- `ruche/api/routes/health.py`
- `ruche/infrastructure/stores/*/interface.py`
- `ruche/brains/protocol.py`

---

*Report generated: 2025-12-15*
*Version: 2.0*
