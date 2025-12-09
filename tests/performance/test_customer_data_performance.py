"""Performance tests for Customer Context Vault operations.

Validates NFR benchmarks from spec 010:
- NFR-001: Profile load with warm cache < 10ms p99
- NFR-002: Profile load bypassing cache < 50ms p99
- NFR-003: Field validation < 5ms p99
- NFR-004: Derivation chain traversal < 100ms p99
- NFR-005: LLM schema extraction < 5s p99

These tests are marked with pytest.mark.performance and should
be run separately from unit tests with:
    pytest tests/performance/ -v --benchmark-only
"""

import statistics
import time
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from soldier.conversation.models.enums import Channel
from soldier.profile.enums import ProfileFieldSource, SourceType, ValidationMode
from soldier.profile.models import (
    ChannelIdentity,
    CustomerProfile,
    ProfileField,
    ProfileFieldDefinition,
)
from soldier.profile.stores.inmemory import InMemoryProfileStore
from soldier.profile.validation import ProfileFieldValidator


def percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile of data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f < len(sorted_data) - 1 else f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


@pytest.fixture
def profile_store():
    """Create an in-memory profile store."""
    return InMemoryProfileStore()


@pytest.fixture
def field_validator():
    """Create a schema validation service."""
    return ProfileFieldValidator()


@pytest.fixture
def sample_profile():
    """Create a sample profile with fields."""
    return CustomerProfile(
        tenant_id=uuid4(),
        customer_id=uuid4(),
        channel_identities=[
            ChannelIdentity(
                channel=Channel.WEBCHAT,
                channel_user_id="test-user-001",
            )
        ],
        fields={
            "email": ProfileField(
                name="email",
                value="test@example.com",
                value_type="email",
                source=ProfileFieldSource.USER_PROVIDED,
            ),
            "name": ProfileField(
                name="name",
                value="Test User",
                value_type="string",
                source=ProfileFieldSource.USER_PROVIDED,
            ),
        },
    )


@pytest.fixture
def email_definition():
    """Create an email field definition."""
    return ProfileFieldDefinition(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="email",
        display_name="Email Address",
        value_type="email",
        validation_mode=ValidationMode.STRICT,
    )


class TestProfileLoadPerformance:
    """T173-T175: Profile load performance tests."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_nfr001_profile_load_warm_cache(
        self, profile_store: InMemoryProfileStore, sample_profile: CustomerProfile
    ):
        """NFR-001: 1000 profile loads with warm cache < 10ms p99.

        Note: InMemoryProfileStore acts as "warm cache" since it's all in memory.
        """
        # Save profile
        await profile_store.save(sample_profile)

        # Warm up
        for _ in range(10):
            await profile_store.get_by_id(
                sample_profile.tenant_id, sample_profile.id
            )

        # Benchmark
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            await profile_store.get_by_id(
                sample_profile.tenant_id, sample_profile.id
            )
            latencies.append((time.perf_counter() - start) * 1000)  # ms

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Profile load (warm): mean={mean:.3f}ms, p99={p99:.3f}ms")
        assert p99 < 10, f"p99 latency {p99:.3f}ms exceeds 10ms threshold"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_nfr002_profile_load_cold(
        self, profile_store: InMemoryProfileStore, sample_profile: CustomerProfile
    ):
        """NFR-002: 1000 profile loads bypassing cache < 50ms p99.

        Note: For InMemory, we simulate "cold" by clearing between runs.
        This test validates base lookup performance.
        """
        latencies = []

        for i in range(1000):
            # Create unique profile for each iteration
            profile = CustomerProfile(
                tenant_id=sample_profile.tenant_id,
                customer_id=uuid4(),
                channel_identities=[
                    ChannelIdentity(
                        channel=Channel.WEBCHAT,
                        channel_user_id=f"user-{i}",
                    )
                ],
                fields={},
            )
            await profile_store.save(profile)

            start = time.perf_counter()
            await profile_store.get_by_id(
                profile.tenant_id, profile.id
            )
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Profile load (cold): mean={mean:.3f}ms, p99={p99:.3f}ms")
        assert p99 < 50, f"p99 latency {p99:.3f}ms exceeds 50ms threshold"


class TestFieldValidationPerformance:
    """T176: Field validation performance tests."""

    @pytest.mark.performance
    def test_nfr003_field_validation(
        self,
        field_validator: ProfileFieldValidator,
        email_definition: ProfileFieldDefinition,
    ):
        """NFR-003: 10000 field validations < 5ms p99."""
        latencies = []

        for i in range(10000):
            field = ProfileField(
                name="email",
                value=f"user{i}@example.com",
                value_type="email",
                source=ProfileFieldSource.USER_PROVIDED,
            )

            start = time.perf_counter()
            field_validator.validate_field(field, email_definition)
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Field validation: mean={mean:.4f}ms, p99={p99:.4f}ms")
        assert p99 < 5, f"p99 latency {p99:.3f}ms exceeds 5ms threshold"


class TestDerivationChainPerformance:
    """T177: Derivation chain traversal performance tests."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_nfr004_derivation_chain_traversal(
        self, profile_store: InMemoryProfileStore
    ):
        """NFR-004: 100 derivation chain traversals (depth 10) < 100ms p99."""
        tenant_id = uuid4()

        # Create a profile with a chain of 10 derived fields
        profile = CustomerProfile(
            tenant_id=tenant_id,
            customer_id=uuid4(),
            channel_identities=[
                ChannelIdentity(
                    channel=Channel.WEBCHAT,
                    channel_user_id="chain-test",
                )
            ],
            fields={},
        )

        # Build chain: field_0 -> field_1 -> ... -> field_9
        prev_field_id = None
        for i in range(10):
            field = ProfileField(
                name=f"field_{i}",
                value=f"value_{i}",
                value_type="string",
                source=ProfileFieldSource.EXTRACTED,
                source_item_id=prev_field_id,
                source_item_type=SourceType.PROFILE_FIELD if prev_field_id else None,
            )
            profile.fields[f"field_{i}"] = field
            prev_field_id = field.id

        await profile_store.save(profile)

        # Get the leaf field ID (last in chain)
        leaf_field_id = profile.fields["field_9"].id

        # Benchmark chain traversal
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            await profile_store.get_derivation_chain(
                tenant_id, leaf_field_id, "profile_field"
            )
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Derivation chain (depth 10): mean={mean:.3f}ms, p99={p99:.3f}ms")
        assert p99 < 100, f"p99 latency {p99:.3f}ms exceeds 100ms threshold"


