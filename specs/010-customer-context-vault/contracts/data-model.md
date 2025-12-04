# Customer Context Vault - Data Model Contracts

This document defines the enhanced data models for the Customer Context Vault hybrid design.

---

## 1. Enhanced ProfileField

```python
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ItemStatus(str, Enum):
    """Explicit lifecycle status for profile data."""
    ACTIVE = "active"           # Current, valid value
    SUPERSEDED = "superseded"   # Replaced by newer value
    EXPIRED = "expired"         # Past expires_at timestamp
    ORPHANED = "orphaned"       # Source item was deleted


class SourceType(str, Enum):
    """Type of source for derived data."""
    PROFILE_FIELD = "profile_field"   # Derived from another field
    PROFILE_ASSET = "profile_asset"   # Derived from an asset (e.g., OCR)
    SESSION = "session"               # Extracted from conversation
    TOOL = "tool"                     # From tool execution
    EXTERNAL = "external"             # From external system


class ProfileField(BaseModel):
    """Single customer fact with lineage and status tracking.

    Enhanced from original to support:
    - Derivation lineage via source_item_id
    - Explicit status management
    - Schema reference for validation
    """
    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique field instance ID")
    name: str = Field(..., description="Field key (e.g., 'email', 'legal_name')")

    # Value
    value: Any = Field(..., description="Field value")
    value_type: str = Field(..., description="Type: string, date, number, boolean, json")

    # Provenance (original)
    source: ProfileFieldSource = Field(..., description="How obtained")
    source_session_id: UUID | None = Field(default=None, description="Source session")
    source_scenario_id: UUID | None = Field(default=None, description="Source scenario")
    source_step_id: UUID | None = Field(default=None, description="Source step")

    # Lineage (NEW - from CCV)
    source_item_id: UUID | None = Field(
        default=None,
        description="ID of ProfileField or ProfileAsset this was derived from"
    )
    source_item_type: SourceType | None = Field(
        default=None,
        description="Type of source item for derivation chain traversal"
    )
    source_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context about derivation (e.g., tool name, extraction quote)"
    )

    # Status (NEW - from CCV)
    status: ItemStatus = Field(
        default=ItemStatus.ACTIVE,
        description="Lifecycle status: active, superseded, or expired"
    )
    superseded_by_id: UUID | None = Field(
        default=None,
        description="ID of the field that replaced this one"
    )
    superseded_at: datetime | None = Field(
        default=None,
        description="When this field was superseded"
    )

    # Verification (original)
    verified: bool = Field(default=False, description="Is verified")
    verification_method: str | None = Field(default=None, description="How verified")
    verified_at: datetime | None = Field(default=None, description="Verification time")
    verified_by: str | None = Field(default=None, description="Who verified")

    # Confidence (original)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    requires_confirmation: bool = Field(default=False, description="Needs user confirm")

    # Timestamps
    collected_at: datetime = Field(default_factory=utc_now, description="Collection time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")
    expires_at: datetime | None = Field(default=None, description="Expiration time")

    # Schema reference (NEW)
    field_definition_id: UUID | None = Field(
        default=None,
        description="Reference to ProfileFieldDefinition for validation"
    )

    # Computed property (NEW)
    @property
    def is_orphaned(self) -> bool:
        """True if source_item_id references a non-existent item.

        Note: This must be computed by the store layer by checking
        if source_item_id exists. The property here is for documentation.
        In practice, status=ORPHANED is set by background job.
        """
        return self.status == ItemStatus.ORPHANED
```

---

## 2. Enhanced ProfileAsset

