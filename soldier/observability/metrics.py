"""Prometheus metrics for Soldier.

Provides standard metrics for request tracking, latencies, token usage,
and system health.
"""

from prometheus_client import Counter, Gauge, Histogram

# Request metrics
REQUEST_COUNT = Counter(
    "soldier_request_count_total",
    "Total number of requests processed",
    labelnames=["tenant_id", "agent_id", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "soldier_request_latency_seconds",
    "Request latency in seconds",
    labelnames=["tenant_id", "agent_id", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# LLM metrics
LLM_TOKENS = Counter(
    "soldier_llm_tokens_total",
    "Total LLM tokens used",
    labelnames=["provider", "model", "direction"],
)

# Alignment metrics
RULES_MATCHED = Histogram(
    "soldier_rules_matched",
    "Number of rules matched per turn",
    labelnames=["tenant_id", "agent_id"],
    buckets=(0, 1, 2, 3, 5, 10, 20, 50),
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    "soldier_active_sessions",
    "Number of active sessions",
    labelnames=["tenant_id", "agent_id"],
)

# Error metrics
ERRORS = Counter(
    "soldier_errors_total",
    "Total number of errors",
    labelnames=["tenant_id", "agent_id", "error_type"],
)

# Pipeline step metrics
PIPELINE_STEP_LATENCY = Histogram(
    "soldier_pipeline_step_latency_seconds",
    "Latency of individual pipeline steps",
    labelnames=["tenant_id", "agent_id", "step"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Memory metrics
MEMORY_EPISODES = Gauge(
    "soldier_memory_episodes",
    "Number of episodes in memory store",
    labelnames=["tenant_id"],
)

MEMORY_ENTITIES = Gauge(
    "soldier_memory_entities",
    "Number of entities in memory store",
    labelnames=["tenant_id"],
)

# Migration metrics
MIGRATION_COUNT = Counter(
    "soldier_migration_count_total",
    "Total number of migrations executed",
    labelnames=["tenant_id", "scenario_type", "outcome"],
)

MIGRATION_LATENCY = Histogram(
    "soldier_migration_latency_seconds",
    "Migration execution latency in seconds",
    labelnames=["tenant_id", "scenario_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

GAP_FILL_COUNT = Counter(
    "soldier_gap_fill_count_total",
    "Total number of gap fills attempted",
    labelnames=["tenant_id", "source", "outcome"],
)

MIGRATION_PLANS_CREATED = Counter(
    "soldier_migration_plans_created_total",
    "Total number of migration plans created",
    labelnames=["tenant_id"],
)

MIGRATION_PLANS_DEPLOYED = Counter(
    "soldier_migration_plans_deployed_total",
    "Total number of migration plans deployed",
    labelnames=["tenant_id"],
)

# Profile cache metrics
PROFILE_CACHE_HITS = Counter(
    "soldier_profile_cache_hits_total",
    "Total number of profile cache hits",
    labelnames=["tenant_id", "cache_key_type"],
)

PROFILE_CACHE_MISSES = Counter(
    "soldier_profile_cache_misses_total",
    "Total number of profile cache misses",
    labelnames=["tenant_id", "cache_key_type"],
)

PROFILE_CACHE_INVALIDATIONS = Counter(
    "soldier_profile_cache_invalidations_total",
    "Total number of profile cache invalidations",
    labelnames=["tenant_id", "operation"],
)

PROFILE_CACHE_ERRORS = Counter(
    "soldier_profile_cache_errors_total",
    "Total number of profile cache errors",
    labelnames=["tenant_id", "operation"],
)

# Customer Context Vault metrics (Phase 11 - T161-T166)

# T161: Derivation chain depth tracking
DERIVATION_CHAIN_DEPTH = Histogram(
    "soldier_derivation_chain_depth",
    "Depth of derivation chains traversed",
    labelnames=["tenant_id"],
    buckets=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
)

# T162: Schema validation errors
SCHEMA_VALIDATION_ERRORS = Counter(
    "soldier_schema_validation_errors_total",
    "Total number of schema validation errors",
    labelnames=["tenant_id", "field_name", "error_type"],
)

# T163: Profile field status gauge
FIELD_STATUS_GAUGE = Gauge(
    "soldier_profile_field_status",
    "Number of profile fields by status",
    labelnames=["tenant_id", "status"],
)

# T164: Gap fill attempts (enhanced - complements GAP_FILL_COUNT)
GAP_FILL_ATTEMPTS = Counter(
    "soldier_gap_fill_attempts_total",
    "Total number of gap fill attempts",
    labelnames=["tenant_id", "field_name", "source"],
)

# T165: Schema extraction success
SCHEMA_EXTRACTION_SUCCESS = Counter(
    "soldier_schema_extraction_success_total",
    "Total successful schema extractions",
    labelnames=["tenant_id", "content_type"],
)

# T166: Schema extraction failed
SCHEMA_EXTRACTION_FAILED = Counter(
    "soldier_schema_extraction_failed_total",
    "Total failed schema extractions",
    labelnames=["tenant_id", "content_type", "error_type"],
)

# Background job metrics
WORKFLOW_EXECUTIONS = Counter(
    "soldier_workflow_executions_total",
    "Total workflow executions",
    labelnames=["workflow_name", "status"],
)

WORKFLOW_LATENCY = Histogram(
    "soldier_workflow_latency_seconds",
    "Workflow execution latency in seconds",
    labelnames=["workflow_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


def setup_metrics() -> None:
    """Initialize metrics configuration.

    This function is called at application startup to ensure
    metrics are properly configured. Currently a no-op as
    prometheus_client handles registration automatically.
    """
    # Metrics are auto-registered when defined
    # This function is a hook for future configuration needs
    pass
