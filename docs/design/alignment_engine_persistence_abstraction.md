
# Persistence Abstraction for the Alignment Engine (SQL / NoSQL Agnostic)

> **Status:** HISTORICAL. This document predates `docs/focal_360/` and the current store split. It uses an older tri-store model (`ConfigStore`, `StateStore`, `AuditStore`) and string IDs; current Focal uses stores in `ruche/stores/` (including `MemoryStore`, `SessionStore`, `AuditStore`, plus `InterlocutorDataStoreInterface`) with UUIDs.
>
> The alignment engine implementation is now `FocalCognitivePipeline` in `ruche/pipelines/focal/pipeline.py`.
>
> For the current approach, see: `docs/design/decisions/001-storage-choice.md` and `docs/architecture/overview.md`.

> Working notes / spec for SmartBeez-style alignment engine persistence, with a single “all included” DB (Postgres *or* Mongo) and a clean abstraction for the engine.

---

## 1. Goals & Constraints

### 1.1 What we want

We want the **alignment engine** (rules, scenarios, interlocutor state, sessions, enforcement, etc.) to:

- **Not care** whether the underlying storage is SQL (e.g. Postgres) or NoSQL (e.g. Mongo).
- Use **one physical database per deployment** (or per environment), not 10 different datastores.
- Keep the **domain model clean** (Pydantic / dataclasses with no DB-specific annotations).
- Allow the engine to be run in:
  - a **monolith** (FastAPI backend + worker),
  - or split into **services** later without rewriting everything.

At the same time, we **don’t** want:

- An over-engineered “unified DB API” that simulates SQL joins in Mongo and vice versa.
- 8+ different store classes that become a maintenance nightmare.

So we aim for a **lean abstraction**:

- One DB (Postgres or Mongo).
- A **small number of persistence interfaces (ports)**.
- Swappable backend implementations **behind** those ports.

---

## 2. Domain Objects vs Persistence

A core design principle:

> **Domain models remain pure. Persistence is an adapter detail.**

### 2.1 Domain models (DB-agnostic)

Examples of **domain objects** for the engine:

- `Rule`
- `Relationship`
- `Scenario`
- `ScenarioStep`
- `ScenarioTransition`
- `ScenarioInstance`
- `SessionState`
- `InterlocutorDataStore`
- `InterlocutorDataField`
- `GlossaryItem`
- `TurnInput`
- `TurnContext`
- `SituationalSnapshot`
- `ResponsePlan`
- `ConstraintViolation`
- `EnforcementResult`
- `TurnRecord`

These are defined using **Pydantic** (or dataclasses) and:

- Know nothing about SQL, Mongo, ORMs, IDs types, etc.
- Only encode the **business structure** and validation.

Example (simplified):

```python
class Rule(BaseModel):
    id: str
    tenant_id: str
    agent_id: str

    name: str
    description: str | None = None

    condition_text: str
    action_text: str

    scope: Literal["GLOBAL", "SCENARIO", "STEP"]
    scope_id: str | None

    is_hard_constraint: bool = False
    enforcement_expression: str | None = None

    enabled: bool = True
```

The **persistence layer** will map this to tables/collections, but **domain code shouldn’t know how**.

---

## 3. Big Picture: One DB, Few Abstractions

### 3.1 One logical database

Concretely, for v1 we assume:

- **One Postgres database** (recommended), or
- **One Mongo database** (alternative).

Both hold:

- **Config & knowledge** (rules, scenarios, steps, glossary, interlocutor data fields, pipeline config).
- **Interlocutor & session state** (InterlocutorDataStore, SessionState).
- **Audit logs** (TurnRecord).

We are *not* talking about “one DB per type of data”. There is **one physical DB** per deployment.

### 3.2 Logical layers

The engine interacts with storage via **a small set of interfaces**:

- `ConfigStore` → for *static-ish* config/knowledge.
- `StateStore` → for *dynamic* customer/session state.
- `AuditStore` → for logs and traces.

