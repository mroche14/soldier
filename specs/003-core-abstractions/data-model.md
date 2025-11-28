# Data Model: Core Abstractions Layer

**Date**: 2025-11-28
**Feature**: 003-core-abstractions

## Overview

This document defines all domain entities for the Core Abstractions Layer. All models use Pydantic v2 with strict validation.

---

## Base Models

### TenantScopedModel
Base for all tenant-scoped entities.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| tenant_id | UUID | required | Owning tenant |
| created_at | datetime | default=utcnow | Creation timestamp |
| updated_at | datetime | default=utcnow | Last modification timestamp |
| deleted_at | datetime | optional, nullable | Soft delete marker |

### AgentScopedModel (extends TenantScopedModel)
Base for entities scoped to an agent.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| agent_id | UUID | required | Owning agent |

---

## Alignment Domain

### Enums

#### Scope
Rule and Template scoping levels.
- `GLOBAL` - Always evaluated
- `SCENARIO` - Only when scenario is active
- `STEP` - Only when in specific step

#### TemplateMode
How templates are used in response generation.
- `SUGGEST` - LLM can adapt the text
- `EXCLUSIVE` - Use exactly, bypass LLM entirely
- `FALLBACK` - Use if LLM fails or violates rules

#### VariableUpdatePolicy
When to refresh variable values.
- `ON_EACH_TURN` - Refresh every turn
- `ON_DEMAND` - Refresh only when requested
- `ON_SCENARIO_ENTRY` - Refresh when entering scenario
- `ON_SESSION_START` - Refresh at session start

### Rule (extends AgentScopedModel)
Behavioral policy: when X, then Y.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| name | str | min=1, max=100 | Rule name |
| description | str | optional | Human description |
| condition_text | str | min=1 | When this is true (natural language) |
| action_text | str | min=1 | Do this action (natural language) |
| scope | Scope | default=GLOBAL | Scoping level |
| scope_id | UUID | optional | scenario_id or step_id when scoped |
| priority | int | ge=-100, le=100, default=0 | Higher wins in conflicts |
| enabled | bool | default=True | Is rule active |
| max_fires_per_session | int | ge=0, default=0 | 0 = unlimited |
| cooldown_turns | int | ge=0, default=0 | Min turns between re-fire |
| is_hard_constraint | bool | default=False | Must be satisfied or fallback |
| attached_tool_ids | list[str] | default=[] | Tool IDs from ToolHub |
| attached_template_ids | list[UUID] | default=[] | Template references |
| embedding | list[float] | optional | Precomputed vector |
| embedding_model | str | optional | Model that generated embedding |

### Scenario (extends AgentScopedModel)
Multi-step conversational flow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| name | str | min=1, max=100 | Scenario name |
| description | str | optional | Human description |
| entry_step_id | UUID | required | First step to enter |
| steps | list[ScenarioStep] | default=[] | All steps in scenario |
| entry_condition_text | str | optional | Condition for auto-activation |
| entry_condition_embedding | list[float] | optional | Vector for entry matching |
| version | int | default=1 | Incremented on edit |
| content_hash | str | optional | SHA256 of serialized content |
| tags | list[str] | default=[] | Categorization tags |
| enabled | bool | default=True | Is scenario active |

### ScenarioStep
Single step within a Scenario.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| scenario_id | UUID | required | Parent scenario |
| name | str | required | Step name |
| description | str | optional | Human description |
| transitions | list[StepTransition] | default=[] | Possible next steps |
| template_ids | list[UUID] | default=[] | Step-scoped templates |
| rule_ids | list[UUID] | default=[] | Step-scoped rules |
| tool_ids | list[str] | default=[] | Available tools |
| is_entry | bool | default=False | Is entry point |
| is_terminal | bool | default=False | Is exit point |
| can_skip | bool | default=False | Allow jumping past |
| reachable_from_anywhere | bool | default=False | Recovery step |
| collects_profile_fields | list[str] | default=[] | Fields collected |
| performs_action | bool | default=False | Has side effects |
| is_required_action | bool | default=False | Must execute |
| is_checkpoint | bool | default=False | Irreversible action |
| checkpoint_description | str | optional | Description if checkpoint |

### StepTransition
Possible transition between steps.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| to_step_id | UUID | required | Target step |
| condition_text | str | required | Natural language condition |
| condition_embedding | list[float] | optional | Vector for matching |
| priority | int | default=0 | Higher evaluated first |
| condition_fields | list[str] | default=[] | Profile fields in condition |

