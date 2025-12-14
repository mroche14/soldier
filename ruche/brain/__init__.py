"""Cognitive mechanics for Focal.

This module contains different cognitive pipeline implementations
that can be used to process conversational turns.

Available mechanics:
- FOCAL: The primary alignment-based pipeline with 12 phases
- LangGraph: State machine based pipeline (future)
- ReAct: Reasoning and acting loop (future)
"""

from ruche.brain.protocol import CognitivePipeline, PipelineResult, ResponseSegment
from ruche.brain.focal import FocalCognitivePipeline

__all__ = [
    "CognitivePipeline",
    "PipelineResult",
    "ResponseSegment",
    "FocalCognitivePipeline",
]