Or, if you want maximum simplicity for now, a single:

- `PersistencePort` that groups all three concerns.

Internally, each of these interfaces can be implemented in Postgres or Mongo.

Engine code never touches SQLAlchemy, Motor, Prisma, etc.; it only calls these interfaces.

---

## 4. Data Categories & Responsibilities

### 4.1 Category 1: Config / Knowledge

**What lives here:**

- `Rule`
- `Scenario`, `ScenarioStep`, `ScenarioTransition`
- `GlossaryItem`
- `InterlocutorDataField`
- Pipeline / LLM task configs

**Characteristics:**

- Written rarely, read often.
- Strong consistency preferred.
- Needs multi-tenant support (tenant-specific rules, scenarios, etc.).

These are handled by `ConfigStore`.

### 4.2 Category 2: State (Interlocutor & Session)

**What lives here:**

- `InterlocutorDataStore` (profile + variables, history & confidence).
- `SessionState` (active scenarios, last intent, per-session variables).

**Characteristics:**

- Read & write **at every turn**.
- Needs to handle concurrency (multiple messages, channels).
- Multi-tenant isolation.

Handled by `StateStore`.

### 4.3 Category 3: Logs & Audit

**What lives here:**

- `TurnRecord` (full trace of each turn: inputs, decisions, enforcement, timings).
- Potentially enforcement / violation logs.

**Characteristics:**

- High volume, append-only.
- Read mostly for analytics and debugging.
- May eventually move to a more analytics-friendly DB (ClickHouse, S3, …).

Handled by `AuditStore`.

### 4.4 Category 4: Vector Store (Separate)

**What lives here:**
- Embeddings for rules, scenarios, intents, memories.

This is already a **separate abstraction** (`VectorStore`) and is not tied to SQL vs NoSQL decision for the “main DB”.

---

## 5. Interfaces: ConfigStore, StateStore, AuditStore

### 5.1 ConfigStore

Main responsibility: **read/write business configuration**.
We can start with **read-mostly** methods; write methods can be added later as you build the Builder / admin UI.

```python
from abc import ABC, abstractmethod
from typing import Sequence

class ConfigStore(ABC):
    # Rules
    @abstractmethod
    async def list_rules_for_agent(
        self, tenant_id: str, agent_id: str
    ) -> Sequence[Rule]:
        ...

    @abstractmethod
    async def get_rule(
        self, tenant_id: str, rule_id: str
    ) -> Rule | None:
        ...

    # Scenarios
    @abstractmethod
    async def list_scenarios_for_agent(
        self, tenant_id: str, agent_id: str
    ) -> Sequence[Scenario]:
        ...

    @abstractmethod
    async def get_scenario_with_graph(
        self, tenant_id: str, scenario_id: str
    ) -> tuple[Scenario, list[ScenarioStep], list[ScenarioTransition]] | None:
        ...

    # Glossary
    @abstractmethod
    async def list_glossary_for_agent(
        self, tenant_id: str, agent_id: str
    ) -> Sequence[GlossaryItem]:
        ...

    # Interlocutor data fields (profile schema)
    @abstractmethod
    async def list_interlocutor_data_fields_for_agent(
        self, tenant_id: str, agent_id: str
    ) -> Sequence[InterlocutorDataField]:
        ...
```

Later, you can extend it with:

- `save_rule`, `save_scenario`, etc. – when building your builder/admin stack.

### 5.2 StateStore

Responsibility: **read/write interlocutor and session state**.

