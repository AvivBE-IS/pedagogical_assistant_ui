"""
Node 4b: score

Assigns a numeric grade 0-100 using the uploaded rubric.
Runs in PARALLEL with the feedback node after evaluate.

Decision logic:
  - No rubric (or generic default)  → returns score=None immediately, no LLM call.
  - Real rubric uploaded             → LLM call via score_prompt, returns int + explanation.

LangSmith visibility:
  - No-rubric path: span completes in <1 ms, inputs show why it was skipped.
  - LLM path: full prompt + JSON response visible in the span.
"""

import json
import re

from app.config.llm_config import get_llm
from app.prompts.system_prompts import score_prompt
from app.schemas.models import GraphState

# The default rubric string set by the upload form when no real rubric was uploaded.
_GENERIC_RUBRIC = "בדוק נכונות, שימוש בנושאים מותרים ואיכות הקוד."


def _has_real_rubric(rubric: str) -> bool:
    """Return True only when the rubric is a substantive uploaded document."""
    rubric = rubric.strip()
    return bool(rubric) and rubric != _GENERIC_RUBRIC


async def score(state: GraphState) -> dict:
    """
    Grade the submission numerically.

    Returns
    -------
    score : int | None
        Numeric grade 0-100, or None when no rubric is available.
    score_explanation : str
        One Hebrew sentence explaining the grade (or why scoring was skipped).
    """
    rubric = state.get("grading_rubric", "")

    if not _has_real_rubric(rubric):
        return {
            "score": None,
            "score_explanation": "אין מחוון — לא ניתן לתת ציון אוטומטי.",
        }

    llm = get_llm()
    chain = score_prompt | llm

    try:
        result = await chain.ainvoke({
            "rubric": rubric,
            "evaluation": state["evaluation"],
            "code": state["code"],
        })
        raw = result.content.strip()
        # Strip markdown fences the model may have added despite instructions
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed: dict = json.loads(raw)
        return {
            "score": int(parsed.get("score", 0)),
            "score_explanation": str(parsed.get("explanation", "")),
        }
    except Exception as exc:
        return {
            "score": None,
            "score_explanation": f"שגיאה בחישוב ציון: {exc}",
        }
