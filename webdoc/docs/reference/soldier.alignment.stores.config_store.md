<a id="focal.alignment.stores.config_store"></a>

# focal.alignment.stores.config\_store

ConfigStore abstract interface.

<a id="focal.alignment.stores.config_store.ConfigStore"></a>

## ConfigStore Objects

```python
class ConfigStore(ABC)
```

Abstract interface for configuration storage.

Manages rules, scenarios, templates, variables, and agent
configuration with support for vector search and scoping.

<a id="focal.alignment.stores.config_store.ConfigStore.get_rule"></a>

#### get\_rule

```python
@abstractmethod
async def get_rule(tenant_id: UUID, rule_id: UUID) -> Rule | None
```

Get a rule by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_rules"></a>

#### get\_rules

```python
@abstractmethod
async def get_rules(tenant_id: UUID,
                    agent_id: UUID,
                    *,
                    scope: Scope | None = None,
                    scope_id: UUID | None = None,
                    enabled_only: bool = True) -> list[Rule]
```

Get rules for an agent with optional filtering.

<a id="focal.alignment.stores.config_store.ConfigStore.save_rule"></a>

#### save\_rule

```python
@abstractmethod
async def save_rule(rule: Rule) -> UUID
```

Save a rule, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_rule"></a>

#### delete\_rule

```python
@abstractmethod
async def delete_rule(tenant_id: UUID, rule_id: UUID) -> bool
```

Soft-delete a rule by setting deleted_at.

<a id="focal.alignment.stores.config_store.ConfigStore.vector_search_rules"></a>

#### vector\_search\_rules

```python
@abstractmethod
async def vector_search_rules(
        query_embedding: list[float],
        tenant_id: UUID,
        agent_id: UUID,
        *,
        limit: int = 10,
        min_score: float = 0.0) -> list[tuple[Rule, float]]
```

Search rules by vector similarity, returning (rule, score) pairs.

<a id="focal.alignment.stores.config_store.ConfigStore.get_scenario"></a>

#### get\_scenario

```python
@abstractmethod
async def get_scenario(tenant_id: UUID, scenario_id: UUID) -> Scenario | None
```

Get a scenario by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_scenarios"></a>

#### get\_scenarios

```python
@abstractmethod
async def get_scenarios(tenant_id: UUID,
                        agent_id: UUID,
                        *,
                        enabled_only: bool = True) -> list[Scenario]
```

Get scenarios for an agent.

<a id="focal.alignment.stores.config_store.ConfigStore.save_scenario"></a>

#### save\_scenario

```python
@abstractmethod
async def save_scenario(scenario: Scenario) -> UUID
```

Save a scenario, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_scenario"></a>

#### delete\_scenario

```python
@abstractmethod
async def delete_scenario(tenant_id: UUID, scenario_id: UUID) -> bool
```

Soft-delete a scenario.

<a id="focal.alignment.stores.config_store.ConfigStore.get_template"></a>

#### get\_template

```python
@abstractmethod
async def get_template(tenant_id: UUID, template_id: UUID) -> Template | None
```

Get a template by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_templates"></a>

#### get\_templates

```python
@abstractmethod
async def get_templates(tenant_id: UUID,
                        agent_id: UUID,
                        *,
                        scope: Scope | None = None,
                        scope_id: UUID | None = None) -> list[Template]
```

Get templates for an agent with optional filtering.

<a id="focal.alignment.stores.config_store.ConfigStore.save_template"></a>

#### save\_template

```python
@abstractmethod
async def save_template(template: Template) -> UUID
```

Save a template, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_template"></a>

#### delete\_template

```python
@abstractmethod
async def delete_template(tenant_id: UUID, template_id: UUID) -> bool
```

Soft-delete a template.

<a id="focal.alignment.stores.config_store.ConfigStore.get_variable"></a>

#### get\_variable

```python
@abstractmethod
async def get_variable(tenant_id: UUID, variable_id: UUID) -> Variable | None
```

Get a variable by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_variables"></a>

#### get\_variables

```python
@abstractmethod
async def get_variables(tenant_id: UUID, agent_id: UUID) -> list[Variable]
```

Get variables for an agent.

<a id="focal.alignment.stores.config_store.ConfigStore.get_variable_by_name"></a>

#### get\_variable\_by\_name

```python
@abstractmethod
async def get_variable_by_name(tenant_id: UUID, agent_id: UUID,
                               name: str) -> Variable | None
```

Get a variable by name.

<a id="focal.alignment.stores.config_store.ConfigStore.save_variable"></a>

