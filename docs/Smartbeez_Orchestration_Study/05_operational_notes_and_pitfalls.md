# Operational Notes and Pitfalls (pragmatic guidance)

This section captures the “gotchas” that tend to decide whether a stack works in production.

## Hatchet (durable workflows)

- **Dependencies can be non-obvious**: upstream self-host examples include RabbitMQ + Postgres; treat upstream docs as the authoritative dependency list.
- **Idempotency is still required**: durable execution + retries means your steps will run again; every side-effect step must be safe to retry.
- **Per-session serialization**: prefer orchestrator-native per-key concurrency over ad-hoc Redis locks; it reduces deadlocks and cleanup paths.
- **Stickiness is an optimization**: only use worker-affinity if you have measured wins (warm LLM clients, hot caches) and it does not become a correctness dependency.

## Restate (durable execution + exactly-once-style semantics)

- **Exactly-once is scoped**: Restate can provide strong semantics for *invocations and state updates*, but external side effects still require idempotency keys and compensations.
- **Great fit for control-plane pipelines**: publish/compile/swap-pointer workflows map naturally (correlation ids, retries, progress).
- **Migration cost**: replacing an existing Hatchet-based ACF workflow model is a major rewrite; don’t underestimate “event wait + supersede” semantics.

## Celery (task queue)

- **Celery is not a workflow engine**: multi-step correctness requires you to add state management (DB/outbox), correlation ids, and compensations yourself.
- **Redis broker caveats** (from Celery docs): Redis works well for rapid transport of small messages; large messages can congest the system; broker memory limits become your throughput ceiling.
- **RabbitMQ broker is common in production**: RabbitMQ is a mature broker for Celery, but you still need idempotency and careful retry policies.

## Redis Streams (message bus)

- **At-least-once means duplicates**: consumers must be idempotent; producers should include deterministic correlation ids.
- **Consumer groups require housekeeping**: pending entries (PEL) will accumulate without XACK; you need a reclaim strategy (claim old pending messages) and monitoring (XPENDING, lag).
- **Trim strategy matters**: MAXLEN/trim policy must align with replay/debug needs and storage budgets.
- **Ordering needs design**: if you need strict per-session order while scaling consumers, you must partition by session (stream-per-session is expensive; hashing into N streams is common).

## RabbitMQ (message broker)

- **Operational maturity**: strong tooling and predictable semantics, but adds another cluster to operate.
- **Routing flexibility**: exchanges/routing keys can model tenant/channel partitioning cleanly.
- **Backpressure is visible**: queue depth is a first-class metric; use it to autoscale consumers.

## The “minimum viable reliability” checklist

Regardless of which orchestrator/bus you pick, enforce these:

1. **Correlation ids everywhere** (turn/tool/publish).
2. **Idempotency keys for side effects** (Redis SETNX or provider-native keys).
3. **Explicit ACK on durable buses** (Streams/RabbitMQ).
4. **Retry policies are bounded** (max retries, backoff, circuit-break when providers degrade).
5. **Tenant isolation is enforced at transport layer** (subjects/keys include `tenant_id`).
