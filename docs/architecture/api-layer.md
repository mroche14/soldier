# API Layer

Focal is a **message ingestion + turn processing engine**. It receives message events from upstream services (channel-gateway, message-router) with tenant and channel context already resolved. Focal’s **Agent Conversation Fabric (ACF)** aggregates one or more messages into a **LogicalTurn** (“a message is not a turn”) and runs the cognitive pipeline once per LogicalTurn.

## Architecture Position

```
Channel Gateway (WhatsApp, Slack, Web, etc.)
       │
       │  Resolves: tenant_id, channel, channel_user_id
       ▼
Message Router (routing, backpressure)
       │
       │  Adds: agent_id, routing metadata
       ▼
    FOCAL (this service)
       │
       │  ACF: mutex + accumulation + supersede signals
       │  Pipeline: processes LogicalTurn, returns response
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

### Chat Request (Multimodal Envelope)

```json
POST /v1/chat
Idempotency-Key: unique-request-id-123  // Optional, for safe retries

{
  "tenant_id": "uuid",                   // Required: resolved upstream
  "agent_id": "uuid",                    // Required: which agent to use
  "channel": "whatsapp|slack|webchat|email|voice",  // Required: channel identifier
  "channel_user_id": "+1234567890",      // Required: user identifier on channel

  "content_type": "text|image|audio|document|location|contact|mixed",  // Required: content type
  "content": {                           // Required: multimodal content envelope
    "text": "I want to return my order", // Optional: text content (null if no text)
    "media": [                           // Optional: media attachments
      {
        "type": "image|audio|video|document",
        "url": "string",
        "mime_type": "image/jpeg",
        "filename": "string | null",
        "caption": "string | null",
        "thumbnail_url": "string | null"
      }
    ],
    "location": {                        // Optional: location data (WhatsApp, etc.)
      "latitude": 37.7749,
      "longitude": -122.4194,
      "name": "San Francisco Office"
    },
    "structured": {}                     // Optional: channel-specific structured data
  },

  "provider_message_id": "string|null",  // Optional: upstream message ID for tracking
  "idempotency_key": "string|null",      // Optional: alternative to header (header takes precedence)
  "session_hint": "string|null",         // Optional: suggested session (Focal may override)
  "received_at": "2025-01-15T10:30:00Z", // Required: ISO8601 timestamp
  "metadata": {                          // Optional: additional context
    "integration_id": "uuid",
    "locale": "en-US"
  }
}
```

**Content Type Examples:**

| Type | Use Case | Fields Used |
|------|----------|-------------|
| `text` | Standard message | `content.text` |
| `image` | Photo with caption | `content.media[0]`, `content.text` (optional) |
| `audio` | Voice message | `content.media[0]` (type=audio) |
| `document` | PDF attachment | `content.media[0]` (type=document) |
| `location` | Share location | `content.location` |
| `mixed` | Text + images | `content.text`, `content.media[]` |

### Chat Response

```json
{
  "response": "I'd be happy to help with your return. Could you provide your order number?",
  "session_id": "sess_abc123",
  "logical_turn_id": "turn_789",
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
data: {"type": "done", "logical_turn_id": "turn_789", "matched_rules": [...]}
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

package ruche.v1;

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
  string logical_turn_id = 3;
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
from ruche.v1 import chat_pb2, chat_pb2_grpc

channel = grpc.secure_channel("ruche.example.com:443", credentials)
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
        print(f"\n[Done: {chunk.done.logical_turn_id}]")
```

## MCP Server (Tool Discovery)

MCP (Model Context Protocol) exposes **tenant-available tools for discovery** by LLM clients (Claude Desktop, Copilot, GPT). MCP is used for **discovery only** - actual tool execution goes through Focal's native Toolbox→ToolGateway flow.

### Three-Tier Tool Visibility Model

| Tier | Scope | Purpose | Source |
|------|-------|---------|--------|
| **Catalog** | Global | All tools Focal knows about | Tool Catalog (ConfigStore) |
| **Tenant-Available** | Tenant | Tools this tenant has access to | Tenant configuration + integrations |
| **Agent-Enabled** | Agent | Tools enabled for this agent | Agent configuration |

**MCP Server exposes Tier 2 (Tenant-Available)** - the middle layer. This shows what tools the tenant CAN use, but not which agents have them enabled.

### Discovery Flow

```
1. LLM Client → MCP Server: tools/list
2. MCP Server → ConfigStore: get_tenant_tools(tenant_id)
3. ConfigStore returns: Tenant-available tools (Catalog ∩ Tenant integrations)
4. MCP Server responds: JSON Schema tool definitions
5. LLM Client displays: Available tools for discovery
```

**Execution Flow** (separate from MCP):

```
1. LLM decides to use tool
2. AlignmentEngine → Toolbox.execute_tool()
3. Toolbox → ToolGateway → External API
4. Result returned to pipeline
```

### MCP Endpoint

```json
GET /mcp/v1/tools?tenant_id=uuid

Response:
{
  "tools": [
    {
      "name": "search_knowledge_base",
      "description": "Search the company knowledge base for relevant articles",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "Search query"},
          "limit": {"type": "integer", "default": 5}
        },
        "required": ["query"]
      },
      "provider": "zendesk"
    },
    {
      "name": "create_ticket",
      "description": "Create a support ticket in the ticketing system",
      "inputSchema": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "description": {"type": "string"},
          "priority": {"type": "string", "enum": ["low", "medium", "high"]}
        },
        "required": ["title", "description"]
      },
      "provider": "jira"
    },
    {
      "name": "focal_search_memory",
      "description": "Search Focal's conversation memory for this tenant",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"},
          "session_id": {"type": "string"}
        },
        "required": ["query"]
      },
      "provider": "focal_internal"
    }
  ]
}
```

### Built-In Focal Tools (Always Available)

These are exposed via MCP for external LLM clients to interact with Focal's internal capabilities:

| Tool | Description | Use Case |
|------|-------------|----------|
| `focal_search_memory` | Search conversation memory | "What did the user say about X?" |
| `focal_get_customer_data` | Retrieve customer variables | "What's the user's email?" |
| `focal_get_scenario_state` | Get current scenario/step | "Where are we in the flow?" |

### Integration Example

**Claude Desktop with Focal MCP:**

```json
// ~/.config/claude/config.json
{
  "mcpServers": {
    "focal": {
      "url": "https://ruche.example.com/mcp/v1",
      "auth": {
        "type": "bearer",
        "token": "tenant_api_key_xyz"
      },
      "params": {
        "tenant_id": "tenant_uuid"
      }
    }
  }
}
```

**Usage:**

```
User: "Search our knowledge base for return policies"

Claude internally sees: search_knowledge_base tool via MCP discovery
Claude calls: search_knowledge_base(query="return policies")
Focal routes: Via native Toolbox→ToolGateway (not MCP execution)

Claude: "Based on the knowledge base, your return policy allows..."
```

### MCP vs Native Execution

| Aspect | MCP Role | Native Toolbox Role |
|--------|----------|---------------------|
| **Discovery** | Expose available tools | N/A |
| **Schema** | Provide JSON Schema | Validate parameters |
| **Execution** | ❌ Not used | ✅ ToolGateway executes |
| **Auth** | Tenant-level API key | Per-integration credentials |
| **Routing** | N/A | Route to correct provider |

**Why separate?** MCP is for external LLM clients discovering what Focal offers. Internal execution stays in Toolbox for consistency, observability, rate limiting, and tenant isolation.

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
  "logical_turn_id": "turn_789"
}
```

### Callback POST

```json
POST https://your-app.com/focal-callback
X-Focal-Signature: sha256=...

{
  "logical_turn_id": "turn_789",
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
      "logical_turn_id": "turn_789"
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
