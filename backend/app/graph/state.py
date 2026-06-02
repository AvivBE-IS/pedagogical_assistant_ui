"""
LangGraph agent state definition.

GraphState is the single mutable data bag that flows through every node
of the grading pipeline.  Using TypedDict keeps the contract explicit and
makes mypy / pyright verification straightforward.

Separation rationale:
  - State lives here rather than in schemas/models.py because it is an
    internal graph concern, not a serialisation/validation concern.
  - Pydantic models in schemas/models.py describe the HTTP contract.
  - TypedDict here describes the in-process pipeline contract.
"""

from __future__ import annotations

from typing import Optional

from typing_extensions import TypedDict


class GraphState(TypedDict):
    """Accumulates data as it flows through the grading pipeline nodes."""

    # ---- pipeline inputs (populated once before graph.ainvoke) ----
    code: str               # Extracted student submission text
    assignment_text: str    # Assignment description from lesson materials
    official_solution: str  # Reference solution for comparison
    grading_rubric: str     # Scoring criteria (may be the generic sentinel)
    allowed_topics: str     # Comma-separated list of permitted concepts
    lesson_number: int      # Ordinal lesson index (1-based)
    lesson_key: str         # Frontend lesson identifier, e.g. "c1-s1-l3"

    # ---- intermediate outputs (each node populates its own field) ----
    analysis: str           # Node 1: structural code breakdown
    retrieved_context: str  # Node 2: RAG chunks or deterministic fallback
    evaluation: str         # Node 3: rubric-based assessment + cheating verdict

    # ---- terminal outputs (parallel branches after evaluate) ----
    feedback: str           # Node 4a: formatted Hebrew markdown feedback
    score: Optional[int]    # Node 4b: numeric grade 0-100, None if no rubric
    score_explanation: str  # Node 4b: one Hebrew sentence explaining the grade
