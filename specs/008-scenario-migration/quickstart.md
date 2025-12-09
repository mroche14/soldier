# Quickstart: Scenario Migration System

**Feature**: 008-scenario-migration
**Date**: 2025-11-29

## Overview

This guide explains how to use the scenario migration system to safely update scenarios while customers have active sessions.

---

## Prerequisites

- Focal API running
- Tenant configured with at least one agent
- Active scenario with sessions (for testing)
- Operator access to approve migrations

---

## Workflow Summary

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. Create New   │ →  │ 2. Generate     │ →  │ 3. Review &     │ →  │ 4. Deploy       │
│    Scenario     │    │    Migration    │    │    Configure    │    │    (Mark        │
│    Version      │    │    Plan         │    │    Policies     │    │    Sessions)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
                                                                              │
                                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 5. JIT Migration: Customer returns → System applies migration → Customer continues  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Prepare New Scenario Version

Update your scenario as needed (add steps, change forks, etc.) but **don't deploy it directly**.

```python
# Example: Adding an age verification step before checkout
new_scenario = {
    "name": "Order Flow",
    "version": 2,  # Increment from current version
    "steps": [
        {"id": "welcome", "name": "Welcome", ...},
        {"id": "age_check", "name": "Age Verification", ...},  # NEW
        {"id": "checkout", "name": "Checkout", ...},
        ...
    ]
}
```

---

## Step 2: Generate Migration Plan

```bash
curl -X POST "http://localhost:8000/api/v1/scenarios/{scenario_id}/migration-plan" \
  -H "X-Tenant-ID: {tenant_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "new_scenario": {...},
    "created_by": "operator@example.com"
  }'
```

**Response:**
```json
{
  "id": "plan-uuid",
  "scenario_id": "scenario-uuid",
  "from_version": 1,
  "to_version": 2,
  "status": "pending",
  "transformation_map": {
    "anchors": [
      {
        "anchor_content_hash": "abc123def456",
        "anchor_name": "Checkout",
        "migration_scenario": "gap_fill",
        "upstream_changes": {
          "inserted_nodes": [
            {"node_name": "Age Verification", "collects_fields": ["age"]}
          ]
        }
      }
    ]
  },
  "summary": {
    "total_anchors": 3,
    "anchors_with_gap_fill": 1,
    "estimated_sessions_affected": 142,
    "warnings": [
      {
        "severity": "info",
        "anchor_name": "Checkout",
        "message": "Customers may be asked for 'age' if not in profile"
      }
    ]
  }
}
```

---

## Step 3: Review Migration Summary

```bash
curl "http://localhost:8000/api/v1/migration-plans/{plan_id}/summary" \
  -H "X-Tenant-ID: {tenant_id}"
```

**What to look for:**

| Field | Meaning |
|-------|---------|
| `anchors_with_clean_graft` | Sessions that migrate silently (no impact) |
| `anchors_with_gap_fill` | Sessions that may need to provide missing data |
| `anchors_with_re_route` | Sessions that may be redirected to different branch |
| `warnings` | Issues requiring attention (checkpoint conflicts, etc.) |

---

## Step 4: Configure Per-Anchor Policies (Optional)

Customize migration behavior per anchor:

```bash
curl -X PUT "http://localhost:8000/api/v1/migration-plans/{plan_id}/policies" \
  -H "X-Tenant-ID: {tenant_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "policies": {
      "abc123def456": {
        "anchor_content_hash": "abc123def456",
        "anchor_name": "Checkout",
        "scope_filter": {
          "include_channels": ["whatsapp"],
          "max_session_age_days": 30
        },
        "update_downstream": true
      }
    }
  }'
```

**Scope Filter Options:**

| Option | Description |
|--------|-------------|
| `include_channels` | Only migrate sessions on these channels |
| `exclude_channels` | Skip sessions on these channels |
| `max_session_age_days` | Skip sessions older than N days |
| `min_session_age_days` | Skip sessions newer than N days |

---

## Step 5: Approve Migration Plan

```bash
curl -X POST "http://localhost:8000/api/v1/migration-plans/{plan_id}/approve" \
  -H "X-Tenant-ID: {tenant_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "approved_by": "operator@example.com"
  }'
```

---

## Step 6: Deploy Migration

```bash
curl -X POST "http://localhost:8000/api/v1/migration-plans/{plan_id}/deploy" \
  -H "X-Tenant-ID: {tenant_id}"
```

**Response:**
```json
{
  "plan_id": "plan-uuid",
  "sessions_marked": 142,
  "sessions_by_anchor": {
    "abc123def456": 45,
    "def789ghi012": 97
  },
  "deployed_at": "2025-11-29T10:30:00Z"
}
```

**Important:** Sessions are now **marked** for migration but migrations are **not applied yet**. They will be applied when customers send their next message.

