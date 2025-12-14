"""Configuration schema generator for cognitive mechanics.

This module provides utilities for generating configuration schemas that can be
used to build wizard UIs for configuring different cognitive mechanics.
"""

from focal.asa.models import ArtifactSchema, ConfigSchema, ParameterSchema


class SchemaGenerator:
    """Generate configuration schemas for wizard UIs.

    The SchemaGenerator helps build structured configuration schemas that
    describe what artifacts and parameters a cognitive mechanic needs.
    These schemas can be used to generate UI wizards for configuration.
    """

    @staticmethod
    def generate_alignment_schema() -> ConfigSchema:
        """Generate configuration schema for alignment mechanic.

        Returns:
            ConfigSchema for alignment-based mechanics
        """
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(
                    name="scenario",
                    type="graph",
                    required=True,
                    description="Conversation flow graph with steps and transitions",
                ),
                ArtifactSchema(
                    name="rules",
                    type="list",
                    required=False,
                    description="Behavioral rules that override scenario flow",
                ),
                ArtifactSchema(
                    name="templates",
                    type="dict",
                    required=False,
                    description="Response templates for different scenarios",
                ),
                ArtifactSchema(
                    name="glossary",
                    type="list",
                    required=False,
                    description="Domain-specific terminology for the agent",
                ),
            ],
            parameters=[
                ParameterSchema(
                    name="checkpoint_mode",
                    type="enum",
                    required=False,
                    description="How to handle checkpoints before irreversible actions",
                    values=["strict", "warn", "disabled"],
                    default="strict",
                ),
                ParameterSchema(
                    name="rule_priority_threshold",
                    type="int",
                    required=False,
                    description="Minimum priority for rules to be considered",
                    min=0,
                    max=100,
                    default=0,
                ),
                ParameterSchema(
                    name="enable_memory",
                    type="bool",
                    required=False,
                    description="Whether to use episodic memory",
                    default=True,
                ),
            ],
        )

    @staticmethod
    def generate_react_schema() -> ConfigSchema:
        """Generate configuration schema for ReAct mechanic.

        Returns:
            ConfigSchema for ReAct-based mechanics
        """
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(
                    name="system_prompt",
                    type="string",
                    required=True,
                    description="System prompt that defines agent behavior",
                ),
                ArtifactSchema(
                    name="reasoning_examples",
                    type="list",
                    required=False,
                    description="Few-shot examples of reasoning chains",
                ),
            ],
            parameters=[
                ParameterSchema(
                    name="max_iterations",
                    type="int",
                    required=True,
                    description="Maximum reasoning iterations before stopping",
                    min=1,
                    max=20,
                    default=5,
                ),
                ParameterSchema(
                    name="temperature",
                    type="float",
                    required=False,
                    description="LLM temperature for response generation",
                    min=0.0,
                    max=2.0,
                    default=0.7,
                ),
                ParameterSchema(
                    name="allow_parallel_tools",
                    type="bool",
                    required=False,
                    description="Whether to allow parallel tool execution",
                    default=False,
                ),
            ],
        )

    @staticmethod
    def generate_planner_executor_schema() -> ConfigSchema:
        """Generate configuration schema for planner-executor mechanic.

        Returns:
            ConfigSchema for planner-executor mechanics
        """
        return ConfigSchema(
            artifacts=[
                ArtifactSchema(
                    name="plan_templates",
                    type="list",
                    required=True,
                    description="Templates for different types of plans",
                ),
                ArtifactSchema(
                    name="execution_policies",
                    type="dict",
                    required=True,
                    description="Policies for plan execution and error handling",
                ),
            ],
            parameters=[
                ParameterSchema(
                    name="replan_on_failure",
                    type="bool",
                    required=False,
                    description="Whether to replan when execution fails",
                    default=True,
                ),
                ParameterSchema(
                    name="max_plan_depth",
                    type="int",
                    required=False,
                    description="Maximum depth of nested plans",
                    min=1,
                    max=10,
                    default=3,
                ),
                ParameterSchema(
                    name="rollback_strategy",
                    type="enum",
                    required=False,
                    description="How to handle rollback on failure",
                    values=["full", "partial", "none"],
                    default="partial",
                ),
            ],
        )

    @staticmethod
    def validate_config_against_schema(
        config: dict, schema: ConfigSchema
    ) -> tuple[bool, list[str]]:
        """Validate a configuration against a schema.

        Args:
            config: Configuration dict to validate
            schema: ConfigSchema to validate against

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check required artifacts
        for artifact in schema.artifacts:
            if artifact.required and artifact.name not in config:
                errors.append(f"Missing required artifact: {artifact.name}")

        # Check required parameters
        for param in schema.parameters:
            if param.required and param.name not in config:
                errors.append(f"Missing required parameter: {param.name}")

        # Validate parameter types and constraints
        for param in schema.parameters:
            if param.name not in config:
                continue

            value = config[param.name]

            # Type-specific validation
            if param.type == "int":
                if not isinstance(value, int):
                    errors.append(f"Parameter {param.name} must be an integer")
                elif param.min is not None and value < param.min:
                    errors.append(
                        f"Parameter {param.name} must be >= {param.min}"
                    )
                elif param.max is not None and value > param.max:
                    errors.append(
                        f"Parameter {param.name} must be <= {param.max}"
                    )

            elif param.type == "float":
                if not isinstance(value, (int, float)):
                    errors.append(f"Parameter {param.name} must be a number")
                elif param.min is not None and value < param.min:
                    errors.append(
                        f"Parameter {param.name} must be >= {param.min}"
                    )
                elif param.max is not None and value > param.max:
                    errors.append(
                        f"Parameter {param.name} must be <= {param.max}"
                    )

            elif param.type == "bool":
                if not isinstance(value, bool):
                    errors.append(f"Parameter {param.name} must be a boolean")

            elif param.type == "enum":
                if param.values and value not in param.values:
                    errors.append(
                        f"Parameter {param.name} must be one of: {', '.join(param.values)}"
                    )

        return len(errors) == 0, errors
