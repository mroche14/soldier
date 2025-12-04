# Data Model: Production Store & Provider Completion

**Feature**: 009-production-stores-providers
**Date**: 2025-11-29

## Overview

This document defines the PostgreSQL schema for all stores and the Redis key structure for session storage.

## PostgreSQL Schemas

### ConfigStore Tables

#### agents
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_prompt TEXT,
    default_model VARCHAR(100),
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    CONSTRAINT uq_agents_tenant_name UNIQUE (tenant_id, name) WHERE deleted_at IS NULL
);

CREATE INDEX idx_agents_tenant ON agents(tenant_id) WHERE deleted_at IS NULL;
```

#### rules
```sql
CREATE TABLE rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    condition_text TEXT NOT NULL,
    condition_embedding vector(1536),
    embedding_model VARCHAR(100),
    action_type VARCHAR(50) NOT NULL,
    action_config JSONB NOT NULL DEFAULT '{}',
    scope VARCHAR(20) NOT NULL DEFAULT 'GLOBAL',
    scope_id UUID,
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_rules_scope CHECK (scope IN ('GLOBAL', 'SCENARIO', 'STEP'))
);

CREATE INDEX idx_rules_tenant_agent ON rules(tenant_id, agent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_rules_scope ON rules(tenant_id, agent_id, scope, scope_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_rules_embedding ON rules USING ivfflat (condition_embedding vector_cosine_ops)
    WITH (lists = 100) WHERE condition_embedding IS NOT NULL AND deleted_at IS NULL;
```

#### scenarios
```sql
CREATE TABLE scenarios (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    entry_condition TEXT,
    entry_embedding vector(1536),
    steps JSONB NOT NULL DEFAULT '[]',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_scenarios_tenant_agent ON scenarios(tenant_id, agent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_scenarios_entry_embedding ON scenarios USING ivfflat (entry_embedding vector_cosine_ops)
    WITH (lists = 50) WHERE entry_embedding IS NOT NULL AND deleted_at IS NULL;
```

#### scenario_archives
```sql
CREATE TABLE scenario_archives (
    tenant_id UUID NOT NULL,
    scenario_id UUID NOT NULL,
    version INTEGER NOT NULL,
    scenario_data JSONB NOT NULL,
    archived_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (tenant_id, scenario_id, version)
);
```

#### templates
```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id),
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'SUGGEST',
    scope VARCHAR(20) NOT NULL DEFAULT 'GLOBAL',
    scope_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_templates_mode CHECK (mode IN ('SUGGEST', 'EXCLUSIVE', 'FALLBACK')),
    CONSTRAINT chk_templates_scope CHECK (scope IN ('GLOBAL', 'SCENARIO', 'STEP'))
);

CREATE INDEX idx_templates_tenant_agent ON templates(tenant_id, agent_id) WHERE deleted_at IS NULL;
```

#### variables
```sql
CREATE TABLE variables (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    default_value TEXT,
    update_policy VARCHAR(30) DEFAULT 'REPLACE',
    resolver_tool_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    CONSTRAINT uq_variables_tenant_agent_name UNIQUE (tenant_id, agent_id, name) WHERE deleted_at IS NULL,
    CONSTRAINT chk_variables_policy CHECK (update_policy IN ('REPLACE', 'APPEND', 'MERGE'))
);

CREATE INDEX idx_variables_tenant_agent ON variables(tenant_id, agent_id) WHERE deleted_at IS NULL;
```

#### tool_activations
```sql
CREATE TABLE tool_activations (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id),
    tool_id VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    policy_overrides JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_tool_activations UNIQUE (tenant_id, agent_id, tool_id)
);

CREATE INDEX idx_tool_activations_tenant_agent ON tool_activations(tenant_id, agent_id);
```

#### migration_plans
```sql
CREATE TABLE migration_plans (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    scenario_id UUID NOT NULL,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    transformation_map JSONB NOT NULL,
    anchor_policies JSONB DEFAULT '{}',
    scope_filter JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ,

    CONSTRAINT chk_migration_status CHECK (status IN ('DRAFT', 'APPROVED', 'DEPLOYED', 'REJECTED'))
);

CREATE INDEX idx_migration_plans_scenario ON migration_plans(tenant_id, scenario_id, from_version, to_version);
```

### MemoryStore Tables

#### episodes
```sql
CREATE TABLE episodes (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    customer_profile_id UUID,
    session_id UUID,
    content TEXT NOT NULL,
    embedding vector(1536),
    embedding_model VARCHAR(100),
    episode_type VARCHAR(50) NOT NULL,
    importance FLOAT DEFAULT 0.5,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    group_id UUID,

    CONSTRAINT chk_episodes_type CHECK (episode_type IN ('TURN', 'SUMMARY', 'FACT', 'EVENT'))
);

CREATE INDEX idx_episodes_tenant_agent ON episodes(tenant_id, agent_id);
CREATE INDEX idx_episodes_customer ON episodes(tenant_id, customer_profile_id) WHERE customer_profile_id IS NOT NULL;
CREATE INDEX idx_episodes_session ON episodes(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_episodes_group ON episodes(group_id) WHERE group_id IS NOT NULL;
CREATE INDEX idx_episodes_valid ON episodes(valid_from, valid_to);
CREATE INDEX idx_episodes_embedding ON episodes USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100) WHERE embedding IS NOT NULL;
```

#### entities
```sql
CREATE TABLE entities (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    customer_profile_id UUID,
    name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    canonical_name VARCHAR(500),
    attributes JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_entities_tenant_agent ON entities(tenant_id, agent_id);
CREATE INDEX idx_entities_name ON entities(tenant_id, name);
CREATE INDEX idx_entities_type ON entities(tenant_id, entity_type);
```

#### relationships
```sql
CREATE TABLE relationships (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    source_entity_id UUID NOT NULL REFERENCES entities(id),
    target_entity_id UUID NOT NULL REFERENCES entities(id),
    relationship_type VARCHAR(100) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',

    CONSTRAINT uq_relationships UNIQUE (source_entity_id, target_entity_id, relationship_type, valid_from)
);

CREATE INDEX idx_relationships_source ON relationships(source_entity_id);
CREATE INDEX idx_relationships_target ON relationships(target_entity_id);
CREATE INDEX idx_relationships_type ON relationships(tenant_id, relationship_type);
```

### AuditStore Tables

#### turn_records
```sql
CREATE TABLE turn_records (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    session_id UUID NOT NULL,
    turn_number INTEGER NOT NULL,
    user_message TEXT NOT NULL,
    assistant_response TEXT,
    context_extracted JSONB,
    rules_matched JSONB DEFAULT '[]',
    scenario_state JSONB,
    tools_executed JSONB DEFAULT '[]',
    token_usage JSONB,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_turn_records_session ON turn_records(session_id);
CREATE INDEX idx_turn_records_tenant ON turn_records(tenant_id);
CREATE INDEX idx_turn_records_created ON turn_records(tenant_id, created_at DESC);
```

#### audit_events
```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    session_id UUID,
    turn_id UUID REFERENCES turn_records(id),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_events_tenant ON audit_events(tenant_id);
CREATE INDEX idx_audit_events_session ON audit_events(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_audit_events_type ON audit_events(tenant_id, event_type);
CREATE INDEX idx_audit_events_created ON audit_events(tenant_id, created_at DESC);
```

### ProfileStore Tables

#### customer_profiles
```sql
CREATE TABLE customer_profiles (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    external_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    merged_into_id UUID REFERENCES customer_profiles(id),

    CONSTRAINT uq_profiles_external UNIQUE (tenant_id, external_id) WHERE external_id IS NOT NULL
);

CREATE INDEX idx_profiles_tenant ON customer_profiles(tenant_id);
```

#### channel_identities
```sql
CREATE TABLE channel_identities (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    channel VARCHAR(50) NOT NULL,
    channel_user_id VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_channel_identity UNIQUE (tenant_id, channel, channel_user_id)
);

CREATE INDEX idx_channel_identities_profile ON channel_identities(profile_id);
CREATE INDEX idx_channel_identities_lookup ON channel_identities(tenant_id, channel, channel_user_id);
```

#### profile_fields
```sql
CREATE TABLE profile_fields (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    field_name VARCHAR(255) NOT NULL,
    field_value TEXT,
    source VARCHAR(50) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    verified BOOLEAN DEFAULT false,
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_to TIMESTAMPTZ,

    CONSTRAINT chk_field_source CHECK (source IN ('USER_PROVIDED', 'EXTRACTED', 'INFERRED', 'SYSTEM'))
);

CREATE INDEX idx_profile_fields_profile ON profile_fields(profile_id);
CREATE INDEX idx_profile_fields_name ON profile_fields(tenant_id, profile_id, field_name);
```

#### profile_assets
```sql
CREATE TABLE profile_assets (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    asset_type VARCHAR(50) NOT NULL,
    asset_reference VARCHAR(500) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profile_assets_profile ON profile_assets(profile_id);
CREATE INDEX idx_profile_assets_type ON profile_assets(tenant_id, profile_id, asset_type);
```

## Redis Key Structure

### Session Store Two-Tier Keys

| Key Pattern | Type | TTL | Description |
|-------------|------|-----|-------------|
| `session:hot:{session_id}` | String (JSON) | 30 min | Hot cache for active sessions |
| `session:persist:{session_id}` | String (JSON) | 7 days | Persistent storage for inactive sessions |
| `session:index:agent:{tenant_id}:{agent_id}` | Set | 7 days | Index of session IDs by agent |
| `session:index:customer:{tenant_id}:{profile_id}` | Set | 7 days | Index of session IDs by customer |
| `session:index:channel:{tenant_id}:{channel}:{user_id}` | String | 7 days | Lookup session by channel identity |

### Session JSON Structure

```json
{
  "session_id": "uuid",
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "customer_profile_id": "uuid",
  "channel": "WEB",
  "user_channel_id": "string",
  "status": "ACTIVE",
  "variables": {},
  "active_scenario_id": "uuid",
  "active_scenario_version": 1,
  "current_step_id": "uuid",
  "step_history": [],
  "pending_migration": null,
  "created_at": "2025-01-15T00:00:00Z",
  "last_activity_at": "2025-01-15T00:00:00Z"
}
```

## Entity Relationships

```
agents 1──* rules
agents 1──* scenarios
agents 1──* templates
agents 1──* variables
agents 1──* tool_activations

scenarios 1──* scenario_archives
scenarios 1──* migration_plans

customer_profiles 1──* channel_identities
customer_profiles 1──* profile_fields
customer_profiles 1──* profile_assets
customer_profiles 1──* episodes

entities *──* relationships (source/target)
```

## Migration Sequence

1. `001_initial_schema.py` - Enable pgvector extension
2. `002_config_store.py` - agents, rules, scenarios, templates, variables, tool_activations
3. `003_memory_store.py` - episodes, entities, relationships
4. `004_audit_store.py` - turn_records, audit_events
5. `005_profile_store.py` - customer_profiles, channel_identities, profile_fields, profile_assets
6. `006_migration_plans.py` - migration_plans, scenario_archives
7. `007_vector_indexes.py` - IVFFlat indexes for embeddings
