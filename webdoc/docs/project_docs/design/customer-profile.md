# Customer Profile

The Customer Profile is a **persistent, cross-session, cross-scenario store** of known facts about a customer (interlocutor). It bridges the gap between ephemeral session variables and unstructured memory.

## Problem Statement

Current data scopes in the system:

| Scope | Lifetime | Use Case |
|-------|----------|----------|
| Session variables | Single conversation | Temporary workflow state |
| Memory (Episodes) | Per session | Conversation recall |
| Agent config | Permanent | Behavior definitions |

**Missing**: A place to store **verified customer facts** that persist across sessions and can be referenced by any scenario.

### Real-World Examples

1. **Customer provides email in Session 1** (returns scenario)
   - Session 2 (support scenario) shouldn't ask again

2. **KYC documents uploaded in Session 1**
   - Session 2 should know identity is verified
   - The documents themselves should be retrievable

3. **Customer states they're a vegetarian**
   - All future product recommendations should respect this

4. **Phone number verified via OTP**
   - Don't re-verify in future sessions

---

## Design

### CustomerProfile Model

```python
class CustomerProfile(BaseModel):
    """Persistent store of verified facts about a customer.

    Stored via ProfileStore interface. Implementations:
    - PostgresProfileStore (relational)
    - MongoDBProfileStore (document)
    - DynamoDBProfileStore (key-value)

    Isolation: tenant_id + customer_id (not session-scoped)
    """
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID

    # Customer identity (channel-independent)
    customer_id: UUID = Field(default_factory=uuid4)

    # Channel identifiers (multiple channels can map to same customer)
    channel_identities: List[ChannelIdentity] = []

    # Core profile fields (structured)
    fields: Dict[str, ProfileField] = {}

    # Attached assets (documents, images, etc.)
    assets: List[ProfileAsset] = []

    # Verification status
    verification_level: VerificationLevel = VerificationLevel.UNVERIFIED

    # Consent tracking
    consents: List[Consent] = []

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_interaction_at: Optional[datetime] = None


class ChannelIdentity(BaseModel):
    """A customer's identity on a specific channel."""
    channel: Channel
    channel_user_id: str  # Phone number, email, etc.
    verified: bool = False
    verified_at: Optional[datetime] = None
    primary: bool = False  # Primary contact for this channel type


class ProfileField(BaseModel):
    """A single fact about a customer."""
    name: str                          # e.g., "email", "date_of_birth", "dietary_preference"
    value: Any                         # The actual value
    value_type: str                    # "string", "date", "number", "boolean", "json"

    # Provenance
    source: ProfileFieldSource         # How we learned this
    source_session_id: Optional[UUID] = None
    source_scenario_id: Optional[UUID] = None
    source_step_id: Optional[UUID] = None

    # Verification
    verified: bool = False
    verification_method: Optional[str] = None  # "otp", "document", "human_review"
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None          # Agent ID or human reviewer

    # Confidence (for LLM-extracted values)
    confidence: float = 1.0            # 0.0 - 1.0
    requires_confirmation: bool = False

    # Lifecycle
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # For time-sensitive data


class ProfileFieldSource(str, Enum):
    """How a profile field was populated."""
    USER_PROVIDED = "user_provided"        # Customer explicitly stated
    LLM_EXTRACTED = "llm_extracted"        # Extracted from conversation
    TOOL_RESULT = "tool_result"            # From external system (CRM, etc.)
    DOCUMENT_EXTRACTED = "document_extracted"  # From uploaded document
    HUMAN_ENTERED = "human_entered"        # Manual entry by support agent
    SYSTEM_INFERRED = "system_inferred"    # Derived from other data


class ProfileAsset(BaseModel):
    """A document or media attached to a customer profile."""
    id: UUID = Field(default_factory=uuid4)
    name: str                          # "id_card_front", "proof_of_address"
    asset_type: str                    # "image", "pdf", "document"

    # Storage reference (actual storage is external)
    storage_provider: str              # "s3", "gcs", "azure_blob"
    storage_path: str                  # Bucket/path reference

    # Metadata
    mime_type: str
    size_bytes: int
    checksum: str                      # SHA256 for integrity

    # Provenance
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_in_session_id: Optional[UUID] = None
    uploaded_in_scenario_id: Optional[UUID] = None

    # Verification
    verified: bool = False
    verification_result: Optional[Dict[str, Any]] = None  # OCR results, etc.

    # Retention
    retention_policy: str = "permanent"  # "permanent", "session_end", "30_days"
    expires_at: Optional[datetime] = None


class VerificationLevel(str, Enum):
    """Customer identity verification status."""
    UNVERIFIED = "unverified"          # No verification performed
    EMAIL_VERIFIED = "email_verified"  # Email confirmed
    PHONE_VERIFIED = "phone_verified"  # Phone confirmed via OTP
    DOCUMENT_VERIFIED = "document_verified"  # ID document validated
    KYC_COMPLETE = "kyc_complete"      # Full KYC process completed


class Consent(BaseModel):
    """Record of customer consent for data processing."""
    consent_type: str                  # "marketing", "data_processing", "third_party_sharing"
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    source_session_id: Optional[UUID] = None
    ip_address: Optional[str] = None   # For audit
```

