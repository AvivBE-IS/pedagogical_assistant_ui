"""
Review routes — /api/reviews

Responsibilities:
  POST /api/reviews                      — save an instructor-approved review
  GET  /api/reviews/lesson/{lesson_key}  — all approved reviews for a lesson
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException

from app.config.database import get_db
from app.utils.serialisation import serialise_doc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", summary="Save an instructor-approved review")
async def create_review(
    lesson_key: str = Form(..., description="Frontend lesson ID, e.g. 'c1-s1-l1'"),
    student_id: str = Form(...),
    student_name: str = Form(...),
    file_name: str = Form(...),
    score: int = Form(...),
    cheating_risk: str = Form(...),
    feedback: str = Form(...),
):
    """
    Persist an approved review.
    Upserts on (lesson_key, student_id) so re-approval overwrites the prior record.
    """
    db = get_db()
    doc = {
        "lesson_key":    lesson_key,
        "student_id":    student_id,
        "student_name":  student_name,
        "file_name":     file_name,
        "score":         score,
        "cheating_risk": cheating_risk,
        "feedback":      feedback,
        "approved_at":   datetime.now(timezone.utc),
    }

    try:
        await db.reviews.update_one(
            {"lesson_key": lesson_key, "student_id": student_id},
            {"$set": doc},
            upsert=True,
        )
    except Exception as exc:
        log.exception("Failed to save review for lesson_key=%s student_id=%s", lesson_key, student_id)
        raise HTTPException(status_code=500, detail="Failed to save review") from exc

    return {"ok": True}


@router.get(
    "/lesson/{lesson_key:path}",
    summary="Fetch all approved reviews for a lesson",
)
async def get_reviews_by_lesson(lesson_key: str):
    db = get_db()
    cursor = db.reviews.find({"lesson_key": lesson_key})
    reviews = await cursor.to_list(length=500)
    return [serialise_doc(r) for r in reviews]
