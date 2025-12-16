# gRPC API

This directory contains the gRPC service implementations for the Ruche platform.

## Overview

The gRPC API provides high-performance service-to-service communication as an alternative to the REST API. It supports:

- Protocol buffer serialization
- Bidirectional streaming for real-time chat
- Lower latency than REST for internal services
- Type-safe contracts via .proto definitions

## Architecture

```
ruche/api/grpc/
├── protos/              # Protocol buffer definitions
│   ├── chat.proto       # ChatService definitions
│   ├── config.proto     # ConfigService definitions
│   └── memory.proto     # MemoryService definitions
├── services/            # Service implementations
│   ├── chat_service.py     # ChatService implementation
│   ├── config_service.py   # ConfigService implementation
│   └── memory_service.py   # MemoryService implementation
├── server.py            # gRPC server setup
├── *_pb2.py             # Generated protobuf code (auto-generated)
└── *_pb2_grpc.py        # Generated gRPC stubs (auto-generated)
```

## Services

### ChatService

Handles conversational message processing:

- `SendMessage`: Unary call - single message in, single response out
- `SendMessageStream`: Server streaming - single message in, streamed response

### MemoryService

Manages memory operations:

- `AddEpisode`: Add a new episode to memory
- `Search`: Search memory using semantic or keyword search
- `GetEntity`: Retrieve a specific entity by ID

### ConfigService

Provides configuration management:

- `ListRules`: List rules for an agent
- `CreateRule`: Create a new rule (placeholder)
- `ListScenarios`: List scenarios for an agent
- `CreateScenario`: Create a new scenario (placeholder)

## Usage

### Starting the gRPC Server

```python
from ruche.api.grpc import serve
from ruche.api.dependencies import (
    get_alignment_engine,
    get_session_store,
    get_config_store,
    get_memory_store,
)

# In your app startup
await serve(
    alignment_engine=await get_alignment_engine(),
    session_store=await get_session_store(),
    config_store=await get_config_store(),
    memory_store=await get_memory_store(),
    host="0.0.0.0",
    port=50051,
)
```

### Client Example (Python)

```python
import grpc
from ruche.api.grpc import chat_pb2, chat_pb2_grpc

# Connect to server
channel = grpc.insecure_channel("localhost:50051")
stub = chat_pb2_grpc.ChatServiceStub(channel)

# Unary call
response = stub.SendMessage(chat_pb2.ChatRequest(
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    agent_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    channel="api",
    user_channel_id="user123",
    message="Hello, how can I help you?",
))

print(f"Response: {response.response}")
print(f"Turn ID: {response.turn_id}")

# Streaming call
for chunk in stub.SendMessageStream(request):
    if chunk.HasField("token"):
        print(chunk.token, end="", flush=True)
    elif chunk.HasField("done"):
        print(f"\nDone: {chunk.done.turn_id}")
    elif chunk.HasField("error"):
        print(f"\nError: {chunk.error.message}")
```

## Regenerating Protocol Buffers

If you modify the .proto files, regenerate the Python code:

```bash
uv run python -m grpc_tools.protoc \
    -I./ruche/api/grpc/protos \
    --python_out=./ruche/api/grpc \
    --grpc_python_out=./ruche/api/grpc \
    ./ruche/api/grpc/protos/chat.proto \
    ./ruche/api/grpc/protos/memory.proto \
    ./ruche/api/grpc/protos/config.proto

# Fix imports in generated files
sed -i 's/^import chat_pb2/from ruche.api.grpc import chat_pb2/' ruche/api/grpc/chat_pb2_grpc.py
sed -i 's/^import memory_pb2/from ruche.api.grpc import memory_pb2/' ruche/api/grpc/memory_pb2_grpc.py
sed -i 's/^import config_pb2/from ruche.api.grpc import config_pb2/' ruche/api/grpc/config_pb2_grpc.py
```

## Implementation Status

| Service | Methods | Status |
|---------|---------|--------|
| ChatService | SendMessage, SendMessageStream | ✅ Implemented |
| MemoryService | AddEpisode, Search, GetEntity | ✅ Implemented |
| ConfigService | ListRules, ListScenarios | ✅ Read-only implemented |
| ConfigService | CreateRule, CreateScenario | ⚠️ Placeholder (use REST API) |

## Documentation

See `docs/architecture/api-layer.md` for detailed API specifications and design decisions.

## Notes

- The gRPC server runs on port 50051 by default
- All services use async implementations via `grpc.aio`
- Error handling follows gRPC status code conventions
- Structured logging is used throughout
- The server supports graceful shutdown
