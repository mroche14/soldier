# API Layer

Focal is a **message processing engine**. It receives messages from upstream services (channel-gateway, message-router) with tenant and channel context already resolved.

## Architecture Position

```
Channel Gateway (WhatsApp, Slack, Web, etc.)
       │
       │  Resolves: tenant_id, channel, user_channel_id
       ▼
Message Router (coalescing, interrupts)
       │
       │  Adds: agent_id, routing metadata
       ▼
    FOCAL (this service)
       │
       │  Processes message, returns response
       ▼
Channel Gateway → User
```

> **Note:** Authentication, rate limiting, and tenant resolution happen upstream. Focal trusts the `tenant_id` and `agent_id` in incoming requests.

## Interface Comparison

| Interface | Best For | Streaming | Type Safety |
|-----------|----------|-----------|-------------|
| **REST** | Web apps, webhooks, broad compatibility | SSE | OpenAPI schema |
| **gRPC** | Service-to-service, mobile SDKs, performance | Native bi-directional | Protobuf contracts |
| **MCP** | LLM-native tools (Claude, Copilot, GPT) | N/A | JSON Schema |

## REST API (FastAPI)

### Core Endpoints

```
# Chat (message processing)
POST /v1/chat                 # Process a message, return response
POST /v1/chat/stream          # SSE streaming response

# Sessions
GET    /v1/sessions/{id}      # Get session state
DELETE /v1/sessions/{id}      # End session

# Memory
POST /v1/memory/episodes      # Ingest episode
GET  /v1/memory/search        # Search memory
GET  /v1/memory/entities/{id} # Get entity

# Configuration (see api-crud.md for full CRUD)
GET  /v1/agents/{agent_id}/rules
GET  /v1/agents/{agent_id}/scenarios
GET  /v1/agents/{agent_id}/templates

# Health
GET  /health
GET  /metrics
```

### Chat Request

```json
POST /v1/chat
Idempotency-Key: unique-request-id-123  // Optional, for safe retries

{
  "tenant_id": "uuid",                   // Required: resolved upstream
  "agent_id": "uuid",                    // Required: which agent to use
  "channel": "whatsapp",                 // Required: whatsapp, slack, webchat, etc.
  "user_channel_id": "+1234567890",      // Required: user identifier on channel
  "session_id": "sess_abc123",           // Optional: existing session (auto-created if omitted)
  "message": "I want to return my order",
  "metadata": {                          // Optional: additional context
    "locale": "en-US"
  }
}
```

### Chat Response

```json
{
  "response": "I'd be happy to help with your return. Could you provide your order number?",
  "session_id": "sess_abc123",
  "turn_id": "turn_789",
  "scenario": {
    "id": "returns",
    "step": "identify_order"
  },
  "matched_rules": ["rule_refund_check"],
  "tools_called": [],
  "tokens_used": 150,
  "latency_ms": 847
}
```

### Streaming (SSE)

```
POST /v1/chat/stream

Response:
data: {"type": "token", "content": "I'd"}
data: {"type": "token", "content": " be"}
data: {"type": "token", "content": " happy"}
...
data: {"type": "done", "turn_id": "turn_789", "matched_rules": [...]}
```

### Idempotency

For safe retries, clients can provide an idempotency key:

```
POST /v1/chat
Idempotency-Key: unique-request-id-123

{
  "tenant_id": "...",
  "agent_id": "...",
  "session_id": "sess_abc123",
  "message": "I want to return my order"
}
```

**Behavior:**
- If the same `Idempotency-Key` is sent within the cache window, the original response is returned
- No duplicate processing occurs
- Cache window: 5 minutes for chat, 1 minute for mutations

**Idempotent Endpoints:**

| Endpoint | Cache Duration | Notes |
|----------|----------------|-------|
| `POST /v1/chat` | 5 minutes | Prevents duplicate messages |
| `POST /v1/rules` | 1 minute | Prevents duplicate rules |
| `POST /v1/scenarios` | 1 minute | Prevents duplicate scenarios |
| `POST /v1/memory/episodes` | 1 minute | Prevents duplicate memories |

**Cache Key Pattern:**
```
idem:{tenant_id}:{idempotency_key}
```

If no `Idempotency-Key` is provided, the request is processed without idempotency protection.

## gRPC API

### Service Definition