### Template (extends AgentScopedModel)
Pre-written response text.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| name | str | min=1, max=100 | Template name |
| text | str | min=1 | Template with {placeholders} |
| mode | TemplateMode | default=SUGGEST | Usage mode |
| scope | Scope | default=GLOBAL | Scoping level |
| scope_id | UUID | optional | scenario_id or step_id |
| conditions | str | optional | Expression for when to use |

### Variable (extends AgentScopedModel)
Dynamic context value resolved at runtime.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| name | str | pattern=^[a-z_][a-z0-9_]*$, max=50 | Variable name |
| description | str | optional | Human description |
| resolver_tool_id | str | required | Tool that computes value |
| update_policy | VariableUpdatePolicy | default=ON_DEMAND | Refresh policy |
| cache_ttl_seconds | int | ge=0, default=0 | 0 = no cache |

### Context
Extracted understanding of user message.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| user_intent | UserIntent | required | Classified intent |
| entities | ExtractedEntities | required | Named entities |
| sentiment | str | optional | Detected sentiment |
| language | str | optional | Detected language |
| raw_message | str | required | Original message |

### UserIntent
Classified user intent.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| primary | str | required | Primary intent label |
| confidence | float | ge=0, le=1 | Confidence score |
| secondary | list[str] | default=[] | Secondary intents |

### ExtractedEntities
Named entities from message.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| entities | dict[str, list[str]] | default={} | Type -> values mapping |

### MatchedRule
Rule that matched with scoring details.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| rule | Rule | required | The matched rule |
| similarity_score | float | ge=0, le=1 | Vector similarity |
| bm25_score | float | ge=0 | Keyword match score |
| final_score | float | ge=0 | Combined weighted score |
| newly_fired | bool | required | First time this session |
| tools_to_execute | list[str] | default=[] | Resolved tool IDs |
| templates_to_consider | list[Template] | default=[] | Resolved templates |

---

## Memory Domain

### Episode
Atomic unit of memory.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| group_id | str | required | Composite key: tenant_id:session_id |
| content | str | required | Memory content |
| content_type | str | default="message" | Type: message, event, document, summary |
| source | str | required | Origin: user, agent, system, external |
| source_metadata | dict[str, Any] | default={} | Additional source info |
| occurred_at | datetime | required | When it happened |
| recorded_at | datetime | default=utcnow | When we learned it |
| embedding | list[float] | optional | Semantic vector |
| embedding_model | str | optional | Model that generated vector |
| entity_ids | list[UUID] | default=[] | Linked entities |

### Entity
Named thing in knowledge graph.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| group_id | str | required | Isolation key |
| name | str | required | Entity name |
| entity_type | str | required | Type: person, order, product, etc. |
| attributes | dict[str, Any] | default={} | Entity properties |
| valid_from | datetime | required | When became valid |
| valid_to | datetime | optional | When stopped being valid |
| recorded_at | datetime | default=utcnow | When recorded |
| embedding | list[float] | optional | Semantic vector |

### Relationship
Connection between entities.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| group_id | str | required | Isolation key |
| from_entity_id | UUID | required | Source entity |
| to_entity_id | UUID | required | Target entity |
| relation_type | str | required | Type: ordered, owns, works_for, etc. |
| attributes | dict[str, Any] | default={} | Relationship properties |
| valid_from | datetime | required | When became valid |
| valid_to | datetime | optional | When stopped being valid |
| recorded_at | datetime | default=utcnow | When recorded |

---

## Conversation Domain

### Enums

#### Channel
Communication channels.
- `WHATSAPP`, `SLACK`, `WEBCHAT`, `EMAIL`, `VOICE`, `API`

#### SessionStatus
Session lifecycle states.
- `ACTIVE`, `IDLE`, `PROCESSING`, `INTERRUPTED`, `CLOSED`

