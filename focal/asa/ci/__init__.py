"""ASA CI integration components.

This package contains components for integrating ASA validation into
continuous integration pipelines to validate configurations before deployment.
"""

from focal.asa.ci.validation import validate_deployment

__all__ = [
    "validate_deployment",
]
