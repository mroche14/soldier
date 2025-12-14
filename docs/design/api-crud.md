# API Design: CRUD Operations

Focal exposes full CRUD operations for all configuration entities. This enables non-developers to modify agent behavior via UI without code changes or restarts.

> **Deployment Mode Note:** These CRUD endpoints are available in **standalone mode** where Focal is the source of truth for configuration. In **External Platform integration mode**, configuration is read-only (loaded from Redis bundles published by the Control Plane). See [deployment modes](../architecture/overview.md#deployment-modes) for details.

## Design Principles

- **RESTful**: Standard HTTP verbs, resource-based URLs
- **Tenant-scoped**: All operations require `tenant_id` (from JWT or header)
- **Versioned**: API versioned via URL prefix (`/v1/`)
- **Consistent**: Same patterns across all resources
- **Auditable**: All mutations logged with actor and timestamp

## Authentication

All endpoints require JWT authentication:

```
Authorization: Bearer <jwt_token>

JWT Claims:
{
  "sub": "user_id",
  "tenant_id": "uuid",
  "roles": ["agent_admin", "viewer"],
  "exp": 1234567890
}
```

## Base URL

```
https://ruche.example.com/v1
```

## Common Patterns

### List with Pagination

```
GET /v1/{resource}?limit=20&offset=0&sort=created_at:desc

Response:
{
  "items": [...],
  "total": 100,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### Filtering

```
GET /v1/rules?scope=global&enabled=true&priority_gte=5
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid rule configuration",
    "details": [
      {"field": "condition_text", "message": "Required field"}
    ]
  }
}
```

---

## Agents

Agents are top-level containers for Scenarios, Rules, Templates, and Tools.

### List Agents

```
GET /v1/agents

Query Parameters:
  - limit: int (default 20, max 100)
  - offset: int (default 0)
  - enabled: bool
  - search: string (name search)

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "Customer Support Bot",
      "description": "Handles customer inquiries",
      "enabled": true,
      "current_version": 5,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T12:30:00Z"
    }
  ],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

### Get Agent

```
GET /v1/agents/{agent_id}

Response: 200 OK
{
  "id": "uuid",
  "name": "Customer Support Bot",
  "description": "Handles customer inquiries",
  "enabled": true,
  "current_version": 5,
  "settings": {
    "model": "openrouter/anthropic/claude-3-5-sonnet",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "stats": {
    "total_sessions": 1500,
    "total_turns": 25000,
    "avg_turns_per_session": 16.7
  },
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T12:30:00Z"
}
```

### Create Agent

```
POST /v1/agents

Request:
{
  "name": "Customer Support Bot",
  "description": "Handles customer inquiries",
  "settings": {
    "model": "openrouter/anthropic/claude-3-5-sonnet",
    "temperature": 0.7
  }
}

Response: 201 Created
{
  "id": "uuid",
  "name": "Customer Support Bot",
  ...
}
```

### Update Agent

```
PUT /v1/agents/{agent_id}

Request:
{
  "name": "Customer Support Bot v2",
  "description": "Updated description",
  "enabled": true,
  "settings": {...}
}

Response: 200 OK
```

### Delete Agent

```
DELETE /v1/agents/{agent_id}

Response: 204 No Content
```

---

## Scenarios

Scenarios define multi-step conversational flows.

### List Scenarios

```
GET /v1/agents/{agent_id}/scenarios

Query Parameters:
  - limit, offset
  - enabled: bool
  - search: string

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "Return Process",
      "description": "Guide customer through product return",
      "entry_step_id": "step-uuid",
      "enabled": true,
      "step_count": 5,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 3
}
```

### Get Scenario

