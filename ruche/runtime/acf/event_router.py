"""EventRouter for ACF.

Routes ACFEvents to appropriate listeners and records side effects in LogicalTurn.
This is ACF's event routing and dispatch mechanism.

Architecture:
- Receives events from Brain/Toolbox via ctx.emit_event()
- Routes to registered listeners based on event patterns
- Stores side effects in LogicalTurn when infra.tool.* events arrive
- Supports async listeners for external integrations
"""

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Protocol

from ruche.observability.logging import get_logger
from ruche.runtime.acf.events import ACFEvent
from ruche.runtime.acf.models import LogicalTurn

logger = get_logger(__name__)


class EventListener(Protocol):
    """Protocol for event listeners.

    Event listeners are async callables that receive an ACFEvent.
    They can be used for:
    - Routing events to AuditStore
    - Updating metrics
    - Sending to live UI streams
    - External integrations
    """

    async def __call__(self, event: ACFEvent) -> None:
        """Handle an event.

        Args:
            event: The event to handle
        """
        ...


class EventRouter:
    """Routes ACFEvents to appropriate listeners.

    EventRouter is the central dispatch mechanism for ACF events. It:
    1. Maintains a registry of listeners per event pattern
    2. Routes events to all matching listeners in parallel
    3. Records side effects in LogicalTurn for infra.tool.* events
    4. Handles listener failures gracefully

    Event patterns support wildcards:
    - "*" matches all events
    - "turn.*" matches all turn events
    - "tool.executed" matches exact event type

    Thread-safety: This class uses internal locks for listener registration.
    Event routing is async-safe via asyncio.
    """

    def __init__(self) -> None:
        """Initialize event router with empty listener registry."""
        self._listeners: dict[str, list[EventListener]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register_listener(
        self, pattern: str, listener: EventListener
    ) -> None:
        """Register a listener for events matching a pattern.

        Args:
            pattern: Event pattern to match (e.g., "*", "turn.*", "tool.executed")
            listener: Async callable to handle matching events

        Examples:
            # Listen to all events
            await router.register_listener("*", audit_store_handler)

            # Listen to all turn events
            await router.register_listener("turn.*", metrics_handler)

            # Listen to specific event type
            await router.register_listener("tool.executed", tool_metrics_handler)
        """
        async with self._lock:
            self._listeners[pattern].append(listener)
            logger.debug(
                "event_listener_registered",
                pattern=pattern,
                total_listeners=len(self._listeners[pattern]),
            )

    async def unregister_listener(
        self, pattern: str, listener: EventListener
    ) -> None:
        """Unregister a listener from a pattern.

        Args:
            pattern: Event pattern the listener was registered for
            listener: The listener to remove
        """
        async with self._lock:
            if pattern in self._listeners:
                try:
                    self._listeners[pattern].remove(listener)
                    logger.debug(
                        "event_listener_unregistered",
                        pattern=pattern,
                        remaining_listeners=len(self._listeners[pattern]),
                    )
                except ValueError:
                    logger.warning(
                        "event_listener_not_found",
                        pattern=pattern,
                    )

    async def route(
        self,
        event: ACFEvent,
        logical_turn: LogicalTurn | None = None,
    ) -> None:
        """Route event to all matching listeners.

        This is the main entry point for event routing. It:
        1. Finds all listeners matching the event type
        2. Dispatches to all matching listeners in parallel
        3. Records side effects in LogicalTurn if needed
        4. Logs routing errors but doesn't fail

        Args:
            event: The event to route
            logical_turn: Optional LogicalTurn to update with side effects

        Side Effects:
            - Calls all matching listeners
            - Updates logical_turn.side_effects for infra.tool.* events
        """
        # Find matching listeners
        matching_listeners = await self._find_matching_listeners(event)

        if not matching_listeners:
            logger.debug(
                "no_listeners_for_event",
                event_type=event.type.value,
                logical_turn_id=event.logical_turn_id,
            )
            return

        # Log routing
        logger.debug(
            "routing_event",
            event_type=event.type.value,
            listener_count=len(matching_listeners),
            logical_turn_id=event.logical_turn_id,
            tenant_id=event.tenant_id,
            agent_id=event.agent_id,
        )

        # Dispatch to all matching listeners in parallel
        tasks = [
            self._dispatch_to_listener(listener, event) for listener in matching_listeners
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Record side effect in LogicalTurn if this is a tool event
        if logical_turn is not None:
            await self._record_side_effect(event, logical_turn)

    async def _find_matching_listeners(
        self, event: ACFEvent
    ) -> list[EventListener]:
        """Find all listeners matching the event.

        Args:
            event: The event to match

        Returns:
            List of listeners that match the event pattern
        """
        matching = []
        event_type = event.type.value

        async with self._lock:
            for pattern, listeners in self._listeners.items():
                if self._matches_pattern(event_type, pattern):
                    matching.extend(listeners)

        return matching

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches a pattern.

        Patterns:
        - "*" → matches ALL events
        - "category.*" → matches all events in category (e.g., "turn.*" matches "turn.started", "turn.completed")
        - "category.name" → exact match (e.g., "turn.started" matches only "turn.started")

        Args:
            event_type: The event type to check (e.g., "turn.started")
            pattern: The pattern to match against (e.g., "*", "turn.*", "turn.started")

        Returns:
            True if event type matches pattern
        """
        # Match all events
        if pattern == "*":
            return True

        # Exact match
        if event_type == pattern:
            return True

        # Category wildcard pattern (e.g., "turn.*")
        if pattern.endswith(".*"):
            category = pattern[:-2]  # Remove the ".*"
            return event_type.startswith(f"{category}.")

        return False

    async def _dispatch_to_listener(
        self, listener: EventListener, event: ACFEvent
    ) -> None:
        """Dispatch event to a single listener with error handling.

        Args:
            listener: The listener to dispatch to
            event: The event to dispatch
        """
        try:
            await listener(event)
        except Exception as e:
            logger.error(
                "event_listener_failed",
                event_type=event.type.value,
                error=str(e),
                logical_turn_id=event.logical_turn_id,
                exc_info=True,
            )

    async def _record_side_effect(
        self, event: ACFEvent, logical_turn: LogicalTurn
    ) -> None:
        """Record side effect in LogicalTurn if this is a tool event.

        ACF stores side effects from infra.tool.* events in LogicalTurn.side_effects.
        This enables supersede decisions to consider executed effects.

        Args:
            event: The event to check
            logical_turn: The LogicalTurn to update
        """
        # Record side effects via TOOL_EXECUTED event type
        from ruche.runtime.acf.events import ACFEventType
        from ruche.runtime.acf.models import SideEffect, SideEffectPolicy

        if event.type != ACFEventType.TOOL_EXECUTED:
            return

        # Extract side effect details from payload
        tool_name = event.payload.get("tool_name")
        policy_str = event.payload.get("policy", "idempotent")

        # Map policy string to enum
        policy_map = {
            "reversible": SideEffectPolicy.REVERSIBLE,
            "irreversible": SideEffectPolicy.IRREVERSIBLE,
            "idempotent": SideEffectPolicy.IDEMPOTENT,
        }
        policy = policy_map.get(policy_str, SideEffectPolicy.IDEMPOTENT)

        side_effect = SideEffect(
            effect_type="tool_call",
            policy=policy,
            tool_name=tool_name,
            idempotency_key=event.payload.get("idempotency_key"),
            details=event.payload,
        )

        logical_turn.side_effects.append(side_effect)

        logger.debug(
            "side_effect_recorded",
            tool_name=tool_name,
            policy=policy.value,
            logical_turn_id=logical_turn.id,
        )
