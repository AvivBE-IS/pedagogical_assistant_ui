"""
Course routes — /api/courses

Responsibilities:
  POST /api/courses        — trigger course_setup_pipeline (book + syllabus upload)
  GET  /api/courses        — list all courses
  GET  /api/courses/{id}   — single course by course_id
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config.database import get_db
from app.services.course_pipeline import course_setup_pipeline
from app.utils.serialisation import serialise_doc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.post("", summary="Set up a new course (book + syllabus)")
async def create_course(
    course_id: str = Form(..., description="Unique course identifier, e.g. 'course-1'"),
    course_name: str = Form(..., description="Human-readable name"),
    n_lessons: int = Form(..., description="Total number of lessons in the course"),
    course_book_file: Optional[UploadFile] = File(
        None, description="Full course book PDF (may be 200+ pages)"
    ),
    syllabus_file: Optional[UploadFile] = File(
        None, description="Syllabus PDF/DOCX — topics auto-extracted per lesson"
    ),
):
    """
    One-time course initialisation.  Runs course_setup_pipeline which:
      1. Extracts text from the course book
      2. Extracts text from the syllabus
      3. Single LLM call: maps every lesson to its allowed topics
      4. Indexes the full course book into a dedicated ChromaDB collection
      5. Saves the course document to MongoDB

    All five steps appear as child spans in the LangSmith
    ``course_setup_pipeline`` trace.
    """
    book_bytes: Optional[bytes] = None
    book_filename: Optional[str] = None
    syl_bytes: Optional[bytes] = None
    syl_filename: Optional[str] = None

    if course_book_file and course_book_file.filename:
        book_bytes = await course_book_file.read()
        book_filename = course_book_file.filename

    if syllabus_file and syllabus_file.filename:
        syl_bytes = await syllabus_file.read()
        syl_filename = syllabus_file.filename

    try:
        await course_setup_pipeline(
            course_id=course_id,
            course_name=course_name,
            n_lessons=n_lessons,
            course_book_bytes=book_bytes,
            course_book_filename=book_filename,
            syllabus_bytes=syl_bytes,
            syllabus_filename=syl_filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.exception("Unexpected error in course setup pipeline")
        raise HTTPException(status_code=500, detail="Course setup failed") from exc

    db = get_db()
    saved = await db.courses.find_one({"course_id": course_id})
    if not saved:
        raise HTTPException(status_code=500, detail="Course was not persisted")
    return serialise_doc(saved)


@router.get("", summary="List all courses")
async def list_courses():
    db = get_db()
    projection = {
        "course_book_filename": 1,
        "course_id": 1,
        "course_name": 1,
        "n_lessons": 1,
        "syllabus_topics": 1,
        "course_book_indexed": 1,
        "langsmith_setup_trace_id": 1,
        "updated_at": 1,
    }
    cursor = db.courses.find({}, projection)
    courses = await cursor.to_list(length=200)
    return [serialise_doc(c) for c in courses]


@router.get("/{course_id}", summary="Get a single course by course_id")
async def get_course(course_id: str):
    db = get_db()
    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return serialise_doc(course)
