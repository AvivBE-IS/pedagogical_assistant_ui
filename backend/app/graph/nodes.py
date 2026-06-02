"""
LangGraph node functions — one async function per pipeline stage.

Each node:
  1. Receives the full GraphState.
  2. Performs exactly one responsibility.
  3. Returns a partial dict containing only the fields it mutates.

Pipeline topology:
    analyze → retrieve → evaluate ┬→ feedback  (parallel)
                                    └→ score     (parallel)

This module intentionally contains ALL node functions so that the graph
wiring in workflow.py has a single, predictable import source.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.config.llm_config import get_llm
from app.graph.state import GraphState
from app.prompts.system_prompts import (
    analyze_prompt,
    evaluate_prompt,
    feedback_prompt,
    score_prompt,
)

log = logging.getLogger(__name__)

# Sentinel rubric string used when no real rubric file was uploaded.
# Keeping it here avoids a magic-string dependency between nodes and the routes.
_GENERIC_RUBRIC = "בדוק נכונות, שימוש בנושאים מותרים ואיכות הקוד."


# ---------------------------------------------------------------------------
# Node 1 — analyze
# Structural static analysis of the student’s submission.
# ---------------------------------------------------------------------------

async def analyze(state: GraphState) -> dict:
    """
    Perform structural analysis of the student’s code.

    Intentionally kept separate from evaluate so the LLM receives a
    factual description of the code rather than being asked to both
    describe and assess in a single prompt (which degrades quality).
    """
    llm = get_llm()
    result = await (analyze_prompt | llm).ainvoke(
        {
            "assignment_text": state["assignment_text"],
            "code": state["code"],
        }
    )
    return {"analysis": result.content.strip()}


# ---------------------------------------------------------------------------
# Node 2 — retrieve
# Hybrid RAG: tries ChromaDB first, falls back to deterministic context.
# ---------------------------------------------------------------------------

async def retrieve(state: GraphState) -> dict:
    """
    Build the grading context for the evaluate node.

    Strategy:
      1. Query the lesson’s ChromaDB collection for semantically relevant chunks.
      2. If the collection is missing or empty (lesson not yet indexed), fall
         back to inlining the official solution and rubric verbatim.

    The fallback guarantees that grading works even before the teacher has
    uploaded lesson materials through the dedicated endpoint.
    """
    from app.services.vector_store import retrieve_context

    lesson_key = state.get("lesson_key", "")
    rag_chunks: Optional[str] = None

    if lesson_key:
        try:
            rag_chunks = await retrieve_context(lesson_key, state["code"])
        except Exception as exc:
            log.warning("ChromaDB retrieve failed for lesson %s: %s", lesson_key, exc)

    topic_header = (
        f"=== ALLOWED TOPICS (lessons 1-{state['lesson_number']}) ===\n"
        f"{state['allowed_topics']}"
    )

    if rag_chunks:
        ctx = f"{topic_header}\n\n{rag_chunks}"
    else:
        ctx = (
            f"{topic_header}\n\n"
            f"=== OFFICIAL SOLUTION ===\n{state['official_solution']}\n\n"
            f"=== GRADING RUBRIC ===\n{state['grading_rubric']}"
        )

    return {"retrieved_context": ctx}


# ---------------------------------------------------------------------------
# Node 3 — evaluate
# Rubric-based assessment; embeds the CHEATING_VERDICT signal.
# ---------------------------------------------------------------------------

async def evaluate(state: GraphState) -> dict:
    """
    Evaluate the submission against the rubric with an encouraging bias.

    The evaluate node embeds a CHEATING_VERDICT marker that is parsed
    downstream by the workflow runner rather than being exposed to students.
    """
    llm = get_llm()
    result = await (evaluate_prompt | llm).ainvoke(
        {
            "analysis": state["analysis"],
            "retrieved_context": state["retrieved_context"],
            "code": state["code"],
        }
    )
    return {"evaluation": result.content.strip()}


# ---------------------------------------------------------------------------
# Node 4a — feedback
# Formats the evaluation into a Hebrew pedagogical markdown document.
# ---------------------------------------------------------------------------

async def feedback(state: GraphState) -> dict:
    """
    Reformat the English evaluation into a Hebrew 3-section sandwich document.

    The three sections map to the sandwich feedback methodology:
      1. Positive reinforcement
      2. Constructive criticism
      3. Next step guidance
    """
    llm = get_llm()
    result = await (feedback_prompt | llm).ainvoke(
        {"evaluation": state["evaluation"]}
    )
    return {"feedback": result.content.strip()}


# ---------------------------------------------------------------------------
# Node 4b — score
# Assigns a numeric grade; runs in parallel with the feedback node.
# ---------------------------------------------------------------------------

async def score(state: GraphState) -> dict:
    """
    Assign a numeric grade 0-100 using the uploaded rubric.

    Short-circuit logic:
      - Returns score=None without an LLM call when the rubric is the generic
        sentinel (i.e. no real rubric was uploaded by the teacher).
      - On LLM JSON parse failure, returns score=None with an error explanation
        instead of raising, so the feedback branch is not affected.
    """
    rubric = state.get("grading_rubric", "").strip()

    # Skip scoring when no substantive rubric was provided.
    if not rubric or rubric == _GENERIC_RUBRIC:
        return {
            "score": None,
            "score_explanation": "אין מחוון — לא ניתן לתת ציון אוטומטי.",
        }

    llm = get_llm()
    try:
        result = await (score_prompt | llm).ainvoke(
            {
                "rubric": rubric,
                "evaluation": state["evaluation"],
                "code": state["code"],
            }
        )
        raw = result.content.strip()
        # Strip any markdown fences the model may add despite instructions.
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed: dict = json.loads(raw)
        return {
            "score": int(parsed.get("score", 0)),
            "score_explanation": str(parsed.get("explanation", "")),
        }
    except Exception as exc:
        log.error("Score node failed: %s", exc)
        return {
            "score": None,
            "score_explanation": f"שגיאה בחישוב ציון: {exc}",
        }