```python
class StateStore(ABC):
    # Interlocutor data

    @abstractmethod
    async def get_interlocutor_data(
        self, tenant_id: str, customer_key: str
    ) -> InterlocutorDataStore | None:
        ...

    @abstractmethod
    async def save_interlocutor_data(
        self, interlocutor_data: InterlocutorDataStore
    ) -> None:
        ...

    @abstractmethod
    async def find_interlocutor_by_channel(
        self,
        tenant_id: str,
        channel_type: str,  # "whatsapp", "email", "webchat", etc.
        channel_id: str,    # phone number, email address, webchat session ID
    ) -> InterlocutorDataStore | None:
        ...

    # Session state

    @abstractmethod
    async def get_session(
        self, tenant_id: str, session_id: str
    ) -> SessionState | None:
        ...

    @abstractmethod
    async def save_session(
        self, session: SessionState
    ) -> None:
        ...
```

This is enough for your **Phase 1 (load)** and **Phase 11 (save)** logic.

### 5.3 AuditStore

Responsibility: **append-only logging of turns**.

```python
class AuditStore(ABC):
    @abstractmethod
    async def record_turn(
        self, record: TurnRecord
    ) -> None:
        ...
```

Later, you might add:

- queries (`list_turns_for_session`, `get_turn`) for debugging and analytics.

---

## 6. One vs Three Interfaces: PersistencePort Option

If you prefer **extreme simplicity** initially, you can group all three stores into **one interface**:

```python
class PersistencePort(ABC):
    # Config methods
    async def list_rules_for_agent(...): ...
    async def list_scenarios_for_agent(...): ...
    async def list_glossary_for_agent(...): ...
    async def list_interlocutor_data_fields_for_agent(...): ...

    # State methods
    async def get_interlocutor_data(...): ...
    async def save_interlocutor_data(...): ...
    async def find_interlocutor_by_channel(...): ...
    async def get_session(...): ...
    async def save_session(...): ...

    # Audit methods
    async def record_turn(...): ...
```

Pros:

- Simple to implement for v1 (`PostgresPersistencePort`).
- Engine code just depends on a single object (`persistence` or `repo`).

Cons:

- Interface will be larger.
- Harder to gradually split concerns later.

**Recommendation:**

- For now, use **3 small store interfaces** (`ConfigStore`, `StateStore`, `AuditStore`).
- Group them in a simple container object for DI:

  ```python
  @dataclass
  class Stores:
      config: ConfigStore
      state: StateStore
      audit: AuditStore
  ```

  And pass `Stores` into pipeline components.

---

## 7. Example: Postgres Implementations

### 7.1 One database, multiple tables

Assume a single Postgres database with tables:

- `rules`
- `scenarios`
- `scenario_steps`
- `scenario_transitions`
- `glossary_items`
- `interlocutor_data`
- `sessions`
- `turn_records`

All rows are **tenant-scoped** (`tenant_id` column). Optionally: apply Row-Level Security (RLS) per tenant.

### 7.2 PostgresConfigStore (sketch)

```python
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

class PostgresConfigStore(ConfigStore):
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def list_rules_for_agent(self, tenant_id: str, agent_id: str) -> list[Rule]:
        query = text(
            "SELECT * FROM rules WHERE tenant_id = :tenant_id AND agent_id = :agent_id"
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query, {"tenant_id": tenant_id, "agent_id": agent_id})).mappings().all()
        return [Rule(**row) for row in rows]

    async def get_rule(self, tenant_id: str, rule_id: str) -> Rule | None:
        query = text(
            "SELECT * FROM rules WHERE tenant_id = :tenant_id AND id = :rule_id"
        )
        async with self.engine.connect() as conn:
            row = (await conn.execute(query, {"tenant_id": tenant_id, "rule_id": rule_id})).mappings().first()
        return Rule(**row) if row else None

    async def list_scenarios_for_agent(self, tenant_id: str, agent_id: str) -> list[Scenario]:
        query = text(
            "SELECT * FROM scenarios WHERE tenant_id = :tenant_id AND agent_id = :agent_id"
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query, {"tenant_id": tenant_id, "agent_id": agent_id})).mappings().all()
        return [Scenario(**row) for row in rows]

    async def get_scenario_with_graph(
        self, tenant_id: str, scenario_id: str
    ) -> tuple[Scenario, list[ScenarioStep], list[ScenarioTransition]] | None:
        async with self.engine.begin() as conn:
            scen_row = (await conn.execute(
                text("SELECT * FROM scenarios WHERE tenant_id = :tenant_id AND id = :sid"),
                {"tenant_id": tenant_id, "sid": scenario_id},
            )).mappings().first()
            if not scen_row:
                return None

            step_rows = (await conn.execute(
                text("SELECT * FROM scenario_steps WHERE tenant_id = :tenant_id AND scenario_id = :sid"),
                {"tenant_id": tenant_id, "sid": scenario_id},
            )).mappings().all()

            trans_rows = (await conn.execute(
                text("SELECT * FROM scenario_transitions WHERE tenant_id = :tenant_id AND scenario_id = :sid"),
                {"tenant_id": tenant_id, "sid": scenario_id},
            )).mappings().all()

        scenario = Scenario(**scen_row)
        steps = [ScenarioStep(**r) for r in step_rows]
        transitions = [ScenarioTransition(**r) for r in trans_rows]
        return scenario, steps, transitions
```

