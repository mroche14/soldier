This is a comprehensive architectural design document addressing your specific context: **Multi-tenant SaaS, Scenario-based (Journeys), Self-evolving Customer Profiles, and Deterministic Rule Enforcement.**

I have integrated our previous conclusions regarding **Policy Checking** (Deterministic vs. Probabilistic) and **Parlant-style Relationships** into this unified system.

---

# Architectural Design Document: The "State-Aware" Agent Engine

## 1. The Core Data Model
To support your requirements (Scoped Rules, Mutable Profiles, Scenarios), we must define the data structures rigorously. This is the "Skeleton" of your system.

### A. The Self-Evolving Customer Profile (`CustomerProfile`)
This is not just a JSON dict; it is a **Ledger**.
*   **Structure:**
    ```json
    {
      "tenant_id": "tenant_123",
      "user_id": "user_abc",
      "variables": {
        "country": {
          "value": "France",
          "history": [
            {"val": "USA", "timestamp": 1700001, "source": "inference"},
            {"val": "France", "timestamp": 1700005, "source": "user_correction"}
          ],
          "confidence": 1.0
        },
        "delivery_address": { ... }
      }
    }
    ```
*   **Evolution Logic:** When the **Setup Agent** creates a rule like *"If user is under 18..."*, it automatically registers `age` as a required key in the Profile Schema for that tenant.

### B. The Scenario (Journey) Structure
A directed graph representing the ideal path.
*   **Nodes (Steps):**
    *   **Action:** Execute Tool (e.g., `check_order`).
    *   **Interaction:** Ask User (e.g., "What is your order ID?").
    *   **Logic:** Internal Check (e.g., `if profile.is_vip`).
*   **Edges (Transitions):**
    *   Triggered by **Intents** (e.g., `user_confirms`) or **Conditions** (e.g., `balance > 0`).
*   **Scopes:**
    *   Each Step contains a list of **Scoped Rules** (e.g., "Don't ask for ID twice").

### C. The Intent Registry (`IntentRegistry`)
*   **Purpose:** A catalog of "Actions the user wants to take."
*   **Storage:** Vector Database + SQL.
*   **Example:**
    *   **Intent:** `request_refund`
    *   **Embeddings:** ["I want my money back", "Refund me", "Return this item"]
    *   **Linked Scenario:** `scenario_refund_process`

---

## 2. Phase 1: The Setup Process (The "Builder")
*You mentioned an agent that sets up scenarios/rules from a prompt. This is critical for preventing "Garbage In."*

**The "Incoherence Detector" Workflow:**
1.  **Ingestion:** User inputs: *"I want an agent that handles returns. VIPs get instant refunds."*
2.  **Analysis (LLM):** The Builder Agent analyzes this against the **Meta-Model**.
3.  **Ambiguity Detection:**
    *   *Ambiguity:* "You mentioned VIPs. How do we define a VIP?" (Missing Variable Definition).
    *   *Incoherence:* "You said instant refunds, but earlier you set a global rule of 'Manual approval for all money movement'. Which takes precedence?" (Rule Conflict).
4.  **Schema Generation:**
    *   Updates `CustomerProfile` schema (adds `is_vip`).
    *   Creates `Scenario: Return_Flow`.
    *   Creates `Rule: refund_policy` (Scoped to `Return_Flow`).

---

## 3. Phase 2: The Runtime Engine (The "Brain")
This is where we solve your specific problem: **Intent vs. Context vs. Scenario State.**

### The Brain
```text
[User Message] -> [1. Extractor] -> [2. Router] -> [3. Scenario Engine] -> [4. Action/Gen] -> [5. Output Check]
```

### Step 1: The Extractor (Sensor)
*Combined Context & Intent Extraction.*
Instead of just "Context Extraction," we perform parallel classification.

*   **Sub-process A: Variable Extraction (Updating Profile)**
    *   LLM extracts entities based on the *current* Profile Schema.
    *   *Result:* Updates `CustomerProfile` (e.g., `country: France`).
*   **Sub-process B: Intent Detection (The Semantic Search)**
    *   **Do not rely solely on "Context Extraction."** You need explicit categorization.
    *   **Search Scope:**
        1.  **Global Intents:** (Start new scenario).
        2.  **Local Intents:** (Valid transitions from the *current* Scenario Step).
    *   **Mechanism:** Vector search against the `IntentRegistry`.
    *   *Output:* `Detected_Intent: "cancel_order" (Confidence: 0.92)`

### Step 2: The Router (The Orchestrator)
*Decides if we stay in the current Scenario, switch, or exit.*

*   **Logic:**
    1.  **Check Global Rules (Blocking):** (Using the Deterministic Engine we designed previously).
        *   *Example:* "User is banned." -> `STOP`.
    2.  **Check Current Scenario:**
        *   If `Active_Scenario` exists: Does `Detected_Intent` match a valid **Transition** from `Current_Step`?
            *   *Yes:* Advance to Next Step.
            *   *No:* Check Global Start Intents (Did the user change the subject?).
    3.  **Conflict Resolution:**
        *   If User is in `Refund_Scenario` (Step: asking for IBAN) but says "Stop, I want to buy something instead" (`buy_intent`), the Router detects the `Global Intent` overrides the `Local Transition`.

