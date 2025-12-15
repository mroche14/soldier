# FOCAL 360 Wave Analysis Report

> **Date**: 2025-12-09
> **Purpose**: Critical analysis of all 6 FOCAL 360 waves to inform project trajectory decisions
> **Method**: Subagent exploration of codebase, documentation, and existing implementations

---

## Executive Summary

This report provides a comprehensive analysis of the 6 proposed FOCAL 360 implementation waves. Each wave was analyzed by a dedicated subagent that explored the relevant codebase, read documentation, and assessed implementation plans against existing infrastructure.

### Overall Verdict

| Wave | Features | Verdict | Effort | Value | Risk |
|------|----------|---------|--------|-------|------|
| **1** | Idempotency + AgentConfig | ✅ **PROCEED** (with modifications) | Low | High | Low |
| **2** | Debouncing + Abuse Detection | ⚠️ **MODIFY SIGNIFICANTLY** | Medium | Mixed | Medium |
| **3** | ChannelCapability + ScenarioConfig | ❌ **DEFER** | High | Low | High |
| **4** | SideEffectRegistry + Turn Cancellation | ❌ **DEPRIORITIZE** | Very High | Low | Very High |
| **5** | Agenda/Goals + Hot Reload | ⚠️ **SPLIT** | Medium | High/Low | Low/High |
| **6** | Reporter + ASA Meta-Agents | ❌ **SKIP** | Very High | Low | Very High |

### Key Finding

**Many FOCAL 360 features solve theoretical problems, not real ones.** The analysis reveals that simpler alternatives exist for most proposed features, and the platform needs battle-testing more than new features.

---

## Wave 1: Foundation (Idempotency + AgentConfig)

### Verdict: ✅ PROCEED WITH MODIFICATIONS

### Analysis Summary

Wave 1 proposes two parallel tasks that wire existing infrastructure:

1. **Idempotency Integration**: Connect existing `IdempotencyCache` to chat endpoint
2. **AgentConfig Integration**: Wire existing `AgentConfig` model into brain

### What Already Exists

**Idempotency:**
- `IdempotencyCache` class at `ruche/api/middleware/idempotency.py` (lines 29-130)
- TODOs at `ruche/api/routes/chat.py` lines 189-193 and 232-234
- `compute_request_fingerprint()` utility (lines 148-165)
- `idempotency_key` parameter already in chat route (line 152)

**AgentConfig:**
- `AgentConfig` model at `ruche/config/models/agent.py` (lines 8-41)
- `Agent` domain model at `ruche/alignment/models/agent.py` with embedded `AgentSettings`
- `AgentConfigStore.get_agent()` method already exists (line 189)
- `StaticConfigLoader` already loads agent in P1.6

### Critical Issue: Model Confusion

**Two different models exist with overlapping purposes:**

| Model | Location | Purpose |
|-------|----------|---------|
| `AgentConfig` | `ruche/config/models/agent.py` | Brain configuration overrides |
| `Agent.settings` | `ruche/alignment/models/agent.py` | Domain model with embedded `AgentSettings` |

**The implementation plan doesn't clarify which to use.** This must be resolved before implementation.

### Recommended Approach

**Use existing `Agent.settings`** (from domain model):
- `StaticConfigLoader` already loads `Agent` in P1.6
- Just need to merge `Agent.settings` onto `PipelineConfig` defaults
- Simpler, leverages existing code
- Avoids creating parallel config systems

### Missing Steps Identified