```python
class ProfileAsset(BaseModel):
    """Document/media attached to profile with lineage and status tracking.

    Enhanced from original to support:
    - Derivation lineage (asset-to-asset, e.g., thumbnail from original)
    - Explicit status management
    - Analysis results linkage
    """
    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    name: str = Field(..., description="Asset name (e.g., 'id_card_front')")
    asset_type: str = Field(..., description="Type: image, pdf, document, audio")

    # Storage
    storage_provider: str = Field(..., description="Storage backend")
    storage_path: str = Field(..., description="Storage location")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size")
    checksum: str = Field(..., description="SHA256 hash")

    # Provenance (original)
    uploaded_at: datetime = Field(default_factory=utc_now, description="Upload time")
    uploaded_in_session_id: UUID | None = Field(default=None, description="Upload session")
    uploaded_in_scenario_id: UUID | None = Field(default=None, description="Upload scenario")

    # Lineage (NEW - from CCV)
    source_item_id: UUID | None = Field(
        default=None,
        description="ID of ProfileAsset this was derived from (e.g., thumbnail from original)"
    )
    source_item_type: SourceType | None = Field(
        default=None,
        description="Type of source item"
    )
    derived_from_tool: str | None = Field(
        default=None,
        description="Tool that created this derived asset (e.g., 'image_resize')"
    )

    # Status (NEW - from CCV)
    status: ItemStatus = Field(
        default=ItemStatus.ACTIVE,
        description="Lifecycle status: active, superseded, or expired"
    )
    superseded_by_id: UUID | None = Field(default=None)
    superseded_at: datetime | None = Field(default=None)

    # Verification (original)
    verified: bool = Field(default=False, description="Is verified")
    verification_result: dict[str, Any] | None = Field(
        default=None,
        description="Verification data (e.g., OCR results)"
    )

    # Retention (original)
    retention_policy: str = Field(default="permanent", description="Retention rule")
    expires_at: datetime | None = Field(default=None, description="Expiration time")

    # Analysis linkage (NEW)
    analysis_field_ids: list[UUID] = Field(
        default_factory=list,
        description="ProfileField IDs derived from this asset (e.g., OCR extractions)"
    )

    # Computed property (NEW)
    @property
    def is_orphaned(self) -> bool:
        """True if source_item_id references a non-existent item.

        Note: This must be computed by the store layer by checking
        if source_item_id exists. The property here is for documentation.
        In practice, status=ORPHANED is set by background job.
        """
        return self.status == ItemStatus.ORPHANED
```

---

## 3. ProfileFieldDefinition (Schema)

```python
class ProfileFieldDefinition(BaseModel):
    """Definition of a profile field that can be collected.

    Agent-scoped schema that defines:
    - What data can be collected
    - How to validate it
    - How to collect it (prompts)
    - Privacy classification
    """
    # Identity
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")

    # Definition
    name: str = Field(
        ...,
        pattern=r"^[a-z_][a-z0-9_]*$",
        max_length=50,
        description="Field key (must match ProfileField.name)"
    )
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Field purpose")

    # Type and Validation
    value_type: str = Field(
        ...,
        description="Type: string, email, phone, date, number, boolean, json"
    )
    validation_regex: str | None = Field(
        default=None,
        description="Regex for value validation"
    )
    validation_tool_id: str | None = Field(
        default=None,
        description="Tool ID for complex validation"
    )
    allowed_values: list[str] | None = Field(
        default=None,
        description="Enum-like allowed values"
    )

    # Collection Settings
    required_verification: bool = Field(
        default=False,
        description="Must be verified to be considered complete"
    )
    verification_methods: list[str] = Field(
        default_factory=list,
        description="Allowed verification methods: otp, document, human_review"
    )

    # Collection Prompts (for GapFillService)
    collection_prompt: str | None = Field(
        default=None,
        description="Prompt to ask customer for this field"
    )
    extraction_examples: list[str] = Field(
        default_factory=list,
        description="Example values for LLM extraction"
    )
    extraction_prompt_hint: str | None = Field(
        default=None,
        description="Hint for LLM extraction from conversation"
    )

    # Privacy Classification
    is_pii: bool = Field(default=False, description="Personally Identifiable Information")
    encryption_required: bool = Field(default=False, description="Requires encryption at rest")
    retention_days: int | None = Field(
        default=None,
        description="Auto-expire after N days (None = permanent)"
    )

    # Freshness (from CCV)
    freshness_seconds: int | None = Field(
        default=None,
        description="Max age before considered stale (None = never stale)"
    )

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    enabled: bool = Field(default=True)
```

---

## 4. ScenarioFieldRequirement