### Session
Runtime conversation state.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| session_id | UUID | default=uuid4 | Unique identifier |
| tenant_id | UUID | required | Owning tenant |
| agent_id | UUID | required | Serving agent |
| channel | Channel | required | Communication channel |
| user_channel_id | str | required | User identifier on channel |
| customer_profile_id | UUID | optional | Linked profile |
| config_version | int | required | Agent version in use |
| active_scenario_id | UUID | optional | Current scenario |
| active_step_id | UUID | optional | Current step |
| active_scenario_version | int | optional | Scenario version |
| step_history | list[StepVisit] | default=[] | Navigation history |
| relocalization_count | int | default=0 | Recovery count |
| rule_fires | dict[str, int] | default={} | rule_id -> fire count |
| rule_last_fire_turn | dict[str, int] | default={} | rule_id -> turn |
| variables | dict[str, Any] | default={} | Cached variable values |
| variable_updated_at | dict[str, datetime] | default={} | Variable timestamps |
| turn_count | int | default=0 | Total turns |
| status | SessionStatus | default=ACTIVE | Current status |
| created_at | datetime | default=utcnow | Creation time |
| last_activity_at | datetime | default=utcnow | Last activity |

### StepVisit
Record of visiting a scenario step.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| step_id | UUID | required | Visited step |
| entered_at | datetime | required | Entry time |
| turn_number | int | required | Turn when entered |
| transition_reason | str | optional | How we got here |
| confidence | float | ge=0, le=1, default=1.0 | Navigation confidence |

### Turn
Single conversation exchange.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| turn_id | UUID | default=uuid4 | Unique identifier |
| tenant_id | UUID | required | Owning tenant |
| session_id | UUID | required | Parent session |
| turn_number | int | required | Sequence number |
| user_message | str | required | User input |
| agent_response | str | required | Agent output |
| scenario_before | dict[str, str] | optional | State before turn |
| scenario_after | dict[str, str] | optional | State after turn |
| matched_rule_ids | list[UUID] | default=[] | Rules that matched |
| tool_calls | list[ToolCall] | default=[] | Tools executed |
| template_ids_used | list[UUID] | default=[] | Templates used |
| enforcement_triggered | bool | default=False | Was enforcement needed |
| enforcement_action | str | optional | What enforcement did |
| latency_ms | int | required | Processing time |
| tokens_used | int | required | Token consumption |
| timestamp | datetime | default=utcnow | Turn time |

### ToolCall
Record of tool execution.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| tool_id | str | required | Tool identifier |
| tool_name | str | required | Human-readable name |
| input | dict[str, Any] | required | Tool input |
| output | Any | required | Tool output |
| success | bool | required | Execution success |
| error | str | optional | Error message if failed |
| latency_ms | int | required | Execution time |

---

## Audit Domain

### TurnRecord
Immutable audit record of a turn.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| turn_id | UUID | required | Turn identifier |
| tenant_id | UUID | required | Owning tenant |
| agent_id | UUID | required | Serving agent |
| session_id | UUID | required | Parent session |
| turn_number | int | required | Sequence number |
| user_message | str | required | User input |
| agent_response | str | required | Agent output |
| matched_rule_ids | list[UUID] | default=[] | Rules matched |
| scenario_id | UUID | optional | Active scenario |
| step_id | UUID | optional | Active step |
| tool_calls | list[ToolCall] | default=[] | Tools executed |
| latency_ms | int | required | Processing time |
| tokens_used | int | required | Token consumption |
| timestamp | datetime | required | Turn time |

### AuditEvent
Generic audit event.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| tenant_id | UUID | required | Owning tenant |
| event_type | str | required | Event classification |
| event_data | dict[str, Any] | required | Event payload |
| session_id | UUID | optional | Related session |
| turn_id | UUID | optional | Related turn |
| timestamp | datetime | default=utcnow | Event time |

---

## Profile Domain

### Enums

#### ProfileFieldSource
How a profile field was populated.
- `USER_PROVIDED`, `LLM_EXTRACTED`, `TOOL_RESULT`, `DOCUMENT_EXTRACTED`, `HUMAN_ENTERED`, `SYSTEM_INFERRED`

#### VerificationLevel
Customer identity verification status.
- `UNVERIFIED`, `EMAIL_VERIFIED`, `PHONE_VERIFIED`, `DOCUMENT_VERIFIED`, `KYC_COMPLETE`

### CustomerProfile
Persistent customer data.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| tenant_id | UUID | required | Owning tenant |
| customer_id | UUID | default=uuid4 | Customer identifier |
| channel_identities | list[ChannelIdentity] | default=[] | Channel mappings |
| fields | dict[str, ProfileField] | default={} | Profile data |
| assets | list[ProfileAsset] | default=[] | Attached documents |
| verification_level | VerificationLevel | default=UNVERIFIED | Identity status |
| consents | list[Consent] | default=[] | Consent records |
| created_at | datetime | default=utcnow | Creation time |
| updated_at | datetime | default=utcnow | Last update |
| last_interaction_at | datetime | optional | Last activity |

