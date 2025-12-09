This is the comprehensive architectural specification for a **Deterministic, Multi-Tenant Agentic Rule Engine**.

It synthesizes the **Amazon AgentCore** philosophy (Deterministic Policy + Probabilistic Grounding) with the **Parlant AlphaEngine** workflow (Graph Retrieval, Iterative Loops, and Scoping).

---

# Architecture: The "Graph-Augmented State Machine"

### Core Philosophy
We decouple **Perception** (LLM) from **Decision** (Code).
1.  **Perception is Probabilistic:** The LLM observes reality and fills a structured schema (The "Sensor").
2.  **Retrieval is Relational:** Rules are not isolated vectors; they are a connected graph of definitions and dependencies.
3.  **Execution is Deterministic:** Python code applies logic to the schema. No LLM "thinks" about the rules.

---

## I. Data Layer: The Rule Graph (Schema)
To solve "Retrieval Fragmentation" (the Parlant problem), we do not store flat lists of rules. We store a directed graph.

**Storage:** Vector Database (for semantic search) + Relational/Graph DB (for metadata).

```json
{
  "tenant_id": "tenant_123",
  "node_id": "rule_refund_cap",
  "type": "RULE", // or "DEFINITION", "JOURNEY_NODE"
  
  // 1. Scoping (Parlant "Journey-Scoped Guidelines")
  // Rules are only visible in specific agent states to prevent pollution.
  "scope": ["global", "journey_refund_flow"],
  
  // 2. The Logic (Amazon "AgentCore Policy")
  // The raw material for the deterministic engine.
  "logic_expression": "refund_amount <= 50 and user_is_premium",
  "natural_language": "Premium users can get refunds up to $50.",

  // 3. Relationships (Parlant "Graph Expansion")
  // Hard links to ensure context integrity.
  "relationships": {
    "depends_on_definitions": ["def_premium_user"], 
    "entails_rules": ["rule_log_transaction"], // If this runs, that MUST run
    "excludes_rules": ["rule_reject_all"]
  }
}
```

---

## II. Runtime Architecture: The Iterative Loop

We abandon the linear "Input $\to$ Answer" flow. We adopt an **Iterative State Loop** to resolve tools and ambiguity *before* disturbing the user.

### The Pipeline Steps

1.  **Context Scoping:** Determine current User State.
2.  **Graph Retrieval:** Fetch Rules + Expand Definitions.
3.  **Semantic Normalization (The Intermediary):** Extract State + Ambiguity Check.
4.  **Auto-Resolution Loop:** If variables are missing, call Tools silently.
5.  **Deterministic Enforcement:** Execute Python Logic.
6.  **Response Generation & Guardrails:** Generate text and check for hallucinations.

---

### Step 1: Context Scoping & Graph Retrieval
**Goal:** Load the correct rules without pollution.

```python
def retrieve_context(tenant_id, user_query, current_state):
    # 1. Vector Search (Semantic)
    # Filter by Scope to avoid "Onboarding" rules appearing in "Refund" flow.
    hits = vector_db.search(
        query=user_query, 
        filters={"tenant_id": tenant_id, "scope": ["global", current_state]}
    )
    
    context_nodes = {hit.id: hit for hit in hits}
    
    # 2. Graph Expansion (The Parlant Mechanism)
    # Recursively pull in dependencies so the LLM understands terms.
    for node in list(context_nodes.values()):
        # Pull Definitions (e.g., What is "Premium User"?)
        for def_id in node.relationships.get("depends_on_definitions", []):
            if def_id not in context_nodes:
                context_nodes[def_id] = db.get(def_id)
                
        # Pull Entailed Rules (e.g., "Must Log Transaction")
        for rule_id in node.relationships.get("entails_rules", []):
            if rule_id not in context_nodes:
                context_nodes[rule_id] = db.get(rule_id)
                
    return list(context_nodes.values())
```

---

### Step 2: Semantic Normalization (The Intermediary Step)
**Goal:** Convert Unstructured Text $\to$ Structured State.
**Critical Addition:** We extract `ambiguity` and `confidence` (Amazon/Parlant insight).

**The System Prompt:**
```text
You are a Fact Extraction Engine. 
You are provided with a User Query and a set of Definitions.

DEFINITIONS:
- "Premium User": Spent > $1000 in last year.
- "Fragile Item": Glass, Ceramics.

TASK:
Analyze the text. Output JSON only. 
If the user is vague, set "is_ambiguous": true.

OUTPUT SCHEMA:
{
  "variables": {
     "refund_amount": float or null,
     "item_type": string or null,
     "is_premium": boolean
  },
  "meta": {
     "is_ambiguous": boolean,
     "ambiguity_reason": string,
     "confidence_score": float (0.0-1.0)
  }
}
```