### Step 3: The Scenario Engine (The State Machine)
*Executes the Logic.*

1.  **Load Rules:** Merge **Global Rules** + **Active Scenario Rules** + **Current Step Rules**.
2.  **Evaluate:** Run the **Deterministic Rule Engine** (from previous discussions).
    *   *Input:* `CustomerProfile` + `Current_State`.
    *   *Check:* Are we allowed to execute the Action defined in this Step?
3.  **Execute:**
    *   If Action is `Ask_User`: Generate question.
    *   If Action is `Tool`: Call Tool.

### Step 4: Output Check (The Guardrail)
*   **Mechanism:** The "Output Check Component" we designed earlier (Policy + Hallucination).
*   **Input:** The final text or tool call.
*   **Role:** Final safety net before the user sees anything.

---

## 4. Answering Your Specific Concerns

### A. "Intent Detection vs. Context Extraction"
> *Recommendation:* **Separate them but run them in parallel.**

*   **Context Extraction** is for **Data** (filling the `CustomerProfile`). It answers "What do we know?"
*   **Intent Detection** is for **Navigation** (moving through the Scenario Graph). It answers "Where do we go?"
*   **Why?** You might extract context ("User is angry") without changing intent (User still wants to "Check Status"). If you mix them, your navigation becomes "fuzzy" and prone to bugs.

### B. "Known Intents Registry" & Observability
> *Recommendation:* **Use it for 'Few-Shot Classification' and 'Heatmaps'.**

You mentioned forgetting the purpose of the registry. Here is why it is vital:
1.  **Optimization (RAG for Classification):** Instead of asking the LLM "What is the intent?" (Zero-shot), you retrieve 5 past examples of "Refund Requests" from the registry and say: "Here are examples of refunds. Does this new message look like them?" This drastically improves accuracy.
2.  **Business Observability:** You can show the business owner a "Heatmap":
    *   *"60% of your users are triggering the 'Refund' intent, but only 10% finish the Scenario. You have a blockage at Step 3."*
    *   This is only possible if you have a structured `IntentRegistry` and not just fuzzy context.

### C. "Self-Evolving CustomerProfile"
> *Recommendation:* **Schema Versioning.**

When the Setup Agent adds a new variable (e.g., `shoe_size`), it versions the schema.
*   **Runtime:** When the Extractor runs, it pulls the *latest* schema for that tenant.
*   **Traceability:** The `history` list in your Profile object is crucial. If a rule misfires because of "wrong country," you need to be able to debug: *"Ah, at 14:00 the Extractor inferred 'France' from 'Bonjour', but at 14:05 the user said 'I am in Quebec'."*

### D. Applying Rules (Deterministic vs. Not)
> *Recommendation:* **The "Hybrid" Approach.**

Use the architecture we finalized in the previous turn:
1.  **Extraction:** LLM populates the `CustomerProfile` and flags (e.g., `is_angry: true`).
2.  **Application:** Python Logic Engine applies the scoped rules to these flags.
    *   *Global Rule:* `if is_angry: escalate_to_human()`
    *   *Scenario Rule:* `if refund_amount > 50: require_reason()`

---

## 5. Potential Pitfalls (The Critique)

1.  **The "Context Window" Trap:**
    *   *Risk:* Passing *all* Global Rules, Scenario Rules, and Profile History to the LLM for every turn will blow up costs and latency.
    *   *Solution:* You need **Rule Retrieval**. Only inject Global Rules + Current Scenario Rules. Do not inject Rules from other Scenarios.

2.  **The "Stuck User" Problem:**
    *   *Risk:* A user is in a Scenario Step waiting for "Yes/No". They say "Maybe". The Intent Detector fails to map "Maybe" to a Transition. The bot loops.
    *   *Solution:* Implement a **"Fallback Transition"** in every Scenario Step. If no Intent matches, trigger a generic "Clarification" intent or "Escalate".

3.  **Scenario "Ping-Pong":**
    *   *Risk:* User says something ambiguous that matches the start of Scenario A and Scenario B. The Router flickers between them.
    *   *Solution:* **Stickiness.** If `Active_Scenario` is set, bias the Intent Detector heavily towards *Local Transitions* over *Global Intents*. Only switch if confidence is very high (>0.85).

## Summary of the Solution

1.  **Setup:** Builder Agent acts as a compiler, turning natural language into a **Scenario Graph**, **Profile Schema**, and **Intent Registry**.
2.  **Input:** User text is split into **Data** (Profile update) and **Signal** (Intent).
3.  **Routing:** A "Sticky Router" prioritizes the current Scenario's edges but listens for Global "Exit/Start" signals.
4.  **Execution:** Rules are applied deterministically based on the extracted Profile state.
5.  **Output:** Final generation is validated against Policy/Hallucination checks.

This structure allows you to promise **"Constraint Following"** (via Scoped Rules) and **"Process Adherence"** (via Scenarios) while handling the messiness of human conversation (via LLM Extraction).