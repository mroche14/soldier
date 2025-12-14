"""Scenario migration handling for FOCAL.

This module manages version transitions when scenarios are updated
while customers are mid-conversation.

Key components:
- MigrationPlanner: Generates migration plans
- MigrationDeployer: Marks sessions for migration
- MigrationExecutor: Executes JIT migrations
- CompositeMapper: Handles multi-version gaps
- GapFillService: Retrieves missing data
"""

# Migration components remain as imported from alignment.migration
# This __init__ marks the directory as a Python package

__all__ = []