---

### Step 3: The Iterative Resolution Loop
**Goal:** Solve missing data via tools *before* asking the user.

```python
def process_interaction(tenant_id, history, state_machine):
    
    loop_count = 0
    max_loops = 3
    
    while loop_count < max_loops:
        # 1. Retrieve & Extract
        context_nodes = retrieve_context(tenant_id, history[-1], state_machine.current_state)
        state = semantic_normalizer.extract(history, context_nodes)
        
        # 2. AMBIGUITY TRAP (Parlant Insight)
        # If the user made no sense, exit immediately. Don't guess.
        if state.meta.is_ambiguous:
             return generate_clarification_question(state.meta.ambiguity_reason)

        # 3. LOGIC CHECK (Identifying Missing Data)
        # We check if we have enough data to execute the retrieved rules.
        missing_vars = []
        for rule in context_nodes:
            if not can_evaluate(rule.logic_expression, state.variables):
                missing_vars.extend(get_required_vars(rule))
        
        # 4. SILENT TOOL RESOLUTION (The "AlphaEngine" Loop)
        # If we miss 'order_status', check if a tool can get it.
        tool_triggered = False
        for var in missing_vars:
            tool = find_tool_for_variable(var)
            if tool:
                result = execute_tool(tool)
                history.append({"role": "tool_output", "content": result})
                state.variables[var] = result # Update state
                tool_triggered = True
        
        if tool_triggered:
            loop_count += 1
            continue # LOOP: Re-evaluate logic with new tool data
            
        # 5. USER INTERVENTION
        # If variables are still missing and no tool can find them, ask user.
        if missing_vars:
            return generate_question_for_user(missing_vars)
            
        # If we are here, we have all data. Break loop and execute.
        break

    return execute_deterministic_logic(state, context_nodes)
```

---

### Step 4: Deterministic Policy Engine (The Enforcer)
**Goal:** Execute Logic safely (`simpleeval`).

```python
from simpleeval import simple_eval

def execute_deterministic_logic(state, rules):
    violations = []
    actions = []

    for rule in rules:
        if rule.type != "RULE": continue
        
        # Safe Evaluation: "amount < 50" -> True/False
        try:
            # We assume rule structure: "condition" -> "action"
            # Or "condition" -> "block"
            is_triggered = simple_eval(rule.logic_expression, names=state.variables)
            
            if is_triggered:
                if rule.is_blocking:
                    violations.append(rule.failure_message)
                else:
                    actions.append(rule.success_action)
                    
        except Exception as e:
            # Fallback for bad rules
            print(f"Rule Execution Error: {e}")

    if violations:
        return {"status": "BLOCKED", "messages": violations}
    
    return {"status": "ALLOWED", "actions": actions}
```

---

## III. Guardrail Layer: Output Verification
**Goal:** Amazon Bedrock-style final check.

Once the Deterministic Engine allows the action and the LLM generates the polite response, we run the final low-latency checks (Self-Hosted ONNX or Groq).

1.  **Relevance Check:**
    *   *Input:* User Query + Agent Response.
    *   *Model:* `cross-encoder/ms-marco-MiniLM-L-6-v2` (ONNX/CPU).
    *   *Logic:* If score < 0.5 AND response is not a "Refusal", Block.

2.  **Grounding Check (Hallucination):**
    *   *Input:* Retrieved Context (Definitions/Rules) + Agent Response.
    *   *Model:* `cross-encoder/nli-deberta-v3-base` (ONNX/CPU) or Llama-3-70B (Groq) Prompt.
    *   *Logic:* If Entailment Score < 0.8, Block.

---

## Summary of Advantages

| Component | Your Previous Design | **New "Graph-Augmented" Design** |
| :--- | :--- | :--- |
| **Logic** | Deterministic | Deterministic |
| **Retrieval** | Fragile (Vector only) | **Robust** (Graph: pulls definitions & chains) |
| **Flow** | Linear (Ask user immediately) | **Iterative** (Try tools first, then ask) |
| **Ambiguity** | Biased to Guessing | **Explicit Trap** (Stops execution if vague) |
| **Scaling** | Search all rules (Pollution) | **Scoped** (Search only relevant State) |

This architecture delivers the **precision of code** (via the Deterministic Engine) with the **cognitive flexibility of an agent** (via the Graph Retrieval and Iterative Loop).