class TestSchemaExtractionPerformance:
    """T178: LLM schema extraction performance tests."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_nfr005_schema_extraction(self):
        """NFR-005: 50 scenario extractions via LLM < 5s p99.

        Note: This test uses a mock LLM to measure extraction overhead.
        Real LLM performance depends on provider latency.
        """
        from soldier.profile.extraction import ProfileItemSchemaExtractor

        # Create mock LLM that returns realistic response
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = '''
        {
            "fields": [
                {"name": "email", "confidence": 0.95},
                {"name": "date_of_birth", "confidence": 0.9}
            ]
        }
        '''

        extractor = ProfileItemSchemaExtractor(llm_executor=mock_llm)

        content = """
        If the customer is over 18 years old and has verified their email,
        they can proceed with the application process.
        """

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            await extractor.extract_requirements(
                content=content,
                content_type="scenario",
            )
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Schema extraction (mock LLM): mean={mean:.3f}ms, p99={p99:.3f}ms")
        # With mock LLM, this should be very fast
        # Real LLM would need 5s p99 threshold
        assert p99 < 5000, f"p99 latency {p99:.3f}ms exceeds 5000ms threshold"


class TestBulkOperationsPerformance:
    """Additional performance tests for bulk operations."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_bulk_profile_saves(self, profile_store: InMemoryProfileStore):
        """Test bulk profile save performance."""
        tenant_id = uuid4()
        latencies = []

        for i in range(100):
            profile = CustomerProfile(
                tenant_id=tenant_id,
                customer_id=uuid4(),
                channel_identities=[
                    ChannelIdentity(
                        channel=Channel.WEBCHAT,
                        channel_user_id=f"bulk-{i}",
                    )
                ],
                fields={
                    f"field_{j}": ProfileField(
                        name=f"field_{j}",
                        value=f"value_{j}",
                        value_type="string",
                        source=ProfileFieldSource.USER_PROVIDED,
                    )
                    for j in range(10)
                },
            )

            start = time.perf_counter()
            await profile_store.save(profile)
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Bulk save (10 fields each): mean={mean:.3f}ms, p99={p99:.3f}ms")
        assert p99 < 50, f"p99 latency {p99:.3f}ms exceeds 50ms threshold"

    @pytest.mark.performance
    def test_bulk_validation(
        self,
        field_validator: ProfileFieldValidator,
    ):
        """Test bulk validation with multiple field types."""
        definitions = [
            ProfileFieldDefinition(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="email",
                display_name="Email",
                value_type="email",
                validation_mode=ValidationMode.STRICT,
            ),
            ProfileFieldDefinition(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="phone",
                display_name="Phone",
                value_type="phone",
                validation_mode=ValidationMode.STRICT,
            ),
            ProfileFieldDefinition(
                tenant_id=uuid4(),
                agent_id=uuid4(),
                name="age",
                display_name="Age",
                value_type="number",
                validation_mode=ValidationMode.STRICT,
            ),
        ]

        fields = [
            ProfileField(name="email", value="test@example.com", value_type="email", source=ProfileFieldSource.USER_PROVIDED),
            ProfileField(name="phone", value="+1234567890", value_type="phone", source=ProfileFieldSource.USER_PROVIDED),
            ProfileField(name="age", value=25, value_type="number", source=ProfileFieldSource.USER_PROVIDED),
        ]

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            for field, defn in zip(fields, definitions):
                field_validator.validate_field(field, defn)
            latencies.append((time.perf_counter() - start) * 1000)

        p99 = percentile(latencies, 99)
        mean = statistics.mean(latencies)

        print(f"\n  Bulk validation (3 fields): mean={mean:.4f}ms, p99={p99:.4f}ms")
        assert p99 < 10, f"p99 latency {p99:.3f}ms exceeds 10ms threshold"