```
GET /v1/agents/{agent_id}/scenarios/{scenario_id}

Response: 200 OK
{
  "id": "uuid",
  "name": "Return Process",
  "description": "Guide customer through product return",
  "entry_step_id": "step-1",
  "entry_condition_text": "Customer wants to return a product",
  "enabled": true,
  "steps": [
    {
      "id": "step-1",
      "name": "Identify Order",
      "description": "Ask customer for order ID",
      "is_entry": true,
      "is_terminal": false,
      "transitions": [
        {
          "to_step_id": "step-2",
          "condition_text": "Customer provides order ID",
          "priority": 0
        }
      ],
      "template_ids": ["tmpl-1"],
      "rule_ids": ["rule-1"],
      "tool_ids": []
    },
    {
      "id": "step-2",
      "name": "Verify Eligibility",
      "description": "Check if order is eligible for return",
      "is_entry": false,
      "is_terminal": false,
      "transitions": [
        {
          "to_step_id": "step-3",
          "condition_text": "Order is eligible",
          "priority": 0
        },
        {
          "to_step_id": "step-4",
          "condition_text": "Order is not eligible",
          "priority": 0
        }
      ],
      "template_ids": [],
      "rule_ids": [],
      "tool_ids": ["check_return_eligibility"]
    }
  ],
  "tags": ["returns", "support"],
  "created_at": "...",
  "updated_at": "..."
}
```

### Create Scenario

```
POST /v1/agents/{agent_id}/scenarios

Request:
{
  "name": "Return Process",
  "description": "Guide customer through product return",
  "entry_condition_text": "Customer wants to return a product",
  "steps": [
    {
      "name": "Identify Order",
      "description": "Ask customer for order ID",
      "is_entry": true,
      "transitions": []
    }
  ],
  "tags": ["returns"]
}

Response: 201 Created
{
  "id": "uuid",
  "entry_step_id": "auto-generated-step-id",
  ...
}
```

### Update Scenario

```
PUT /v1/agents/{agent_id}/scenarios/{scenario_id}

Request:
{
  "name": "Updated Return Process",
  "description": "...",
  "enabled": true,
  "steps": [...]
}

Response: 200 OK
```

### Delete Scenario

```
DELETE /v1/agents/{agent_id}/scenarios/{scenario_id}

Response: 204 No Content
```

### Add Step to Scenario

```
POST /v1/agents/{agent_id}/scenarios/{scenario_id}/steps

Request:
{
  "name": "New Step",
  "description": "...",
  "transitions": [
    {"to_step_id": "existing-step", "condition_text": "..."}
  ]
}

Response: 201 Created
```

### Update Step

```
PUT /v1/agents/{agent_id}/scenarios/{scenario_id}/steps/{step_id}

Request:
{
  "name": "Updated Step Name",
  "transitions": [...],
  "template_ids": [...],
  "rule_ids": [...],
  "tool_ids": [...]
}

Response: 200 OK
```

### Delete Step

```
DELETE /v1/agents/{agent_id}/scenarios/{scenario_id}/steps/{step_id}

Response: 204 No Content

Note: Cannot delete entry step. Must reassign entry first.
```

---

## Rules

Rules define behavioral policies.

### List Rules

```
GET /v1/agents/{agent_id}/rules

Query Parameters:
  - limit, offset
  - scope: global|scenario|step
  - scope_id: uuid (filter by specific scenario/step)
  - enabled: bool
  - priority_gte: int
  - priority_lte: int
  - search: string

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "Refund Policy Check",
      "condition_text": "Customer asks about refunds",
      "action_text": "Check order status before explaining refund policy",
      "scope": "global",
      "scope_id": null,
      "priority": 10,
      "enabled": true,
      "max_fires_per_session": 0,
      "cooldown_turns": 0,
      "attached_tool_ids": ["check_order_status"],
      "attached_template_ids": [],
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 25
}
```

### Get Rule

```
GET /v1/agents/{agent_id}/rules/{rule_id}

Response: 200 OK
{
  "id": "uuid",
  "name": "Refund Policy Check",
  "condition_text": "Customer asks about refunds",
  "action_text": "Check order status before explaining refund policy",
  "scope": "global",
  "scope_id": null,
  "priority": 10,
  "enabled": true,
  "max_fires_per_session": 0,
  "cooldown_turns": 0,
  "attached_tool_ids": ["check_order_status"],
  "attached_template_ids": ["refund_template"],
  "is_hard_constraint": false,
  "created_at": "...",
  "updated_at": "..."
}
```

### Create Rule

