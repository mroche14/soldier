"""Tests for profile domain models."""

from datetime import UTC, datetime
from uuid import uuid4

from soldier.conversation.models import Channel
from soldier.customer_data import (
    ChannelIdentity,
    Consent,
    CustomerDataStore,
    ProfileAsset,
    VariableEntry,
    VariableSource,
    VerificationLevel,
)
from soldier.customer_data.enums import (
    FallbackAction,
    ItemStatus,
    RequiredLevel,
    SourceType,
    ValidationMode,
)
from soldier.customer_data.models import (
    CustomerDataField,
    ScenarioFieldRequirement,
)


class TestCustomerProfile:
    """Tests for CustomerDataStore model."""

    def test_create_valid_profile(self) -> None:
        """Should create a valid customer profile."""
        profile = CustomerDataStore(
            tenant_id=uuid4(),
        )
        assert profile.verification_level == VerificationLevel.UNVERIFIED
        assert len(profile.channel_identities) == 0
        assert len(profile.fields) == 0

    def test_profile_with_channel_identities(self) -> None:
        """Should create profile with channel identities."""
        identity = ChannelIdentity(
            channel=Channel.WHATSAPP,
            channel_user_id="+1234567890",
            verified=True,
            primary=True,
        )
        profile = CustomerDataStore(
            tenant_id=uuid4(),
            channel_identities=[identity],
        )
        assert len(profile.channel_identities) == 1
        assert profile.channel_identities[0].verified is True

    def test_profile_with_fields(self) -> None:
        """Should create profile with fields."""
        field = VariableEntry(
            name="email",
            value="user@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        profile = CustomerDataStore(
            tenant_id=uuid4(),
            fields={"email": field},
        )
        assert "email" in profile.fields
        assert profile.fields["email"].value == "user@example.com"

    def test_profile_verification_levels(self) -> None:
        """Should accept all verification levels."""
        for level in VerificationLevel:
            profile = CustomerDataStore(
                tenant_id=uuid4(),
                verification_level=level,
            )
            assert profile.verification_level == level


class TestChannelIdentity:
    """Tests for ChannelIdentity model."""

    def test_create_valid_identity(self) -> None:
        """Should create a valid channel identity."""
        identity = ChannelIdentity(
            channel=Channel.EMAIL,
            channel_user_id="user@example.com",
        )
        assert identity.channel == Channel.EMAIL
        assert identity.verified is False
        assert identity.primary is False

    def test_verified_identity(self) -> None:
        """Should track verification."""
        identity = ChannelIdentity(
            channel=Channel.WHATSAPP,
            channel_user_id="+1234567890",
            verified=True,
            verified_at=datetime.now(UTC),
            primary=True,
        )
        assert identity.verified is True
        assert identity.verified_at is not None


class TestProfileField:
    """Tests for VariableEntry model."""

    def test_create_valid_field(self) -> None:
        """Should create a valid profile field."""
        field = VariableEntry(
            name="first_name",
            value="John",
            value_type="string",
            source=VariableSource.LLM_EXTRACTED,
        )
        assert field.name == "first_name"
        assert field.value == "John"
        assert field.confidence == 1.0

    def test_field_with_provenance(self) -> None:
        """Should track provenance."""
        field = VariableEntry(
            name="order_preference",
            value="express_shipping",
            value_type="string",
            source=VariableSource.TOOL_RESULT,
            source_session_id=uuid4(),
            source_scenario_id=uuid4(),
            confidence=0.85,
        )
        assert field.source_session_id is not None
        assert field.confidence == 0.85

    def test_all_field_sources(self) -> None:
        """Should accept all field sources."""
        for source in VariableSource:
            field = VariableEntry(
                name="test",
                value="value",
                value_type="string",
                source=source,
            )
            assert field.source == source


class TestProfileAsset:
    """Tests for ProfileAsset model."""

    def test_create_valid_asset(self) -> None:
        """Should create a valid profile asset."""
        asset = ProfileAsset(
            name="ID Document",
            asset_type="image",
            storage_provider="s3",
            storage_path="bucket/path/doc.jpg",
            mime_type="image/jpeg",
            size_bytes=102400,
            checksum="abc123hash",
        )
        assert asset.name == "ID Document"
        assert asset.size_bytes == 102400
        assert asset.retention_policy == "permanent"

    def test_asset_with_verification(self) -> None:
        """Should track verification."""
        asset = ProfileAsset(
            name="Passport",
            asset_type="pdf",
            storage_provider="gcs",
            storage_path="bucket/passport.pdf",
            mime_type="application/pdf",
            size_bytes=204800,
            checksum="xyz789hash",
            verified=True,
            verification_result={"status": "valid", "expiry": "2030-01-01"},
        )
        assert asset.verified is True
        assert asset.verification_result["status"] == "valid"


