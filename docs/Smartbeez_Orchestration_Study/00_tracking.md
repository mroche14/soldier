# Tracking (SmartBeez Orchestration Study)

This file is a lightweight “study checklist” so you can expand/validate items systematically.

## 0) Scope confirmation

- [ ] Confirm which orchestration layer should be canonical (Hatchet vs Restate vs Celery-only).
- [ ] Confirm whether the ChannelGateway→MessageRouter transport is Redis Streams, RabbitMQ, or something else.
- [ ] Confirm whether ToolHub/ToolGateway async execution uses the *same* orchestration layer as turn processing.

## 1) Repo-grounded facts (verify in code/docs)

- [ ] `soldier`: ACF LogicalTurn processing is Hatchet workflow (`ruche/runtime/acf/workflow.py`).
- [ ] `soldier`: ACF mutex is currently Redis-based; concurrency-group replacement is planned (`docs/architecture/ACF_SCALABILITY_ANALYSIS.md`).
- [ ] `soldier`: Webhook delivery is designed to be Hatchet-based (`docs/architecture/webhook-system.md`).
- [ ] `sb_agent_hub`: Celery broker/backend is Redis (`/home/marvin/Projects/sb_agent_hub/3-backend/app/core/celery_app.py`).
- [ ] `kernel_agent`: Control-plane publish pipeline is Restate workflow pattern (`/home/marvin/Projects/kernel_agent/apps/control-api/src/control_api/publisher/publish_workflow.py`).
- [ ] `kernel_agent`: ChannelGateway↔MessageRouter contract is Redis Streams (`/home/marvin/Projects/kernel_agent/docs/contracts/CHANNEL_GATEWAY_MESSAGE_ROUTER.md`).

## 2) “Minimum viable set” decisions

- [ ] Decide the single orchestration engine for *durable workflows*.
- [ ] Decide the single message-bus transport for inbound/outbound events.
- [ ] Decide where idempotency/dedup lives (Redis keys, DB outbox, or orchestrator-native).
- [ ] Decide “stickiness” needs (per-session sequential processing vs worker affinity).

## 3) Implementation mapping (turn into work items)

- [ ] If Hatchet is canonical: list what to remove/avoid (Restate, Celery) and what to implement in Hatchet.
- [ ] If Restate is canonical: list migration steps from Hatchet ACF → Restate actor/workflow.
- [ ] If Celery is canonical: list what reliability gaps are acceptable and what patterns (outbox, idempotency, retries) must be added.
