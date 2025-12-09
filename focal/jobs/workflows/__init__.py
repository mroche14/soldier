"""Hatchet workflow definitions.

This module contains all background job workflows:
- ExpireStaleFieldsWorkflow: Marks expired fields based on expires_at
- DetectOrphanedItemsWorkflow: Detects items with deleted sources
- ExtractSchemaRequirementsWorkflow: Extracts profile requirements from scenarios
"""

from focal.jobs.workflows.orphan_detection import (
    DetectOrphanedItemsWorkflow,
    DetectOrphansInput,
    DetectOrphansOutput,
)
from focal.jobs.workflows.profile_expiry import (
    ExpireFieldsInput,
    ExpireFieldsOutput,
    ExpireStaleFieldsWorkflow,
)
from focal.jobs.workflows.schema_extraction import (
    ExtractSchemaInput,
    ExtractSchemaOutput,
    ExtractSchemaRequirementsWorkflow,
)

__all__ = [
    "ExpireStaleFieldsWorkflow",
    "ExpireFieldsInput",
    "ExpireFieldsOutput",
    "DetectOrphanedItemsWorkflow",
    "DetectOrphansInput",
    "DetectOrphansOutput",
    "ExtractSchemaRequirementsWorkflow",
    "ExtractSchemaInput",
    "ExtractSchemaOutput",
]
