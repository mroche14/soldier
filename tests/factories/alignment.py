"""Test factories for alignment domain models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from soldier.alignment.context.models import (
    Context,
    ExtractedEntity,
    ScenarioSignal,
    Sentiment,
    Turn,
    Urgency,
)
from soldier.alignment.models import Rule, Scope


class RuleFactory:
    """Factory for creating Rule instances for testing."""

    @staticmethod
    def create(
        *,
        id: UUID | None = None,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        name: str = "Test Rule",
        description: str | None = "A test rule",
        condition_text: str = "When the user asks about testing",
        action_text: str = "Respond helpfully about testing",
        scope: Scope = Scope.GLOBAL,
        scope_id: UUID | None = None,
        priority: int = 0,
        enabled: bool = True,
        max_fires_per_session: int = 0,
        cooldown_turns: int = 0,
        is_hard_constraint: bool = False,
        attached_tool_ids: list[str] | None = None,
        attached_template_ids: list[UUID] | None = None,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> Rule:
        """Create a Rule with sensible defaults.

        Args:
            id: Rule ID (auto-generated if not provided)
            tenant_id: Tenant ID (auto-generated if not provided)
            agent_id: Agent ID (auto-generated if not provided)
            name: Rule name
            description: Human-readable description
            condition_text: When condition
            action_text: Then action
            scope: Scoping level
            scope_id: ID for scoped rules
            priority: Rule priority (-100 to 100)
            enabled: Whether rule is active
            max_fires_per_session: Max times rule can fire
            cooldown_turns: Turns between re-fires
            is_hard_constraint: Whether this is a hard constraint
            attached_tool_ids: Tool IDs to execute
            attached_template_ids: Template IDs for responses
            embedding: Precomputed embedding
            embedding_model: Model that generated embedding

        Returns:
            Configured Rule instance
        """
        return Rule(
            id=id or uuid4(),
            tenant_id=tenant_id or uuid4(),
            agent_id=agent_id or uuid4(),
            name=name,
            description=description,
            condition_text=condition_text,
            action_text=action_text,
            scope=scope,
            scope_id=scope_id,
            priority=priority,
            enabled=enabled,
            max_fires_per_session=max_fires_per_session,
            cooldown_turns=cooldown_turns,
            is_hard_constraint=is_hard_constraint,
            attached_tool_ids=attached_tool_ids or [],
            attached_template_ids=attached_template_ids or [],
            embedding=embedding,
            embedding_model=embedding_model,
        )

    @staticmethod
    def create_batch(
        count: int,
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        **kwargs: Any,
    ) -> list[Rule]:
        """Create multiple rules with the same tenant/agent.

        Args:
            count: Number of rules to create
            tenant_id: Shared tenant ID
            agent_id: Shared agent ID
            **kwargs: Additional args passed to create()

        Returns:
            List of Rule instances
        """
        shared_tenant = tenant_id or uuid4()
        shared_agent = agent_id or uuid4()
        return [
            RuleFactory.create(
                tenant_id=shared_tenant,
                agent_id=shared_agent,
                name=f"Test Rule {i + 1}",
                **kwargs,
            )
            for i in range(count)
        ]

    @staticmethod
    def create_hard_constraint(
        *,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        name: str = "Hard Constraint Rule",
        condition_text: str = "Always apply",
        action_text: str = "Never mention competitors",
        **kwargs: Any,
    ) -> Rule:
        """Create a hard constraint rule.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID
            name: Rule name
            condition_text: When condition
            action_text: Then action
            **kwargs: Additional args passed to create()

        Returns:
            Hard constraint Rule instance
        """
        return RuleFactory.create(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name=name,
            condition_text=condition_text,
            action_text=action_text,
            is_hard_constraint=True,
            priority=100,  # High priority for constraints
            **kwargs,
        )


class ContextFactory:
    """Factory for creating Context instances for testing."""

    @staticmethod
    def create(
        *,
        message: str = "Hello, I need help with my order",
        embedding: list[float] | None = None,
        timestamp: datetime | None = None,
        intent: str | None = "get help",
        entities: list[ExtractedEntity] | None = None,
        sentiment: Sentiment | None = Sentiment.NEUTRAL,
        topic: str | None = "support",
        urgency: Urgency = Urgency.NORMAL,
        scenario_signal: ScenarioSignal | None = None,
        turn_count: int = 0,
        recent_topics: list[str] | None = None,
    ) -> Context:
        """Create a Context with sensible defaults.

        Args:
            message: Original user message
            embedding: Vector representation
            timestamp: Message timestamp
            intent: Synthesized intent
            entities: Extracted entities
            sentiment: Detected sentiment
            topic: Topic classification
            urgency: Urgency level
            scenario_signal: Scenario navigation signal
            turn_count: Number of turns
            recent_topics: Recent topics

        Returns:
            Configured Context instance
        """
        return Context(
            message=message,
            embedding=embedding,
            timestamp=timestamp or datetime.utcnow(),
            intent=intent,
            entities=entities or [],
            sentiment=sentiment,
            topic=topic,
            urgency=urgency,
            scenario_signal=scenario_signal,
            turn_count=turn_count,
            recent_topics=recent_topics or [],
        )

    @staticmethod
    def create_with_entities(
        message: str,
        entities: dict[str, str],
        **kwargs: Any,
    ) -> Context:
        """Create context with extracted entities.

        Args:
            message: User message
            entities: Dict of entity_type -> value
            **kwargs: Additional args passed to create()

        Returns:
            Context with entities
        """
        entity_list = [
            ExtractedEntity(type=etype, value=value)
            for etype, value in entities.items()
        ]
        return ContextFactory.create(
            message=message,
            entities=entity_list,
            **kwargs,
        )

    @staticmethod
    def create_frustrated(
        message: str = "This is ridiculous, nothing works!",
        **kwargs: Any,
    ) -> Context:
        """Create context for a frustrated user.

        Args:
            message: Frustrated message
            **kwargs: Additional args passed to create()

        Returns:
            Context with frustrated sentiment
        """
        return ContextFactory.create(
            message=message,
            sentiment=Sentiment.FRUSTRATED,
            urgency=Urgency.HIGH,
            **kwargs,
        )


class TurnFactory:
    """Factory for creating Turn instances for testing."""

    @staticmethod
    def create_user(
        content: str = "Hello",
        timestamp: datetime | None = None,
    ) -> Turn:
        """Create a user turn."""
        return Turn(role="user", content=content, timestamp=timestamp)

    @staticmethod
    def create_assistant(
        content: str = "How can I help you?",
        timestamp: datetime | None = None,
    ) -> Turn:
        """Create an assistant turn."""
        return Turn(role="assistant", content=content, timestamp=timestamp)

    @staticmethod
    def create_conversation(
        exchanges: list[tuple[str, str]],
    ) -> list[Turn]:
        """Create a conversation from user/assistant pairs.

        Args:
            exchanges: List of (user_message, assistant_response) tuples

        Returns:
            List of alternating Turn instances
        """
        turns = []
        for user_msg, assistant_msg in exchanges:
            turns.append(TurnFactory.create_user(user_msg))
            turns.append(TurnFactory.create_assistant(assistant_msg))
        return turns