```python
class RequiredLevel(str, Enum):
    """How strictly a field is required."""
    HARD = "hard"   # Must have to proceed
    SOFT = "soft"   # Nice to have, can proceed without


class FallbackAction(str, Enum):
    """What to do when a required field is missing."""
    ASK = "ask"       # Ask the customer
    SKIP = "skip"     # Proceed without (soft requirements only)
    BLOCK = "block"   # Block scenario entry
    EXTRACT = "extract"  # Try LLM extraction from conversation


class ScenarioFieldRequirement(BaseModel):
    """Binding between a scenario/step and required profile fields.

    Defines what customer data is needed for a scenario to execute.
    Used by GapFillService and ScenarioFilter.
    """
    # Identity
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(..., description="Owning tenant")
    agent_id: UUID = Field(..., description="Owning agent")

    # Binding
    scenario_id: UUID = Field(..., description="Scenario requiring this field")
    step_id: UUID | None = Field(
        default=None,
        description="Specific step (None = scenario-wide requirement)"
    )
    rule_id: UUID | None = Field(
        default=None,
        description="Specific rule (for rule-scoped requirements)"
    )

    # Requirement
    field_name: str = Field(
        ...,
        description="ProfileFieldDefinition.name that is required"
    )
    required_level: RequiredLevel = Field(
        default=RequiredLevel.HARD,
        description="How strictly required"
    )
    fallback_action: FallbackAction = Field(
        default=FallbackAction.ASK,
        description="What to do if missing"
    )

    # Conditional Requirements
    when_condition: str | None = Field(
        default=None,
        description="Expression for conditional requirement (e.g., 'order_type == \"international\"')"
    )
    depends_on_fields: list[str] = Field(
        default_factory=list,
        description="Other fields that must be present for this to apply"
    )

    # Priority
    collection_order: int = Field(
        default=0,
        description="Order in which to collect if multiple fields missing (lower = first)"
    )

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

---

## 5. Enhanced CustomerProfile

```python
class CustomerProfile(BaseModel):
    """Persistent customer data container.

    Enhanced with:
    - Field status summary for quick status checks
    - Lineage query helpers
    """
    # Identity
    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    tenant_id: UUID = Field(..., description="Owning tenant")
    customer_id: UUID = Field(default_factory=uuid4, description="Customer identifier")

    # Channel identities (original)
    channel_identities: list[ChannelIdentity] = Field(
        default_factory=list,
        description="Channel mappings"
    )

    # Profile data with status tracking
    fields: dict[str, ProfileField] = Field(
        default_factory=dict,
        description="Profile fields (keyed by name, only ACTIVE fields)"
    )
    field_history: dict[str, list[ProfileField]] = Field(
        default_factory=dict,
        description="Historical field versions (all statuses)"
    )

    # Assets with status tracking
    assets: list[ProfileAsset] = Field(
        default_factory=list,
        description="Attached documents (only ACTIVE)"
    )
    asset_history: list[ProfileAsset] = Field(
        default_factory=list,
        description="Historical asset versions (all statuses)"
    )

    # Verification and consent (original)
    verification_level: VerificationLevel = Field(
        default=VerificationLevel.UNVERIFIED,
        description="Identity status"
    )
    consents: list[Consent] = Field(
        default_factory=list,
        description="Consent records"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now, description="Creation time")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update")
    last_interaction_at: datetime | None = Field(default=None, description="Last activity")

    # Status summary (NEW - computed)
    @property
    def active_field_count(self) -> int:
        """Count of active fields."""
        return len(self.fields)

    @property
    def expired_field_count(self) -> int:
        """Count of expired fields across history."""
        return sum(
            1 for versions in self.field_history.values()
            for f in versions if f.status == ItemStatus.EXPIRED
        )

    # Lineage helpers (NEW)
    def get_derived_fields(self, source_item_id: UUID) -> list[ProfileField]:
        """Get all fields derived from a specific source."""
        return [
            f for f in self.fields.values()
            if f.source_item_id == source_item_id
        ]

    def get_derivation_chain(self, field_name: str) -> list[UUID]:
        """Get full derivation chain for a field (source IDs from root to field)."""
        chain = []
        field = self.fields.get(field_name)
        visited = set()

        while field and field.source_item_id and field.source_item_id not in visited:
            visited.add(field.source_item_id)
            chain.insert(0, field.source_item_id)
            # Look up source (could be field or asset)
            if field.source_item_type == SourceType.PROFILE_FIELD:
                field = next(
                    (f for f in self.fields.values() if f.id == field.source_item_id),
                    None
                )
            else:
                break  # Asset or external source - end of chain

        return chain
