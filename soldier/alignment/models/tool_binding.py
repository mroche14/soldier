"""Tool binding models for execution scheduling."""

from typing import Literal

from pydantic import BaseModel, Field


class ToolBinding(BaseModel):
    """Tool execution binding with timing and variable tracking.

    Defines when and how a tool should be executed relative to scenario steps,
    which variables it can fill, and its dependencies on other tools.
    """

    tool_id: str = Field(..., description="Tool identifier from ToolHub")
    when: Literal["BEFORE_STEP", "DURING_STEP", "AFTER_STEP"] = Field(
        default="DURING_STEP", description="When to execute tool relative to step"
    )
    required_variables: list[str] = Field(
        default_factory=list, description="Variable names this tool can fill"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="Tool IDs that must execute first"
    )
