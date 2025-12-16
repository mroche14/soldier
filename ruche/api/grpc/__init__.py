"""gRPC API module.

This module provides gRPC endpoints as an alternative to REST.
Supports high-performance service-to-service communication with:
- Protocol buffer serialization
- Bidirectional streaming
- Lower latency for internal services
"""

from ruche.api.grpc.server import GRPCServer, serve

# Import generated protobuf modules
from ruche.api.grpc import chat_pb2, chat_pb2_grpc
from ruche.api.grpc import config_pb2, config_pb2_grpc
from ruche.api.grpc import memory_pb2, memory_pb2_grpc

# Import service implementations
from ruche.api.grpc.services.chat_service import ChatService
from ruche.api.grpc.services.config_service import ConfigService
from ruche.api.grpc.services.memory_service import MemoryService

__all__ = [
    # Server
    "GRPCServer",
    "serve",
    # Generated modules
    "chat_pb2",
    "chat_pb2_grpc",
    "config_pb2",
    "config_pb2_grpc",
    "memory_pb2",
    "memory_pb2_grpc",
    # Service implementations
    "ChatService",
    "ConfigService",
    "MemoryService",
]