```
POST /v1/agents/{agent_id}/rules

Request:
{
  "name": "Refund Policy Check",
  "condition_text": "Customer asks about refunds",
  "action_text": "Check order status before explaining refund policy",
  "scope": "global",
  "priority": 10,
  "enabled": true,
  "attached_tool_ids": ["check_order_status"]
}

Response: 201 Created
{
  "id": "uuid",
  ...
}

Note: Embedding is computed automatically on creation.
```

### Update Rule

```
PUT /v1/agents/{agent_id}/rules/{rule_id}

Request:
{
  "name": "Updated Rule Name",
  "condition_text": "Updated condition",
  "action_text": "Updated action",
  "priority": 15,
  "enabled": true
}

Response: 200 OK

Note: If condition_text or action_text changes, embedding is recomputed.
```

### Delete Rule

```
DELETE /v1/agents/{agent_id}/rules/{rule_id}

Response: 204 No Content
```

### Bulk Operations

```
POST /v1/agents/{agent_id}/rules/bulk

Request:
{
  "operations": [
    {"action": "create", "data": {...}},
    {"action": "update", "id": "uuid", "data": {...}},
    {"action": "delete", "id": "uuid"}
  ]
}

Response: 200 OK
{
  "results": [
    {"action": "create", "success": true, "id": "new-uuid"},
    {"action": "update", "success": true, "id": "uuid"},
    {"action": "delete", "success": true, "id": "uuid"}
  ]
}
```

---

## Templates

Templates define pre-written responses.

### List Templates

```
GET /v1/agents/{agent_id}/templates

Query Parameters:
  - limit, offset
  - mode: suggest|exclusive|fallback
  - scope: global|scenario|step
  - scope_id: uuid
  - search: string

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "Refund Confirmation",
      "text": "Your refund for order {order_id} has been processed...",
      "mode": "exclusive",
      "scope": "step",
      "scope_id": "refund-complete-step",
      "conditions": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 15
}
```

### Get Template

```
GET /v1/agents/{agent_id}/templates/{template_id}

Response: 200 OK
{
  "id": "uuid",
  "name": "Refund Confirmation",
  "text": "Your refund for order {order_id} has been processed. The amount of {refund_amount} will be credited to your {payment_method} within 3-5 business days.",
  "mode": "exclusive",
  "scope": "step",
  "scope_id": "refund-complete-step",
  "conditions": "refund_status == 'approved'",
  "variables_used": ["order_id", "refund_amount", "payment_method"],
  "created_at": "...",
  "updated_at": "..."
}
```

### Create Template

```
POST /v1/agents/{agent_id}/templates

Request:
{
  "name": "Refund Confirmation",
  "text": "Your refund for order {order_id} has been processed...",
  "mode": "exclusive",
  "scope": "step",
  "scope_id": "refund-complete-step",
  "conditions": "refund_status == 'approved'"
}

Response: 201 Created
```

### Update Template

```
PUT /v1/agents/{agent_id}/templates/{template_id}

Request:
{
  "name": "Updated Template",
  "text": "Updated text with {variables}",
  "mode": "suggest"
}

Response: 200 OK
```

### Delete Template

```
DELETE /v1/agents/{agent_id}/templates/{template_id}

Response: 204 No Content
```

### Preview Template

Render a template with sample data:

```
POST /v1/agents/{agent_id}/templates/{template_id}/preview

Request:
{
  "variables": {
    "order_id": "12345",
    "refund_amount": "$99.00",
    "payment_method": "credit card"
  }
}

Response: 200 OK
{
  "rendered": "Your refund for order 12345 has been processed. The amount of $99.00 will be credited to your credit card within 3-5 business days."
}
```

---

## Tools

Tools define side-effect actions. Tool definitions are read-only in Focal (managed by ToolHub), but activation per agent is configurable.

### List Available Tools

