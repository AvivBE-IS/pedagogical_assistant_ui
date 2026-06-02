"""
LangGraph state machine — compilation and runner.

Graph topology (evaluate fans out to two parallel branches):

    analyze → retrieve → evaluate ─┬→ feedback → END
                                    └→ score    → END

Feedback and score run in parallel after evaluate — both are
visible as sibling spans in LangSmith under the same trace.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from langgraph.graph import END, StateGraph

from app.graph.nodes import analyze, evaluate, feedback, retrieve, score
from app.graph.state import GraphState

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Build and compile the graph (module-level singleton)
# ---------------------------------------------------------------------------

_workflow = StateGraph(GraphState)

_workflow.add_node("analyze", analyze)
_workflow.add_node("retrieve", retrieve)
_workflow.add_node("evaluate", evaluate)
_workflow.add_node("feedback", feedback)
_workflow.add_node("score", score)          # parallel scoring branch

_workflow.set_entry_point("analyze")
_workflow.add_edge("analyze", "retrieve")
_workflow.add_edge("retrieve", "evaluate")
_workflow.add_edge("evaluate", "feedback")  # branch 1 — parallel
_workflow.add_edge("evaluate", "score")     # branch 2 — parallel
_workflow.add_edge("feedback", END)
_workflow.add_edge("score", END)

grading_graph = _workflow.compile()

# ---------------------------------------------------------------------------
# Runner — called by the POST /api/submissions route handler
# ---------------------------------------------------------------------------


async def run_grading_graph(
    student_code: str,
    assignment_text: str,
    official_solution: str,
    grading_rubric: str,
    allowed_topics: str = "general",
    lesson_number: int = 1,
    lesson_key: str = "",
    run_name: str = "grading_graph",
    metadata: Optional[dict] = None,
) -> tuple[str, bool, Optional[int], str]:
    """
    Execute the grading graph and return a 4-tuple.

    Parameters
    ----------
    run_name:
        LangSmith trace label — set to the submitted filename for easy lookup.
    metadata:
        Key/value evidence visible in the LangSmith Metadata tab.

    Returns
    -------
    feedback_text:
        Cleaned Hebrew markdown feedback (CHEATING_VERDICT line stripped out).
    cheating_flag:
        True when the LLM emitted CHEATING_VERDICT: YES.
    score:
        Numeric grade 0-100, or None when no rubric was uploaded.
    score_explanation:
        One Hebrew sentence explaining the grade (or why scoring was skipped).
    """
    initial_state: GraphState = {
        "code": student_code,
        "assignment_text": assignment_text,
        "official_solution": official_solution,
        "grading_rubric": grading_rubric,
        "allowed_topics": allowed_topics,
        "lesson_number": lesson_number,
        "lesson_key": lesson_key,
        # Output fields — each node populates its own field on return
        "analysis": "",
        "retrieved_context": "",
        "evaluation": "",
        "feedback": "",
        "score": None,
        "score_explanation": "",
    }

    final_state = await grading_graph.ainvoke(
        initial_state,
        config={
            "run_name": run_name,
            "metadata": metadata or {},
        },
    )

    raw_feedback: str = final_state["feedback"]

    # Parse the cheating verdict embedded by the evaluate node.
    cheating_flag = bool(
        re.search(r"CHEATING_VERDICT:\s*YES", raw_feedback, re.IGNORECASE)
    )

    # Strip the verdict line — it is internal metadata, not shown to students.
    clean_fb = re.sub(
        r"\nCHEATING_VERDICT:\s*(YES|NO)\s*$",
        "",
        raw_feedback,
        flags=re.IGNORECASE,
    ).strip()

    # Remove stray ASCII/Latin characters that slip through Hebrew-only prompts.
    clean_fb = re.sub(
        r"[^\u05d0-\u05ea\u05f0-\u05f4\s\d.,!?()'\"\\[\]#/:*\-\u2013\u2014\n]",
        "",
        clean_fb,
    )

    ai_score: Optional[int] = final_state.get("score")
    score_explanation: str = final_state.get("score_explanation", "")

    log.info(
        "Grading complete | lesson=%s cheating=%s score=%s",
        lesson_key,
        cheating_flag,
        ai_score,
    )

    return clean_fb, cheating_flag, ai_score, score_explanation


# ---------------------------------------------------------------------------
# Build and compile the graph (module-level singleton)
# ---------------------------------------------------------------------------

_workflow = StateGraph(GraphState)

_workflow.add_node("analyze", analyze)
_workflow.add_node("retrieve", retrieve)
_workflow.add_node("evaluate", evaluate)
_workflow.add_node("feedback", feedback)
_workflow.add_node("score", score)          # parallel scoring branch

_workflow.set_entry_point("analyze")
_workflow.add_edge("analyze", "retrieve")
_workflow.add_edge("retrieve", "evaluate")
_workflow.add_edge("evaluate", "feedback")  # branch 1
_workflow.add_edge("evaluate", "score")     # branch 2 — runs in parallel
_workflow.add_edge("feedback", END)
_workflow.add_edge("score", END)

grading_graph = _workflow.compile()

# ---------------------------------------------------------------------------
# Runner — called by the POST /api/submissions route handler
# ---------------------------------------------------------------------------

async def run_grading_graph(
    student_code: str,
    assignment_text: str,
    official_solution: str,
    grading_rubric: str,
    allowed_topics: str = "general",
    lesson_number: int = 1,
    lesson_key: str = "",
    run_name: str = "grading_graph",
    metadata: dict | None = None,
) -> tuple[str, bool, int | None, str]:
    """
    Execute the grading graph and return a 4-tuple.

    Parameters
    ----------
    run_name : str
        LangSmith trace label — set to the submitted filename for easy lookup.
    metadata : dict
        Key/value evidence visible in the LangSmith Metadata tab.

    Returns
    -------
    feedback_text : str
        Cleaned Hebrew markdown feedback (CHEATING_VERDICT line stripped out).
    cheating_flag : bool
        True when the LLM emitted CHEATING_VERDICT: YES.
    score : int | None
        Numeric grade 0-100, or None when no rubric was uploaded.
    score_explanation : str
        One Hebrew sentence explaining the grade (or why scoring was skipped).
    """
    initial_state: GraphState = {
        "code": student_code,
        "assignment_text": assignment_text,
        "official_solution": official_solution,
        "grading_rubric": grading_rubric,
        "allowed_topics": allowed_topics,
        "lesson_number": lesson_number,
        "lesson_key": lesson_key,
        # Output fields — each node populates its own field
        "analysis": "",
        "retrieved_context": "",
        "evaluation": "",
        "feedback": "",
        "score": None,
        "score_explanation": "",
    }

    final_state = await grading_graph.ainvoke(
        initial_state,
        config={
            "run_name": run_name,
            "metadata": metadata or {},
        },
    )

    raw_feedback: str = final_state["feedback"]

    # Parse cheating verdict embedded by the feedback node
    cheating_flag = bool(
        re.search(r"CHEATING_VERDICT:\s*YES", raw_feedback, re.IGNORECASE)
    )

    # Strip the verdict line — internal metadata, not shown to students
    clean_fb = re.sub(
        r"\nCHEATING_VERDICT:\s*(YES|NO)\s*$",
        "",
        raw_feedback,
        flags=re.IGNORECASE,
    ).strip()

    # Remove any stray non-Hebrew characters that are not digits, punctuation,
    # whitespace, or standard Markdown markers (#, *, etc.)
    clean_fb = re.sub(
        r"[^\u05d0-\u05ea\u05f0-\u05f4\s\d.,!?()'\"\\[\]#/:*\-\u2013\u2014\n]",
        "",
        clean_fb,
    )

    ai_score: int | None = final_state.get("score")
    score_explanation: str = final_state.get("score_explanation", "")

    return clean_fb, cheating_flag, ai_score, score_explanation
