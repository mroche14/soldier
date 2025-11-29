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


def setup_metrics() -> None:
    """Initialize metrics configuration.

    This function is called at application startup to ensure
    metrics are properly configured. Currently a no-op as
    prometheus_client handles registration automatically.
    """
    # Metrics are auto-registered when defined
    # This function is a hook for future configuration needs
    pass
