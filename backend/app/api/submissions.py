"""
Submission routes — /api/submissions

Responsibilities:
  POST   /api/submissions                        — submit student file for AI grading
  GET    /api/submissions/lesson/{lesson_id}     — all submissions for a lesson
  GET    /api/submissions/{submission_id}        — single submission by MongoDB ObjectId
  PATCH  /api/submissions/{submission_id}/approve — instructor finalises feedback
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config.database import get_db
from app.graph.workflow import run_grading_graph
from app.services.file_processor import extract_text
from app.utils.serialisation import serialise_doc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("", summary="Submit a student file for AI grading")
async def create_submission(
    student_name: str = Form(...),
    student_id: str = Form(...),
    lesson_id: Optional[str] = Form(None, description="MongoDB ObjectId of the lesson"),
    lesson_key: Optional[str] = Form(None, description="Frontend key, e.g. 'c1-s1-l1'"),
    submission_file: UploadFile = File(..., description="Student work (PDF/DOCX/TXT)"),
):
    """
    Grade a student submission through the 4-node LangGraph pipeline:
      analyze → retrieve → evaluate ┬→ feedback
                                    └→ score

    The submission document is persisted to MongoDB whether the AI call
    succeeds or fails — on failure the AI feedback contains a human-readable
    Hebrew error message so the instructor is aware.
    """
    db = get_db()

    # ── Resolve lesson ──────────────────────────────────────────────────────
    lesson = None
    if lesson_id:
        try:
            oid = ObjectId(lesson_id)
            lesson = await db.lessons.find_one({"_id": oid})
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid lesson_id format")
    elif lesson_key:
        lesson = await db.lessons.find_one({"lesson_key": lesson_key})
    else:
        raise HTTPException(
            status_code=422, detail="Provide lesson_id or lesson_key"
        )

    if not lesson:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found. Create it first via POST /api/lessons.",
        )

    # ── Extract submission text ─────────────────────────────────────────────
    file_bytes = await submission_file.read()
    try:
        extracted_code = extract_text(file_bytes, submission_file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    resolved_lesson_key: str = lesson.get("lesson_key") or lesson_key or ""
    assignment_ctx: str = lesson.get("assignment_context", "")
    solution_ctx: str = lesson.get("solution_context", "")
    lesson_rubric: str = lesson.get(
        "grading_rubric",
        "Check correctness, use of allowed topics, and code quality.",
    )

    # ── Run grading pipeline ────────────────────────────────────────────────
    langsmith_metadata = {
        "student_name":     student_name,
        "student_file":     submission_file.filename,
        "lesson_key":       resolved_lesson_key,
        "lecture_file":     lesson.get("lecture_file_url", "—"),
        "lecture_chars":    len(lesson.get("lecture_context", "")),
        "assignment_file":  lesson.get("assignment_file_url", "—"),
        "assignment_chars": len(assignment_ctx),
        "solution_file":    lesson.get("solution_file_url", "—"),
        "solution_chars":   len(solution_ctx),
        "rubric_chars":     len(lesson_rubric),
        "rubric_preview":   lesson_rubric[:120].replace("\n", " "),
        "allowed_topics":   ", ".join(lesson.get("allowed_topics", ["general"])),
        "submission_chars": len(extracted_code),
    }

    ai_provider = "ollama"
    cheating_flag = False
    ai_score: Optional[int] = None
    score_explanation = ""

    try:
        ai_feedback, cheating_flag, ai_score, score_explanation = await run_grading_graph(
            student_code=extracted_code,
            assignment_text=assignment_ctx,
            official_solution=solution_ctx,
            grading_rubric=lesson_rubric,
            allowed_topics=", ".join(lesson.get("allowed_topics", ["general"])),
            lesson_number=lesson.get("lesson_number", 1),
            lesson_key=resolved_lesson_key,
            run_name=submission_file.filename or "submission",
            metadata=langsmith_metadata,
        )
    except Exception as exc:
        log.exception("Grading pipeline failed for lesson_key=%s", resolved_lesson_key)
        ai_feedback = (
            f"\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05ea\u05d4\u05dc\u05d9\u05da "
            f"\u05d4\u05d1\u05d3\u05d9\u05e7\u05d4 \u05d4\u05d0\u05d5\u05d8\u05d5\u05de\u05d8\u05d9\u05ea. "
            f"\u05d0\u05e0\u05d0 \u05e4\u05e0\u05d4 \u05dc\u05de\u05d3\u05e8\u05d9\u05da. ({exc})"
        )
        ai_provider = "error"

    # ── Persist submission ──────────────────────────────────────────────────
    submission_doc = {
        "student_name":              student_name,
        "student_id":                student_id,
        "lesson_id":                 lesson_id or "",
        "lesson_key":                resolved_lesson_key,
        "submitted_file_url":        submission_file.filename,
        "extracted_code":            extracted_code,
        "ai_feedback_draft":         ai_feedback,
        "recommended_score":         ai_score,
        "score_explanation":         score_explanation,
        "cheating_flag":             cheating_flag,
        "ai_provider":               ai_provider,
        "instructor_final_feedback": None,
        "approved_at":               None,
        "created_at":                datetime.now(timezone.utc),
    }

    result = await db.submissions.insert_one(submission_doc)
    submission_doc["_id"] = str(result.inserted_id)
    return submission_doc


# NOTE: the /lesson/{lesson_id} route MUST be defined before /{submission_id}
# so FastAPI does not mis-route /lesson/... to the ObjectId handler.
@router.get(
    "/lesson/{lesson_id}",
    summary="Get all submissions for a lesson",
)
async def get_submissions_by_lesson(lesson_id: str):
    db = get_db()
    cursor = db.submissions.find({"lesson_id": lesson_id})
    submissions = await cursor.to_list(length=200)
    return [serialise_doc(s) for s in submissions]


@router.get("/{submission_id}", summary="Get a single submission by MongoDB ObjectId")
async def get_submission(submission_id: str):
    db = get_db()
    try:
        oid = ObjectId(submission_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid submission_id format")

    submission = await db.submissions.find_one({"_id": oid})
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return serialise_doc(submission)


@router.patch(
    "/{submission_id}/approve",
    summary="Instructor approves and finalises feedback",
)
async def approve_submission(
    submission_id: str,
    final_feedback: str = Form(...),
    final_score: int = Form(...),
):
    db = get_db()
    try:
        oid = ObjectId(submission_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid submission_id format")

    result = await db.submissions.update_one(
        {"_id": oid},
        {
            "$set": {
                "instructor_final_feedback": final_feedback,
                "recommended_score":         final_score,
                "approved_at":               datetime.now(timezone.utc),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"message": "Submission approved", "submission_id": submission_id}