---

## Profile Field Definitions (Schema)

Scenarios can **declare required fields** that should be persisted to the profile. This creates a schema of expected customer data.

```python
class ProfileFieldDefinition(AgentScopedModel):
    """Definition of a profile field that scenarios can require.

    Stored via ConfigStore. Defines what customer data can be collected.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]*$", max_length=50)
    display_name: str                  # "Email Address", "Date of Birth"
    description: Optional[str] = None

    # Type and validation
    value_type: str                    # "string", "email", "phone", "date", "number", "boolean"
    validation_regex: Optional[str] = None
    validation_tool_id: Optional[str] = None  # Tool for complex validation

    # Collection settings
    required_verification: bool = False
    verification_methods: List[str] = []  # ["otp", "document"]

    # Privacy
    is_pii: bool = False               # Personally Identifiable Information
    encryption_required: bool = False
    retention_days: Optional[int] = None  # Auto-delete after N days

    # Extraction hints for LLM (used by gap fill in scenario-update-methods.md)
    extraction_examples: List[str] = []  # Example values: ["john@example.com", "jane.doe@company.org"]
    extraction_prompt_hint: Optional[str] = None  # "Look for email patterns like name@domain"
    collection_prompt: Optional[str] = None  # "What is your email address?"


class ScenarioFieldRequirement(BaseModel):
    """A scenario's requirement for a profile field."""
    field_name: str                    # References ProfileFieldDefinition.name
    required_at_step_id: Optional[UUID] = None  # If null, required at scenario entry
    required: bool = True              # False = optional but will use if available
    fallback_action: str = "ask"       # "ask", "skip", "block"
```

---

## Integration with Scenarios

### Scenario Model Update

```python
class Scenario(AgentScopedModel):
    # ... existing fields ...

    # Profile field requirements
    required_fields: List[ScenarioFieldRequirement] = []

    # Fields this scenario may collect (for documentation/audit)
    collects_fields: List[str] = []
```

### ScenarioStep Model Update

```python
class ScenarioStep(BaseModel):
    # ... existing fields ...

    # Profile fields required to enter this step
    required_profile_fields: List[str] = []

    # Profile fields this step collects
    collects_profile_fields: List[str] = []

    # If true, collected fields are persisted to CustomerProfile
    persist_to_profile: bool = True
```

---

## ProfileStore Interface