### 7.3 PostgresStateStore (sketch)

For simplicity, treat `InterlocutorDataStore` and `SessionState` as **JSON columns**.

```python
class PostgresStateStore(StateStore):
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def get_interlocutor_data(self, tenant_id: str, customer_key: str) -> InterlocutorDataStore | None:
        query = text(
            "SELECT data FROM interlocutor_data WHERE tenant_id = :tenant_id AND customer_key = :ck"
        )
        async with self.engine.connect() as conn:
            row = (await conn.execute(query, {"tenant_id": tenant_id, "ck": customer_key})).mappings().first()
        return InterlocutorDataStore(**row["data"]) if row else None

    async def save_interlocutor_data(self, interlocutor_data: InterlocutorDataStore) -> None:
        payload = interlocutor_data.model_dump()
        query = text(
            """
            INSERT INTO interlocutor_data (tenant_id, customer_key, data)
            VALUES (:tenant_id, :ck, :data)
            ON CONFLICT (tenant_id, customer_key)
            DO UPDATE SET data = EXCLUDED.data
            """
        )
        async with self.engine.begin() as conn:
            await conn.execute(
                query,
                {
                    "tenant_id": interlocutor_data.tenant_id,
                    "ck": interlocutor_data.customer_key,
                    "data": payload,
                },
            )

    async def get_session(self, tenant_id: str, session_id: str) -> SessionState | None:
        query = text(
            "SELECT data FROM sessions WHERE tenant_id = :tenant_id AND session_id = :sid"
        )
        async with self.engine.connect() as conn:
            row = (await conn.execute(query, {"tenant_id": tenant_id, "sid": session_id})).mappings().first()
        return SessionState(**row["data"]) if row else None

    async def save_session(self, session: SessionState) -> None:
        payload = session.model_dump()
        query = text(
            """
            INSERT INTO sessions (tenant_id, session_id, data)
            VALUES (:tenant_id, :sid, :data)
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET data = EXCLUDED.data
            """
        )
        async with self.engine.begin() as conn:
            await conn.execute(
                query,
                {
                    "tenant_id": session.tenant_id,
                    "sid": session.session_id,
                    "data": payload,
                },
            )
```

### 7.4 PostgresAuditStore (sketch)

```python
class PostgresAuditStore(AuditStore):
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def record_turn(self, record: TurnRecord) -> None:
        payload = record.model_dump()
        query = text(
            """
            INSERT INTO turn_records (tenant_id, agent_id, session_id, turn_index, data)
            VALUES (:tenant_id, :agent_id, :session_id, :turn_index, :data)
            """
        )
        async with self.engine.begin() as conn:
            await conn.execute(
                query,
                {
                    "tenant_id": record.tenant_id,
                    "agent_id": record.agent_id,
                    "session_id": record.session_id,
                    "turn_index": record.turn_index,
                    "data": payload,
                },
            )
```

