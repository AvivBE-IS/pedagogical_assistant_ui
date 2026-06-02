"""
Lesson routes — /api/lessons

Responsibilities:
  POST /api/lessons             — upload lesson materials (triggers lesson_upload_pipeline)
  GET  /api/lessons             — list lessons (optional ?course_id= filter)
  GET  /api/lessons/{lesson_id} — single lesson by MongoDB ObjectId
"""

from __future__ import annotations

import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config.database import get_db
from app.services.lesson_pipeline import lesson_upload_pipeline
from app.utils.serialisation import serialise_doc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.post("", summary="Upload a new lesson with PDF materials")
async def create_lesson(
    course_id: str = Form(..., description="Unique course identifier, e.g. 'course-1'"),
    lesson_key: str = Form(..., description="Frontend lesson ID, e.g. 'c1-s1-l1'"),
    lesson_number: int = Form(0, description="Leave 0 to auto-derive from lesson_key"),
    grading_rubric: str = Form(
        "\u05d1\u05d3\u05d5\u05e7 \u05e0\u05db\u05d5\u05e0\u05d5\u05ea, \u05e9\u05d9\u05de\u05d5\u05e9 \u05d1\u05e0\u05d5\u05e9\u05d0\u05d9\u05dd \u05de\u05d5\u05ea\u05e8\u05d9\u05dd \u05d5\u05d0\u05d9\u05db\u05d5\u05ea \u05d4\u05e7\u05d5\u05d3.",
        description="Free-text rubric (overridden if rubric_file is provided)",
    ),
    allowed_topics: str = Form(
        "general",
        description="Fallback topics string if course syllabus_topics not yet available",
    ),
    lecture_file: UploadFile = File(..., description="Lecture file (PDF/DOCX/TXT)"),
    assignment_file: UploadFile = File(..., description="Assignment description file"),
    solution_file: UploadFile = File(..., description="Reference solution file"),
    rubric_file: Optional[UploadFile] = File(None, description="Grading rubric file (optional)"),
):
    """
    Upload lesson materials and run lesson_upload_pipeline which:
      1. Extracts text from lecture / assignment / solution (in parallel)
      2. Extracts text from the optional rubric file
      3. Resolves allowed topics from the course's syllabus_topics in MongoDB
         (falls back to the ``allowed_topics`` form field if course not set up)
      4. Saves the lesson document to MongoDB
      5. Indexes lesson texts into a dedicated ChromaDB collection

    All steps appear as child spans in the LangSmith ``lesson_upload_pipeline`` trace.
    The trace_id is stored in MongoDB under ``langsmith_upload_trace_id``.
    """
    # Auto-derive lesson_number from key when caller passes 0 (e.g. c1-s1-l3 → 3).
    if lesson_number == 0:
        try:
            lesson_number = int(lesson_key.rsplit("-l", 1)[-1])
        except (ValueError, IndexError):
            lesson_number = 0

    lecture_bytes = await lecture_file.read()
    assignment_bytes = await assignment_file.read()
    solution_bytes = await solution_file.read()

    rubric_bytes: Optional[bytes] = None
    rubric_filename: Optional[str] = None
    if rubric_file and rubric_file.filename:
        rubric_bytes = await rubric_file.read()
        rubric_filename = rubric_file.filename

    try:
        await lesson_upload_pipeline(
            course_id=course_id,
            lesson_key=lesson_key,
            lesson_number=lesson_number,
            grading_rubric=grading_rubric,
            allowed_topics_form=allowed_topics,
            lecture_bytes=lecture_bytes,
            lecture_filename=lecture_file.filename or "",
            assignment_bytes=assignment_bytes,
            assignment_filename=assignment_file.filename or "",
            solution_bytes=solution_bytes,
            solution_filename=solution_file.filename or "",
            rubric_bytes=rubric_bytes,
            rubric_filename=rubric_filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.exception("Unexpected error in lesson upload pipeline for lesson_key=%s", lesson_key)
        raise HTTPException(status_code=500, detail="Lesson upload failed") from exc

    db = get_db()
    saved = await db.lessons.find_one({"lesson_key": lesson_key})
    if not saved:
        raise HTTPException(status_code=500, detail="Lesson was not persisted")
    return serialise_doc(saved)


@router.get("", summary="List all lessons (optionally filter by course)")
async def list_lessons(course_id: Optional[str] = None):
    db = get_db()
    query = {"course_id": course_id} if course_id else {}
    # Omit large text blobs from the list view; callers can fetch individually if needed.
    cursor = db.lessons.find(query, {"lecture_context": 0})
    lessons = await cursor.to_list(length=200)
    return [serialise_doc(lesson) for lesson in lessons]


@router.get("/{lesson_id}", summary="Get a single lesson by MongoDB ObjectId")
async def get_lesson(lesson_id: str):
    db = get_db()
    try:
        oid = ObjectId(lesson_id)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid lesson_id format")

    lesson = await db.lessons.find_one({"_id": oid})
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return serialise_doc(lesson)
