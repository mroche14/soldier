# Customer Context Vault - Store Interface Contracts

This document defines the enhanced ProfileStore interface and supporting services.

---

## 1. Enhanced ProfileStore Interface

```python
from abc import ABC, abstractmethod
from uuid import UUID

from focal.conversation.models import Channel
from focal.profile.models import (
    ChannelIdentity,
    CustomerProfile,
    ItemStatus,
    ProfileAsset,
    ProfileField,
    ProfileFieldDefinition,
    ScenarioFieldRequirement,
)


class ProfileStore(ABC):
    """Abstract interface for customer profile storage.

    Enhanced to support:
    - Status-aware queries
    - Lineage traversal
    - Schema management
    - Field history
    """

    # =========================================================================
    # PROFILE CRUD (Original + Enhanced)
    # =========================================================================

    @abstractmethod
    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerProfile | None:
        """Get profile by customer ID.

        Args:
            tenant_id: Tenant identifier
            customer_id: Customer identifier
            include_history: If True, populate field_history and asset_history

        Returns:
            CustomerProfile with active fields/assets, or None if not found
        """
        pass

    @abstractmethod
    async def get_by_id(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerProfile | None:
        """Get profile by profile ID."""
        pass

    @abstractmethod
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
        *,
        include_history: bool = False,
    ) -> CustomerProfile | None:
        """Get profile by channel identity."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile:
        """Get existing profile or create new one for channel identity."""
        pass

    @abstractmethod
    async def save(self, profile: CustomerProfile) -> UUID:
        """Save a profile (create or update)."""
        pass

    @abstractmethod
    async def delete(self, tenant_id: UUID, profile_id: UUID) -> bool:
        """Soft-delete a profile."""
        pass

    # =========================================================================
    # FIELD OPERATIONS (Enhanced with Status)
    # =========================================================================

    @abstractmethod
    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update a profile field.

        If supersede_existing is True and a field with the same name exists:
        - Existing field is marked status=superseded
        - New field is linked via superseded_by_id
        - New field gets status=active

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to update
            field: New field value
            supersede_existing: Whether to supersede existing field

        Returns:
            ID of the new field
        """
        pass

    @abstractmethod
    async def get_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileField | None:
        """Get a specific field by name.

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to query
            field_name: Field name to retrieve
            status: Filter by status (None = any status, returns most recent)

        Returns:
            ProfileField or None
        """
        pass

    @abstractmethod
    async def get_field_history(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
    ) -> list[ProfileField]:
        """Get all versions of a field (all statuses).

        Returns:
            List of ProfileField ordered by collected_at DESC
        """
        pass

    @abstractmethod
    async def expire_stale_fields(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark fields past expires_at as status=expired.

        Args:
            tenant_id: Tenant to process
            profile_id: Specific profile (None = all profiles in tenant)

        Returns:
            Number of fields marked as expired
        """
        pass

    # =========================================================================
    # ASSET OPERATIONS (Enhanced with Status)
    # =========================================================================

    @abstractmethod
    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
        *,
        supersede_existing: bool = False,
    ) -> UUID:
        """Add an asset to profile.

        Args:
            tenant_id: Tenant identifier
            profile_id: Profile to update
            asset: Asset to add
            supersede_existing: If True, supersede existing asset with same name

        Returns:
            ID of the new asset
        """
        pass

    @abstractmethod
    async def get_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_id: UUID,
    ) -> ProfileAsset | None:
        """Get a specific asset by ID."""
        pass

    @abstractmethod
    async def get_asset_by_name(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileAsset | None:
        """Get asset by name with optional status filter."""
        pass

    # =========================================================================
    # LINEAGE OPERATIONS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_derivation_chain(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str,  # "profile_field" or "profile_asset"
    ) -> list[dict]:
        """Get full derivation chain for an item.

        Traverses source_item_id links back to root source.

        Args:
            tenant_id: Tenant identifier
            item_id: Starting item ID
            item_type: Type of item

        Returns:
            List of items in chain, from root to item.
            Each dict has: {id, type, name, source_metadata}
        """
        pass

    @abstractmethod
    async def get_derived_items(
        self,
        tenant_id: UUID,
        source_item_id: UUID,
    ) -> dict[str, list]:
        """Get all items derived from a source.

        Args:
            tenant_id: Tenant identifier
            source_item_id: Source item ID

        Returns:
            Dict with "fields" and "assets" lists
        """
        pass

    @abstractmethod
    async def check_has_dependents(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Check if an item has dependent derived items.

        Used to prevent hard-delete of items with dependents.
        """
        pass

    # =========================================================================
    # CHANNEL OPERATIONS (Original)
    # =========================================================================

    @abstractmethod
    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        identity: ChannelIdentity,
    ) -> bool:
        """Link a new channel identity to profile."""
        pass

    @abstractmethod
    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_profile_id: UUID,
        target_profile_id: UUID,
    ) -> bool:
        """Merge source profile into target profile.

        - All channel identities moved to target
        - All fields/assets moved to target
        - Source profile is soft-deleted
        - Maintains lineage references
        """
        pass

    # =========================================================================
    # SCHEMA OPERATIONS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_field_definitions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[ProfileFieldDefinition]:
        """Get all field definitions for an agent."""
        pass

    @abstractmethod
    async def get_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> ProfileFieldDefinition | None:
        """Get a specific field definition by name."""
        pass

    @abstractmethod
    async def save_field_definition(
        self,
        definition: ProfileFieldDefinition,
    ) -> UUID:
        """Save a field definition."""
        pass

    @abstractmethod
    async def delete_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> bool:
        """Delete a field definition."""
        pass

    # =========================================================================
    # SCENARIO REQUIREMENTS (NEW)
    # =========================================================================

    @abstractmethod
    async def get_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Get field requirements for a scenario/step.

        Args:
            tenant_id: Tenant identifier
            scenario_id: Scenario to query
            step_id: Optional step filter (None = scenario-wide only)

        Returns:
            List of requirements ordered by collection_order
        """
        pass

    @abstractmethod
    async def save_scenario_requirement(
        self,
        requirement: ScenarioFieldRequirement,
    ) -> UUID:
        """Save a scenario field requirement."""
        pass

    @abstractmethod
    async def delete_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> int:
        """Delete requirements for a scenario/step.

        Returns:
            Number of requirements deleted
        """
        pass

    @abstractmethod
    async def get_missing_fields(
        self,
        tenant_id: UUID,
        profile: CustomerProfile,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> list[ScenarioFieldRequirement]:
        """Get requirements not satisfied by the profile.

        Checks:
        - Field exists with status=active
        - Field meets freshness requirements
        - Field verified if required

        Args:
            tenant_id: Tenant identifier
            profile: Customer profile to check
            scenario_id: Scenario to check against
            step_id: Optional step filter
            required_level: Filter by level ("hard", "soft", or None for all)

        Returns:
            List of unmet requirements
        """
        pass
```