---

## 8. Example: Mongo Implementations (high-level)

If later you want to use **Mongo** instead of Postgres, you’d have:

```python
from motor.motor_asyncio import AsyncIOMotorDatabase

class MongoConfigStore(ConfigStore):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def list_rules_for_agent(self, tenant_id: str, agent_id: str) -> list[Rule]:
        cursor = self.db.rules.find({"tenant_id": tenant_id, "agent_id": agent_id})
        docs = await cursor.to_list(None)
        return [Rule(**doc) for doc in docs]

    # Other methods similarly...
```

```python
class MongoStateStore(StateStore):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_interlocutor_data(self, tenant_id: str, customer_key: str) -> InterlocutorDataStore | None:
        doc = await self.db.interlocutor_data.find_one({"tenant_id": tenant_id, "customer_key": customer_key})
        return InterlocutorDataStore(**doc["data"]) if doc else None

    async def save_interlocutor_data(self, interlocutor_data: InterlocutorDataStore) -> None:
        await self.db.interlocutor_data.update_one(
            {"tenant_id": interlocutor_data.tenant_id, "customer_key": interlocutor_data.customer_key},
            {"$set": {"data": interlocutor_data.model_dump()}},
            upsert=True,
        )

    # same pattern for session
```

```python
class MongoAuditStore(AuditStore):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def record_turn(self, record: TurnRecord) -> None:
        await self.db.turn_records.insert_one(record.model_dump())
```

Notice: **engine code doesn’t change** – only the wiring at startup.

---

## 9. Transactions & Unit of Work

### 9.1 Do we need cross-aggregate transactions?

In typical turns, you'll do:

- Update `SessionState`.
- Update `InterlocutorDataStore`.
- Record `TurnRecord`.

Ideally, those are **all-or-nothing**.

- In Postgres, this is easy: use a transaction.
- In Mongo, you may only have per-document atomicity unless using multi-document transactions (cluster requirements).

### 9.2 UnitOfWork abstraction (optional but useful)

To support both worlds, you can introduce a `UnitOfWork` interface:

```python
class UnitOfWork(ABC):
    config: ConfigStore
    state: StateStore
    audit: AuditStore

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb): ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...
```

- `PostgresUnitOfWork` → manages one DB transaction (BEGIN/COMMIT/ROLLBACK).
- `MongoUnitOfWork` → may be a best-effort (no real global transaction), or uses Mongo’s own transaction features if available.

Then in your **Phase 11** code you do:

```python
async with unit_of_work as uow:
    await uow.state.save_session(session)
    await uow.state.save_interlocutor_data(interlocutor_data)
    await uow.audit.record_turn(turn_record)
    await uow.commit()
```

For Postgres: all three writes are transactional.  
For Mongo: either per-document atomic or multi-document transactions depending on setup.

If this feels heavy for v1, you can:

- Start **without** `UnitOfWork`,
- Accept the tiny risk of partial writes on crash,
- Add it later once core behaviour works.

---

## 10. Integration with the 11 Phases

### Phase 1 (load)

- `StateStore`:
  - `find_interlocutor_by_channel`
  - `get_interlocutor_data`
  - `get_session`
- `ConfigStore`:
  - `list_rules_for_agent`
  - `list_scenarios_for_agent`
  - `list_glossary_for_agent`
  - `list_interlocutor_data_fields_for_agent`

### Phase 3 & 11 (update / persist)

- After Phase 3 (in-memory updates), we **only mark** which updates must be persisted.
- In Phase 11:
  - `StateStore.save_session`
  - `StateStore.save_interlocutor_data`
  - `AuditStore.record_turn`

Other phases (2, 4, 5, 6, 7, 8, 9, 10) work purely in memory and with `VectorStore` for retrieval.

---

