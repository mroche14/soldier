"""Unit tests for VariableResolver."""

import pytest

from ruche.brains.focal.phases.execution.variable_resolver import VariableResolver


@pytest.fixture
def resolver() -> VariableResolver:
    return VariableResolver()


@pytest.mark.parametrize(
    "template,variables,expected",
    [
        ("Hello {name}", {"name": "Alice"}, "Hello Alice"),
        ("{greeting} {name}", {"greeting": "Hi", "name": "Bob"}, "Hi Bob"),
        ("Hello {name}", {}, "Hello {name}"),
        ("Code: {{literal}}", {}, "Code: {literal}"),
        ("", {"name": "Alice"}, ""),
        ("Hello world", {"name": "Alice"}, "Hello world"),
    ],
)
def test_resolve_template(resolver: VariableResolver, template: str, variables: dict, expected: str) -> None:
    result = resolver.resolve(template, variables)
    assert result == expected


@pytest.mark.parametrize("invalid_input", [None, 123, ["list"], {"dict": "value"}])
def test_resolve_rejects_invalid_template_type(resolver: VariableResolver, invalid_input) -> None:
    with pytest.raises(TypeError):
        resolver.resolve(invalid_input, {})


# Tests for resolve_variables() method (Phase 7 additions)


@pytest.mark.asyncio
async def test_resolve_from_profile_only(resolver: VariableResolver) -> None:
    """Test resolving variables from customer profile only."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore, VariableEntry
    from ruche.interlocutor_data.enums import ItemStatus, VariableSource
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={
            "name": VariableEntry(name="name", value="Alice", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
            "email": VariableEntry(name="email", value="alice@example.com", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
        }
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={},
    )

    required_vars = {"name", "email"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert known_vars == {"name": "Alice", "email": "alice@example.com"}
    assert len(missing_vars) == 0


@pytest.mark.asyncio
async def test_resolve_from_session_only(resolver: VariableResolver) -> None:
    """Test resolving variables from session only."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={},
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={"session_id": "abc123", "page": "checkout"},
    )

    required_vars = {"session_id", "page"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert known_vars == {"session_id": "abc123", "page": "checkout"}
    assert len(missing_vars) == 0


@pytest.mark.asyncio
async def test_resolve_from_both_profile_priority(resolver: VariableResolver) -> None:
    """Test that profile takes priority over session when both have the same variable."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore, VariableEntry
    from ruche.interlocutor_data.enums import ItemStatus, VariableSource
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={
            "name": VariableEntry(name="name", value="ProfileName", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
        }
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={"name": "SessionName", "other": "value"},
    )

    required_vars = {"name", "other"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    # Profile should take priority
    assert known_vars["name"] == "ProfileName"
    assert known_vars["other"] == "value"
    assert len(missing_vars) == 0


@pytest.mark.asyncio
async def test_partial_resolution_some_missing(resolver: VariableResolver) -> None:
    """Test partial resolution where some variables are missing."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore, VariableEntry
    from ruche.interlocutor_data.enums import ItemStatus, VariableSource
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={
            "name": VariableEntry(name="name", value="Alice", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
        }
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={"email": "alice@example.com"},
    )

    required_vars = {"name", "email", "phone", "address"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert known_vars == {"name": "Alice", "email": "alice@example.com"}
    assert missing_vars == {"phone", "address"}


@pytest.mark.asyncio
async def test_all_missing(resolver: VariableResolver) -> None:
    """Test when all variables are missing."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={},
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={},
    )

    required_vars = {"name", "email", "phone"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert len(known_vars) == 0
    assert missing_vars == {"name", "email", "phone"}


@pytest.mark.asyncio
async def test_all_resolved(resolver: VariableResolver) -> None:
    """Test when all variables are resolved."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore, VariableEntry
    from ruche.interlocutor_data.enums import ItemStatus, VariableSource
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={
            "name": VariableEntry(name="name", value="Alice", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
            "email": VariableEntry(name="email", value="alice@example.com", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
        }
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={"phone": "555-1234"},
    )

    required_vars = {"name", "email", "phone"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert known_vars == {"name": "Alice", "email": "alice@example.com", "phone": "555-1234"}
    assert len(missing_vars) == 0


@pytest.mark.asyncio
async def test_inactive_profile_fields_ignored(resolver: VariableResolver) -> None:
    """Test that inactive profile fields are ignored."""
    from uuid import uuid4
    from ruche.domain.interlocutor.models import InterlocutorDataStore, VariableEntry
    from ruche.interlocutor_data.enums import ItemStatus, VariableSource
    from ruche.conversation.models.session import Session
    from ruche.conversation.models.enums import Channel

    profile = InterlocutorDataStore(
        interlocutor_id=uuid4(),
        tenant_id=uuid4(),
        fields={
            "name": VariableEntry(name="name", value="Alice", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.ACTIVE),
            "old_email": VariableEntry(name="old_email", value="old@example.com", value_type="string", source=VariableSource.USER_PROVIDED, status=ItemStatus.SUPERSEDED),
        }
    )

    session = Session(
        session_id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        channel=Channel.WEBCHAT,
        user_channel_id="user123",
        config_version=1,
        variables={},
    )

    required_vars = {"name", "old_email"}
    known_vars, missing_vars = await resolver.resolve_variables(required_vars, profile, session)

    assert known_vars == {"name": "Alice"}
    assert missing_vars == {"old_email"}
