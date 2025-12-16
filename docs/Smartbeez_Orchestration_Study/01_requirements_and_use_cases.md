# Requirements and Use-Cases (what the stack must actually do)

This is the “source of truth” for *why* we need orchestration/messaging at all, mapped to the three repos’ reality.

## A. Conversation turn processing (session-serialized)

**Need**:
- One “writer” per `{tenant, agent, session/interlocutor, channel}` at a time (avoid parallel brain runs).
- Ability to *queue* new messages while a turn is processing (or supersede/cancel).
- Durable recovery: if a pod dies mid-turn, a different pod continues without losing the turn.

**Repo evidence**:
- `soldier`: Hatchet-based LogicalTurn workflow + `wait_for_event("new_message")` accumulation.
- `soldier`: Redis mutex is used today; docs recommend replacing with Hatchet concurrency groups.

## B. ChannelGateway → MessageRouter → Cognitive layer (ingress/egress bus)

**Need**:
- Fast ACK (<50ms) at webhook edge; queue the rest.
- Backpressure: if cognitive layer is slow, the queue grows safely.
- At-least-once delivery with explicit ACK and re-delivery after crash.
- Per-tenant isolation and per-session ordering (or at minimum: stable ordering within a session key).

**Repo evidence**:
- `kernel_agent`: explicit Redis Streams contract for ChannelGateway↔MessageRouter.
- `soldier`: architecture docs describe Redis stream subjects `events.inbound.*`, `events.routed.*`, `events.outbound.*` (implementation varies).

## C. Tool execution (sync and async; side-effect policy)

**Need**:
- Same tool API surface to the brain, with policy-driven routing:
  - **Sync**: return result immediately.
  - **Async**: return receipt, then callback with final result later.
- Strong idempotency for side-effectful tools (payments, provisioning).
- Support multi-step orchestration (retries, timers, compensations) for “Path A”-class tools.

**Repo evidence**:
- `soldier`: Toolbox/ToolGateway with side-effect policy docs; built into runtime.
- `kernel_agent`: “Path A/B/C” model (Restate + Celery/RabbitMQ, or direct Celery, or MQ edges).

## D. Control-plane publishing (config compilation + distribution)

**Need**:
- Accept admin changes → compile/validate → publish bundles → atomic pointer swap → notify runtime.
- Durability and idempotency (exactly-once pointer swap matters).
- Observable progress and easy retries.

**Repo evidence**:
- `kernel_agent`: Restate workflow pattern around publish stages + Redis bundles/pointers.
- `soldier`: docs describe a similar multi-plane architecture; Hatchet is already present as a durable runtime.

## E. Webhook delivery + retries (platform events to tenant endpoints)

**Need**:
- Durable retries and scheduling with exponential backoff.
- No “homegrown queue” if an orchestration engine is already running.

**Repo evidence**:
- `soldier`: webhook delivery is explicitly designed to be Hatchet-based.

## Non-negotiable cross-cutting requirements

- Multi-tenant scoping: every key/queue subject includes `tenant_id`.
- No sticky sessions as a requirement; “stickiness” is an optimization knob only.
- Idempotency is mandatory for all side-effectful operations (no “exactly-once” fantasies without dedupe).