class TestConsent:
    """Tests for Consent model."""

    def test_create_granted_consent(self) -> None:
        """Should create a granted consent."""
        consent = Consent(
            consent_type="marketing",
            granted=True,
            granted_at=datetime.now(UTC),
        )
        assert consent.granted is True
        assert consent.revoked_at is None

    def test_create_revoked_consent(self) -> None:
        """Should create a revoked consent."""
        consent = Consent(
            consent_type="data_sharing",
            granted=False,
            granted_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        assert consent.granted is False
        assert consent.revoked_at is not None

    def test_consent_with_session_context(self) -> None:
        """Should track session context."""
        consent = Consent(
            consent_type="terms_of_service",
            granted=True,
            source_session_id=uuid4(),
            ip_address="192.168.1.1",
        )
        assert consent.source_session_id is not None
        assert consent.ip_address == "192.168.1.1"


class TestItemStatusEnum:
    """Tests for ItemStatus enum (T020)."""

    def test_all_status_values_exist(self) -> None:
        """Should have all expected status values."""
        assert ItemStatus.ACTIVE == "active"
        assert ItemStatus.SUPERSEDED == "superseded"
        assert ItemStatus.EXPIRED == "expired"
        assert ItemStatus.ORPHANED == "orphaned"

    def test_status_is_string_enum(self) -> None:
        """Status values should be strings."""
        for status in ItemStatus:
            assert isinstance(status.value, str)


class TestSourceTypeEnum:
    """Tests for SourceType enum."""

    def test_all_source_types_exist(self) -> None:
        """Should have all expected source types."""
        assert SourceType.PROFILE_FIELD == "profile_field"
        assert SourceType.PROFILE_ASSET == "profile_asset"
        assert SourceType.SESSION == "session"
        assert SourceType.TOOL == "tool"
        assert SourceType.EXTERNAL == "external"


class TestValidationModeEnum:
    """Tests for ValidationMode enum."""

    def test_all_modes_exist(self) -> None:
        """Should have all expected validation modes."""
        assert ValidationMode.STRICT == "strict"
        assert ValidationMode.WARN == "warn"
        assert ValidationMode.DISABLED == "disabled"


class TestProfileFieldLineageAndStatus:
    """Tests for VariableEntry lineage and status fields (T021)."""

    def test_field_has_id(self) -> None:
        """VariableEntry should have unique ID."""
        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
        )
        assert field.id is not None

    def test_field_default_status_is_active(self) -> None:
        """VariableEntry should default to ACTIVE status."""
        field = VariableEntry(
            name="name",
            value="John",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
        )
        assert field.status == ItemStatus.ACTIVE

    def test_field_with_lineage(self) -> None:
        """VariableEntry should track lineage."""
        source_id = uuid4()
        field = VariableEntry(
            name="extracted_name",
            value="Jane Doe",
            value_type="string",
            source=VariableSource.DOCUMENT_EXTRACTED,
            source_item_id=source_id,
            source_item_type=SourceType.PROFILE_ASSET,
            source_metadata={"tool": "ocr", "confidence": 0.95},
        )
        assert field.source_item_id == source_id
        assert field.source_item_type == SourceType.PROFILE_ASSET
        assert field.source_metadata["tool"] == "ocr"

    def test_field_superseded_status(self) -> None:
        """VariableEntry should track superseded status."""
        new_field_id = uuid4()
        field = VariableEntry(
            name="phone",
            value="+1234567890",
            value_type="phone",
            source=VariableSource.USER_PROVIDED,
            status=ItemStatus.SUPERSEDED,
            superseded_by_id=new_field_id,
            superseded_at=datetime.now(UTC),
        )
        assert field.status == ItemStatus.SUPERSEDED
        assert field.superseded_by_id == new_field_id
        assert field.superseded_at is not None

    def test_field_is_orphaned_property(self) -> None:
        """VariableEntry.is_orphaned should return True when status is ORPHANED."""
        field = VariableEntry(
            name="derived_field",
            value="data",
            value_type="string",
            source=VariableSource.TOOL_RESULT,
            status=ItemStatus.ORPHANED,
        )
        assert field.is_orphaned is True

    def test_field_not_orphaned_when_active(self) -> None:
        """VariableEntry.is_orphaned should return False when status is ACTIVE."""
        field = VariableEntry(
            name="active_field",
            value="data",
            value_type="string",
            source=VariableSource.USER_PROVIDED,
            status=ItemStatus.ACTIVE,
        )
        assert field.is_orphaned is False

    def test_field_definition_id_reference(self) -> None:
        """VariableEntry should reference field definition."""
        def_id = uuid4()
        field = VariableEntry(
            name="email",
            value="test@example.com",
            value_type="email",
            source=VariableSource.USER_PROVIDED,
            field_definition_id=def_id,
        )
        assert field.field_definition_id == def_id


