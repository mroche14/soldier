# Special Note – Data Storage, Replication & “Brain-Only” Mode

> **Purpose of this note**  
> This section explains how our alignment engine manages customer and business data when interacting with external systems (CRM, ERP, OMS, Shopify, etc.). It clarifies what we mean by “brain-only” mode, why some level of data replication is unavoidable, and how we control it in a precise and configurable way.

---

## 1. Reality Check: Pure “Brain-Only” Is Impossible

Our engine is designed to act as a **reasoning and orchestration brain** on top of external systems. In theory, this could mean:

- *“We store nothing, we only call your tools (CRM, ERP, Shopify, etc.).”*

In practice, this is **not realistic**:

- As soon as we call a tool (e.g. a CRM API) and use the result to:
  
  - answer the user,
  - maintain a multi-turn conversation,
  - enforce rules and scenarios,
  - or debug issues later,
  
  we **must** keep some representation of that data, at least:
  
  - in-memory for the current turn,
  - often in session state (for continuity across messages),
  - and sometimes in logs or metrics (for observability).

So the question is **not** whether we replicate data (we do), but **how much, how long, and in what form**.

---

## 2. Three Conceptual Layers: SoR, Cache, Logs

To reason clearly about data, we distinguish three layers:

1. **System of Record (SoR)**  
   Where the **truth** lives.
   
   - Example: Salesforce/HubSpot as CRM, Shopify as e‑commerce, custom ERP as order management.
   - For some tenants without a CRM, our own database can be the SoR.

2. **Operational State / Cache**  
   What the **brain** uses to think and act efficiently.
   
   - `CustomerDataStore` & `SessionState` (logical view of customer + session variables).
   - May be backed by:
     - internal DB (Postgres),
     - in-memory cache (Redis, etc.),
     - or re-hydrated from external systems.
   - This layer can replicate **a subset** of SoR data for performance and reliability.

3. **Logs & Observability**  
   What we keep for:
   
   - debugging and tracing,
   - metrics and analytics,
   - compliance/audit when required.
   - It may contain:
     - full payloads,
     - redacted/hashed values,
     - or only metadata (tool name, success/fail, latency) depending on configuration.

These three layers can be configured **per tenant** and even **per variable**.

---

## 3. Per-Variable Storage Modes

For each variable defined in the system (e.g. `email`, `customer_tier`, `last_order_id`), we allow a **storage policy**:

```python
class VariableDefinition(BaseModel):
    key: str
    scope: Literal["IDENTITY", "BUSINESS", "CASE", "SESSION"]
    type: Literal["string", "number", "boolean", "datetime", "json"]

    storage_mode: Literal[
        "INTERNAL_ONLY",    # Our DB is the System of Record
        "EXTERNAL_ONLY",    # External system (CRM/ERP/etc.) is System of Record
        "HYBRID_CACHE",     # External is SoR, our DB holds a long-term cache
        "SESSION_ONLY"      # Per-session only, never persisted
    ]

    # Whether we keep a durable copy in our internal DB
    persist_in_db: bool = True

    # Whether we store complete payloads in logs/traces
    log_payloads: bool = False

    # Resolver ID used to read/write this field in external systems
    external_resolver_id: str | None = None
```

### 3.1. INTERNAL_ONLY

- **Use case**:  
  Tenants **without** a CRM, or fields that exist only in our engine (e.g. internal scores, preferences, scenario state).
- **SoR**: our database.
- **Behaviour**:
  - Read/write in our DB.
  - Can optionally be synced out via tools if needed.

### 3.2. EXTERNAL_ONLY

- **Use case**:  
  Tenants **with** CRM/ERP/Shopify where the business insists that the external system is the single source of truth for a field.
- **SoR**: external system only.
- **Behaviour**:
  - Reads: via tools (e.g. `crm.get_email`), optionally cached in memory or session.
  - Writes: via tools (e.g. `crm.update_email`).
  - `persist_in_db = False` means we **do not** store a durable copy in our DB; any local copy is treated as **temporary (cache/session)**.
  - `log_payloads = False` can be used to avoid storing raw values in logs; we only log metadata.

### 3.3. HYBRID_CACHE

- **Use case**:  
  External system is the SoR, but we want a **long-lived cache** in our DB for performance, resilience or analytics.
- **SoR**: external system.
- **Behaviour**:
  - Reads:
    - Use local cache if fresh,
    - Otherwise call external resolver and refresh the cache.
  - Writes:
    - Update external system,
    - Then update our cached copy.
  - This is explicitly a mirror: if needed, we can reconstruct or prune it.

### 3.4. SESSION_ONLY

- **Use case**:  
  Very sensitive or transient information (e.g. one-time codes, temporary choices) that should **not survive the session**.
- **SoR**: none (session-level only).
- **Behaviour**:
  - Values live only in `SessionState` for the duration of the conversation/session.
  - Never persisted to the long-term profile DB.
  - Typically, only minimal/logical hints are stored in logs, if at all.