```
GET /v1/tools

Query Parameters:
  - limit, offset
  - provider: composio|custom|openai
  - category: string
  - search: string

Response: 200 OK
{
  "items": [
    {
      "id": "check_order_status",
      "name": "Check Order Status",
      "description": "Retrieve current status of a customer order",
      "provider": "custom",
      "input_schema": {
        "type": "object",
        "properties": {
          "order_id": {"type": "string"}
        },
        "required": ["order_id"]
      },
      "output_schema": {...},
      "policy": {
        "path": "B",
        "completion": "sync",
        "timeout_s": 5
      }
    }
  ]
}
```

### List Agent Tool Activations

```
GET /v1/agents/{agent_id}/tools

Response: 200 OK
{
  "items": [
    {
      "tool_id": "check_order_status",
      "tool_name": "Check Order Status",
      "status": "enabled",
      "policy_override": null,
      "enabled_at": "..."
    },
    {
      "tool_id": "process_payment",
      "tool_name": "Process Payment",
      "status": "disabled",
      "disabled_at": "..."
    }
  ]
}
```

### Enable Tool for Agent

```
POST /v1/agents/{agent_id}/tools/{tool_id}/enable

Request:
{
  "policy_override": {
    "timeout_s": 10
  }
}

Response: 200 OK
{
  "tool_id": "check_order_status",
  "status": "enabled",
  "enabled_at": "..."
}
```

### Disable Tool for Agent

```
POST /v1/agents/{agent_id}/tools/{tool_id}/disable

Response: 200 OK
{
  "tool_id": "check_order_status",
  "status": "disabled",
  "disabled_at": "..."
}
```

---

## Variables

Variables define dynamic context values resolved at runtime.

### List Variables

```
GET /v1/agents/{agent_id}/variables

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "name": "customer_profile",
      "description": "Current customer profile data",
      "resolver_tool_id": "get_customer_profile",
      "update_policy": "on_session_start",
      "cache_ttl_seconds": 300,
      "created_at": "..."
    }
  ]
}
```

### Create Variable

```
POST /v1/agents/{agent_id}/variables

Request:
{
  "name": "customer_profile",
  "description": "Current customer profile data",
  "resolver_tool_id": "get_customer_profile",
  "update_policy": "on_session_start",
  "cache_ttl_seconds": 300
}

Response: 201 Created
```

### Update Variable

```
PUT /v1/agents/{agent_id}/variables/{variable_id}

Request:
{
  "description": "Updated description",
  "update_policy": "on_demand",
  "cache_ttl_seconds": 600
}

Response: 200 OK
```

### Delete Variable

```
DELETE /v1/agents/{agent_id}/variables/{variable_id}

Response: 204 No Content
```

---

## Publishing

After making changes, publish to make them live.

### Get Publish Status

```
GET /v1/agents/{agent_id}/publish

Response: 200 OK
{
  "current_version": 5,
  "draft_version": 6,
  "has_unpublished_changes": true,
  "last_published_at": "2025-01-15T12:00:00Z",
  "last_published_by": "user_id",
  "changes_since_publish": {
    "scenarios_added": 1,
    "scenarios_modified": 2,
    "rules_added": 5,
    "rules_modified": 3,
    "templates_added": 2
  }
}
```

### Publish Changes

```
POST /v1/agents/{agent_id}/publish

Request:
{
  "description": "Added return flow and updated refund rules"
}

Response: 202 Accepted
{
  "publish_id": "uuid",
  "version": 6,
  "status": "pending",
  "started_at": "..."
}
```

### Get Publish Job Status

```
GET /v1/agents/{agent_id}/publish/{publish_id}

Response: 200 OK
{
  "publish_id": "uuid",
  "version": 6,
  "status": "completed",
  "stages": [
    {"name": "validate", "status": "completed", "duration_ms": 150},
    {"name": "compile", "status": "completed", "duration_ms": 300},
    {"name": "write_bundles", "status": "completed", "duration_ms": 100},
    {"name": "swap_pointer", "status": "completed", "duration_ms": 10},
    {"name": "invalidate_cache", "status": "completed", "duration_ms": 50}
  ],
  "started_at": "...",
  "completed_at": "..."
}
```

### Rollback to Previous Version

