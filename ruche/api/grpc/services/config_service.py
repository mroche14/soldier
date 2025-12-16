"""ConfigService gRPC implementation."""

from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from ruche.api.grpc import config_pb2, config_pb2_grpc
from ruche.brains.focal.stores import AgentConfigStore
from ruche.observability.logging import get_logger

logger = get_logger(__name__)


class ConfigService(config_pb2_grpc.ConfigServiceServicer):
    """gRPC ConfigService implementation.

    Provides configuration management operations via gRPC.
    """

    def __init__(self, config_store: AgentConfigStore) -> None:
        """Initialize ConfigService.

        Args:
            config_store: Agent configuration store
        """
        self._config_store = config_store

    def _datetime_to_timestamp(self, dt) -> Timestamp:
        """Convert datetime to protobuf Timestamp.

        Args:
            dt: Python datetime

        Returns:
            Protobuf Timestamp
        """
        timestamp = Timestamp()
        timestamp.FromDatetime(dt)
        return timestamp

    async def ListRules(
        self, request: config_pb2.ListRulesRequest, context: grpc.aio.ServicerContext
    ) -> config_pb2.ListRulesResponse:
        """List rules for an agent.

        Args:
            request: List rules request
            context: gRPC context

        Returns:
            ListRulesResponse with rules
        """
        logger.info(
            "grpc_list_rules_request",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            limit=request.limit,
            offset=request.offset,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return config_pb2.ListRulesResponse()

        # Get rules from store
        rules = await self._config_store.get_rules(tenant_id, agent_id)

        # Apply pagination
        limit = request.limit if request.limit > 0 else 100
        offset = request.offset if request.offset >= 0 else 0
        paginated_rules = rules[offset : offset + limit]

        # Convert to gRPC rules
        grpc_rules = []
        for rule in paginated_rules:
            grpc_rules.append(
                config_pb2.Rule(
                    id=str(rule.id),
                    tenant_id=str(rule.tenant_id),
                    agent_id=str(rule.agent_id),
                    name=rule.name,
                    condition_text=rule.condition_text,
                    action_type=rule.action.action_type,
                    action_params={},  # Simplified for now
                    priority=rule.priority,
                    enabled=rule.enabled,
                    created_at=self._datetime_to_timestamp(rule.created_at),
                    updated_at=self._datetime_to_timestamp(rule.updated_at),
                )
            )

        logger.info(
            "grpc_list_rules_completed",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            total_count=len(rules),
            returned_count=len(grpc_rules),
        )

        return config_pb2.ListRulesResponse(
            rules=grpc_rules,
            total_count=len(rules),
        )

    async def CreateRule(
        self, request: config_pb2.CreateRuleRequest, context: grpc.aio.ServicerContext
    ) -> config_pb2.Rule:
        """Create a new rule.

        Args:
            request: Create rule request
            context: gRPC context

        Returns:
            Created Rule
        """
        logger.info(
            "grpc_create_rule_request",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            name=request.name,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return config_pb2.Rule()

        # Note: Actual rule creation would require full Rule model construction
        # This is a placeholder that shows the pattern
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "CreateRule not yet fully implemented - use REST API for now",
        )
        return config_pb2.Rule()

    async def ListScenarios(
        self, request: config_pb2.ListScenariosRequest, context: grpc.aio.ServicerContext
    ) -> config_pb2.ListScenariosResponse:
        """List scenarios for an agent.

        Args:
            request: List scenarios request
            context: gRPC context

        Returns:
            ListScenariosResponse with scenarios
        """
        logger.info(
            "grpc_list_scenarios_request",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            limit=request.limit,
            offset=request.offset,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return config_pb2.ListScenariosResponse()

        # Get scenarios from store
        scenarios = await self._config_store.get_scenarios(tenant_id, agent_id)

        # Apply pagination
        limit = request.limit if request.limit > 0 else 100
        offset = request.offset if request.offset >= 0 else 0
        paginated_scenarios = scenarios[offset : offset + limit]

        # Convert to gRPC scenarios
        grpc_scenarios = []
        for scenario in paginated_scenarios:
            grpc_scenarios.append(
                config_pb2.Scenario(
                    id=str(scenario.id),
                    tenant_id=str(scenario.tenant_id),
                    agent_id=str(scenario.agent_id),
                    name=scenario.name,
                    description=scenario.description or "",
                    enabled=scenario.enabled,
                    created_at=self._datetime_to_timestamp(scenario.created_at),
                    updated_at=self._datetime_to_timestamp(scenario.updated_at),
                )
            )

        logger.info(
            "grpc_list_scenarios_completed",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            total_count=len(scenarios),
            returned_count=len(grpc_scenarios),
        )

        return config_pb2.ListScenariosResponse(
            scenarios=grpc_scenarios,
            total_count=len(scenarios),
        )

    async def CreateScenario(
        self, request: config_pb2.CreateScenarioRequest, context: grpc.aio.ServicerContext
    ) -> config_pb2.Scenario:
        """Create a new scenario.

        Args:
            request: Create scenario request
            context: gRPC context

        Returns:
            Created Scenario
        """
        logger.info(
            "grpc_create_scenario_request",
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            name=request.name,
        )

        try:
            tenant_id = UUID(request.tenant_id)
            agent_id = UUID(request.agent_id)
        except ValueError as e:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid UUID: {e}")
            return config_pb2.Scenario()

        # Note: Actual scenario creation would require full Scenario model construction
        # This is a placeholder that shows the pattern
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "CreateScenario not yet fully implemented - use REST API for now",
        )
        return config_pb2.Scenario()