---

## 2. CachedProfileStore Wrapper

```python
from datetime import timedelta
from typing import Any

from focal.profile.store import ProfileStore


class CachedProfileStore(ProfileStore):
    """Redis-cached ProfileStore wrapper.

    Implements two-tier caching:
    - Redis (hot cache, TTL-based)
    - PostgreSQL (persistent storage)

    Cache invalidation strategy:
    - Read operations check cache first
    - Write operations invalidate cache after DB write
    - Background job handles TTL-based expiry
    """

    def __init__(
        self,
        backend: ProfileStore,
        redis_client: Any,  # redis.asyncio.Redis
        cache_ttl: timedelta = timedelta(minutes=30),
        field_defs_ttl: timedelta = timedelta(hours=1),
    ) -> None:
        """Initialize cached store.

        Args:
            backend: Underlying ProfileStore (e.g., PostgresProfileStore)
            redis_client: Async Redis client
            cache_ttl: TTL for profile cache
            field_defs_ttl: TTL for field definitions cache
        """
        self._backend = backend
        self._redis = redis_client
        self._cache_ttl = cache_ttl
        self._field_defs_ttl = field_defs_ttl

    def _profile_key(self, tenant_id: UUID, customer_id: UUID) -> str:
        """Generate cache key for profile."""
        return f"profile:{tenant_id}:{customer_id}"

    def _field_defs_key(self, tenant_id: UUID, agent_id: UUID) -> str:
        """Generate cache key for field definitions."""
        return f"field_defs:{tenant_id}:{agent_id}"

    def _scenario_reqs_key(self, tenant_id: UUID, scenario_id: UUID) -> str:
        """Generate cache key for scenario requirements."""
        return f"scenario_reqs:{tenant_id}:{scenario_id}"

    async def _get_cached_profile(
        self,
        tenant_id: UUID,
        customer_id: UUID,
    ) -> CustomerProfile | None:
        """Get profile from cache."""
        key = self._profile_key(tenant_id, customer_id)
        data = await self._redis.get(key)
        if data:
            return CustomerProfile.model_validate_json(data)
        return None

    async def _cache_profile(
        self,
        profile: CustomerProfile,
    ) -> None:
        """Cache a profile."""
        key = self._profile_key(profile.tenant_id, profile.customer_id)
        await self._redis.setex(
            key,
            int(self._cache_ttl.total_seconds()),
            profile.model_dump_json(),
        )

    async def _invalidate_profile(
        self,
        tenant_id: UUID,
        customer_id: UUID,
    ) -> None:
        """Invalidate profile cache."""
        key = self._profile_key(tenant_id, customer_id)
        await self._redis.delete(key)

    # =========================================================================
    # PROFILE CRUD (Cached)
    # =========================================================================

    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_history: bool = False,
    ) -> CustomerProfile | None:
        """Get profile with cache check."""
        # History queries bypass cache (too complex to cache efficiently)
        if include_history:
            return await self._backend.get_by_customer_id(
                tenant_id, customer_id, include_history=True
            )

        # Try cache first
        cached = await self._get_cached_profile(tenant_id, customer_id)
        if cached:
            return cached

        # Cache miss - load from backend
        profile = await self._backend.get_by_customer_id(
            tenant_id, customer_id, include_history=False
        )
        if profile:
            await self._cache_profile(profile)

        return profile

    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: ProfileField,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update field and invalidate cache."""
        # Get customer_id for cache invalidation
        profile = await self._backend.get_by_id(tenant_id, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Update in backend
        field_id = await self._backend.update_field(
            tenant_id, profile_id, field, supersede_existing=supersede_existing
        )

        # Invalidate cache
        await self._invalidate_profile(tenant_id, profile.customer_id)

        return field_id

    # ... (other methods follow same pattern: delegate to backend, invalidate on write)
```