## 11. Multi-Tenancy Considerations

### 11.1 Tenant first

Every persisted entity has `tenant_id` as a **first-class field**:

- `Rule`, `Scenario`, `ScenarioStep`, `InterlocutorDataStore`, `SessionState`, `TurnRecord`, etc.

Queries in stores always filter by `tenant_id`. Example in Postgres:

```sql
SELECT * FROM rules WHERE tenant_id = :tenant_id AND agent_id = :agent_id;
```

### 11.2 RLS (Row-Level Security) in Postgres (optional)

If you use Postgres and want stronger isolation:

- Use Row-Level Security with policies like:

  ```sql
  CREATE POLICY tenant_isolation ON rules
  USING (tenant_id = current_setting('app.tenant_id')::text);
  ```

Then, in your app code, set `SET app.tenant_id = :tenant_id` per connection.

This is an **extra safety net** on top of the app’s filters.

### 11.3 NoSQL tenant isolation

In Mongo, every document has `tenant_id` and you **always** include it in your queries and indexes:

```python
await db.rules.find_one({"tenant_id": tenant_id, "id": rule_id})
```

---

## 12. Testing Strategy

### 12.1 Pure domain tests

- Test phases 2–10 using **in-memory fake stores**, e.g.:

```python
class InMemoryStateStore(StateStore):
    def __init__(self):
        self.customers = {}
        self.sessions = {}

    async def get_interlocutor_data(self, tenant_id: str, customer_key: str) -> InterlocutorDataStore | None:
        return self.interlocutors.get((tenant_id, customer_key))

    async def save_interlocutor_data(self, data: InterlocutorDataStore) -> None:
        self.interlocutors[(data.tenant_id, data.customer_key)] = data

    # etc.
```

No DB at all; just Python dicts.

### 12.2 Integration tests per backend

For Postgres:

- Spin up a test DB (Docker or tmp).
- Run migrations / schema.
- Run tests against `PostgresConfigStore`, `PostgresStateStore`, `PostgresAuditStore`.

For Mongo:

- Use `mongo-memory-server` or a test container.
- Run the same engine-level tests with `Mongo*Store` implementations.

Because the **engine only depends on the interfaces**, all engine tests can run with **in-memory** or **real DB** depending on the suite.

---

## 13. Evolution & Migration

This abstraction allows you to:

- Start with **Postgres only** (simpler for migrations, joins, SQL tools).
- Later, if some tenants or deployments prefer Mongo, implement a **Mongo adapter** without rewriting the engine.

Schema changes:

- The domain models evolve (e.g. new field on `Rule`),
- You update:
  - DB schema (SQL migrations or Mongo schema migration script),
  - `Postgres*Store` and `Mongo*Store` mapping code (now in `ruche/stores/`),
- Domain logic remains unchanged.

---

## 14. Summary of Decisions

1. **One physical DB per deployment** (Postgres recommended, Mongo possible).
2. Domain objects (`Rule`, `Scenario`, `InterlocutorDataStore`, etc.) are **pure models** (Pydantic), DB-agnostic.
3. Engine interacts with storage via **3 small interfaces**:
   - `ConfigStore`
   - `StateStore`
   - `AuditStore`
   Optionally wrapped in a `Stores` container.
4. These interfaces have **Postgres** and **Mongo** implementations (only one needed for v1).
5. Retrieval / embeddings use a separate `VectorStore` abstraction.
6. Optional `UnitOfWork` if you want cross-aggregate transactions; not required for v1.
7. Multi-tenancy via explicit `tenant_id` field in every persisted entity; RLS is optional but recommended with Postgres.
8. Tests run against **in-memory stores** for domain logic, and against specific DB adapters for integration.

This setup gives you:

- Enough abstraction to **swap SQL/NoSQL later**,
- Without falling into over-engineered “generic DB” territory,
- While keeping your alignment engine code **clean, testable, and focused on the logic**, not the storage.
