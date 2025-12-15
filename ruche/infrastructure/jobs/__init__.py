"""Background job infrastructure.

This module provides Hatchet-based background job orchestration for:
- Field expiry management
- Orphan detection
- Schema extraction from scenarios/rules

Usage:
    from ruche.infrastructure.jobs import HatchetClient
    from ruche.infrastructure.jobs.workflows import ExpireStaleFieldsWorkflow

    client = HatchetClient(config)
    # Register workflows with Hatchet
"""

from ruche.infrastructure.jobs.client import HatchetClient

__all__ = ["HatchetClient"]