**Idempotency:**
1. Fingerprint validation (hash request body, return 422 on mismatch)
2. Cache key format specification (`idempotency:{tenant_id}:{idempotency_key}`)
3. Streaming endpoint documentation (SSE can't be cached)
4. Redis backend for production

**AgentConfig:**
1. Design decision document on Agent vs AgentConfig usage
2. Executor creation strategy (executors created at init, not per-turn)
3. Caching layer for agent lookups (avoid DB hit per turn)
4. Fallback behavior when agent not found

### Impact Radius

**Idempotency** (Low Risk):
- `ruche/api/routes/chat.py` - Add cache logic
- `ruche/api/middleware/idempotency.py` - Add Redis backend
- `config/default.toml` - Add config section

**AgentConfig** (Medium Risk):
- `ruche/alignment/engine.py` - Add config loading in P1.6
- `ruche/config/loader.py` - Add merge logic
- Every brain step that uses model/temperature/max_tokens

### Potential Problems

1. **Race conditions in idempotency**: Two requests with same key arrive simultaneously
   - Mitigation: Use Redis SETNX for atomic writes

2. **Config model confusion**: Implementation could wire wrong model
   - Mitigation: Write design decision doc FIRST

3. **Executor creation timing**: LLMExecutor created at engine init, not per-turn
   - Mitigation: Build merged config in P1.6, pass to each step

### Recommendation

**Proceed with Wave 1** after:
1. Writing design decision doc on Agent vs AgentConfig (1 day)
2. Adding fingerprint validation to idempotency plan
3. Specifying cache key format with tenant_id

**Estimated Effort**: 3-6 days (as planned)

---

## Wave 2: Ingress & Safety (Debouncing + Abuse Detection)

### Verdict: ⚠️ MODIFY SIGNIFICANTLY

### Analysis Summary

Wave 2 proposes two features:
1. **Debouncing**: Coalesce rapid user messages within a time window
2. **Abuse Detection**: Track and flag abusive behavior patterns

### Critical Finding: Debouncing is Fundamentally Flawed

**The debouncing proposal solves the wrong problem.**

#### Why Debouncing Breaks the Architecture

1. **Rapid messages are legitimate user behavior**
   - User sends "refund my order" then "order #12345" - these are TWO distinct turns
   - Coalescing destroys turn-by-turn context the brain depends on

2. **Rate limiting already handles volumetric abuse**
   - Free: 60/min, Pro: 600/min, Enterprise: 6000/min
   - This IS the throttling mechanism

3. **Idempotency handles accidental duplicates**
   - Same idempotency key = same response
   - This is the correct solution for duplicate clicks

4. **Session state evolution depends on discrete turn boundaries**
   - `turn_number` increments become non-sequential with coalescing
   - Scenario step transitions rely on single-turn boundaries

5. **Creates distributed state coupling**
   - Engine is stateless and horizontal-scaling ready
   - Debouncing requires stateful coordination (which pod is processing what?)

#### Edge Cases That Break

| Scenario | Current Behavior | With Debouncing | Problem |
|----------|------------------|-----------------|---------|
| User sends "help" then "cancel help" | Two turns, second cancels intent | Coalesced into one turn | Lost cancellation intent |
| User corrects typo: "refnd" → "refund" | Two turns, second overrides | Coalesced: "refnd refund" | Garbled input to LLM |
| Message 1 executes tool, Message 2 arrives | Tool committed, Message 2 processed | Message 2 cancelled/merged | Irreversible action + lost input |

#### What Problem Is Actually Being Solved?

The documentation mentions "two or three messages back to back" but doesn't explain:
- Is this a performance problem? (Rate limiting handles this)
- Is this a UX problem? (Users expect each message answered)
- Is this a cost problem? (Per-turn token usage is intentional)

**Verdict: Debouncing is a solution in search of a problem.**

### Abuse Detection: Valuable but Needs Simplification

**What Works:**
- Clear use case (detecting harassment, policy violations)
- Good integration points (TurnRecord, AuditStore, OutcomeCategory)
- Follows existing patterns (similar to SAFETY_REFUSAL handling)

**What Needs Fixing:**
- Too many detection layers (middleware AND brain)
- Unclear thresholds
- Missing graduated response

### Recommended Approach for Abuse Detection

**Move to background job (not middleware)**:

```python
# ruche/jobs/workflows/abuse_detection.py
class AbuseDetectionWorkflow:
    """Analyze turn patterns to detect abuse."""

    async def detect_abuse_patterns(self, tenant_id: UUID) -> list[CustomerAbuseReport]:
        # Query last 24h of turns per customer
        # Detect:
        # - Excessive rate limit hits (>10/hour)
        # - Repeated SAFETY_REFUSAL (>5/day)
        # - Pattern spamming (same message 10+ times)
```

**Benefits:**
- Zero request latency impact (analysis is async)
- Leverages existing AuditStore and Hatchet infrastructure
- Sophisticated pattern detection over time windows

### Impact Radius

**If debouncing implemented (NOT RECOMMENDED):**
- `ruche/api/middleware/ingress.py` (NEW - 200-300 lines)
- Requires Redis for distributed state
- Touches 100% of user-facing traffic

**Abuse detection (recommended approach):**
- `ruche/alignment/models/outcome.py` - Add enum value
- `ruche/jobs/workflows/abuse_detection.py` (NEW)
- `ruche/interlocutor_data/models.py` - Add `abuse_risk_score` field

### Recommendation

1. **SKIP debouncing entirely** - Rate limiting + idempotency are sufficient
2. **Implement abuse detection as background job** - 1-2 days
3. **Add `ABUSE_SUSPECTED` to OutcomeCategory** - 5 minutes
4. **Create Hatchet workflow for pattern analysis** - 3-4 hours

**Revised Effort**: 1-2 days (down from 3-5 days)

---

## Wave 3: Config & Channels (ChannelCapability + ScenarioConfig)

### Verdict: ❌ DEFER

### Analysis Summary

Wave 3 proposes:
1. **ChannelCapability**: Metadata model for channel features (max length, rich media support)
2. **ScenarioConfig**: Per-scenario configuration overrides

### ChannelCapability: Duplicates Existing Formatters

**What Already Exists:**

```python
# ruche/alignment/generation/formatters/whatsapp.py
class WhatsAppFormatter(ChannelFormatter):
    MAX_LENGTH = 4096  # Already defined

# ruche/alignment/generation/formatters/sms.py
class SMSFormatter(ChannelFormatter):
    MAX_LENGTH = 160  # Already defined
```

**The formatters ARE the capability model.** They already encode:
- Max message length per channel
- Rich media support
- Markdown conversion rules
- Channel-specific formatting

**Adding ChannelCapability creates two sources of truth:**

```python
# Now we have TWO sources of truth:
channel_profile.max_length = 4096  # In config
WhatsAppFormatter.MAX_LENGTH = 4096  # In code

# What if they disagree?
```

**Channel capabilities are static** - WhatsApp max length doesn't change. Making this configurable creates risk with no benefit.

### ScenarioConfig: Premature Complexity

**Creates 6-level config hierarchy:**

1. Pydantic defaults (code)
2. `default.toml` (file)
3. `{env}.toml` (file)
4. Environment variables (runtime)
5. AgentConfig (database) ← **NOT YET IMPLEMENTED**
6. ScenarioConfig (database) ← **PROPOSED**

**Debugging becomes a nightmare:**
- "Why is this scenario using GPT-4 instead of Claude?"
- Check 6 different places

**Multi-scenario sessions break the model:**
- You can't have different configs for P2 when 3 scenarios are active
- Which config wins for shared brain steps?

**Unclear use cases:**
- When would you want GPT-4 for one scenario but Claude for another *within the same agent*?
- Step-level config already exists for fine-tuning

### Impact Radius

**ChannelCapability:**
- New model layer (~400 lines)
- Refactor all formatters
- Risk of duplication with existing code

**ScenarioConfig:**
- ~600 lines new code, ~400 lines modified
- Database migration required (JSONB column)
- Affects every turn execution

### Recommendation

**Replace Wave 3 with simpler alternatives:**

1. **Complete AgentConfig integration** (carry-over from Wave 1)
   - This provides 90% of the value with 20% of complexity

2. **Add formatter tests** (currently missing!)
   - `tests/unit/alignment/generation/formatters/` is empty

3. **Document existing formatter behavior**
   - No new code, just documentation

4. **Skip ChannelCapability** - formatters already handle this

5. **Skip ScenarioConfig** - wait 6 months for real use cases

**Revised Effort**: 2-3 days (down from 5-7 days)

---

## Wave 4: Side-Effects & Tools (SideEffectRegistry + Turn Cancellation)

### Verdict: ❌ DEPRIORITIZE

### Analysis Summary

Wave 4 proposes:
1. **SideEffectRegistry**: Classify tools as REVERSIBLE/COMPENSATABLE/IRREVERSIBLE
2. **Turn Cancellation**: Cancel in-flight turns before irreversible actions

### The Problem Being Solved is Extremely Rare

**Real-world scenario:** User triggers IRREVERSIBLE tool, realizes mistake in <1 second, sends "CANCEL" before execution completes.

**Probability: Near zero.**
- Users don't type that fast
- Network latency alone is 100-500ms
- By the time "CANCEL" arrives, tool has executed

### Complexity is Enormous

**Race conditions are unavoidable:**

```python
# Thread 1: Tool execution
async def execute_refund_tool():
    if not cancelled():  # Check: OK to execute
        # ← CANCEL ARRIVES HERE (race condition)
        await payment_provider.refund(amount)  # Too late
```

**Partial execution creates inconsistencies:**
- 3 tools scheduled: `[validate_refund, issue_refund, send_email]`
- Cancel arrives after `issue_refund` but before `send_email`
- Refund issued, email not sent, user thinks it was cancelled

**Compensation failures are undefined:**
- What if compensation tool fails?
- Retry? How many times?
- Alert operations team?
- Leave system in inconsistent state?

**Cancellation token propagation requires massive refactor:**
- Every async call in 11 phases needs token parameter
- Every phase boundary needs check
- Estimated: 200+ lines changed in engine alone

### What Already Exists

`ScenarioStep.is_checkpoint` already marks irreversible steps:

```python
class ScenarioStep(BaseModel):
    is_checkpoint: bool = False  # Already exists!
```

The side-effect registry adds minimal value beyond this.

### Simpler Alternatives

1. **Confirmation steps before checkpoints** (2 days)
   ```python
   if step.is_checkpoint and not session.confirmed_checkpoint:
       return "Are you sure you want to issue a refund? Reply 'yes' to confirm."
   ```

2. **Debounce input** - Wait 500ms before processing (already rejected as bad UX)

3. **Idempotency keys** - Already in Wave 1, prevents duplicate tool execution

### Impact Radius

**If implemented as proposed:**
- Core engine refactor (200+ lines)
- New registry system
- Compensation workflow
- 50+ test cases (many timing-dependent, flaky)
- Ongoing maintenance burden

### Recommendation

**Skip Wave 4 entirely.** Replace with:

1. **Pre-checkpoint confirmation** (2 days)
   - Add `checkpoint_confirmation_required` config flag
   - Before tools on `is_checkpoint` step, require user confirmation
   - Store confirmation in `Session.checkpoint_confirmations`

2. **Request superseding** (2 days)
   - When new message arrives before previous completes, mark old as superseded
   - Don't execute tools for superseded turns

**Revised Effort**: 4 days total (vs 6-10 days for full Wave 4)

**Value**: Covers 95% of use cases without compensation complexity

---

## Wave 5: Lifecycle & Proactive (Agenda/Goals + Hot Reload)

### Verdict: ⚠️ SPLIT INTO TWO WAVES

### Analysis Summary

Wave 5 attempts to deliver two **fundamentally different feature sets**:

1. **Agenda/Goals**: Proactive customer engagement (follow-ups, scheduled tasks)
2. **Hot Reload**: Runtime config updates via Redis pub/sub

**These should be separate waves** with different priorities.

### Agenda/Goals: ✅ PROCEED

**Business Value: HIGH**
- Enables proactive customer engagement
- Key differentiator for "360 customer support"
- Unlocks use cases like:
  - "Follow up in 24h if no response"
  - "Send reminder 1h before appointment"
  - "Check if issue resolved after 3 days"

**Technical Complexity: MEDIUM**
- New subsystem but follows existing patterns
- Hatchet integration is proven (3 workflows already exist)
- AgendaStore follows four-stores pattern
- Goal is a simple model attached to ResponsePlan

**What Exists:**
- Hatchet framework at `ruche/jobs/` with working workflows
- `ResponsePlan` exists (Goal attachment point)
- `Session` model has appropriate storage hooks
- Redis patterns in `ruche/conversation/stores/redis.py`

**What's Missing:**
- `ruche/agenda/` module (models, store, workflows)
- Outbound message trigger endpoint
- Follow-up workflow

**Risk: LOW**
- Isolated from core brain
- Fails gracefully (no Hatchet = no follow-ups, but agent works)
- Easy to test (deterministic scheduling)

### Hot Reload: ❌ DEFER

**Business Value: LOW-MEDIUM**
- Nice to have: Config changes without restart
- But: Restarting pods is fast (<30s), not painful
- Alternative: Blue/green deployment works fine

**Technical Complexity: VERY HIGH**

**Race conditions at every phase boundary:**
- User at P7 when new config publishes
- P1-P6 used old scenario graph
- P7 tries to execute tool bound to old step
- New config removed that step

**Cache coherence across 5+ caches:**
1. Agent config cache
2. Scenario graph cache
3. Rule embeddings cache
4. Template cache
5. Customer data schema cache

Invalidating one but not others creates inconsistency.

**Session pinning undefined:**
- Proposal says "Old sessions continue on old version"
- No implementation mechanism exists
- `Session.config_version` exists but isn't used for pinning

**Redis pub/sub limitations:**
- Fire-and-forget (no ACKs)
- No persistence (message lost if subscriber offline)
- No replay (can't retrieve missed messages)

### Impact Radius

**Agenda/Goals (Contained):**
- New `ruche/agenda/` module
- `ruche/alignment/planning/models.py` - Add Goal to ResponsePlan
- `ruche/jobs/workflows/follow_up.py` - New workflow
- Risk: LOW

**Hot Reload (Wide):**
- Touches every phase of brain
- All config-dependent caches
- Session version management
- New Redis pub/sub dependency
- Risk: VERY HIGH

### Recommendation

**Split Wave 5:**

**Wave 5A: Agenda & Goals** (3-5 days)
- AgendaTask and Goal models
- AgendaStore interface + InMemory
- Hatchet follow-up workflow
- Outbound message trigger
- **Proceed immediately**

**Wave 5B: Hot Reload** (defer to post-MVP)
- High complexity, low immediate value
- Rolling deployments suffice for now
- Revisit if manual restarts become painful (>10/day)

---

## Wave 6: Meta-Agents (Reporter + ASA)

### Verdict: ❌ SKIP ENTIRELY

### Analysis Summary

Wave 6 proposes two "meta-agents":

1. **Reporter**: Analytics narrator providing natural language summaries from audit data
2. **ASA (Agent Setter Agent)**: Configuration builder that helps design rules/scenarios

### Critical Finding: These Are Premature and Risky

**Platform Immaturity:**
- Core 11-phase brain is 93% complete but not battle-tested
- Building meta-agents before base agents are stable is premature

**Unclear Product-Market Fit:**
- No evidence tenants want conversational config builders
- They might prefer UI wizards, API-first, or pre-built templates

### ASA: Dangerous and Unnecessary

**Security Concerns:**
- ASA has godmode access to tenant configurations
- Zero safeguards defined in spec
- Can delete production rules, create infinite loops, misconfigure policies

**What Could Go Wrong:**
```
Tenant: "I want a refund rule."
ASA: [Creates rule that triggers too broadly]
ASA: [Sets wrong side_effect_policy]
ASA: [Forgets amount limit constraint]
Result: Agent issues unlimited refunds to anyone saying "money back"
```

**Simpler Alternative: Wizard UI** (2-3 weeks)
- Step-by-step forms for rule/scenario creation
- Real-time validation
- Preview mode before commit
- Deterministic, safe, predictable

### Reporter: Questionable ROI

**What It Does:**
- Natural language summaries ("Top 3 intents this week")
- Trend analysis ("Abuse flags increased 20%")

**Privacy Concerns:**
- TurnRecord includes raw customer messages (PII)
- No redaction layer defined
- LLM prompt injection risk via customer messages

**Simpler Alternative: Dashboards** (2 days)
- Metabase/Grafana with pre-built queries
- Faster, more precise, shareable
- No LLM costs

### Complexity of "Agents That Build Agents"

This is recursive design complexity:
1. Customer-facing agents use rules/scenarios
2. ASA generates rules/scenarios
3. How does ASA know what makes a "good" rule?
4. Who validates ASA's output?
5. How do you prevent ASA from creating broken configs?

**You're building an AI code generator** - a frontier research problem, not a production feature.

### What Would Be Required

**Infrastructure that doesn't exist:**
- Agent persona framework (currently just `system_prompt: str`)
- Tool-calling for internal APIs (admin APIs are REST, not tools)
- Simulation/sandbox mode
- Change approval workflow
- PII redaction layer
- Evaluation framework

**Estimated: ~40% of needed infrastructure exists, ~60% would need to be built.**

### Recommendation

**Skip Wave 6 entirely.** Replace with:

1. **Config Wizard UI** (2-3 weeks)
   - Step-by-step forms
   - Deterministic, safe
   - Immediate user value

2. **Metabase/Grafana Dashboards** (2 days)
   - Connect to AuditStore
   - Pre-built queries for common analytics
   - Shareable, bookmarkable

3. **Focus on stability**
   - Production battle-testing
   - Multi-tenant scale testing
   - Security audit

**Revisit meta-agents in 6-12 months** after platform is proven in production.

---

## Recommended Revised Roadmap

### Phase 1: Foundation (Weeks 1-2)

| Task | Effort | Priority |
|------|--------|----------|
| Design decision: Agent vs AgentConfig | 1 day | BLOCKING |
| Wave 1: Idempotency integration | 2-3 days | HIGH |
| Wave 1: AgentConfig integration | 2-3 days | HIGH |

### Phase 2: Safety & Stability (Weeks 3-4)

| Task | Effort | Priority |
|------|--------|----------|
| Wave 2 Revised: Abuse detection (background job) | 1-2 days | HIGH |
| Formatter tests (currently missing) | 1 day | MEDIUM |
| Pre-checkpoint confirmation | 2 days | MEDIUM |

### Phase 3: Proactive Features (Weeks 5-6)

| Task | Effort | Priority |
|------|--------|----------|
| Wave 5A: Agenda & Goals | 3-5 days | HIGH |
| Outbound message trigger | 1-2 days | HIGH |

### Deferred (Post-MVP)

| Feature | Reason | Alternative |
|---------|--------|-------------|
| Debouncing | Solves wrong problem | Rate limiting + idempotency |
| ChannelCapability | Duplicates formatters | Document existing formatters |
| ScenarioConfig | Premature complexity | AgentConfig is sufficient |
| Side-Effect Registry | Over-engineered | Confirmation steps |
| Turn Cancellation | Rare edge case | Request superseding |
| Hot Reload | High complexity | Rolling deployments |
| Reporter | Questionable ROI | Dashboards |
| ASA | Dangerous | Wizard UI |

---

## Summary of Key Insights

### 1. Many Features Solve Theoretical Problems

**Debouncing**: "Users send rapid messages" → But that's legitimate behavior, not a bug
**Cancellation**: "Users want to cancel mid-turn" → But they can't type fast enough
**Meta-agents**: "Tenants want conversational config" → But wizards are safer and faster

### 2. Simpler Alternatives Exist

| Proposed | Alternative | Effort Savings |
|----------|-------------|----------------|
| Debouncing | Rate limiting (exists) | 3-5 days |
| Cancellation | Confirmation steps | 4-6 days |
| ChannelCapability | Document formatters | 4-6 days |
| ScenarioConfig | AgentConfig only | 3-5 days |
| Hot Reload | Rolling deployments | 1-2 weeks |
| ASA | Wizard UI | 4-8 weeks |
| Reporter | Dashboards | 1-2 weeks |

### 3. Config Hierarchy is Complex Enough

Current: 5 levels (Pydantic → TOML → env TOML → env vars → AgentConfig)
Proposed: 6 levels (+ ScenarioConfig)

**Don't add more layers until current layers are proven.**

### 4. Platform Needs Battle-Testing

- 93% of implementation tasks complete
- Zero production deployment experience
- Focus on stability, not features

### 5. Build for Real Problems, Not Hypothetical Ones

> "The right amount of complexity is the minimum needed for current use cases."

Wait for:
- Customer feedback
- Production metrics
- Real pain points

Then build features to address them.

---

## Appendix: Files Referenced in Analysis

### Core Infrastructure
- `ruche/api/middleware/idempotency.py` - IdempotencyCache
- `ruche/api/routes/chat.py` - Chat endpoint with TODOs
- `ruche/config/models/agent.py` - AgentConfig model
- `ruche/alignment/models/agent.py` - Agent domain model
- `ruche/alignment/engine.py` - AlignmentEngine
- `ruche/alignment/execution/tool_executor.py` - Tool execution
- `ruche/alignment/models/scenario.py` - ScenarioStep.is_checkpoint
- `ruche/alignment/generation/formatters/` - Channel formatters
- `ruche/jobs/workflows/` - Hatchet workflows
- `ruche/audit/models/turn_record.py` - TurnRecord

### Documentation
- `docs/acf/README.md` - FOCAL 360 overview
- `docs/acf/gap_analysis.md` - Existing vs missing
- `docs/acf/WAVE_EXECUTION_GUIDE.md` - Wave execution plans
- `docs/architecture/kernel-agent-integration.md` - Hot reload design
- `CLAUDE.md` - Project conventions

### Configuration
- `config/default.toml` - Default configuration
- `ruche/config/loader.py` - Config loading

---

## Decision Log

This section should be updated as decisions are made:

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-09 | Analysis complete | 6 subagents analyzed all waves |
| TBD | Wave 1 approach | Pending: Agent vs AgentConfig decision |
| TBD | Wave 2 scope | Pending: Confirm debouncing skip |
| TBD | Wave 3 scope | Pending: Confirm deferral |
| TBD | Wave 4 scope | Pending: Confirm deprioritization |
| TBD | Wave 5 split | Pending: Confirm Agenda proceeds, Hot Reload defers |
| TBD | Wave 6 scope | Pending: Confirm skip |

---

*Report generated by Claude Code analysis agents*
*Last updated: 2025-12-09*
