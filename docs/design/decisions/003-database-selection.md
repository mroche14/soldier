# ADR-003: Database Selection Strategy

**Status**: Accepted
**Date**: 2025-12-15
**Deciders**: [Team]

## Context

Ruche is a multi-tenant conversational AI platform requiring persistent storage for four distinct domains:

| Store | Purpose | Access Pattern |
|-------|---------|----------------|
| **ConfigStore** | Rules, Scenarios, Templates, Variables | Read-heavy, write-rarely, versioned |
| **MemoryStore** | Episodes, Entities, Relationships (knowledge graph) | Append-heavy, semantic search, graph traversal |
| **SessionStore** | Active conversation state | High-frequency read/write, TTL-based |
| **AuditStore** | Turn records, events, compliance | Append-only, time-series queries |

Key requirements:
- Multi-tenant isolation with zero data leakage
- Horizontal scaling capability
- Sub-200ms retrieval latency
- Vector similarity search for rule matching and memory retrieval
- Graph traversal for knowledge relationships

## Decision

### Primary Database: PostgreSQL

Use **PostgreSQL** as the primary database for all four stores, with **Redis** as a caching layer for sessions.

```
┌─────────────────────────────────────────┐
│           PostgreSQL (Primary)           │
│                                          │
│  ┌──────────────┐  ┌──────────────────┐ │
│  │ ConfigStore  │  │   SessionStore   │ │
│  │              │  │   (persistent)   │ │
│  └──────────────┘  └──────────────────┘ │
│  ┌──────────────┐  ┌──────────────────┐ │
│  │ MemoryStore  │  │   AuditStore     │ │
│  │ (pgvector)   │  │  (TimescaleDB*)  │ │
│  └──────────────┘  └──────────────────┘ │
│                                          │
│  * TimescaleDB extension when needed     │
└─────────────────────────────────────────┘
                      │
┌─────────────────────┴──────────────────┐
│         Redis (Session Cache)           │
│  TTL=1h, sub-ms reads, hot sessions     │
└─────────────────────────────────────────┘
```

### Store-Specific Configuration

#### ConfigStore: PostgreSQL

- Standard relational tables with JSONB for flexible fields
- pgvector extension for rule condition embeddings
- Row Level Security (RLS) for tenant isolation

#### MemoryStore: PostgreSQL + pgvector

- Episodes stored with embedding vectors
- Entities and Relationships in relational tables
- Graph traversal via recursive CTEs
- pgvector HNSW indexes for vector similarity

#### SessionStore: Redis (cache) + PostgreSQL (persistent)

- Redis: Active sessions with 1-hour TTL
- PostgreSQL: Durable storage for session recovery
- Write-through: Save to both on every update
- Read-through: Redis first, PostgreSQL on miss

#### AuditStore: PostgreSQL (→ TimescaleDB at scale)

- Time-partitioned tables (monthly)
- BRIN indexes for time-range queries
- Upgrade to TimescaleDB extension when audit volume exceeds 100M rows

### Multi-Tenancy: Row Level Security (RLS)

All tables include `tenant_id` with RLS policies:

```sql
-- Example RLS policy
ALTER TABLE rules ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON rules
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

Benefits:
- Defense in depth: Even buggy application code cannot leak cross-tenant data
- Single schema: Migrations apply once, not per-tenant
- Minimal overhead: ~5% query overhead with proper indexing

## Decision Drivers

### Why PostgreSQL as Primary

| Factor | Justification |
|--------|---------------|
| **Unified operations** | One database to backup, monitor, scale, secure |
| **ACID guarantees** | Configuration and session state require transactional integrity |
| **pgvector performance** | Benchmarks show 28× lower p95 latency vs some dedicated vector DBs on 50M vectors |
| **RLS for multi-tenancy** | Database-level isolation without schema-per-tenant complexity |
| **Mature ecosystem** | Tooling, hosting options, team familiarity |
| **Graph via CTEs** | Recursive queries handle depth-2 traversals under 100ms |

### Why Redis for Session Cache

| Factor | Justification |
|--------|---------------|
| **Sub-millisecond latency** | Sessions read on every turn; PostgreSQL's 5-10ms adds up |
| **Native TTL** | Automatic expiration without cron jobs |
| **Throughput** | Millions of ops/second vs tens of thousands |
| **Memory efficiency** | Session data is small, fits in RAM |

### Why NOT Other Databases

| Database | Reason to Avoid |
|----------|-----------------|
| **MongoDB** | Data is relational (Rules → Scenarios → Steps). JSONB covers flexible schema needs. |
| **Neo4j** | Depth-2 traversals work fine in PostgreSQL CTEs. Add Neo4j only if graph queries become bottleneck. |
| **Dedicated Vector DB** | pgvector handles up to 10M vectors efficiently. Extra service = extra complexity. |
| **ClickHouse** | Overkill unless ingesting 1B+ events/day. TimescaleDB handles typical audit loads. |
| **DynamoDB/Cassandra** | Relational access patterns. Extreme write scale not needed. |

## Scaling Path

Start simple, evolve based on measured bottlenecks:

| Stage | Stack | Trigger to Evolve |
|-------|-------|-------------------|
| **MVP** | PostgreSQL + Redis | Just build it |
| **Growth** | + TimescaleDB extension | Audit queries > 500ms |
| **Scale** | + Neo4j for MemoryStore | Graph traversals > 200ms, depth > 3 required |
| **Massive** | + ClickHouse for analytics | > 1B events/day |

## Performance Targets

| Operation | Target | PostgreSQL Capability |
|-----------|--------|----------------------|
| Vector search (top-10) | < 50ms | Achievable with HNSW index |
| BM25 full-text search | < 30ms | Native GIN indexes |
| Graph traversal (depth 2) | < 100ms | Recursive CTEs |
| Session read (cached) | < 1ms | Redis |
| Session read (cold) | < 10ms | PostgreSQL |
| Audit time-range query | < 200ms | BRIN + partitioning |

## Implementation Details

### Required PostgreSQL Extensions

```sql
-- Vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search (built-in, no extension needed)
-- Just configure GIN indexes

