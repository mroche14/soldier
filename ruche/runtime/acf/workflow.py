"""Hatchet workflow integration for LogicalTurn processing.

This is a stub for future Hatchet integration. The workflow orchestrates:
1. Mutex acquisition
2. Message accumulation
3. Pipeline execution
4. Commit and response
5. Mutex release

IMPORTANT: This is infrastructure-only. Will be implemented when
Hatchet integration is prioritized.
"""

from typing import Any


class LogicalTurnWorkflow:
    """Hatchet workflow for processing a LogicalTurn.

    Workflow steps:
    1. acquire_mutex - Acquire session lock (held across all steps)
    2. accumulate - Wait for message completion
    3. run_pipeline - Execute CognitivePipeline
    4. commit_and_respond - Persist state, send response
    5. release_mutex - Release session lock

    Note: This is a stub. Actual Hatchet implementation will use decorators
    and Hatchet SDK patterns.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize workflow.

        Args:
            config: Workflow configuration (will include Hatchet client, stores)
        """
        self._config = config

    async def execute(self, workflow_input: dict[str, Any]) -> dict[str, Any]:
        """Execute the workflow.

        This is a placeholder for the Hatchet-orchestrated workflow.

        Args:
            workflow_input: Initial workflow data (session_key, initial_message, etc.)

        Returns:
            Workflow result
        """
        raise NotImplementedError(
            "LogicalTurnWorkflow requires Hatchet integration. "
            "See docs/focal_360/architecture/topics/06-hatchet-integration.md"
        )

    # Future steps (will be @hatchet.step() decorated):
    # - async def acquire_mutex(self, ctx) -> dict
    # - async def accumulate(self, ctx) -> dict
    # - async def run_pipeline(self, ctx) -> dict
    # - async def commit_and_respond(self, ctx) -> dict
    # - async def on_failure(self, ctx) -> None