```protobuf
syntax = "proto3";

package focal.v1;

service ChatService {
  // Unary: single message in, single response out
  rpc SendMessage(ChatRequest) returns (ChatResponse);

  // Server streaming: single message in, streamed response
  rpc SendMessageStream(ChatRequest) returns (stream ChatChunk);

  // Bi-directional: for multi-turn without re-auth
  rpc Converse(stream ChatRequest) returns (stream ChatChunk);
}

service MemoryService {
  rpc AddEpisode(AddEpisodeRequest) returns (AddEpisodeResponse);
  rpc Search(SearchRequest) returns (SearchResponse);
  rpc GetEntity(GetEntityRequest) returns (Entity);
}

service ConfigService {
  rpc ListRules(ListRulesRequest) returns (ListRulesResponse);
  rpc CreateRule(CreateRuleRequest) returns (Rule);
  rpc ListScenarios(ListScenariosRequest) returns (ListScenariosResponse);
  rpc CreateScenario(CreateScenarioRequest) returns (Scenario);
}

message ChatRequest {
  string session_id = 1;
  string message = 2;
  map<string, string> metadata = 3;
}

message ChatResponse {
  string response = 1;
  string session_id = 2;
  string turn_id = 3;
  ScenarioStep scenario = 4;
  repeated string matched_rules = 5;
  repeated ToolCall tools_called = 6;
}

message ChatChunk {
  oneof chunk {
    string token = 1;
    ChatResponse done = 2;
  }
}
```

### Client Usage (Python)

```python
import grpc
from focal.v1 import chat_pb2, chat_pb2_grpc

channel = grpc.secure_channel("focal.example.com:443", credentials)
stub = chat_pb2_grpc.ChatServiceStub(channel)

# Unary call
response = stub.SendMessage(chat_pb2.ChatRequest(
    session_id="sess_123",
    message="I want a refund"
))

# Streaming
for chunk in stub.SendMessageStream(request):
    if chunk.HasField("token"):
        print(chunk.token, end="")
    else:
        print(f"\n[Done: {chunk.done.turn_id}]")
```

## MCP Server

MCP (Model Context Protocol) allows LLMs to use Focal as a tool provider.

### Exposed Tools

```json
{
  "tools": [
    {
      "name": "focal_chat",
      "description": "Send a message to the Focal agent and get a response",
      "inputSchema": {
        "type": "object",
        "properties": {
          "session_id": {"type": "string"},
          "message": {"type": "string"}
        },
        "required": ["session_id", "message"]
      }
    },
    {
      "name": "focal_search_memory",
      "description": "Search the agent's knowledge graph for relevant information",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"},
          "session_id": {"type": "string"}
        },
        "required": ["query"]
      }
    },
    {
      "name": "focal_add_episode",
      "description": "Add a new piece of information to the agent's memory",
      "inputSchema": {
        "type": "object",
        "properties": {
          "text": {"type": "string"},
          "session_id": {"type": "string"},
          "source": {"type": "string"}
        },
        "required": ["text"]
      }
    },
    {
      "name": "focal_get_scenario_state",
      "description": "Get the current scenario and state for a session",
      "inputSchema": {
        "type": "object",
        "properties": {
          "session_id": {"type": "string"}
        },
        "required": ["session_id"]
      }
    }
  ]
}
```

### Integration Example

With Claude Desktop or Copilot configured to use Focal's MCP server:

```
User: "What does Focal know about my last order?"

Claude internally calls: focal_search_memory(query="last order", session_id="...")

Claude: "Based on Focal's memory, your last order was #12345 placed on Jan 10..."
```

## Webhook Callbacks

For async operations, Focal can POST results to a callback URL:

### Request with Callback

```json
POST /v1/chat
{
  "session_id": "sess_123",
  "message": "Process my return",
  "callback_url": "https://your-app.com/focal-callback",
  "callback_secret": "webhook_secret_xyz"
}
```

### Immediate Response

```json
{
  "status": "processing",
  "turn_id": "turn_789"
}
```

### Callback POST

```json
POST https://your-app.com/focal-callback
X-Focal-Signature: sha256=...

{
  "turn_id": "turn_789",
  "response": "Your return has been processed...",
  "matched_rules": [...],
  "tools_called": [...]
}
```

## Rate Limiting

Per-tenant limits enforced at API layer:

| Tier | Requests/min | Concurrent | Memory ops/min |
|------|--------------|------------|----------------|
| Free | 60 | 5 | 100 |
| Pro | 600 | 50 | 1000 |
| Enterprise | Custom | Custom | Custom |

Response headers:
```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 542
X-RateLimit-Reset: 1705312800
```

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "RULE_VIOLATION",
    "message": "Response violated safety rule: no_legal_advice",
    "details": {
      "rule_id": "rule_safety_legal",
      "turn_id": "turn_789"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `INVALID_REQUEST` | 400 | Malformed request |
| `TENANT_NOT_FOUND` | 400 | Unknown tenant_id |
| `AGENT_NOT_FOUND` | 400 | Unknown agent_id |
| `SESSION_NOT_FOUND` | 404 | Session ID doesn't exist |
| `RULE_VIOLATION` | 422 | Response couldn't satisfy rules |
| `TOOL_FAILED` | 500 | Tool execution error |
| `LLM_ERROR` | 502 | LLM provider error |

## Versioning

API versioned via URL path:

- `/v1/chat` - Current stable
- `/v2/chat` - Breaking changes (when needed)

Deprecation communicated via header:
```
X-Focal-Deprecation: v1 deprecated 2025-06-01, use v2
```
