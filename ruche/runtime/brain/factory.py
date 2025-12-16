"""BrainFactory for creating Brain instances based on agent configuration.

The factory pattern allows the platform to support multiple Brain types
(FOCAL, LangGraph, Agno, custom) without hardcoding dependencies.
"""

from typing import Callable

from ruche.brains.focal.models.agent import Agent
from ruche.runtime.brain.protocol import Brain


class BrainFactory:
    """Factory for creating Brain instances based on brain_type.

    Supports:
    - FOCAL alignment brain (default)
    - LangGraph (if factory registered)
    - Agno (if factory registered)
    - Custom brains (via register())

    Each factory is a callable that takes an Agent and returns a Brain.
    """

    def __init__(
        self,
        focal_factory: Callable[[Agent], Brain] | None = None,
        langgraph_factory: Callable[[Agent], Brain] | None = None,
        agno_factory: Callable[[Agent], Brain] | None = None,
    ):
        """Initialize factory with optional brain constructors.

        Args:
            focal_factory: Factory function for FOCAL brains
            langgraph_factory: Factory function for LangGraph brains
            agno_factory: Factory function for Agno brains
        """
        self._factories: dict[str, Callable[[Agent], Brain]] = {}

        if focal_factory:
            self._factories["focal"] = focal_factory
        if langgraph_factory:
            self._factories["langgraph"] = langgraph_factory
        if agno_factory:
            self._factories["agno"] = agno_factory

    def create(self, brain_type: str, agent: Agent) -> Brain:
        """Create a Brain instance based on brain_type.

        Args:
            brain_type: Type of brain to create ("focal", "langgraph", "agno")
            agent: Agent configuration

        Returns:
            Instantiated Brain

        Raises:
            ValueError: If brain_type not registered
        """
        factory = self._factories.get(brain_type)
        if not factory:
            raise ValueError(
                f"Unknown brain type: {brain_type}. "
                f"Available: {list(self._factories.keys())}"
            )

        return factory(agent)

    def register(self, brain_type: str, factory: Callable[[Agent], Brain]) -> None:
        """Register a custom brain factory.

        Args:
            brain_type: Identifier for this brain type
            factory: Callable that takes Agent and returns Brain
        """
        self._factories[brain_type] = factory

    @property
    def available_types(self) -> list[str]:
        """Get list of registered brain types."""
        return list(self._factories.keys())
