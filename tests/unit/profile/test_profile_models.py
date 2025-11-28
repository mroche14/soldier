"""Tests for profile domain models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from soldier.conversation.models import Channel
from soldier.profile import (
    ChannelIdentity,
    Consent,
    CustomerProfile,
    ProfileAsset,
    ProfileField,
    ProfileFieldSource,
    VerificationLevel,
)


class TestCustomerProfile:
    """Tests for CustomerProfile model."""

    def test_create_valid_profile(self) -> None:
        """Should create a valid customer profile."""
        profile = CustomerProfile(
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
        profile = CustomerProfile(
            tenant_id=uuid4(),
            channel_identities=[identity],
        )
        assert len(profile.channel_identities) == 1
        assert profile.channel_identities[0].verified is True

    def test_profile_with_fields(self) -> None:
        """Should create profile with fields."""
        field = ProfileField(
            name="email",
            value="user@example.com",
            value_type="email",
            source=ProfileFieldSource.USER_PROVIDED,
        )
        profile = CustomerProfile(
            tenant_id=uuid4(),
            fields={"email": field},
        )
        assert "email" in profile.fields
        assert profile.fields["email"].value == "user@example.com"

    def test_profile_verification_levels(self) -> None:
        """Should accept all verification levels."""
        for level in VerificationLevel:
            profile = CustomerProfile(
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
            verified_at=datetime.now(timezone.utc),
            primary=True,
        )
        assert identity.verified is True
        assert identity.verified_at is not None


class TestProfileField:
    """Tests for ProfileField model."""

    def test_create_valid_field(self) -> None:
        """Should create a valid profile field."""
        field = ProfileField(
            name="first_name",
            value="John",
            value_type="string",
            source=ProfileFieldSource.LLM_EXTRACTED,
        )
        assert field.name == "first_name"
        assert field.value == "John"
        assert field.confidence == 1.0

    def test_field_with_provenance(self) -> None:
        """Should track provenance."""
        field = ProfileField(
            name="order_preference",
            value="express_shipping",
            value_type="string",
            source=ProfileFieldSource.TOOL_RESULT,
            source_session_id=uuid4(),
            source_scenario_id=uuid4(),
            confidence=0.85,
        )
        assert field.source_session_id is not None
        assert field.confidence == 0.85

    def test_all_field_sources(self) -> None:
        """Should accept all field sources."""
        for source in ProfileFieldSource:
            field = ProfileField(
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
            granted_at=datetime.now(timezone.utc),
        )
        assert consent.granted is True
        assert consent.revoked_at is None

    def test_create_revoked_consent(self) -> None:
        """Should create a revoked consent."""
        consent = Consent(
            consent_type="data_sharing",
            granted=False,
            granted_at=datetime.now(timezone.utc),
            revoked_at=datetime.now(timezone.utc),
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