```python
class ProfileStore(ABC):
    """Interface for customer profile persistence."""

    @abstractmethod
    async def get_by_customer_id(
        self,
        tenant_id: UUID,
        customer_id: UUID,
    ) -> CustomerProfile | None:
        """Get profile by customer ID."""
        pass

    @abstractmethod
    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile | None:
        """Find profile by channel identity (e.g., phone number)."""
        pass

    @abstractmethod
    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> CustomerProfile:
        """Get existing or create new profile for a channel identity."""
        pass

    @abstractmethod
    async def update_field(
        self,
        profile_id: UUID,
        field: ProfileField,
    ) -> None:
        """Update a single profile field."""
        pass

    @abstractmethod
    async def add_asset(
        self,
        profile_id: UUID,
        asset: ProfileAsset,
    ) -> None:
        """Attach an asset to the profile."""
        pass

    @abstractmethod
    async def merge_profiles(
        self,
        primary_id: UUID,
        secondary_id: UUID,
    ) -> CustomerProfile:
        """Merge two profiles (e.g., when linking channels)."""
        pass

    @abstractmethod
    async def link_channel(
        self,
        profile_id: UUID,
        channel_identity: ChannelIdentity,
    ) -> None:
        """Link a new channel identity to an existing profile."""
        pass
```

---

## Session-Profile Linking

When a session starts, it's linked to a CustomerProfile:

```python
class Session(BaseModel):
    # ... existing fields ...

    # Link to persistent customer profile
    customer_profile_id: Optional[UUID] = None

    # Snapshot of profile fields at session start (for migration safety)
    profile_snapshot_version: Optional[int] = None
```

### Session Initialization Flow

```python
async def initialize_session(
    tenant_id: UUID,
    agent_id: UUID,
    channel: Channel,
    channel_user_id: str,
) -> Session:
    """Initialize a session, linking to CustomerProfile."""

    # Get or create customer profile
    profile = await profile_store.get_or_create(
        tenant_id=tenant_id,
        channel=channel,
        channel_user_id=channel_user_id,
    )

    session = Session(
        tenant_id=tenant_id,
        agent_id=agent_id,
        channel=channel,
        user_channel_id=channel_user_id,
        customer_profile_id=profile.id,
        # ... other fields
    )

    return session
```

---

## Usage in ScenarioFilter

The CustomerProfile simplifies scenario entry and migration:

### Scenario Entry with Profile Check

```python
async def check_scenario_entry(
    context: Context,
    session: Session,
    config: ScenarioFilterConfig,
) -> ScenarioFilterResult:
    """Check if conversation should enter a scenario."""

    # ... existing matching logic ...

    if best.score >= config.entry_threshold:
        scenario = await config_store.get_scenario(best.scenario_id)

        # Check if profile has required fields
        profile = await profile_store.get_by_customer_id(
            session.tenant_id,
            session.customer_profile_id,
        )

        missing_fields = check_required_fields(scenario, profile)

        if missing_fields and scenario.entry_requires_all_fields:
            # Can't enter scenario yet - need to collect fields first
            return ScenarioFilterResult(
                scenario_action="none",
                confidence=best.score,
                reasoning=f"Missing required fields: {missing_fields}",
                missing_profile_fields=missing_fields,  # New field
            )

        return ScenarioFilterResult(
            scenario_action="start",
            target_scenario_id=scenario.id,
            target_step_id=scenario.entry_step_id,
            confidence=best.score,
            reasoning=f"Matched scenario '{scenario.name}'",
        )
```

### Profile-Aware Step Transition

```python
async def evaluate_step_transition(
    context: Context,
    current_step: ScenarioStep,
    profile: CustomerProfile,
) -> bool:
    """Check if transition is allowed based on profile state."""

    for field_name in current_step.required_profile_fields:
        field = profile.fields.get(field_name)

        if field is None:
            return False  # Missing required field

        if current_step.requires_verified_fields and not field.verified:
            return False  # Field not verified

    return True
```

---

## Benefits for Scenario Migration

With CustomerProfile, scenario migrations (from the scenario-update-methods.md) become simpler:

### Gap Fill Becomes Trivial

**Before**: LLM scans conversation history to extract missing values
**After**: Check CustomerProfile for the required field