---

## 3. SchemaValidationService

```python
import re
from typing import Any

from focal.profile.models import ProfileField, ProfileFieldDefinition


class SchemaValidationError(Exception):
    """Raised when field validation fails."""

    def __init__(self, field_name: str, errors: list[str]) -> None:
        self.field_name = field_name
        self.errors = errors
        super().__init__(f"Validation failed for {field_name}: {errors}")


class SchemaValidationService:
    """Validates ProfileFields against ProfileFieldDefinitions."""

    def __init__(self, profile_store: ProfileStore) -> None:
        self._store = profile_store
        self._definition_cache: dict[str, ProfileFieldDefinition] = {}

    async def get_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> ProfileFieldDefinition | None:
        """Get field definition with caching."""
        cache_key = f"{tenant_id}:{agent_id}:{field_name}"
        if cache_key not in self._definition_cache:
            definition = await self._store.get_field_definition(
                tenant_id, agent_id, field_name
            )
            if definition:
                self._definition_cache[cache_key] = definition
        return self._definition_cache.get(cache_key)

    def validate_field(
        self,
        field: ProfileField,
        definition: ProfileFieldDefinition,
    ) -> list[str]:
        """Validate a field against its definition.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Type validation
        if not self._validate_type(field.value, definition.value_type):
            errors.append(
                f"Value type mismatch: expected {definition.value_type}, "
                f"got {type(field.value).__name__}"
            )

        # Regex validation
        if definition.validation_regex and isinstance(field.value, str):
            if not re.match(definition.validation_regex, field.value):
                errors.append(
                    f"Value does not match pattern: {definition.validation_regex}"
                )

        # Allowed values validation
        if definition.allowed_values and field.value not in definition.allowed_values:
            errors.append(
                f"Value not in allowed values: {definition.allowed_values}"
            )

        # Verification requirement
        if definition.required_verification and not field.verified:
            errors.append("Field requires verification but is not verified")

        return errors

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "date": lambda v: isinstance(v, str),  # ISO format string
            "email": lambda v: isinstance(v, str) and "@" in v,
            "phone": lambda v: isinstance(v, str),
            "json": lambda v: isinstance(v, (dict, list)),
        }
        checker = type_checks.get(expected_type, lambda v: True)
        return checker(value)

    async def validate_and_raise(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field: ProfileField,
    ) -> None:
        """Validate field and raise if invalid."""
        definition = await self.get_definition(tenant_id, agent_id, field.name)
        if definition:
            errors = self.validate_field(field, definition)
            if errors:
                raise SchemaValidationError(field.name, errors)
```

---

## 4. Enhanced GapFillService Integration