---

## Step 7: Monitor Deployment

```bash
curl "http://localhost:8000/api/v1/migration-plans/{plan_id}/deployment-status" \
  -H "X-Tenant-ID: {tenant_id}"
```

**Response:**
```json
{
  "plan_id": "plan-uuid",
  "status": "deployed",
  "sessions_marked": 142,
  "migrations_applied": 89,
  "migrations_pending": 53,
  "migrations_by_scenario": {
    "clean_graft": 67,
    "gap_fill": 18,
    "re_route": 4
  },
  "checkpoint_blocks": 2,
  "deployed_at": "2025-11-29T10:30:00Z",
  "last_migration_at": "2025-11-29T14:22:15Z"
}
```

---

## Migration Scenarios Explained

### Clean Graft (Silent)

**When:** Upstream path unchanged, only downstream changes

**Customer Experience:** Nothing - seamlessly continues with new downstream flow

**Example:**
```
V1: Welcome → Checkout → Confirm
V2: Welcome → Checkout → Payment → Confirm  (Payment added downstream)

Customer at "Checkout" → Silently teleported to V2 Checkout → Sees Payment next
```

---

### Gap Fill (May Require Data)

**When:** New upstream step collects data

**Customer Experience:** May be asked for missing data (or auto-filled from profile/history)

**Example:**
```
V1: Welcome → Checkout
V2: Welcome → Age Check → Checkout  (Age Check added upstream)

Customer at "Checkout" in V1:
1. System checks profile for "age" → Found? Continue silently
2. System extracts "age" from conversation → Found with confidence? Continue
3. Neither found → Ask customer: "Before we continue, what is your age?"
```

---

### Re-Route (May Redirect)

**When:** New upstream fork with conditions

**Customer Experience:** May be redirected to different branch (or blocked by checkpoint)

**Example:**
```
V1: Welcome → Checkout → Confirm
V2: Welcome → Age Check → [age < 18?] → Rejection
                        → [age >= 18?] → Checkout → Confirm

Customer at "Checkout" in V1, age=17:
- System evaluates fork: age < 18 is TRUE
- Check for checkpoints: Has customer passed "Payment Processed"?
  - Yes: Block teleport, log warning, continue on V1 path
  - No: Teleport to "Rejection" step
```

---

## Checkpoint Blocking

Checkpoints represent irreversible actions (payment processed, order shipped, etc.).

**Rule:** If a customer has passed a checkpoint, they cannot be teleported to a step that would "undo" the checkpoint.

**Example:**
```
Customer completed payment at "Payment" checkpoint
New fork would redirect underage customers to "Rejection"
But we can't undo the payment
→ Teleportation BLOCKED
→ Warning logged for operator
→ Customer continues normally
```

---

## Configuration

Configure migration behavior in `config/default.toml`:

```toml
[scenario_migration]
enabled = true

[scenario_migration.deployment]
auto_mark_sessions = true
require_approval = true

[scenario_migration.gap_fill]
extraction_enabled = true
extraction_confidence_threshold = 0.85
confirmation_threshold = 0.95
max_conversation_turns = 20

[scenario_migration.re_routing]
enabled = true
notify_user = true
notification_template = "I have new instructions. Let me redirect our conversation."

[scenario_migration.checkpoints]
block_teleport_past_checkpoint = true

[scenario_migration.retention]
version_retention_days = 7
plan_retention_days = 30
```

---

## Troubleshooting

### Issue: Sessions not being marked

**Check:**
1. Plan status is `approved`
2. Scope filters match target sessions
3. Sessions are at anchor steps (content hash matches)

### Issue: Gap fill not extracting data

**Check:**
1. `extraction_enabled = true` in config
2. Conversation history available (within `max_conversation_turns`)
3. Field definition has extraction hints

### Issue: Customers being asked for data they provided

**Check:**
1. Data is in profile (not just session variables)
2. Extraction confidence meets threshold
3. Field name matches exactly

### Issue: Checkpoint blocking unexpectedly

**Check:**
1. Step is correctly marked as `is_checkpoint = true`
2. Customer actually visited the checkpoint step
3. Teleport target is upstream of checkpoint

---

## Best Practices

1. **Start with small changes** - Test migration with minor scenario updates first

2. **Use scope filters** - Limit migration to specific channels or session ages initially

3. **Review warnings carefully** - Checkpoint conflicts and data collection requirements need attention

4. **Monitor deployment status** - Track `migrations_applied` vs `migrations_pending`

5. **Keep version retention reasonable** - 7 days is usually sufficient; longer creates storage overhead

6. **Log re-routes and gap fills** - Useful for debugging customer issues

7. **Test with Clean Graft first** - Downstream-only changes are lowest risk
