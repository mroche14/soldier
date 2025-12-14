"""Test factories for alignment domain models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ruche.alignment.context.models import (
    ExtractedEntity,
    ScenarioSignal,
    Sentiment,
    Turn,
    Urgency,
)
from ruche.alignment.context.situation_snapshot import (
    CandidateVariableInfo,
    SituationSnapshot,
)
from ruche.alignment.models import Rule, Scope
from ruche.alignment.models.tool_binding import ToolBinding


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
        tool_bindings: list[ToolBinding] | None = None,
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
            attached_tool_ids: Tool IDs to execute (deprecated)
            attached_template_ids: Template IDs for responses
            tool_bindings: Tool bindings with timing
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
            tool_bindings=tool_bindings or [],
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


class SituationSnapshotFactory:
    """Factory for creating SituationSnapshot instances for testing."""

    @staticmethod
    def create(
        *,
        message: str = "Hello, I need help with my order",
        embedding: list[float] | None = None,
        new_intent_label: str | None = "get help",
        canonical_intent_label: str | None = None,
        intent_changed: bool = False,
        topic_changed: bool = False,
        tone: str = "neutral",
        frustration_level: str | None = None,
        scenario_signal: ScenarioSignal | None = None,
        turn_count: int = 0,
        candidate_variables: dict[str, CandidateVariableInfo] | None = None,
    ) -> SituationSnapshot:
        """Create a SituationSnapshot with sensible defaults.

        Args:
            message: Original user message
            embedding: Vector representation
            new_intent_label: Newly detected intent
            canonical_intent_label: Normalized intent label
            intent_changed: Whether intent changed from previous turn
            topic_changed: Whether topic changed from previous turn
            tone: Detected tone (neutral, frustrated, etc.)
            frustration_level: Level of frustration if any
            scenario_signal: Scenario navigation signal
            turn_count: Number of turns
            candidate_variables: Extracted variable candidates

        Returns:
            Configured SituationSnapshot instance
        """
        return SituationSnapshot(
            message=message,
            embedding=embedding,
            new_intent_label=new_intent_label,
            canonical_intent_label=canonical_intent_label,
            intent_changed=intent_changed,
            topic_changed=topic_changed,
            tone=tone,
            frustration_level=frustration_level,
            scenario_signal=scenario_signal,
            turn_count=turn_count,
            candidate_variables=candidate_variables or {},
        )

    @staticmethod
    def create_with_variables(
        message: str,
        variables: dict[str, str],
        **kwargs: Any,
    ) -> SituationSnapshot:
        """Create snapshot with extracted variables.

        Args:
            message: User message
            variables: Dict of variable_name -> value
            **kwargs: Additional args passed to create()

        Returns:
            SituationSnapshot with variables
        """
        variable_info = {
            name: CandidateVariableInfo(value=value, scope="CASE")
            for name, value in variables.items()
        }
        return SituationSnapshotFactory.create(
            message=message,
            candidate_variables=variable_info,
            **kwargs,
        )

    @staticmethod
    def create_frustrated(
        message: str = "This is ridiculous, nothing works!",
        **kwargs: Any,
    ) -> SituationSnapshot:
        """Create snapshot for a frustrated user.

        Args:
            message: Frustrated message
            **kwargs: Additional args passed to create()

        Returns:
            SituationSnapshot with frustrated tone
        """
        return SituationSnapshotFactory.create(
            message=message,
            tone="frustrated",
            frustration_level="high",
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