#### save\_variable

```python
@abstractmethod
async def save_variable(variable: Variable) -> UUID
```

Save a variable, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_variable"></a>

#### delete\_variable

```python
@abstractmethod
async def delete_variable(tenant_id: UUID, variable_id: UUID) -> bool
```

Soft-delete a variable.

<a id="focal.alignment.stores.config_store.ConfigStore.get_agent"></a>

#### get\_agent

```python
@abstractmethod
async def get_agent(tenant_id: UUID, agent_id: UUID) -> Agent | None
```

Get an agent by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_agents"></a>

#### get\_agents

```python
@abstractmethod
async def get_agents(tenant_id: UUID,
                     *,
                     enabled_only: bool = False,
                     limit: int = 20,
                     offset: int = 0) -> tuple[list[Agent], int]
```

Get agents for a tenant with pagination.

**Returns**:

  Tuple of (agents list, total count)

<a id="focal.alignment.stores.config_store.ConfigStore.save_agent"></a>

#### save\_agent

```python
@abstractmethod
async def save_agent(agent: Agent) -> UUID
```

Save an agent, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_agent"></a>

#### delete\_agent

```python
@abstractmethod
async def delete_agent(tenant_id: UUID, agent_id: UUID) -> bool
```

Soft-delete an agent.

<a id="focal.alignment.stores.config_store.ConfigStore.get_tool_activation"></a>

#### get\_tool\_activation

```python
@abstractmethod
async def get_tool_activation(tenant_id: UUID, agent_id: UUID,
                              tool_id: str) -> ToolActivation | None
```

Get a tool activation by agent and tool ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_tool_activations"></a>

#### get\_tool\_activations

```python
@abstractmethod
async def get_tool_activations(tenant_id: UUID,
                               agent_id: UUID) -> list[ToolActivation]
```

Get all tool activations for an agent.

<a id="focal.alignment.stores.config_store.ConfigStore.save_tool_activation"></a>

#### save\_tool\_activation

```python
@abstractmethod
async def save_tool_activation(activation: ToolActivation) -> UUID
```

Save a tool activation, returning its ID.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_tool_activation"></a>

#### delete\_tool\_activation

```python
@abstractmethod
async def delete_tool_activation(tenant_id: UUID, agent_id: UUID,
                                 tool_id: str) -> bool
```

Delete a tool activation.

<a id="focal.alignment.stores.config_store.ConfigStore.get_migration_plan"></a>

#### get\_migration\_plan

```python
@abstractmethod
async def get_migration_plan(tenant_id: UUID,
                             plan_id: UUID) -> MigrationPlan | None
```

Get migration plan by ID.

<a id="focal.alignment.stores.config_store.ConfigStore.get_migration_plan_for_versions"></a>

#### get\_migration\_plan\_for\_versions

```python
@abstractmethod
async def get_migration_plan_for_versions(
        tenant_id: UUID, scenario_id: UUID, from_version: int,
        to_version: int) -> MigrationPlan | None
```

Get migration plan for specific version transition.

<a id="focal.alignment.stores.config_store.ConfigStore.save_migration_plan"></a>

#### save\_migration\_plan

```python
@abstractmethod
async def save_migration_plan(plan: MigrationPlan) -> UUID
```

Save or update migration plan.

<a id="focal.alignment.stores.config_store.ConfigStore.list_migration_plans"></a>

#### list\_migration\_plans

```python
@abstractmethod
async def list_migration_plans(tenant_id: UUID,
                               scenario_id: UUID | None = None,
                               status: MigrationPlanStatus | None = None,
                               limit: int = 50) -> list[MigrationPlan]
```

List migration plans for scenario.

<a id="focal.alignment.stores.config_store.ConfigStore.delete_migration_plan"></a>

#### delete\_migration\_plan

```python
@abstractmethod
async def delete_migration_plan(tenant_id: UUID, plan_id: UUID) -> bool
```

Delete a migration plan.

<a id="focal.alignment.stores.config_store.ConfigStore.archive_scenario_version"></a>

#### archive\_scenario\_version

```python
@abstractmethod
async def archive_scenario_version(tenant_id: UUID,
                                   scenario: Scenario) -> None
```

Archive scenario version before update.

<a id="focal.alignment.stores.config_store.ConfigStore.get_archived_scenario"></a>

#### get\_archived\_scenario

```python
@abstractmethod
async def get_archived_scenario(tenant_id: UUID, scenario_id: UUID,
                                version: int) -> Scenario | None
```

Get archived scenario by version.