### ChannelIdentity
Customer identity on a channel.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| channel | Channel | required | Communication channel |
| channel_user_id | str | required | User ID on channel |
| verified | bool | default=False | Is verified |
| verified_at | datetime | optional | Verification time |
| primary | bool | default=False | Primary for channel type |

### ProfileField
Single customer fact.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| name | str | required | Field name |
| value | Any | required | Field value |
| value_type | str | required | Type: string, date, number, etc. |
| source | ProfileFieldSource | required | How obtained |
| source_session_id | UUID | optional | Source session |
| source_scenario_id | UUID | optional | Source scenario |
| source_step_id | UUID | optional | Source step |
| verified | bool | default=False | Is verified |
| verification_method | str | optional | How verified |
| verified_at | datetime | optional | Verification time |
| verified_by | str | optional | Who verified |
| confidence | float | ge=0, le=1, default=1.0 | Extraction confidence |
| requires_confirmation | bool | default=False | Needs user confirm |
| collected_at | datetime | default=utcnow | Collection time |
| updated_at | datetime | default=utcnow | Last update |
| expires_at | datetime | optional | Expiration time |

### ProfileAsset
Document attached to profile.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | default=uuid4 | Unique identifier |
| name | str | required | Asset name |
| asset_type | str | required | Type: image, pdf, document |
| storage_provider | str | required | Storage backend |
| storage_path | str | required | Storage location |
| mime_type | str | required | MIME type |
| size_bytes | int | required | File size |
| checksum | str | required | SHA256 hash |
| uploaded_at | datetime | default=utcnow | Upload time |
| uploaded_in_session_id | UUID | optional | Upload session |
| uploaded_in_scenario_id | UUID | optional | Upload scenario |
| verified | bool | default=False | Is verified |
| verification_result | dict[str, Any] | optional | Verification data |
| retention_policy | str | default="permanent" | Retention rule |
| expires_at | datetime | optional | Expiration time |

### Consent
Customer consent record.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| consent_type | str | required | Type: marketing, data_processing, etc. |
| granted | bool | required | Is consent granted |
| granted_at | datetime | optional | Grant time |
| revoked_at | datetime | optional | Revocation time |
| source_session_id | UUID | optional | Source session |
| ip_address | str | optional | IP for audit |

---

## Provider Domain

### LLMResponse
Response from LLM generation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| text | str | required | Generated text |
| usage | TokenUsage | required | Token consumption |
| model | str | required | Model used |
| finish_reason | str | required | Why generation stopped |

### TokenUsage
Token counts for generation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| prompt_tokens | int | ge=0 | Input tokens |
| completion_tokens | int | ge=0 | Output tokens |
| total_tokens | int | ge=0 | Total tokens |

### RerankResult
Reranked document with score.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| index | int | ge=0 | Original index |
| score | float | ge=0, le=1 | Relevance score |
| document | str | required | Document text |

---

## Entity Relationships

```
Tenant (1) ──────────────── (*) Agent
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                  Rule       Scenario       Template
                    │             │
                    │      ┌──────┴──────┐
                    │      ▼             │
                    │  ScenarioStep ─────┘
                    │      │
                    └──────┼── StepTransition
                           │
                           ▼
                      Variable

Session ──────────────── CustomerProfile
    │                         │
    ├── StepVisit             ├── ChannelIdentity
    │                         ├── ProfileField
    └── Turn                  ├── ProfileAsset
         │                    └── Consent
         └── ToolCall

Episode ──────────────── Entity ──────── Relationship
    │                      │                  │
    └──────────────────────┴──────────────────┘
              (via group_id isolation)

TurnRecord (audit copy of Turn)
AuditEvent (generic audit record)
```

---

## State Transitions

### SessionStatus
```
     ┌─────────────────────────────┐
     │                             │
     ▼                             │
  ACTIVE ──► PROCESSING ──► ACTIVE ┘
     │            │
     │            ▼
     │      INTERRUPTED ──► ACTIVE
     │
     ▼
   IDLE ──────────────────► ACTIVE
     │
     ▼
  CLOSED (terminal)
```

### VerificationLevel
```
UNVERIFIED ──► EMAIL_VERIFIED ──► PHONE_VERIFIED ──► DOCUMENT_VERIFIED ──► KYC_COMPLETE
     │                │                 │                    │
     └────────────────┴─────────────────┴────────────────────┘
                   (can skip levels)
```
