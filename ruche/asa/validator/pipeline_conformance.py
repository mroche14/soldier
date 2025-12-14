"""Pipeline conformance tests.

This module defines conformance tests that EVERY CognitivePipeline implementation
must pass, regardless of which cognitive mechanic it implements. These tests
ensure universal safety and behavioral requirements.
"""

import time
from abc import ABC, abstractmethod

from ruche.asa.models import Issue, Severity, ValidationResult


class PipelineConformanceTests(ABC):
    """Conformance tests that EVERY CognitivePipeline must pass.

    These are mechanic-agnostic safety and behavioral requirements that apply
    to all cognitive pipeline implementations (alignment, ReAct, planner-executor, etc.).

    To test a pipeline implementation, create a subclass and implement the
    `get_pipeline` fixture method.
    """

    @abstractmethod
    def get_pipeline(self):
        """Get the pipeline instance to test.

        Returns:
            CognitivePipeline instance
        """
        pass

    async def test_tools_go_through_toolbox(self, ctx) -> ValidationResult:
        """All tool calls MUST go through the Toolbox (no direct execution).

        This ensures all tool executions are logged, monitored, and can be
        controlled by tenant-level policies.

        Args:
            ctx: TurnContext with tools configured

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()

        try:
            result = await pipeline.process_turn(ctx)

            # Verify all tool calls were logged through Toolbox
            for call in result.tool_calls:
                if not hasattr(call, "source") or call.source != "toolbox":
                    issues.append(
                        Issue(
                            severity=Severity.ERROR,
                            code="TOOLBOX_BYPASS",
                            message="All tools must be executed via Toolbox, not directly",
                            location=f"tool_call:{call.get('name', 'unknown')}",
                        )
                    )
        except Exception as e:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TEST_EXECUTION_FAILED",
                    message=f"Failed to execute test: {str(e)}",
                )
            )

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    async def test_required_events_are_emitted(self, ctx) -> ValidationResult:
        """Pipeline MUST emit required lifecycle events.

        Required events:
        - turn.started: Emitted when turn processing begins
        - turn.completed: Emitted when turn processing completes

        Args:
            ctx: TurnContext with event bus configured

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()
        events = []

        # Setup event capture
        def capture_event(event):
            events.append(event)

        if hasattr(ctx, "event_bus") and ctx.event_bus:
            ctx.event_bus.subscribe(capture_event)

        try:
            result = await pipeline.process_turn(ctx)

            # Required events for all pipelines
            required_events = {"turn.started", "turn.completed"}
            emitted_events = {e.type for e in events if hasattr(e, "type")}

            missing_events = required_events - emitted_events
            if missing_events:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="MISSING_REQUIRED_EVENTS",
                        message=f"Missing required events: {', '.join(missing_events)}",
                        fix="Ensure pipeline emits turn.started and turn.completed events",
                    )
                )
        except Exception as e:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TEST_EXECUTION_FAILED",
                    message=f"Failed to execute test: {str(e)}",
                )
            )

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    async def test_supersede_checked_before_irreversible(self, ctx) -> ValidationResult:
        """Pipeline MUST check for supersede BEFORE irreversible actions.

        This prevents executing irreversible tools when a newer agent version exists,
        which could cause the user to receive outdated behavior.

        Args:
            ctx: TurnContext with irreversible tools configured

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()

        try:
            # Setup: Create superseding agent version
            if hasattr(ctx, "config_store") and hasattr(ctx, "agent"):
                await ctx.config_store.save_agent(
                    ctx.agent.clone_with_version(ctx.agent.version + 1)
                )

            # Setup: Configure pipeline to use irreversible tool
            ctx.available_tools = [
                {
                    "name": "send_email",
                    "side_effect_policy": "irreversible",
                }
            ]

            result = await pipeline.process_turn(ctx)

            # Pipeline should have detected supersede and NOT executed tool
            if not result.get("superseded"):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="SUPERSEDE_NOT_CHECKED",
                        message="Pipeline must detect supersede before executing irreversible tools",
                        fix="Add supersede check before tool execution phase",
                    )
                )

            if len(result.get("tool_calls", [])) > 0:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TOOL_EXECUTED_WHEN_SUPERSEDED",
                        message="No irreversible tools should execute when agent is superseded",
                        fix="Skip tool execution when supersede is detected",
                    )
                )
        except Exception as e:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TEST_EXECUTION_FAILED",
                    message=f"Failed to execute test: {str(e)}",
                )
            )

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    async def test_pipelineresult_contract(self, ctx) -> ValidationResult:
        """Pipeline MUST return well-formed PipelineResult.

        Required fields:
        - response: The generated response
        - session_state: Updated session state
        - tool_calls: List of tool calls (may be empty)
        - events: List of emitted events
        - metadata.mechanic: Which mechanic was used
        - metadata.pipeline_version: Pipeline version

        Args:
            ctx: TurnContext

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()

        try:
            result = await pipeline.process_turn(ctx)

            # Required fields
            if not result.get("response"):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="MISSING_RESPONSE",
                        message="PipelineResult must include 'response' field",
                    )
                )

            if not result.get("session_state"):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="MISSING_SESSION_STATE",
                        message="PipelineResult must include 'session_state' field",
                    )
                )

            if "tool_calls" not in result or not isinstance(
                result.get("tool_calls"), list
            ):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="INVALID_TOOL_CALLS",
                        message="PipelineResult must include 'tool_calls' as a list",
                    )
                )

            if "events" not in result or not isinstance(result.get("events"), list):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="INVALID_EVENTS",
                        message="PipelineResult must include 'events' as a list",
                    )
                )

            # Metadata contract
            metadata = result.get("metadata", {})
            if not metadata.get("mechanic"):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="MISSING_MECHANIC_METADATA",
                        message="PipelineResult.metadata must declare which mechanic was used",
                        fix="Add metadata.mechanic field (e.g., 'alignment', 'react', etc.)",
                    )
                )

            if not metadata.get("pipeline_version"):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        code="MISSING_PIPELINE_VERSION",
                        message="PipelineResult.metadata should declare pipeline version",
                        fix="Add metadata.pipeline_version field",
                    )
                )
        except Exception as e:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TEST_EXECUTION_FAILED",
                    message=f"Failed to execute test: {str(e)}",
                )
            )

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    async def test_timeout_handling(self, ctx) -> ValidationResult:
        """Pipeline MUST respect timeout configuration.

        Pipelines should gracefully timeout when processing takes too long,
        rather than blocking indefinitely.

        Args:
            ctx: TurnContext with short timeout configured

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()

        try:
            # Configure very short timeout
            if hasattr(ctx, "config"):
                ctx.config.pipeline_timeout_ms = 100

            # Inject slow tool
            ctx.available_tools = [
                {"name": "slow_tool", "estimated_duration_ms": 5000}
            ]

            start = time.time()
            result = await pipeline.process_turn(ctx)
            duration_ms = (time.time() - start) * 1000

            # Should timeout gracefully
            if duration_ms >= 200:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TIMEOUT_NOT_RESPECTED",
                        message=f"Pipeline took {duration_ms:.0f}ms but timeout was 100ms",
                        fix="Implement timeout handling in pipeline execution",
                    )
                )

            if not result.get("timed_out"):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        code="TIMEOUT_NOT_INDICATED",
                        message="Result should indicate timeout occurred",
                        fix="Add timed_out=True to PipelineResult when timeout happens",
                    )
                )
        except Exception as e:
            # Timeout exception is acceptable
            if "timeout" not in str(e).lower():
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TEST_EXECUTION_FAILED",
                        message=f"Failed to execute test: {str(e)}",
                    )
                )

        return ValidationResult(valid=len(issues) == 0, issues=issues)

    async def test_tenant_isolation(self, ctx) -> ValidationResult:
        """Pipeline MUST NOT leak data across tenants.

        Session state, cache keys, and all data must be properly scoped by tenant_id
        to prevent cross-tenant data leakage.

        Args:
            ctx: TurnContext

        Returns:
            ValidationResult indicating pass/fail
        """
        issues = []
        pipeline = self.get_pipeline()

        try:
            # Create contexts for two different tenants
            tenant_a_ctx = ctx.clone_with_tenant("tenant-a")
            tenant_b_ctx = ctx.clone_with_tenant("tenant-b")

            # Process turn for tenant A
            result_a = await pipeline.process_turn(tenant_a_ctx)

            # Process turn for tenant B
            result_b = await pipeline.process_turn(tenant_b_ctx)

            # Verify no cross-contamination in session state
            session_a = result_a.get("session_state", {})
            session_b = result_b.get("session_state", {})

            if session_a.get("tenant_id") != "tenant-a":
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TENANT_ID_MISMATCH",
                        message="Session state for tenant A has wrong tenant_id",
                    )
                )

            if session_b.get("tenant_id") != "tenant-b":
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TENANT_ID_MISMATCH",
                        message="Session state for tenant B has wrong tenant_id",
                    )
                )

            # Verify cache keys include tenant_id (if pipeline exposes them)
            if hasattr(pipeline, "_get_cache_keys"):
                cache_keys_a = pipeline._get_cache_keys()
                cache_keys_b = pipeline._get_cache_keys()

                for key in cache_keys_a:
                    if "tenant-a" not in str(key):
                        issues.append(
                            Issue(
                                severity=Severity.ERROR,
                                code="CACHE_KEY_MISSING_TENANT",
                                message=f"Cache key for tenant A missing tenant_id: {key}",
                                fix="Include tenant_id in all cache keys",
                            )
                        )

                for key in cache_keys_b:
                    if "tenant-b" not in str(key):
                        issues.append(
                            Issue(
                                severity=Severity.ERROR,
                                code="CACHE_KEY_MISSING_TENANT",
                                message=f"Cache key for tenant B missing tenant_id: {key}",
                                fix="Include tenant_id in all cache keys",
                            )
                        )
        except Exception as e:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TEST_EXECUTION_FAILED",
                    message=f"Failed to execute test: {str(e)}",
                )
            )

        return ValidationResult(valid=len(issues) == 0, issues=issues)
