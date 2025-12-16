# Minimal Stack Recommendations (what to run, and why)

This section proposes **minimal** stacks, then the “next additions” only if required by concrete use-cases.

## Option 0: Keep everything (NOT recommended)

Hatchet + Restate + Celery + Redis + RabbitMQ produces duplication:
- two workflow engines (Hatchet + Restate),
- one task queue (Celery),
- 1–2 brokers (RabbitMQ + Redis),
- multiple message-bus stories (Redis Streams vs Celery broker).

This increases operational cost and makes correctness ambiguous (“which system is authoritative?”).

## Option 1 (recommended for convergence): Hatchet as the single durable orchestrator

**Run** (minimum):
- PostgreSQL (already needed by soldier’s stores)
- Redis (sessions, cache, optional streams/idem keys)
- Hatchet engine/API + its upstream deps (verify: Postgres + RabbitMQ in self-host)
- Redis Streams (optional but recommended) for ChannelGateway↔MessageRouter bus

**Use Hatchet for**:
- Turn processing (ACF LogicalTurn workflows)
- Webhook delivery workflows
- Tool “Path A” multi-step orchestrations (durable, timed, compensations)
- Control-plane publish pipeline (replace Restate publish workflow pattern)

**Use Redis (not Celery) for**:
- Idempotency keys (`SETNX` + TTL)
- Bundle pointers + cache invalidation pubsub
- Streams for inbound/outbound message buffering (if you keep the kernel_agent contract)

**Why this fits your stated preference**:
- You consider soldier’s implementations “better thought-out”; soldier is Hatchet-first already.
- Hatchet provides per-key concurrency and documented “sticky” strategies when you want affinity.

## Option 2: Restate as the single durable orchestrator

**Run**:
- Restate service (plus its storage requirements)
- Redis (bundles/pointers/caching; potentially Streams bus)
- A DB for SoT/outbox (Supabase/Postgres)

**Use Restate for**:
- Publish workflow durability (already)
- Potentially: turn processing as an actor/service per session key

**Cost**:
- Requires migrating soldier’s ACF workflow model away from Hatchet semantics (`wait_for_event`, existing worker setup, toolbox integration points).

## Option 3: Celery-centric (only if you accept weaker workflow semantics)

**Run**:
- Redis or RabbitMQ broker
- Celery workers + beat
- Redis/DB for idempotency/outbox and tool state

**When it can work**:
- Only if tools are mostly idempotent, short-lived, and you don’t need durable “sleep until webhook” or strong workflow-state recovery.

**Why it’s risky**:
- You’ll reinvent orchestration features in application code (state machines, retries, compensations, progress tracking).

## Practical “minimum viable” recommendation

If you want the smallest set that still supports enterprise-grade correctness:

1. Pick **one durable orchestrator** (Hatchet or Restate) and use it for **both** control-plane and runtime-plane durable workflows.
2. Use **Redis** for:
   - hot configuration cache,
   - idempotency/dedupe keys,
   - (optionally) Streams for message bus.
3. Add **RabbitMQ** only if:
   - your chosen orchestrator requires it (Hatchet self-host), or
   - you keep Celery and need a stronger broker than Redis.