```

---

## 6. Database Schema (PostgreSQL)

### customer_profiles

```sql
CREATE TABLE customer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    verification_level VARCHAR(50) NOT NULL DEFAULT 'unverified',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction_at TIMESTAMPTZ,

    CONSTRAINT uq_profile_customer UNIQUE (tenant_id, customer_id)
);

CREATE INDEX idx_profiles_tenant ON customer_profiles(tenant_id);
CREATE INDEX idx_profiles_customer ON customer_profiles(tenant_id, customer_id);
```

### profile_fields

```sql
CREATE TABLE profile_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    tenant_id UUID NOT NULL,

    -- Field identity
    name VARCHAR(50) NOT NULL,
    value JSONB NOT NULL,
    value_type VARCHAR(50) NOT NULL,

    -- Provenance
    source VARCHAR(50) NOT NULL,
    source_session_id UUID,
    source_scenario_id UUID,
    source_step_id UUID,

    -- Lineage (NEW)
    source_item_id UUID,
    source_item_type VARCHAR(50),
    source_metadata JSONB DEFAULT '{}',

    -- Status (NEW)
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    superseded_by_id UUID REFERENCES profile_fields(id),
    superseded_at TIMESTAMPTZ,

    -- Verification
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_method VARCHAR(100),
    verified_at TIMESTAMPTZ,
    verified_by VARCHAR(255),

    -- Confidence
    confidence FLOAT NOT NULL DEFAULT 1.0,
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Schema reference
    field_definition_id UUID,

    CONSTRAINT chk_status CHECK (status IN ('active', 'superseded', 'expired', 'orphaned')),
    CONSTRAINT chk_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

-- Indexes
CREATE INDEX idx_fields_profile ON profile_fields(profile_id);
CREATE INDEX idx_fields_tenant ON profile_fields(tenant_id);
CREATE INDEX idx_fields_name_active ON profile_fields(profile_id, name) WHERE status = 'active';
CREATE INDEX idx_fields_source_item ON profile_fields(source_item_id) WHERE source_item_id IS NOT NULL;
CREATE INDEX idx_fields_status ON profile_fields(status);
CREATE INDEX idx_fields_expires ON profile_fields(expires_at) WHERE expires_at IS NOT NULL;
```

### profile_assets

```sql
CREATE TABLE profile_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    tenant_id UUID NOT NULL,

    -- Asset identity
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,

    -- Storage
    storage_provider VARCHAR(50) NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    checksum VARCHAR(64) NOT NULL,

    -- Provenance
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uploaded_in_session_id UUID,
    uploaded_in_scenario_id UUID,

    -- Lineage (NEW)
    source_item_id UUID,
    source_item_type VARCHAR(50),
    derived_from_tool VARCHAR(100),

    -- Status (NEW)
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    superseded_by_id UUID REFERENCES profile_assets(id),
    superseded_at TIMESTAMPTZ,

    -- Verification
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_result JSONB,

    -- Retention
    retention_policy VARCHAR(50) NOT NULL DEFAULT 'permanent',
    expires_at TIMESTAMPTZ,

    CONSTRAINT chk_asset_status CHECK (status IN ('active', 'superseded', 'expired', 'orphaned'))
);

