<a id="focal.alignment.migration.gap_fill"></a>

# focal.alignment.migration.gap\_fill

Gap fill service for retrieving missing field values.

Attempts to fill missing data without asking the customer:
1. Check customer profile (cross-session, persistent)
2. Check session variables (current conversation)
3. Extract from conversation history (LLM-based)

<a id="focal.alignment.migration.gap_fill.USE_THRESHOLD"></a>

#### USE\_THRESHOLD

Minimum confidence to use extracted value

<a id="focal.alignment.migration.gap_fill.NO_CONFIRM_THRESHOLD"></a>

#### NO\_CONFIRM\_THRESHOLD

Confidence above which no confirmation needed

<a id="focal.alignment.migration.gap_fill.GapFillService"></a>

## GapFillService Objects

```python
class GapFillService()
```

Service for filling missing fields without user interaction.

Implements a tiered approach:
1. Profile data (highest priority - verified, cross-session)
2. Session variables (current conversation data)
3. Conversation extraction (LLM-based, lower confidence)

<a id="focal.alignment.migration.gap_fill.GapFillService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(profile_store: "ProfileStore | None" = None,
             llm_provider: "LLMProvider | None" = None) -> None
```

Initialize the gap fill service.

**Arguments**:

- `profile_store` - Store for customer profiles
- `llm_provider` - LLM provider for conversation extraction

<a id="focal.alignment.migration.gap_fill.GapFillService.fill_gap"></a>

#### fill\_gap

```python
async def fill_gap(field_name: str,
                   session: "Session",
                   field_type: str = "string",
                   field_description: str | None = None) -> GapFillResult
```

Try to fill a missing field without asking the user.

**Arguments**:

- `field_name` - Name of the field to fill
- `session` - Current session
- `field_type` - Expected type (string, number, date, etc.)
- `field_description` - Human description for extraction
  

**Returns**:

  GapFillResult with fill status and value

<a id="focal.alignment.migration.gap_fill.GapFillService.try_profile_fill"></a>

#### try\_profile\_fill

```python
async def try_profile_fill(field_name: str,
                           session: "Session") -> GapFillResult
```

Try to fill from customer profile.

**Arguments**:

- `field_name` - Field to look up
- `session` - Current session
  

**Returns**:

  GapFillResult from profile or not found

<a id="focal.alignment.migration.gap_fill.GapFillService.try_session_fill"></a>

#### try\_session\_fill

```python
def try_session_fill(field_name: str, session: "Session") -> GapFillResult
```

Try to fill from session variables.

**Arguments**:

- `field_name` - Field to look up
- `session` - Current session
  

**Returns**:

  GapFillResult from session or not found

<a id="focal.alignment.migration.gap_fill.GapFillService.try_conversation_extraction"></a>

#### try\_conversation\_extraction

```python
async def try_conversation_extraction(field_name: str,
                                      session: "Session",
                                      field_type: str = "string",
                                      field_description: str | None = None,
                                      max_turns: int = 20) -> GapFillResult
```

Try to extract field value from conversation history.

Uses LLM to find and extract the field value from recent
conversation turns.

**Arguments**:

- `field_name` - Field to extract
- `session` - Current session
- `field_type` - Expected type
- `field_description` - Human description
- `max_turns` - Maximum turns to include
  

**Returns**:

  GapFillResult with extraction or not found

<a id="focal.alignment.migration.gap_fill.GapFillService.persist_extracted_values"></a>

#### persist\_extracted\_values

```python
async def persist_extracted_values(session: "Session",
                                   results: list[GapFillResult]) -> int
```

Persist extracted values to profile for future use.

**Arguments**:

- `session` - Current session
- `results` - Gap fill results to persist
  

**Returns**:

  Number of values persisted

<a id="focal.alignment.migration.gap_fill.GapFillService.fill_multiple"></a>

#### fill\_multiple

```python
async def fill_multiple(
    field_names: list[str],
    session: "Session",
    field_definitions: dict[str, dict[str, Any]] | None = None
) -> dict[str, GapFillResult]
```

Fill multiple fields at once.

**Arguments**:

- `field_names` - Fields to fill
- `session` - Current session
- `field_definitions` - Optional field type/description info
  

**Returns**:

  Dict mapping field name to result

