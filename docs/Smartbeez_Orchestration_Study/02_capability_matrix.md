# Capability Matrix (Hatchet vs Restate vs Celery; Redis Streams vs RabbitMQ)

This matrix is intentionally opinionated toward the *requirements* in `01_requirements_and_use_cases.md`, not generic “feature lists”.

## 1) Orchestrators / Execution Runtimes

| Capability | Hatchet (soldier) | Restate (kernel_agent) | Celery (sb_agent_hub) |
|---|---|---|---|
| Durable execution (resume after crash) | Yes (workflow history + retries; worker can pick up) | Yes (Durable Execution; recover partial progress) | Partially (task retry; not workflow-state durable by default) |
| Multi-step workflows | Yes (workflows / DAG-ish patterns) | Yes (workflows/services; timers/promises) | Requires manual chaining + state management |
| Timers / scheduled runs | Yes | Yes | Yes (beat), but not “durable sleep” the same way |
| Concurrency control (per key) | Yes (concurrency key + strategies like GROUP_ROUND_ROBIN; also “sticky” support) | Yes (actor-like services + isolated state per entity) | Requires routing by key + single consumer per queue partition (app-level) |
| “Wait for event” / event-driven pause | Yes (run-on-event + wait patterns) | Yes (promises + durable timers/events) | Not native; emulate with polling/callback tasks |
| Operational footprint | Needs Hatchet service + its deps | Needs Restate service | Needs broker + workers (+ result backend if used) |
| Existing adoption in these repos | Strong (ACF runtime, webhooks) | Strong (control-plane publish + message bus contracts) | Medium (background tasks + periodic tasks) |

## 2) Message Transports (for ChannelGateway↔MessageRouter and async tool results)

| Capability | Redis Streams | RabbitMQ | Redis Lists/PubSub (Celery-on-Redis style) |
|---|---|---|---|
| Delivery semantics | At-least-once (consumer groups + ACK) | At-least-once (ACK) | Broker-dependent; Redis broker is fast but can be fragile for large payloads |
| Ordering | Per-stream append order; consumer groups can parallelize (ordering per consumer/key must be designed) | Queue ordering; can partition by routing keys/exchanges | Queue ordering per list; PubSub is best-effort |
| Backpressure | Stream length + consumer lag; must monitor pending/lag | Queue depth; mature tooling | Redis memory becomes the hard limit |
| Replay/debug | Yes (stream history until trimmed) | Yes (if durable queues; but replay is more manual) | Limited |
| Operational complexity | Low if Redis already required | Medium (extra broker to run/monitor) | Low, but higher risk at scale |
| Existing adoption in these repos | Strong (kernel_agent contracts) | Mentioned (Hatchet self-host, Celery best practice) | Used in sb_agent_hub |

## 3) Clarifying the “stickiness” question

Stickiness shows up in two different ways and they should not be conflated:

1. **Session serialization** (must-have): only one turn executes per session key at a time.
2. **Worker affinity** (optional): prefer continuing a workflow on the same worker to reuse warm caches or reduce cross-worker coordination.

Hatchet explicitly documents “sticky workflows” as a scheduling strategy, but the architecture goal across repos is **no sticky sessions required**; worker affinity is an optimization knob, not a correctness requirement.

## 4) Observed mismatches to resolve

- `soldier` docs currently state “Hatchet already uses RabbitMQ internally”; upstream Hatchet’s self-host compose includes RabbitMQ + Postgres, but this repo’s local `docker-compose.yml` currently runs Hatchet without RabbitMQ. The integration study should treat Hatchet’s *actual* required dependencies as **upstream-source-of-truth**, not local-compose assumptions.