-- TimescaleDB (when needed for AuditStore)
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Index Strategy

```sql
-- ConfigStore: Rule retrieval
CREATE INDEX idx_rules_tenant_agent ON rules(tenant_id, agent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_rules_embedding ON rules USING hnsw (condition_embedding vector_cosine_ops);

-- MemoryStore: Episode retrieval
CREATE INDEX idx_episodes_group ON episodes(group_id);
CREATE INDEX idx_episodes_embedding ON episodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_episodes_content_fts ON episodes USING gin(to_tsvector('english', content));

-- SessionStore: Session lookup
CREATE INDEX idx_sessions_tenant_agent ON sessions(tenant_id, agent_id);

-- AuditStore: Time-range queries
CREATE INDEX idx_audit_time ON audit_turns USING brin(created_at);
```

### Connection Pooling

Use PgBouncer or built-in connection pooling:

```toml
[storage.postgres]
min_connections = 5
max_connections = 20
connection_timeout_seconds = 30
```

## Consequences

### Positive

- **Operational simplicity**: Single database technology to master
- **Cost efficiency**: No additional managed services initially
- **Flexibility**: Can add specialized databases later based on real needs
- **Strong isolation**: RLS provides database-level multi-tenancy
- **Familiar tooling**: Standard SQL, widespread hosting options

### Negative

- **Not best-in-class for any single domain**: Trade-off for unified stack
- **Scaling limits**: May need specialized DBs at very high scale
- **pgvector limitations**: Performance degrades past 10M vectors per table

### Mitigations

- Monitor query latencies; add specialized databases when targets exceeded
- Partition large tables by tenant for better vector index performance
- Use read replicas for analytics to isolate from OLTP workload

## References

### Research Sources

- [Pgvector Benchmarks & Reality Check](https://medium.com/@DataCraft-Innovations/postgres-vector-search-with-pgvector-benchmarks-costs-and-reality-check-f839a4d2b66f) - May 2025 performance analysis
- [AWS: Multi-tenant RLS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) - Row Level Security patterns
- [Cloudflare: TimescaleDB vs ClickHouse](https://blog.cloudflare.com/timescaledb-art/) - Time-series database selection
- [Neo4j Graphiti Knowledge Graphs](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/) - AI memory store patterns
- [Redis vs PostgreSQL Performance](https://dizzy.zone/2025/09/24/Redis-is-fast-Ill-cache-in-Postgres/) - September 2025 benchmarks
- [TimescaleDB for Logs](https://dev.to/polliog/why-i-chose-postgres-timescaledb-over-clickhouse-for-storing-10m-logs-1e18) - Audit log storage
- [Vector Database Comparison 2025](https://www.firecrawl.dev/blog/best-vector-databases-2025) - Industry overview
- [AI Agent State Management](https://dev.to/inboryn_99399f96579fcd705/state-management-patterns-for-long-running-ai-agents-redis-vs-statefulsets-vs-external-databases-39c5) - Session storage patterns

### Internal Documentation

- [ADR-001: Storage and Provider Architecture](001-storage-choice.md) - Interface definitions
- [Memory Layer](../../architecture/memory-layer.md) - Knowledge graph design
- [Configuration Overview](../../architecture/configuration-overview.md) - Config system design

---

## Appendix: Benchmark Reference Data

### pgvector Performance (May 2025)

| Dataset Size | QPS at 99% Recall | p95 Latency |
|--------------|-------------------|-------------|
| 1M vectors | 2,847 | 12ms |
| 10M vectors | 891 | 38ms |
| 50M vectors | 471 | 89ms |

Source: pgvectorscale benchmarks

### Redis vs PostgreSQL Session Reads

| Database | p50 Latency | p99 Latency | Max QPS |
|----------|-------------|-------------|---------|
| Redis | 0.3ms | 1.2ms | 1.2M |
| PostgreSQL | 4.1ms | 12.3ms | 45K |

Source: September 2025 benchmarks

### TimescaleDB Compression

| Data Type | Compression Ratio | Disk Usage (100GB raw) |
|-----------|-------------------|------------------------|
| Audit logs | 90-95% | 5-10GB |
| Time-series metrics | 85-92% | 8-15GB |

Source: Production deployments
