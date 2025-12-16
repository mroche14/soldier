# Stub Files Documentation

**Last Updated**: 2025-12-16

## Overview

This document catalogs intentional stub files in the codebase. Each stub exists for a specific reason and represents either:

- **PLANNED**: Scheduled for implementation in a known timeframe
- **OPTIONAL**: Alternative backend/provider for specific use cases
- **FUTURE**: Low priority, implement only when specific conditions are met

All stubs contain clear `NotImplementedError` messages explaining their current status and when they should be implemented.

---

## Storage Backend Stubs

These are alternative storage implementations. **PostgreSQL is the primary production backend** for all stores. Other backends are OPTIONAL and should only be implemented when specific operational requirements emerge.

### Neo4j Memory Store

- **File**: `ruche/memory/stores/neo4j.py`
- **Status**: OPTIONAL
- **Category**: Alternative Memory Backend
- **Reason**: Graph database optimized for complex entity relationship traversals
- **Current Solution**: PostgreSQL with pgvector (working, performant for current needs)
- **Prerequisites**:
  - Neo4j 5.0+ with vector search capabilities
  - `neo4j` Python driver
  - Graph query performance testing showing PostgreSQL limitations
- **Implementation Triggers**:
  - Graph traversals exceed 200ms in PostgreSQL
  - Depth > 3 relationship queries become common
  - Complex graph pattern matching is required
