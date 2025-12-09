# Quickstart: API CRUD Operations

**Date**: 2025-11-29
**Feature**: 001-api-crud

## Overview

This guide shows how to use the Focal CRUD API to manage agent configurations.

## Prerequisites

1. Focal API running (`uv run uvicorn focal.api.app:create_app --factory`)
2. Valid JWT token with `tenant_id` claim

## Authentication

All requests require a JWT bearer token:

```bash
export TOKEN="eyJhbG..."
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/agents
```

## Quick Examples

### 1. Create an Agent

```bash
curl -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Support Bot",
    "description": "Handles customer inquiries",
    "settings": {
      "llm_provider": "anthropic",
      "llm_model": "claude-3-5-sonnet",
      "temperature": 0.7
    }
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Customer Support Bot",
  "enabled": true,
  "current_version": 1,
  ...
}
```

### 2. Add Rules to Agent

```bash
# Create a global rule
curl -X POST http://localhost:8000/v1/agents/{agent_id}/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Greeting Rule",
    "condition_text": "User says hello or greets the agent",
    "action_text": "Respond with a friendly greeting and offer assistance",
    "scope": "global",
    "priority": 10
  }'
```

### 3. Bulk Create Rules

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/rules/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {
        "action": "create",
        "data": {
          "name": "Refund Policy",
          "condition_text": "Customer asks about refunds",
          "action_text": "Explain the 30-day refund policy"
        }
      },
      {
        "action": "create",
        "data": {
          "name": "Shipping Info",
          "condition_text": "Customer asks about shipping",
          "action_text": "Provide shipping timeframes and tracking info"
        }
      }
    ]
  }'
```

Response:
```json
{
  "results": [
    {"action": "create", "success": true, "id": "..."},
    {"action": "create", "success": true, "id": "..."}
  ]
}
```

### 4. Create a Template

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/templates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Order Confirmation",
    "text": "Your order {order_id} has been confirmed. Expected delivery: {delivery_date}.",
    "mode": "suggest",
    "scope": "global"
  }'
```

### 5. Preview Template

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/templates/{template_id}/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "order_id": "ORD-12345",
      "delivery_date": "January 15, 2025"
    }
  }'
```

Response:
```json
{
  "rendered": "Your order ORD-12345 has been confirmed. Expected delivery: January 15, 2025."
}
```

### 6. Create a Scenario

```bash
curl -X POST http://localhost:8000/v1/agents/{agent_id}/scenarios \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
    "tags": ["returns", "support"]
  }'
```

### 7. Publish Changes

```bash
# Check publish status
curl http://localhost:8000/v1/agents/{agent_id}/publish \
  -H "Authorization: Bearer $TOKEN"

# Publish changes
curl -X POST http://localhost:8000/v1/agents/{agent_id}/publish \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Added greeting rule and return flow"
  }'
```

Response:
```json
{
  "publish_id": "...",
  "version": 2,
  "status": "pending",
  "started_at": "..."
}
```

### 8. List with Pagination and Filters

```bash
# List rules with filters
curl "http://localhost:8000/v1/agents/{agent_id}/rules?scope=global&enabled=true&limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "items": [...],
  "total": 25,
  "limit": 10,
  "offset": 0,
  "has_more": true
}
```

## Common Patterns

### Filtering by Scope

```bash
# Global rules only
GET /v1/agents/{id}/rules?scope=global

# Rules for a specific scenario
GET /v1/agents/{id}/rules?scope=scenario&scope_id={scenario_id}

# Rules for a specific step
GET /v1/agents/{id}/rules?scope=step&scope_id={step_id}
```

### Priority Range Filtering

```bash
# High priority rules (50-100)
GET /v1/agents/{id}/rules?priority_gte=50

# Low priority rules (-100 to 0)
GET /v1/agents/{id}/rules?priority_lte=0
```

### Template Modes

```bash
# Suggested templates only
GET /v1/agents/{id}/templates?mode=suggest

# Fallback templates
GET /v1/agents/{id}/templates?mode=fallback
```

## Error Handling

All errors return consistent format:

```json
{
  "error": {
    "code": "RULE_NOT_FOUND",
    "message": "Rule with ID xyz does not exist"
  }
}
```

Common error codes:
- `AGENT_NOT_FOUND` - Agent doesn't exist
- `RULE_NOT_FOUND` - Rule doesn't exist
- `INVALID_REQUEST` - Validation failed
- `ENTRY_STEP_DELETION` - Cannot delete entry step
- `RATE_LIMIT_EXCEEDED` - Too many requests

## Next Steps

1. Create your first agent with the POST /agents endpoint
2. Add rules to define agent behavior
3. Create scenarios for multi-step flows
4. Add templates for consistent responses
5. Publish to make changes live
