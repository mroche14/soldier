"""FOCAL cognitive pipeline implementation.

This module implements the FOCAL (Focused Contextual Alignment) pipeline,
which is the core alignment mechanic for processing conversational turns.

The FocalCognitivePipeline coordinates 12 phases:
1. Identification & Context Loading - Resolve customer, load session & history
2. Situational Sensor - Extract intent, tone, candidate variables
3. Interlocutor Data Update - Update customer profile in-memory
4. Retrieval - Find candidate rules, scenarios, memory
5. Reranking - Improve candidate ordering
6. LLM Filtering - Judge which rules/scenarios apply
7. Scenario Orchestration - Navigate scenario graph
8. Response Planning - Build response plan from contributions
9. Tool Execution - Execute tools from matched rules
10. Response Generation - Generate natural language response
11. Enforcement - Validate against constraints
12. Persistence - Save session, customer data, turn record
"""

from ruche.mechanics.focal.pipeline import FocalCognitivePipeline

__all__ = ["FocalCognitivePipeline"]