- **Priority**: Low
- **Complexity**: Medium (3-5 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### MongoDB Memory Store

- **File**: `ruche/memory/stores/mongodb.py`
- **Status**: OPTIONAL
- **Category**: Alternative Memory Backend
- **Reason**: Document-oriented storage for flexible schema evolution
- **Current Solution**: PostgreSQL with JSONB (working, performant)
- **Prerequisites**:
  - MongoDB 6.0+ with Atlas Vector Search
  - `motor` async driver
  - Horizontal scaling requirements documented
- **Implementation Triggers**:
  - Need for horizontal sharding beyond PostgreSQL capabilities
  - Extremely flexible schema requirements emerge
  - Multi-region replication with MongoDB Atlas is required
- **Priority**: Low
- **Complexity**: Medium (3-5 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### ClickHouse Audit Store

- **File**: `ruche/audit/stores/clickhouse.py`
- **Status**: OPTIONAL
- **Category**: Alternative Audit Backend
- **Reason**: Columnar database for high-volume analytics on audit data
- **Current Solution**: PostgreSQL (working for current audit volumes)
- **Prerequisites**:
  - ClickHouse 23.0+
  - `clickhouse-driver` or `asynch` driver
  - Audit data volume exceeding 1M rows requiring analytics
- **Implementation Triggers**:
  - Audit queries become slow (>1s for common queries)
  - Real-time analytics dashboards are required
  - Audit data exceeds 1M rows and growing rapidly
- **Priority**: Low
- **Complexity**: Medium (3-5 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### TimescaleDB Audit Store

- **File**: `ruche/audit/stores/timescale.py`
- **Status**: OPTIONAL
- **Category**: Alternative Audit Backend
- **Reason**: Time-series database optimized for audit data with automatic partitioning
- **Current Solution**: PostgreSQL with manual partitioning (if needed)
- **Prerequisites**:
  - TimescaleDB 2.0+ (PostgreSQL extension)
  - Complex data retention policies documented
  - Time-series query patterns documented
- **Implementation Triggers**:
  - Time-series queries are primary access pattern
  - Need automatic time-based partitioning (hypertables)
  - Complex retention policies (e.g., keep detailed data for 30 days, aggregates for 1 year)
- **Priority**: Low
- **Complexity**: Low (1-2 days, TimescaleDB is a PostgreSQL extension)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### MongoDB Audit Store

- **File**: `ruche/audit/stores/mongodb.py`
- **Status**: OPTIONAL
- **Category**: Alternative Audit Backend
- **Reason**: Document-oriented storage for flexible audit event schemas
- **Current Solution**: PostgreSQL with JSONB (working)
- **Prerequisites**:
  - MongoDB 6.0+
  - `motor` async driver
  - Highly variable audit event types documented
- **Implementation Triggers**:
  - Audit event schemas are extremely varied and evolving
  - Need automatic TTL-based expiration
  - Horizontal scaling for audit data is required
- **Priority**: Low
- **Complexity**: Medium (3-5 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### DynamoDB Session Store

- **File**: `ruche/conversation/stores/dynamodb.py`
- **Status**: OPTIONAL
- **Category**: Alternative Session Backend
- **Reason**: AWS-native session storage for AWS deployments
- **Current Solution**: Redis (primary), InMemory (dev)
- **Prerequisites**:
  - AWS account with DynamoDB access
  - `aioboto3` library
  - AWS-specific deployment architecture
- **Implementation Triggers**:
  - Deployment is AWS-native and needs AWS-native services
  - Multi-region global tables are required
  - Redis is not available or preferred in the deployment environment
- **Priority**: Low
- **Complexity**: Medium (3-4 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

### MongoDB Session Store

- **File**: `ruche/conversation/stores/mongodb.py`
- **Status**: OPTIONAL
- **Category**: Alternative Session Backend
- **Reason**: Document-oriented session storage with flexible schema
- **Current Solution**: Redis (primary), InMemory (dev)
- **Prerequisites**:
  - MongoDB 6.0+
  - `motor` async driver
  - Documented need for flexible session schema
- **Implementation Triggers**:
  - Session state requires extremely flexible schema
  - TTL-based session expiration in MongoDB is preferred over Redis
  - Horizontal scaling for session data is required
- **Priority**: Low
- **Complexity**: Medium (2-3 days)
- **Reference**: `docs/design/decisions/003-database-selection.md`

---

## AI Provider Stubs

These are alternative AI service providers. **Current implementations** include OpenAI, Cohere, and Jina for embeddings; Cohere and Jina for reranking. Additional providers should only be added when there's a specific use case or domain requirement.

### Voyage Embedding Provider

- **File**: `ruche/infrastructure/providers/embedding/voyage.py`
- **Status**: OPTIONAL
- **Category**: Alternative Embedding Provider
- **Reason**: Domain-specific high-quality embeddings (code, finance, law)
- **Current Solution**: OpenAI, Cohere, Jina (working)
- **Prerequisites**:
  - Voyage API key (`VOYAGE_API_KEY`)
  - `voyageai` Python library
  - Documented need for domain-specific embeddings
- **Implementation Triggers**:
  - Need domain-specific models (voyage-code-3, voyage-finance-2, voyage-law-2)
  - Retrieval quality improvements over OpenAI/Cohere are demonstrated
  - Specific customer requests Voyage integration
- **Priority**: Low
- **Complexity**: Low (1 day, similar to existing providers)
- **Reference**: Existing providers in `ruche/infrastructure/providers/embedding/`

### Voyage Rerank Provider

- **File**: `ruche/infrastructure/providers/rerank/voyage.py`
- **Status**: OPTIONAL
- **Category**: Alternative Rerank Provider
- **Reason**: Domain-specific reranking for improved retrieval
- **Current Solution**: Cohere, Jina (working)
- **Prerequisites**:
  - Voyage API key (`VOYAGE_API_KEY`)
  - `voyageai` Python library
  - Documented need for domain-specific reranking
- **Implementation Triggers**:
  - Need rerank-2 model for specific domains
  - Reranking quality improvements over Cohere/Jina are demonstrated
  - Specific customer requests Voyage integration
- **Priority**: Low
- **Complexity**: Low (1 day, similar to existing providers)
- **Reference**: Existing providers in `ruche/infrastructure/providers/rerank/`

### Cross-Encoder Rerank Provider

- **File**: `ruche/infrastructure/providers/rerank/cross_encoder.py`
- **Status**: OPTIONAL
- **Category**: Alternative Rerank Provider (Local)
- **Reason**: Local/offline reranking using sentence-transformers models
- **Current Solution**: Cohere, Jina (API-based, working)
- **Prerequisites**:
  - `sentence-transformers` library
  - GPU support (optional but recommended)
  - Local model weights and storage
- **Implementation Triggers**:
  - Offline/air-gapped deployment requirements
  - Cost optimization (avoid API calls for reranking)
  - Need for custom fine-tuned reranking models
  - GPU infrastructure is available
- **Priority**: Low
- **Complexity**: Medium (2-3 days, requires model loading and GPU support)
- **Reference**: Existing providers in `ruche/infrastructure/providers/rerank/`

---

## API Layer Stubs

These are partially implemented or planned API features.

### gRPC Server

- **File**: `ruche/api/grpc/server.py`
- **Status**: PLANNED (Partial Implementation)
- **Category**: Alternative API Protocol
- **Reason**: High-performance service-to-service communication
- **Current Solution**: REST API with FastAPI (working, fully functional)
- **Current State**: gRPC server implementation is COMPLETE and functional. Service implementations exist:
  - `ChatService` (`ruche/api/grpc/services/chat_service.py`) - COMPLETE
  - `ConfigService` (`ruche/api/grpc/services/config_service.py`) - PARTIAL (CreateRule/CreateScenario not implemented)
  - `MemoryService` (`ruche/api/grpc/services/memory_service.py`) - COMPLETE
- **Prerequisites**:
  - gRPC proto definitions (COMPLETE: `ruche/api/grpc/protos/`)
  - Generated Python code (COMPLETE: `*_pb2.py`, `*_pb2_grpc.py`)
  - Service implementations (MOSTLY COMPLETE, see above)
- **Remaining Work**:
  - Implement `ConfigService.CreateRule()` method
  - Implement `ConfigService.CreateScenario()` method
  - Add gRPC server to main application startup
  - Add gRPC endpoint documentation
- **Implementation Triggers**:
  - Internal service-to-service communication needs lower latency than REST
  - Bidirectional streaming is required for real-time features
  - Protocol buffer serialization is preferred over JSON
- **Priority**: Medium
- **Complexity**: Low (1-2 days for remaining work)
- **Reference**: `docs/architecture/api-layer.md`

### gRPC Module Init

- **File**: `ruche/api/grpc/__init__.py`
- **Status**: COMPLETE
- **Category**: Module Initialization
- **Reason**: Export gRPC server and services
- **Current State**: Fully implemented. Exports:
  - `GRPCServer` and `serve` function
  - Generated protobuf modules (`*_pb2`, `*_pb2_grpc`)
  - Service implementations (`ChatService`, `ConfigService`, `MemoryService`)
- **No Action Required**: This file is complete and functional.

### Configuration API Routes

- **File**: `ruche/api/routes/config.py`
- **Status**: FUTURE
- **Category**: API Endpoint Placeholder
- **Reason**: Runtime configuration management via API
- **Current Solution**: Configuration via TOML files and environment variables (working)
- **Current State**: Empty placeholder with router defined
- **Prerequisites**:
  - Requirements for runtime config changes documented
  - Security model for config changes defined
  - Validation and rollback strategy defined
- **Implementation Triggers**:
  - Need to change configuration without restarting the application
  - Multi-tenant configuration management UI is required
  - Dynamic feature flags are needed
- **Priority**: Low
- **Complexity**: Medium (3-5 days, requires careful security design)
- **Reference**: `docs/architecture/configuration-overview.md`

---

## Other Stubs

### Memory Ingestion Module

- **File**: `ruche/memory/ingestion/__init__.py`
- **Status**: COMPLETE
- **Category**: Module Initialization
- **Reason**: Export memory ingestion components
- **Current State**: Fully implemented. Exports:
  - `EntityExtractor`
  - `ConversationSummarizer`
  - `MemoryIngestor`
- **No Action Required**: This file is complete and functional.

---

## Summary Table

| Category | File | Status | Priority | Complexity | Trigger |
|----------|------|--------|----------|------------|---------|
| **Storage** | `memory/stores/neo4j.py` | OPTIONAL | Low | Medium | Graph queries >200ms |
| **Storage** | `memory/stores/mongodb.py` | OPTIONAL | Low | Medium | Horizontal scaling needed |
| **Storage** | `audit/stores/clickhouse.py` | OPTIONAL | Low | Medium | >1M audit rows, analytics needed |
| **Storage** | `audit/stores/timescale.py` | OPTIONAL | Low | Low | Time-series primary pattern |
| **Storage** | `audit/stores/mongodb.py` | OPTIONAL | Low | Medium | Flexible audit schema needed |
| **Storage** | `conversation/stores/dynamodb.py` | OPTIONAL | Low | Medium | AWS-native deployment |
| **Storage** | `conversation/stores/mongodb.py` | OPTIONAL | Low | Medium | Flexible session schema |
| **Provider** | `providers/embedding/voyage.py` | OPTIONAL | Low | Low | Domain-specific embeddings |
| **Provider** | `providers/rerank/voyage.py` | OPTIONAL | Low | Low | Domain-specific reranking |
| **Provider** | `providers/rerank/cross_encoder.py` | OPTIONAL | Low | Medium | Offline/GPU deployment |
| **API** | `api/grpc/server.py` | PLANNED | Medium | Low | Service-to-service needs |
| **API** | `api/grpc/__init__.py` | COMPLETE | N/A | N/A | N/A |
| **API** | `api/routes/config.py` | FUTURE | Low | Medium | Runtime config changes |
| **Other** | `memory/ingestion/__init__.py` | COMPLETE | N/A | N/A | N/A |

---

## Decision Criteria

### When to Implement Storage Stubs

Implement alternative storage backends only when:

1. **Performance bottleneck identified**: Current solution (PostgreSQL/Redis) shows measurable performance issues
2. **Specific operational requirement**: Deployment environment requires specific technology (e.g., AWS-native)
3. **Documented use case**: Clear customer/operational need documented in GitHub issue or design doc
4. **Resource availability**: Team has bandwidth to implement AND maintain the new backend

### When to Implement Provider Stubs

Implement alternative AI providers only when:

1. **Quality improvement demonstrated**: Benchmarks show clear improvement over existing providers
2. **Domain-specific need**: Customer requires domain-specific models (code, finance, law)
3. **Cost optimization**: Provider offers significant cost savings for production workloads
4. **Customer request**: Specific customer integration requirement

### When to Implement API Stubs

Implement API features only when:

1. **User requirement**: Clear user story or customer request
2. **Architectural need**: Required for planned features (e.g., gRPC for service mesh)
3. **Performance requirement**: REST API proves insufficient for latency/throughput needs

---

## Development Guidelines

### Adding New Stubs

When adding a new stub file:

1. **Add clear docstring** explaining the purpose and future implementation
2. **Raise NotImplementedError** with helpful message pointing to current alternatives
3. **Reference documentation** pointing to design decisions or requirements
4. **Update this document** with categorization and implementation criteria
5. **Add to `.gitignore` if needed** (empty files should not be committed)

### Example Stub Template

```python
"""[Provider/Store Name] implementation of [Interface].

This is a placeholder for future implementation when [specific condition].

See docs/[reference] for requirements:
- Use when [trigger condition 1]
- Use when [trigger condition 2]
- Requires [dependency 1], [dependency 2]
"""

from ruche.[module].interface import [Interface]


class [ClassName]([Interface]):
    """[Provider/Store Name] implementation.

    Future implementation will provide:
    - [Feature 1]
    - [Feature 2]
    - [Feature 3]
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "[ClassName] not yet implemented. "
            "Use [Alternative1] for [use case 1] or [Alternative2] for [use case 2]. "
            "[ClassName] implementation is planned for [specific trigger]."
        )
```

---

## References

- **Database Selection**: `docs/design/decisions/003-database-selection.md`
- **API Layer Architecture**: `docs/architecture/api-layer.md`
- **Configuration Overview**: `docs/architecture/configuration-overview.md`
- **Implementation Waves**: `docs/implementation/IMPLEMENTATION_WAVES.md`