class TestProfileAssetLineageAndStatus:
    """Tests for ProfileAsset lineage and status fields (T022)."""

    def test_asset_default_status_is_active(self) -> None:
        """ProfileAsset should default to ACTIVE status."""
        asset = ProfileAsset(
            name="document",
            asset_type="pdf",
            storage_provider="s3",
            storage_path="path/to/doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum="abc123",
        )
        assert asset.status == ItemStatus.ACTIVE

    def test_asset_with_lineage(self) -> None:
        """ProfileAsset should track lineage."""
        source_id = uuid4()
        asset = ProfileAsset(
            name="thumbnail",
            asset_type="image",
            storage_provider="s3",
            storage_path="path/to/thumb.jpg",
            mime_type="image/jpeg",
            size_bytes=512,
            checksum="xyz789",
            source_item_id=source_id,
            source_item_type=SourceType.PROFILE_ASSET,
            derived_from_tool="image_resize",
        )
        assert asset.source_item_id == source_id
        assert asset.source_item_type == SourceType.PROFILE_ASSET
        assert asset.derived_from_tool == "image_resize"

    def test_asset_analysis_field_ids(self) -> None:
        """ProfileAsset should track derived field IDs."""
        field_ids = [uuid4(), uuid4()]
        asset = ProfileAsset(
            name="id_card",
            asset_type="image",
            storage_provider="s3",
            storage_path="path/to/id.jpg",
            mime_type="image/jpeg",
            size_bytes=2048,
            checksum="hash123",
            analysis_field_ids=field_ids,
        )
        assert len(asset.analysis_field_ids) == 2
        assert field_ids[0] in asset.analysis_field_ids

    def test_asset_is_orphaned_property(self) -> None:
        """ProfileAsset.is_orphaned should work correctly."""
        asset = ProfileAsset(
            name="orphaned_asset",
            asset_type="pdf",
            storage_provider="s3",
            storage_path="path/to/orphan.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum="orphan123",
            status=ItemStatus.ORPHANED,
        )
        assert asset.is_orphaned is True


class TestProfileFieldDefinition:
    """Tests for CustomerDataField model (T023)."""

    def test_create_valid_definition(self) -> None:
        """Should create valid field definition."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="email",
            display_name="Email Address",
            value_type="email",
        )
        assert definition.name == "email"
        assert definition.enabled is True

    def test_definition_with_validation_regex(self) -> None:
        """Should support regex validation."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="phone",
            display_name="Phone Number",
            value_type="phone",
            validation_regex=r"^\+?[1-9]\d{1,14}$",
        )
        assert definition.validation_regex is not None

    def test_definition_with_allowed_values(self) -> None:
        """Should support allowed values."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="country",
            display_name="Country",
            value_type="string",
            allowed_values=["US", "UK", "CA"],
        )
        assert len(definition.allowed_values) == 3

    def test_definition_with_collection_prompt(self) -> None:
        """Should support collection prompts for gap fill."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="date_of_birth",
            display_name="Date of Birth",
            value_type="date",
            collection_prompt="What is your date of birth?",
            extraction_examples=["1990-01-15", "1985-06-22"],
        )
        assert definition.collection_prompt is not None
        assert len(definition.extraction_examples) == 2

    def test_definition_pii_classification(self) -> None:
        """Should support PII classification."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="ssn",
            display_name="Social Security Number",
            value_type="string",
            is_pii=True,
            encryption_required=True,
            retention_days=365,
        )
        assert definition.is_pii is True
        assert definition.encryption_required is True
        assert definition.retention_days == 365

    def test_definition_freshness(self) -> None:
        """Should support freshness settings."""
        definition = CustomerDataField(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            name="credit_score",
            display_name="Credit Score",
            value_type="number",
            freshness_seconds=86400,  # 1 day
        )
        assert definition.freshness_seconds == 86400


class TestScenarioFieldRequirement:
    """Tests for ScenarioFieldRequirement model (T024)."""

    def test_create_valid_requirement(self) -> None:
        """Should create valid requirement."""
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            field_name="email",
        )
        assert requirement.required_level == RequiredLevel.HARD
        assert requirement.fallback_action == FallbackAction.ASK

    def test_requirement_with_soft_level(self) -> None:
        """Should support soft requirements."""
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            field_name="preferred_name",
            required_level=RequiredLevel.SOFT,
            fallback_action=FallbackAction.SKIP,
        )
        assert requirement.required_level == RequiredLevel.SOFT
        assert requirement.fallback_action == FallbackAction.SKIP

    def test_requirement_with_step_binding(self) -> None:
        """Should support step-level binding."""
        step_id = uuid4()
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            step_id=step_id,
            field_name="verification_code",
        )
        assert requirement.step_id == step_id

    def test_requirement_with_condition(self) -> None:
        """Should support conditional requirements."""
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            field_name="passport_number",
            when_condition='order_type == "international"',
            depends_on_fields=["country"],
        )
        assert requirement.when_condition is not None
        assert "country" in requirement.depends_on_fields

    def test_requirement_collection_order(self) -> None:
        """Should support collection order."""
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            field_name="secondary_email",
            collection_order=5,
        )
        assert requirement.collection_order == 5

    def test_requirement_human_review_flag(self) -> None:
        """Should support needs_human_review flag."""
        requirement = ScenarioFieldRequirement(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scenario_id=uuid4(),
            field_name="auto_extracted",
            needs_human_review=True,
            extraction_confidence=0.75,
        )
        assert requirement.needs_human_review is True
        assert requirement.extraction_confidence == 0.75
