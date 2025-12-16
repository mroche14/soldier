# Repo Alignment and Migration Notes (soldier ↔ sb_agent_hub ↔ kernel_agent)

This file translates the stack choices into concrete “what changes where” guidance.

## A. If Hatchet is canonical (recommended convergence path)

### soldier (this repo)

- Keep: Hatchet workflows for ACF + webhooks + (future) tool orchestration.
- Change: replace Redis mutex with Hatchet concurrency groups (docs already recommend this).
- Decide: whether inbound/outbound “event bus” becomes Redis Streams (kernel_agent contract) or Hatchet-triggered workflows (less portable across services).

### sb_agent_hub

- Decide what Celery is doing that Hatchet cannot (often: “background jobs” and beat schedules).
- Likely change:
  - Replace Celery task fanout for long-running jobs with Hatchet workflows.
  - Keep Redis for caching/session storage.
  - If periodic tasks exist: either (a) Hatchet scheduled runs, or (b) keep Celery beat only if strictly necessary.

### kernel_agent

- Replace Restate “publish pipeline” durable orchestration with Hatchet workflow(s) that implement the same stages:
  - validate → compile → apply → write_bundles → swap_pointer → invalidate_cache → notify
- Keep (optional): Redis Streams bus contracts (they are orthogonal to orchestrator choice).

## B. If Restate is canonical

### soldier

- Major migration: ACF LogicalTurn Hatchet workflow becomes Restate “service per session key” or workflow.
- You must re-implement:
  - message accumulation (`wait_for_event`) and supersede logic,
  - existing Hatchet worker infrastructure,
  - any Hatchet-based webhook workflows.

### sb_agent_hub

- Celery becomes optional for heavy execution; Restate can orchestrate and/or trigger tasks.
- Redis remains for caching and bundles.

## C. Shared contracts that should be unified (regardless of engine)

### 1) Correlation + idempotency

Unify a single correlation-id scheme across repos:
- turn-level: `{tenant}:{agent}:{session}:{turn_id}`
- tool-level: `{tenant}:{agent}:{session}:{event_offset}:{tool_name}` (or equivalent)
- publish-level: `{tenant}:{agent}:v{version}`

Then require one idempotency strategy:
- Redis: `SETNX idem:{hash} 1 EX <ttl>`
- DB outbox row uniqueness (publish pipeline)

### 2) Message bus subjects (ChannelGateway / MessageRouter)

Adopt one consistent naming convention (example):
- `events.inbound.{tenant}.{channel}`
- `events.routed.{tenant}.{channel}`
- `events.outbound.{tenant}.{channel}`

If you use Redis Streams, standardize:
- stream maxlen/trim
- consumer group names
- pending-claim strategy and visibility timeouts

### 3) Tool results callback contract

Standardize a single callback endpoint contract for async tool completion:
- Must include `tenant`, `agent`, `session`, correlation id, idempotency key, final status.
- Must be authorized (JWT scope or mTLS) and must not leak cross-tenant.