```python
from focal.alignment.migration.gap_fill import GapFillService
from focal.profile.models import ScenarioFieldRequirement, FallbackAction


class EnhancedGapFillService(GapFillService):
    """GapFillService enhanced with schema-driven requirements."""

    def __init__(
        self,
        profile_store: ProfileStore,
        llm_executor: Any = None,
        schema_validator: SchemaValidationService | None = None,
    ) -> None:
        super().__init__(profile_store, llm_executor)
        self._schema_validator = schema_validator

    async def fill_scenario_requirements(
        self,
        session: "Session",
        scenario_id: UUID,
        step_id: UUID | None = None,
    ) -> dict[str, "GapFillResult"]:
        """Fill all missing fields for a scenario/step.

        Uses ScenarioFieldRequirement to determine what's needed,
        ProfileFieldDefinition for collection prompts.

        Args:
            session: Current session
            scenario_id: Scenario to check
            step_id: Optional step filter

        Returns:
            Dict mapping field_name to GapFillResult
        """
        # Get customer profile
        profile = await self._profile_store.get_by_id(
            session.tenant_id,
            session.customer_profile_id,
        )
        if not profile:
            return {}

        # Get missing requirements
        missing = await self._profile_store.get_missing_fields(
            tenant_id=session.tenant_id,
            profile=profile,
            scenario_id=scenario_id,
            step_id=step_id,
        )

        results = {}
        for req in missing:
            # Get field definition for collection hints
            definition = await self._profile_store.get_field_definition(
                session.tenant_id,
                session.agent_id,
                req.field_name,
            )

            # Try to fill based on fallback action
            result = await self._fill_by_strategy(
                session=session,
                requirement=req,
                definition=definition,
            )
            results[req.field_name] = result

        return results

    async def _fill_by_strategy(
        self,
        session: "Session",
        requirement: ScenarioFieldRequirement,
        definition: ProfileFieldDefinition | None,
    ) -> "GapFillResult":
        """Fill field based on requirement's fallback action."""

        if requirement.fallback_action == FallbackAction.EXTRACT:
            # Try LLM extraction first
            result = await self.try_conversation_extraction(
                field_name=requirement.field_name,
                session=session,
                field_type=definition.value_type if definition else "string",
                field_description=definition.description if definition else None,
            )
            if result.filled:
                # Track lineage
                result.source_item_type = SourceType.SESSION
                result.source_metadata = {
                    "session_id": str(session.session_id),
                    "extraction_method": "llm",
                }
                return result

        # Standard gap fill (profile -> session -> extraction)
        result = await self.fill_gap(
            field_name=requirement.field_name,
            session=session,
            field_type=definition.value_type if definition else "string",
            field_description=definition.description if definition else None,
        )

        # Attach field definition for caller
        result.field_definition = definition

        return result
```

---

## 5. Configuration (TOML)

```toml
# config/default.toml

[profile]
# Store backend
store_provider = "postgres"  # "postgres", "inmemory"

# Redis caching
cache_enabled = true
cache_ttl_seconds = 1800           # 30 minutes
field_definitions_ttl_seconds = 3600  # 1 hour
scenario_requirements_ttl_seconds = 3600

# Schema validation
validation_enabled = true
validation_strict = false  # If true, reject unknown fields

# Expiry management
auto_expire_enabled = true
expire_check_interval_seconds = 300  # 5 minutes

# Lineage
lineage_tracking_enabled = true
max_derivation_chain_depth = 10

# Privacy
auto_encrypt_pii = true
pii_encryption_key_id = "${PROFILE_PII_ENCRYPTION_KEY}"

[profile.freshness]
# Default freshness settings (can be overridden per field)
default_freshness_seconds = 0  # 0 = never stale
stale_field_action = "warn"    # "warn", "block", "ignore"
```

---

## 6. Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Cache metrics
PROFILE_CACHE_HITS = Counter(
    "profile_cache_hits_total",
    "Profile cache hit count",
    ["tenant_id"],
)

PROFILE_CACHE_MISSES = Counter(
    "profile_cache_misses_total",
    "Profile cache miss count",
    ["tenant_id"],
)

PROFILE_CACHE_INVALIDATIONS = Counter(
    "profile_cache_invalidations_total",
    "Profile cache invalidation count",
    ["tenant_id", "reason"],
)

# Lineage metrics
DERIVATION_CHAIN_DEPTH = Histogram(
    "profile_derivation_chain_depth",
    "Depth of derivation chains traversed",
    ["tenant_id"],
    buckets=[1, 2, 3, 5, 10, 20],
)

# Schema metrics
SCHEMA_VALIDATION_ERRORS = Counter(
    "profile_schema_validation_errors_total",
    "Schema validation error count",
    ["tenant_id", "field_name", "error_type"],
)

# Status metrics
FIELD_STATUS_GAUGE = Gauge(
    "profile_fields_by_status",
    "Count of fields by status",
    ["tenant_id", "status"],
)

# Gap fill metrics
GAP_FILL_ATTEMPTS = Counter(
    "gap_fill_attempts_total",
    "Gap fill attempt count",
    ["tenant_id", "scenario_id", "source"],
)

GAP_FILL_SUCCESS_RATE = Gauge(
    "gap_fill_success_rate",
    "Gap fill success rate",
    ["tenant_id", "scenario_id"],
)
```
