"""Prometheus metrics for Focal.

Provides standard metrics for request tracking, latencies, token usage,
and system health.
"""

from prometheus_client import Counter, Gauge, Histogram

# Request metrics
REQUEST_COUNT = Counter(
    "focal_request_count_total",
    "Total number of requests processed",
    labelnames=["tenant_id", "agent_id", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "focal_request_latency_seconds",
    "Request latency in seconds",
    labelnames=["tenant_id", "agent_id", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# LLM metrics
LLM_TOKENS = Counter(
    "focal_llm_tokens_total",
    "Total LLM tokens used",
    labelnames=["provider", "model", "direction"],
)

# Alignment metrics
RULES_MATCHED = Histogram(
    "focal_rules_matched",
    "Number of rules matched per turn",
    labelnames=["tenant_id", "agent_id"],
    buckets=(0, 1, 2, 3, 5, 10, 20, 50),
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    "focal_active_sessions",
    "Number of active sessions",
    labelnames=["tenant_id", "agent_id"],
)

# Error metrics
ERRORS = Counter(
    "focal_errors_total",
    "Total number of errors",
    labelnames=["tenant_id", "agent_id", "error_type"],
)

# Customer data update metrics (Phase 3)
CUSTOMER_DATA_UPDATES = Counter(
    "focal_customer_data_updates_total",
    "Total customer data updates processed",
    labelnames=["tenant_id", "scope", "is_update"],
)

CUSTOMER_DATA_VALIDATION_ERRORS = Counter(
    "focal_customer_data_validation_errors_total",
    "Customer data validation errors",
    labelnames=["tenant_id", "field_type"],
)

CUSTOMER_DATA_PERSISTENCE_MARKED = Counter(
    "focal_customer_data_persistence_marked_total",
    "Updates marked for persistence",
    labelnames=["tenant_id", "scope"],
)

# Pipeline step metrics
PIPELINE_STEP_LATENCY = Histogram(
    "focal_pipeline_step_latency_seconds",
    "Latency of individual pipeline steps",
    labelnames=["tenant_id", "agent_id", "step"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

# Memory metrics
MEMORY_EPISODES = Gauge(
    "focal_memory_episodes",
    "Number of episodes in memory store",
    labelnames=["tenant_id"],
)

MEMORY_ENTITIES = Gauge(
    "focal_memory_entities",
    "Number of entities in memory store",
    labelnames=["tenant_id"],
)

# Migration metrics
MIGRATION_COUNT = Counter(
    "focal_migration_count_total",
    "Total number of migrations executed",
    labelnames=["tenant_id", "scenario_type", "outcome"],
)

MIGRATION_LATENCY = Histogram(
    "focal_migration_latency_seconds",
    "Migration execution latency in seconds",
    labelnames=["tenant_id", "scenario_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

GAP_FILL_COUNT = Counter(
    "focal_gap_fill_count_total",
    "Total number of gap fills attempted",
    labelnames=["tenant_id", "source", "outcome"],
)

MIGRATION_PLANS_CREATED = Counter(
    "focal_migration_plans_created_total",
    "Total number of migration plans created",
    labelnames=["tenant_id"],
)

MIGRATION_PLANS_DEPLOYED = Counter(
    "focal_migration_plans_deployed_total",
    "Total number of migration plans deployed",
    labelnames=["tenant_id"],
)

# Profile cache metrics
PROFILE_CACHE_HITS = Counter(
    "focal_profile_cache_hits_total",
    "Total number of profile cache hits",
    labelnames=["tenant_id", "cache_key_type"],
)

PROFILE_CACHE_MISSES = Counter(
    "focal_profile_cache_misses_total",
    "Total number of profile cache misses",
    labelnames=["tenant_id", "cache_key_type"],
)

PROFILE_CACHE_INVALIDATIONS = Counter(
    "focal_profile_cache_invalidations_total",
    "Total number of profile cache invalidations",
    labelnames=["tenant_id", "operation"],
)

PROFILE_CACHE_ERRORS = Counter(
    "focal_profile_cache_errors_total",
    "Total number of profile cache errors",
    labelnames=["tenant_id", "operation"],
)

# Customer Context Vault metrics (Phase 11 - T161-T166)

# T161: Derivation chain depth tracking
DERIVATION_CHAIN_DEPTH = Histogram(
    "focal_derivation_chain_depth",
    "Depth of derivation chains traversed",
    labelnames=["tenant_id"],
    buckets=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
)

# T162: Schema validation errors
SCHEMA_VALIDATION_ERRORS = Counter(
    "focal_schema_validation_errors_total",
    "Total number of schema validation errors",
    labelnames=["tenant_id", "field_name", "error_type"],
)

# T163: Profile field status gauge
FIELD_STATUS_GAUGE = Gauge(
    "focal_profile_field_status",
    "Number of profile fields by status",
    labelnames=["tenant_id", "status"],
)

# T164: Gap fill attempts (enhanced - complements GAP_FILL_COUNT)
GAP_FILL_ATTEMPTS = Counter(
    "focal_gap_fill_attempts_total",
    "Total number of gap fill attempts",
    labelnames=["tenant_id", "field_name", "source"],
)

# T165: Schema extraction success
SCHEMA_EXTRACTION_SUCCESS = Counter(
    "focal_schema_extraction_success_total",
    "Total successful schema extractions",
    labelnames=["tenant_id", "content_type"],
)

# T166: Schema extraction failed
SCHEMA_EXTRACTION_FAILED = Counter(
    "focal_schema_extraction_failed_total",
    "Total failed schema extractions",
    labelnames=["tenant_id", "content_type", "error_type"],
)

# Background job metrics
WORKFLOW_EXECUTIONS = Counter(
    "focal_workflow_executions_total",
    "Total workflow executions",
    labelnames=["workflow_name", "status"],
)

WORKFLOW_LATENCY = Histogram(
    "focal_workflow_latency_seconds",
    "Workflow execution latency in seconds",
    labelnames=["workflow_name"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# Retrieval metrics (Phase 4)
RETRIEVAL_DURATION = Histogram(
    "focal_retrieval_duration_seconds",
    "Retrieval duration per object type",
    labelnames=["tenant_id", "object_type", "strategy"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0),
)

HYBRID_RETRIEVAL_ENABLED = Gauge(
    "focal_hybrid_retrieval_enabled",
    "Whether hybrid retrieval is enabled per object type",
    labelnames=["object_type"],
)

BM25_SCORE_CONTRIBUTION = Histogram(
    "focal_bm25_score_contribution",
    "BM25 score contribution to final hybrid scores",
    labelnames=["object_type"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

PARALLEL_RETRIEVAL_DURATION = Histogram(
    "focal_parallel_retrieval_duration_seconds",
    "Total duration of parallel retrieval execution",
    labelnames=["tenant_id", "num_tasks"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5),
)

# Phase 5: Rule Selection & Filtering metrics
RULE_FILTER_EVALUATIONS = Counter(
    "focal_rule_filter_evaluations_total",
    "Total rule evaluations by LLM",
    labelnames=["tenant_id", "agent_id", "applicability"],
)

RULE_FILTER_UNSURE = Counter(
    "focal_rule_filter_unsure_total",
    "Total UNSURE rule evaluations",
    labelnames=["tenant_id", "agent_id", "policy"],
)

RELATIONSHIP_EXPANSION = Counter(
    "focal_relationship_expansion_total",
    "Total relationship expansions",
    labelnames=["tenant_id", "agent_id", "kind"],
)

RELATIONSHIP_EXPANSION_DEPTH = Histogram(
    "focal_relationship_expansion_depth",
    "Relationship expansion depth",
    labelnames=["tenant_id", "agent_id"],
    buckets=[1, 2, 3, 4, 5],
)

RULE_EXCLUSIONS = Counter(
    "focal_rule_exclusions_total",
    "Total rules excluded via relationships",
    labelnames=["tenant_id", "agent_id"],
)

# Phase 6: Scenario Orchestration metrics
SCENARIO_LIFECYCLE_DECISIONS = Counter(
    "focal_scenario_lifecycle_decisions_total",
    "Lifecycle decisions by action",
    labelnames=["action"],  # start, continue, pause, complete, cancel
)

SCENARIO_STEPS_SKIPPED = Counter(
    "focal_scenario_steps_skipped_total",
    "Steps skipped via automatic relocation",
    labelnames=["scenario_name"],
)

SCENARIO_CONTRIBUTIONS = Counter(
    "focal_scenario_contributions_total",
    "Contribution types by scenario",
    labelnames=["contribution_type"],  # ask, inform, confirm, action_hint
)

ACTIVE_SCENARIOS_PER_SESSION = Histogram(
    "focal_active_scenarios_per_session",
    "Number of simultaneous active scenarios",
    buckets=[0, 1, 2, 3, 5, 10],
)

# Phase 8: Response Planning metrics
response_planning_duration = Histogram(
    "focal_response_planning_duration_seconds",
    "Time spent in response planning phase",
    labelnames=["tenant_id"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)

response_type_counter = Counter(
    "focal_response_type_total",
    "Count of response types generated",
    labelnames=["type", "tenant_id"],
)

scenario_contributions_gauge = Histogram(
    "focal_scenario_contributions_count",
    "Number of scenario contributions per turn",
    labelnames=["tenant_id"],
    buckets=(0, 1, 2, 3, 5, 10),
)

constraints_extracted_counter = Counter(
    "focal_response_constraints_extracted_total",
    "Count of constraints extracted from rules",
    labelnames=["constraint_type", "tenant_id"],
)

# Phase 11: Persistence metrics
PERSISTENCE_DURATION = Histogram(
    "focal_persistence_duration_seconds",
    "Time spent in parallel persistence operations",
    labelnames=["operation"],  # session, customer_data, turn_record, parallel
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

PERSISTENCE_OPERATIONS = Counter(
    "focal_persistence_operations_total",
    "Total persistence operations",
    labelnames=["operation", "status"],  # session/audit/profile, success/failure
)

PERSISTENCE_PARALLEL_SAVINGS = Histogram(
    "focal_persistence_parallel_savings_seconds",
    "Time saved by parallel persistence vs sequential",
    buckets=(0.0, 0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5),
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
