"""
Lesson upload pipeline — traced end-to-end in LangSmith.

This pipeline runs once per lesson when a teacher uploads lesson materials.
It replaces the inline logic that was previously in the POST /api/lessons route.

Steps:
  1. extract_lecture_text     — extract text from lecture file
  2. extract_assignment_text  — extract text from assignment file
  3. extract_solution_text    — extract text from solution file
  4. extract_rubric_text      — extract text from rubric file (optional)
  5. resolve_allowed_topics   — look up topics from course syllabus_topics in MongoDB
                                (falls back to the form field if course not set up)
  6. save_lesson_to_mongodb   — upsert lesson document
  7. index_lesson_to_chromadb — chunk + embed lesson texts into ChromaDB

Each step is a separate LangSmith span with explicit inputs/outputs so the trace
is readable to anyone without needing to dig into the code.
The parent trace_id is stored in MongoDB (``langsmith_upload_trace_id``).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app.config.database import get_db
from app.services.file_processor import extract_text
from app.services.vector_store import index_lesson

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1-4 — Text extraction (one span per file)
# ---------------------------------------------------------------------------

@traceable(name="extract_file_text", run_type="tool")
async def _traced_extract_file(file_bytes: bytes, filename: str, label: str) -> dict:
    """
    Extract all text from a single uploaded file.

    Inputs:  label (lecture | assignment | solution | rubric), filename, file_size_bytes
    Outputs: n_chars_extracted
    """
    text = await asyncio.to_thread(extract_text, file_bytes, filename)
    return {
        "label": label,
        "text": text,
        "filename": filename,
        "file_size_bytes": len(file_bytes),
        "n_chars_extracted": len(text),
    }


# ---------------------------------------------------------------------------
# Step 5 — Resolve allowed topics
# ---------------------------------------------------------------------------

@traceable(name="resolve_allowed_topics", run_type="tool")
async def _traced_resolve_topics(
    course_id: str,
    lesson_number: int,
    form_fallback: str,
) -> dict:
    """
    Look up the allowed topics for this lesson from the course's
    ``syllabus_topics`` map that was built during course setup.

    If the course hasn't been set up yet (no ``syllabus_topics``), falls back
    to the value supplied in the upload form.

    Inputs:  course_id, lesson_number, form_fallback
    Outputs: topics (comma-separated string), source ("syllabus" | "form_field")
    """
    db = get_db()
    course = await db.courses.find_one(
        {"course_id": course_id}, {"syllabus_topics": 1}
    )

    if course and course.get("syllabus_topics"):
        topics_map: dict = course["syllabus_topics"]
        topics_list = topics_map.get(str(lesson_number))
        if topics_list:
            topics_str = (
                ", ".join(topics_list)
                if isinstance(topics_list, list)
                else str(topics_list)
            )
            return {
                "topics": topics_str,
                "source": "syllabus",
                "lesson_number": lesson_number,
                "course_id": course_id,
            }

    # Graceful fallback
    return {
        "topics": form_fallback,
        "source": "form_field",
        "lesson_number": lesson_number,
        "course_id": course_id,
    }


# ---------------------------------------------------------------------------
# Step 6 — Save lesson to MongoDB
# ---------------------------------------------------------------------------

@traceable(name="save_lesson_to_mongodb", run_type="tool")
async def _traced_save_lesson(lesson_doc: dict) -> dict:
    """
    Upsert the lesson document in the ``lessons`` collection.
    Re-uploading materials for the same lesson_key updates the existing record.

    Inputs:  lesson_key, course_id, n_chars (lecture + assignment + solution)
    Outputs: mongodb_id, is_upsert
    """
    db = get_db()
    result = await db.lessons.update_one(
        {"lesson_key": lesson_doc["lesson_key"]},
        {
            "$set": lesson_doc,
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    saved = await db.lessons.find_one({"lesson_key": lesson_doc["lesson_key"]})
    return {
        "mongodb_id": str(saved["_id"]),
        "lesson_key": lesson_doc["lesson_key"],
        "is_upsert": result.upserted_id is not None,
    }


# ---------------------------------------------------------------------------
# Step 7 — Index lesson to ChromaDB
# ---------------------------------------------------------------------------

@traceable(name="index_lesson_to_chromadb", run_type="tool")
async def _traced_index_lesson(lesson_key: str, texts: dict[str, str]) -> dict:
    """
    Chunk and embed the lesson texts into a dedicated ChromaDB collection
    (``les_<lesson_key>``).  Used by the grading pipeline's retrieve node.

    Inputs:  lesson_key, n_chars_total
    Outputs: n_chunks_indexed, collection_name
    """
    n_chunks = await index_lesson(lesson_key, texts)
    return {
        "lesson_key": lesson_key,
        "n_chars_total": sum(len(t) for t in texts.values()),
        "n_chunks_indexed": n_chunks,
        "collection_name": f"les_{lesson_key}",
    }


# ---------------------------------------------------------------------------
# Parent pipeline — lesson_upload_pipeline
# ---------------------------------------------------------------------------

@traceable(name="lesson_upload_pipeline", run_type="chain")
async def lesson_upload_pipeline(
    course_id: str,
    lesson_key: str,
    lesson_number: int,
    grading_rubric: str,
    allowed_topics_form: str,
    lecture_bytes: bytes,
    lecture_filename: str,
    assignment_bytes: bytes,
    assignment_filename: str,
    solution_bytes: bytes,
    solution_filename: str,
    rubric_bytes: Optional[bytes],
    rubric_filename: Optional[str],
) -> dict:
    """
    Full lesson upload pipeline traced end-to-end in LangSmith.

    This is the top-level span.  All sub-steps appear as child spans, giving
    full visibility into:
      - Which files were uploaded and how many characters were extracted
      - Whether topics came from the course syllabus or from the form
      - How many ChromaDB chunks were created
      - The exact MongoDB document that was saved

    The LangSmith trace_id is stored in MongoDB (``langsmith_upload_trace_id``)
    so you can navigate: MongoDB lesson doc → LangSmith trace in one click.
    """
    run = get_current_run_tree()
    trace_id = str(run.id) if run else None

    # ── Steps 1-4: Extract files (lecture, assignment, solution run in parallel) ──
    extract_tasks = [
        _traced_extract_file(lecture_bytes, lecture_filename, "lecture"),
        _traced_extract_file(assignment_bytes, assignment_filename, "assignment"),
        _traced_extract_file(solution_bytes, solution_filename, "solution"),
    ]
    if rubric_bytes and rubric_filename:
        extract_tasks.append(
            _traced_extract_file(rubric_bytes, rubric_filename, "rubric")
        )

    extract_results = await asyncio.gather(*extract_tasks, return_exceptions=True)

    texts: dict[str, str] = {}
    for res in extract_results:
        if isinstance(res, Exception):
            raise res
        texts[res["label"]] = res["text"]

    # Rubric file overrides the form text field if provided
    if rubric_bytes and rubric_filename and "rubric" in texts:
        grading_rubric = texts["rubric"]

    # ── Step 5: Resolve topics ───────────────────────────────────────────────
    topics_result = await _traced_resolve_topics(
        course_id, lesson_number, allowed_topics_form
    )
    allowed_topics_str = topics_result["topics"]

    # ── Step 6: Save to MongoDB ──────────────────────────────────────────────
    lesson_doc = {
        "course_id": course_id,
        "lesson_key": lesson_key,
        "lesson_number": lesson_number,
        "lecture_file_url": lecture_filename,
        "assignment_file_url": assignment_filename,
        "solution_file_url": solution_filename,
        "lecture_context": texts.get("lecture", ""),
        "assignment_context": texts.get("assignment", ""),
        "solution_context": texts.get("solution", ""),
        "grading_rubric": grading_rubric,
        "allowed_topics": [t.strip() for t in allowed_topics_str.split(",")],
        "langsmith_upload_trace_id": trace_id,
        "updated_at": datetime.now(timezone.utc),
    }

    save_result = await _traced_save_lesson(lesson_doc)

    # ── Step 7: Index to ChromaDB ────────────────────────────────────────────
    index_result = await _traced_index_lesson(
        lesson_key,
        {
            "lecture": texts.get("lecture", ""),
            "assignment": texts.get("assignment", ""),
            "solution": texts.get("solution", ""),
        },
    )

    return {
        "lesson_key": lesson_key,
        "mongodb_id": save_result["mongodb_id"],
        "is_upsert": save_result["is_upsert"],
        "topics_source": topics_result["source"],
        "allowed_topics": allowed_topics_str,
        "n_chunks_indexed": index_result["n_chunks_indexed"],
        "langsmith_trace_id": trace_id,
    }
