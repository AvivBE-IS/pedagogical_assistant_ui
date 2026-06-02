"""
LangGraph conditional edge routing functions.

Convention: each function receives the current GraphState and returns the
name of the next node (a string).  LangGraph calls these functions
automatically when the edge is registered with add_conditional_edges().

The pipeline currently uses static parallel edges from evaluate, so no
conditional routing is active.  This module is the designated extension
point for future branching requirements such as:
  - Fast-path rejection for empty submissions.
  - Re-route flagged submissions directly to an instructor queue.
  - Retry evaluate when an LLM parse error is detected.
"""

from __future__ import annotations

from app.graph.state import GraphState


def route_after_evaluate(state: GraphState) -> str:  # noqa: ARG001
    """
    Placeholder conditional router after the evaluate node.

    Currently unused — the workflow uses two static add_edge() calls from
    evaluate to feedback and score instead, which LangGraph runs in parallel.

    Extend this function when conditional branching is required:
      - Return "flag_review" to bypass student-facing feedback for high-risk submissions.
      - Return "feedback" or "score" individually to disable one branch.
    """
    return "feedback"