```
POST /v1/agents/{agent_id}/rollback

Request:
{
  "target_version": 4,
  "reason": "Bug in version 5"
}

Response: 202 Accepted
{
  "rollback_id": "uuid",
  "from_version": 5,
  "to_version": 4,
  "status": "pending"
}
```

---

## Sessions

Session management APIs.

### List Sessions

```
GET /v1/agents/{agent_id}/sessions

Query Parameters:
  - limit, offset
  - channel: whatsapp|slack|webchat
  - active: bool (has activity in last 24h)
  - scenario_id: uuid (in specific scenario)

Response: 200 OK
{
      "items": [
        {
          "session_id": "uuid",
          "channel": "whatsapp",
          "channel_user_id": "+1234567890",
          "active_scenario_id": "uuid",
          "active_step_id": "uuid",
          "turn_count": 12,
          "created_at": "...",
      "last_activity_at": "..."
    }
  ]
}
```

### Get Session

```
GET /v1/sessions/{session_id}

Response: 200 OK
{
  "session_id": "uuid",
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "channel": "whatsapp",
  "channel_user_id": "+1234567890",
  "active_scenario_id": "uuid",
  "active_step_id": "uuid",
  "turn_count": 12,
  "variables": {
    "customer_name": "John Doe",
    "order_id": "12345"
  },
  "rule_fires": {
    "rule-1": 2,
    "rule-3": 1
  },
  "config_version": 5,
  "created_at": "...",
  "last_activity_at": "..."
}
```

### Update Session

Force scenario step or variables:

```
PATCH /v1/sessions/{session_id}

Request:
{
  "active_scenario_id": "new-scenario",
  "active_step_id": "new-step",
  "variables": {
    "custom_var": "value"
  }
}

Response: 200 OK
```

### Delete Session

```
DELETE /v1/sessions/{session_id}

Response: 204 No Content
```

### Get Session History

```
GET /v1/sessions/{session_id}/turns

Query Parameters:
  - limit, offset
  - sort: asc|desc (by turn_number)

Response: 200 OK
  {
    "items": [
      {
      "logical_turn_id": "uuid",
      "turn_number": 1,
      "user_message": "I want to return my order",
      "agent_response": "I'd be happy to help...",
      "matched_rules": ["rule-1", "rule-2"],
      "tools_called": ["check_order_status"],
      "scenario_before": null,
      "scenario_after": {"id": "return-flow", "step": "identify-order"},
      "latency_ms": 450,
      "tokens_used": 150,
      "timestamp": "..."
    }
  ]
}
```

---

## Webhooks

Configure webhooks for event notifications.

### List Webhooks

```
GET /v1/agents/{agent_id}/webhooks

Response: 200 OK
{
  "items": [
    {
      "id": "uuid",
      "url": "https://example.com/webhook",
      "events": ["session.created", "scenario.completed", "rule.matched"],
      "enabled": true,
      "secret": "whsec_...",
      "created_at": "..."
    }
  ]
}
```

### Create Webhook

```
POST /v1/agents/{agent_id}/webhooks

Request:
{
  "url": "https://example.com/webhook",
  "events": ["session.created", "scenario.completed"],
  "enabled": true
}

Response: 201 Created
{
  "id": "uuid",
  "secret": "whsec_generated_secret"
}
```

### Event Types

| Event | Payload |
|-------|---------|
| `session.created` | `{session_id, agent_id, channel, channel_user_id}` |
| `session.ended` | `{session_id, turn_count, duration_minutes}` |
| `scenario.entered` | `{session_id, scenario_id, scenario_name}` |
| `scenario.completed` | `{session_id, scenario_id, outcome}` |
| `rule.matched` | `{session_id, rule_id, rule_name, logical_turn_id}` |
| `tool.called` | `{session_id, tool_id, tool_name, success}` |
| `enforcement.triggered` | `{session_id, rule_id, action: regenerate|fallback}` |

---

## Rate Limits

Per-tenant rate limits:

| Tier | Read/min | Write/min | Publish/hour |
|------|----------|-----------|--------------|
| Free | 1000 | 100 | 10 |
| Pro | 10000 | 1000 | 100 |
| Enterprise | Custom | Custom | Custom |

Response headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1705312800
```
