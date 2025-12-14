# FOCAL Pipeline Phases

This directory will contain individual phase implementations extracted from the main pipeline.py file.

## Planned Phase Modules

1. **p01_identification.py** - Customer resolution and context loading
2. **p02_situational.py** - Situational sensor for intent and variable extraction
3. **p03_data_update.py** - In-memory customer data updates
4. **p04_retrieval.py** - Parallel retrieval of rules, scenarios, intents, memory
5. **p05_reranking.py** - Reranking of retrieval candidates
6. **p06_filtering.py** - LLM-based filtering of rules and scenarios
7. **p07_orchestration.py** - Scenario graph navigation
8. **p08_planning.py** - Response planning from scenario contributions
9. **p09_execution.py** - Tool execution
10. **p10_generation.py** - Response generation
11. **p11_enforcement.py** - Constraint validation and enforcement
12. **p12_persistence.py** - Parallel persistence to stores

## Current State

All phase logic currently resides in `pipeline.py` as private methods of the `FocalCognitivePipeline` class.

Future refactoring will extract each phase into its own module with a consistent interface.