---

## 4. How This Affects the Engine Behaviour

### 4.1. Reads (resolving variables)

When the engine needs a variable (e.g. a rule or scenario step requires `last_order_id`), it uses the `storage_mode`:

- `INTERNAL_ONLY`  
  → read it directly from `CustomerDataStore` (our DB).

- `EXTERNAL_ONLY`  
  → call the configured resolver tool (e.g. `shopify.get_last_order_id`),  
  → optionally place the result in:
  
  - in-memory structures for this turn,
  - `SessionState` for the rest of the session,
  - **not** in the persistent DB if `persist_in_db = False`.

- `HYBRID_CACHE`  
  → try to read from internal cache,  
  → if stale or missing, call the external system and refresh the cache.

- `SESSION_ONLY`  
  → read from `SessionState` only.

From a **rules/scenarios** perspective, nothing changes: they just ask for `var("last_order_id")`. The storage policy is handled by the engine.

### 4.2. Writes (updating variables)

When the LLM sensor or tools produce updated values:

- `INTERNAL_ONLY`  
  → write into our DB (`CustomerDataStore`) as the source of truth.

- `EXTERNAL_ONLY`  
  → write to the external system via tool (`external_resolver_id`),  
  → possibly keep a **short-lived session copy**, but no durable DB record if `persist_in_db = False`.

- `HYBRID_CACHE`  
  → write to external system (SoR) and update our DB cache.

- `SESSION_ONLY`  
  → write only into `SessionState`, cleared when the session ends.

---

## 5. Why This Is Still Valuable Even If We “Replicate” Data

It is true that we **cannot avoid** having some replication:

- A response the user sees often includes values coming from external tools.
- Multi-turn reasoning requires us to remember some data across messages.
- Safety, enforcement and debugging benefit from having some trace of what happened.

However, this design is still extremely valuable because it lets us:

1. **Choose the real System of Record per tenant and per variable**
   
   - For some tenants, our DB acts as a mini-CRM.
   - For others, their CRM/ERP/Shopify remains the only SoR.

2. **Control the amount and duration of local copies**
   
   - From “no durable copy, session-only” → up to “full hybrid mirror with analytics”.

3. **Control what goes into logs and observability**
   
   - We can log:
     - full payloads (for internal/testing environments),
     - or redacted/hashed IDs only (for production with strict compliance).

4. **Express data policies explicitly**
   
   - Instead of opaque glue code, the storage policy becomes a first-class, declarative part of the configuration (`VariableDefinition`).

---

## 6. Example Tenant Profiles

### 6.1. Tenant A – No CRM (we act as mini-CRM)

- Most variables:
  
  ```toml
  storage_mode = "INTERNAL_ONLY"
  persist_in_db = true
  log_payloads = true/false (depending on sensitivity)
  ```

- Our DB is the SoR for customer data.

- External tools might handle payments, shipping, etc., but identity and customer profile live primarily in our system.

### 6.2. Tenant B – Has CRM & Shopify (we act as brain + cache)

- Identity / business fields from CRM (email, company, tier):
  
  ```toml
  storage_mode = "EXTERNAL_ONLY"       # or "HYBRID_CACHE"
  persist_in_db = false                # or true if we want a long-term cache
  external_resolver_id = "crm.contact"
  log_payloads = false                 # log only metadata
  ```

- E‑commerce context fields (last_order_id, last_cart_total) from Shopify:
  
  ```toml
  storage_mode = "HYBRID_CACHE"
  persist_in_db = true
  external_resolver_id = "shopify.customer_orders"
  ```

- Internal AI-only variables (scenario state, behaviour scores, etc.):
  
  ```toml
  storage_mode = "INTERNAL_ONLY"
  persist_in_db = true
  ```

- Ultra-sensitive transient inputs:
  
  ```toml
  storage_mode = "SESSION_ONLY"
  persist_in_db = false
  log_payloads = false
  ```

This allows Tenant B to keep their existing systems as SoR, while our engine provides alignment, orchestration and intelligence on top, with a clearly bounded and configurable level of local replication.

---

## 7. Summary

- A **zero-storage** AI brain is a myth: as soon as we interact with external systems and offer multi-turn, auditable conversations, some level of data replication is unavoidable.
- Our design acknowledges this and makes **data storage and replication a first-class, configurable concept**:
  - per variable,
  - per tenant,
  - with explicit choices about:
    - System of Record,
    - persistence,
    - caching,
    - and logging.
- This is what allows us to support:
  - tenants with no CRM (we become a mini-CRM),
  - tenants with strong existing systems (we are a thin, alignment-focused brain on top),
  - and nuanced data policies (privacy-sensitive, compliant deployments).

This note can be included as a dedicated “Data Storage & Replication Policy” section in the architecture or alignment engine specification.
