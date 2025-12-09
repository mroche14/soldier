"""Background job infrastructure.

This module provides Hatchet-based background job orchestration for:
- Field expiry management
- Orphan detection
- Schema extraction from scenarios/rules

Usage:
    from focal.jobs import HatchetClient
    from focal.jobs.workflows import ExpireStaleFieldsWorkflow

    client = HatchetClient(config)
    # Register workflows with Hatchet
"""

from focal.jobs.client import HatchetClient

__all__ = ["HatchetClient"]