```python
async def gap_fill_check(
    scenario_v2: Scenario,
    inserted_step: ScenarioStep,
    profile: CustomerProfile,
) -> GapFillResult:
    """Check if gap can be filled from profile."""

    required_fields = inserted_step.required_profile_fields

    for field_name in required_fields:
        field = profile.fields.get(field_name)

        if field is not None:
            # Already have this data - gap is filled
            continue

        # Don't have it - need to ask
        return GapFillResult(
            can_skip=False,
            missing_field=field_name,
            action="ask_user",
        )

    return GapFillResult(can_skip=True)
```

### Re-Routing Uses Profile State

```python
async def evaluate_new_fork(
    fork_step: ScenarioStep,
    profile: CustomerProfile,
) -> str:
    """Determine which branch to take based on profile."""

    # Example: age check fork
    age = profile.fields.get("date_of_birth")
    if age and calculate_age(age.value) < 18:
        return "underage_branch"
    else:
        return "adult_branch"
```

---

## Configuration

```toml
[profile]
store_provider = "postgres"  # "postgres", "mongodb", "dynamodb"

# Field extraction from conversations
auto_extract_fields = true
extraction_confidence_threshold = 0.8
require_confirmation_below = 0.9

# Verification
default_verification_required = false

# Privacy
encrypt_pii_fields = true
pii_encryption_key_id = "kms://customer-data-key"

# Retention
# default_retention_days = <unset>  # unset = permanent
asset_retention_days = 365
```

---

## Privacy and Compliance Considerations

### GDPR/CCPA Support

```python
async def export_customer_data(profile_id: UUID) -> CustomerDataExport:
    """Export all data for a customer (GDPR data portability)."""
    pass

async def delete_customer_data(profile_id: UUID) -> None:
    """Delete all customer data (GDPR right to erasure)."""
    pass

async def anonymize_customer_data(profile_id: UUID) -> None:
    """Anonymize customer data (retain for analytics, remove PII)."""
    pass
```

### Audit Trail

All profile changes are logged:

```python
class ProfileAuditEntry(BaseModel):
    """Audit log for profile changes."""
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID
    action: str  # "field_updated", "asset_added", "verification_completed"
    field_name: Optional[str] = None
    old_value_hash: Optional[str] = None  # Hash, not value (for PII)
    new_value_hash: Optional[str] = None
    actor: str  # "system", "agent:{id}", "user", "human:{id}"
    session_id: Optional[UUID] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
```

---

## Relationship to Other Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA SCOPE HIERARCHY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  TENANT SCOPE                                                        │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │  AGENT SCOPE                                                 │    │    │
│  │  │  - Scenarios, Rules, Templates, Variables (definitions)      │    │    │
│  │  │  - ProfileFieldDefinitions (schema)                          │    │    │
│  │  │                                                               │    │    │
│  │  │  ┌─────────────────────────────────────────────────────┐    │    │    │
│  │  │  │  CUSTOMER SCOPE (NEW)                                │    │    │    │
│  │  │  │  - CustomerProfile                                   │    │    │    │
│  │  │  │  - ProfileFields (verified facts)                    │    │    │    │
│  │  │  │  - ProfileAssets (documents)                         │    │    │    │
│  │  │  │  - Consents                                          │    │    │    │
│  │  │  │                                                       │    │    │    │
│  │  │  │  ┌─────────────────────────────────────────────┐    │    │    │    │
│  │  │  │  │  SESSION SCOPE                               │    │    │    │    │
│  │  │  │  │  - Session state                             │    │    │    │    │
│  │  │  │  │  - Scenario navigation                       │    │    │    │    │
│  │  │  │  │  - Session variables (ephemeral)             │    │    │    │    │
│  │  │  │  │  - Episodes (conversation memory)            │    │    │    │    │
│  │  │  │  └─────────────────────────────────────────────┘    │    │    │    │
│  │  │  │                                                       │    │    │    │
│  │  │  └─────────────────────────────────────────────────────┘    │    │    │
│  │  │                                                               │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## See Also

- [Domain Model](./domain-model.md) - Core entity definitions
- [Scenario Update Methods](./scenario-update-methods.md) - How profile enables migrations
- [Alignment Engine](../architecture/alignment-engine.md) - Scenario navigation
