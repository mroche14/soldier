<a id="focal.api.models.chat"></a>

# focal.api.models.chat

Chat request and response models.

<a id="focal.api.models.chat.ScenarioState"></a>

## ScenarioState Objects

```python
class ScenarioState(BaseModel)
```

Current scenario and step state.

<a id="focal.api.models.chat.ScenarioState.id"></a>

#### id

Scenario ID if in a scenario.

<a id="focal.api.models.chat.ScenarioState.step"></a>

#### step

Current step ID within the scenario.

<a id="focal.api.models.chat.ChatRequest"></a>

## ChatRequest Objects

```python
class ChatRequest(BaseModel)
```

Request body for POST /v1/chat and POST /v1/chat/stream.

Contains all information needed to process a user message through
the alignment engine.

<a id="focal.api.models.chat.ChatRequest.tenant_id"></a>

#### tenant\_id

Tenant identifier (resolved upstream by gateway).

<a id="focal.api.models.chat.ChatRequest.agent_id"></a>

#### agent\_id

Agent to process the message.

<a id="focal.api.models.chat.ChatRequest.channel"></a>

#### channel

Channel source: whatsapp, slack, webchat, etc.

<a id="focal.api.models.chat.ChatRequest.user_channel_id"></a>

#### user\_channel\_id

User identifier on the channel (e.g., phone number, Slack user ID).

<a id="focal.api.models.chat.ChatRequest.message"></a>

#### message

The user's message text.

<a id="focal.api.models.chat.ChatRequest.session_id"></a>

#### session\_id

Optional existing session ID. Auto-created if omitted.

<a id="focal.api.models.chat.ChatRequest.metadata"></a>

#### metadata

Optional additional context (locale, device info, etc.).

<a id="focal.api.models.chat.ChatResponse"></a>

## ChatResponse Objects

```python
class ChatResponse(BaseModel)
```

Response body for POST /v1/chat.

Contains the agent's response along with metadata about the turn.

<a id="focal.api.models.chat.ChatResponse.response"></a>

#### response

The agent's response text.

<a id="focal.api.models.chat.ChatResponse.session_id"></a>

#### session\_id

Session identifier (existing or newly created).

<a id="focal.api.models.chat.ChatResponse.turn_id"></a>

#### turn\_id

Unique identifier for this turn.

<a id="focal.api.models.chat.ChatResponse.scenario"></a>

#### scenario

Current scenario state if in a scenario.

<a id="focal.api.models.chat.ChatResponse.matched_rules"></a>

#### matched\_rules

IDs of rules that matched this turn.

<a id="focal.api.models.chat.ChatResponse.tools_called"></a>

#### tools\_called

IDs of tools that were executed.

<a id="focal.api.models.chat.ChatResponse.tokens_used"></a>

#### tokens\_used

Total tokens consumed (prompt + completion).

<a id="focal.api.models.chat.ChatResponse.latency_ms"></a>

#### latency\_ms

Total processing time in milliseconds.

<a id="focal.api.models.chat.TokenEvent"></a>

## TokenEvent Objects

```python
class TokenEvent(BaseModel)
```

Incremental token during streaming.

<a id="focal.api.models.chat.DoneEvent"></a>

## DoneEvent Objects

```python
class DoneEvent(BaseModel)
```

Final event when streaming completes.

<a id="focal.api.models.chat.ErrorEvent"></a>

## ErrorEvent Objects

```python
class ErrorEvent(BaseModel)
```

Error event during streaming.