CREATE INDEX idx_assets_profile ON profile_assets(profile_id);
CREATE INDEX idx_assets_tenant ON profile_assets(tenant_id);
CREATE INDEX idx_assets_status ON profile_assets(status);
CREATE INDEX idx_assets_source ON profile_assets(source_item_id) WHERE source_item_id IS NOT NULL;
```

### profile_field_definitions

```sql
CREATE TABLE profile_field_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,

    -- Definition
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Validation
    value_type VARCHAR(50) NOT NULL,
    validation_regex VARCHAR(500),
    validation_tool_id VARCHAR(255),
    allowed_values JSONB,

    -- Collection
    required_verification BOOLEAN NOT NULL DEFAULT FALSE,
    verification_methods JSONB DEFAULT '[]',
    collection_prompt TEXT,
    extraction_examples JSONB DEFAULT '[]',
    extraction_prompt_hint TEXT,

    -- Privacy
    is_pii BOOLEAN NOT NULL DEFAULT FALSE,
    encryption_required BOOLEAN NOT NULL DEFAULT FALSE,
    retention_days INTEGER,
    freshness_seconds INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT uq_field_def_name UNIQUE (tenant_id, agent_id, name)
);

CREATE INDEX idx_field_defs_agent ON profile_field_definitions(tenant_id, agent_id);
```

### scenario_field_requirements

```sql
CREATE TABLE scenario_field_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,

    -- Binding
    scenario_id UUID NOT NULL,
    step_id UUID,
    rule_id UUID,

    -- Requirement
    field_name VARCHAR(50) NOT NULL,
    required_level VARCHAR(20) NOT NULL DEFAULT 'hard',
    fallback_action VARCHAR(20) NOT NULL DEFAULT 'ask',

    -- Conditions
    when_condition TEXT,
    depends_on_fields JSONB DEFAULT '[]',
    collection_order INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_required_level CHECK (required_level IN ('hard', 'soft')),
    CONSTRAINT chk_fallback_action CHECK (fallback_action IN ('ask', 'skip', 'block', 'extract'))
);

CREATE INDEX idx_scenario_reqs_scenario ON scenario_field_requirements(tenant_id, scenario_id);
CREATE INDEX idx_scenario_reqs_step ON scenario_field_requirements(step_id) WHERE step_id IS NOT NULL;
```

### channel_identities

> **Note**: This table already exists in migration `005_customer_profiles.py` from Phase 9 (Production Stores).
> No new migration needed for this table. Shown here for completeness.

```sql
CREATE TABLE channel_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    tenant_id UUID NOT NULL,

    channel VARCHAR(50) NOT NULL,
    channel_user_id VARCHAR(255) NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_channel_identity UNIQUE (tenant_id, channel, channel_user_id)
);

CREATE INDEX idx_channel_profile ON channel_identities(profile_id);
CREATE INDEX idx_channel_lookup ON channel_identities(tenant_id, channel, channel_user_id);
```

### consents

```sql
CREATE TABLE consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES customer_profiles(id),
    tenant_id UUID NOT NULL,

    consent_type VARCHAR(100) NOT NULL,
    granted BOOLEAN NOT NULL,
    granted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    source_session_id UUID,
    ip_address VARCHAR(45),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_profile ON consents(profile_id);
```

---

## 7. Cache Key Patterns (Redis)

```python
CACHE_PATTERNS = {
    # Full profile cache
    "profile": "profile:{tenant_id}:{customer_id}",

    # Field definitions cache (agent-scoped)
    "field_definitions": "field_defs:{tenant_id}:{agent_id}",

    # Scenario requirements cache
    "scenario_requirements": "scenario_reqs:{tenant_id}:{scenario_id}",

    # Derivation chain cache (for frequently accessed chains)
    "derivation_chain": "deriv:{tenant_id}:{item_id}",
}

# TTL Configuration
CACHE_TTL = {
    "profile": 1800,              # 30 minutes
    "field_definitions": 3600,    # 1 hour (less frequently changed)
    "scenario_requirements": 3600, # 1 hour
    "derivation_chain": 300,      # 5 minutes (computed, can be stale)
}
```

---

## 8. GapFillResult Enhancement

```python
class GapFillResult(BaseModel):
    """Enhanced result from gap fill operation."""

    field_name: str
    filled: bool
    value: Any | None = None
    source: GapFillSource
    confidence: float = 0.0
    needs_confirmation: bool = False
    extraction_quote: str | None = None

    # NEW: Schema reference
    field_definition: ProfileFieldDefinition | None = None
    validation_errors: list[str] = Field(default_factory=list)

    # NEW: Lineage tracking
    source_item_id: UUID | None = None
    source_item_type: SourceType | None = None
```
