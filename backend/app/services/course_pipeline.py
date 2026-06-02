"""
Course setup pipeline — traced end-to-end in LangSmith.

This pipeline runs ONCE per course and handles everything needed before any
lesson can be uploaded or graded:

  1. extract_course_book_text   — PyMuPDF / docx extraction (may be 200+ pages)
  2. extract_syllabus_text      — extract text from the syllabus file
  3. extract_all_lessons_topics — single LLM call: syllabus → {lesson: [topics]}
  4. index_course_book_to_chromadb — chunk + embed the full book (course collection)
  5. save_course_to_mongodb     — upsert course document

Each step is a separate LangSmith span (@traceable) with explicit inputs/outputs
so anyone reading the trace can understand exactly what happened and how long each
step took.  The parent trace id is stored in MongoDB so you can jump from a course
document directly to its LangSmith trace.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app.config.database import get_db
from app.config.llm_config import get_llm
from app.prompts.system_prompts import syllabus_all_topics_prompt
from app.services.file_processor import extract_text
from app.services.vector_store import index_course_book

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step 1 — Extract course book text
# ---------------------------------------------------------------------------

@traceable(name="extract_course_book_text", run_type="tool")
async def _traced_extract_course_book(file_bytes: bytes, filename: str) -> dict:
    """
    Extract all text from the course book file (PDF/DOCX/TXT).

    Inputs:  filename, file_size_bytes
    Outputs: n_chars extracted
    """
    text = await asyncio.to_thread(extract_text, file_bytes, filename)
    return {
        "text": text,
        "filename": filename,
        "file_size_bytes": len(file_bytes),
        "n_chars_extracted": len(text),
    }


# ---------------------------------------------------------------------------
# Step 2 — Extract syllabus text
# ---------------------------------------------------------------------------

@traceable(name="extract_syllabus_text", run_type="tool")
async def _traced_extract_syllabus(file_bytes: bytes, filename: str) -> dict:
    """
    Extract all text from the course syllabus file.

    Inputs:  filename, file_size_bytes
    Outputs: n_chars extracted
    """
    text = await asyncio.to_thread(extract_text, file_bytes, filename)
    return {
        "text": text,
        "filename": filename,
        "file_size_bytes": len(file_bytes),
        "n_chars_extracted": len(text),
    }


# ---------------------------------------------------------------------------
# Step 3 — LLM: extract all lessons' topics from syllabus in one call
# ---------------------------------------------------------------------------

@traceable(name="extract_all_lessons_topics", run_type="llm")
async def _traced_extract_all_topics(syllabus_text: str, n_lessons: int) -> dict:
    """
    Single LLM call: analyse the full syllabus and return a JSON map of
    lesson_number → list of allowed topics.

    Inputs:  syllabus_text (first 12 000 chars), n_lessons
    Outputs: topics_map {str: list[str]}, n_lessons_parsed, parse_success
    """
    llm = get_llm()
    chain = syllabus_all_topics_prompt | llm
    try:
        res = await chain.ainvoke({
            "syllabus": syllabus_text[:12_000],
            "n_lessons": n_lessons,
        })
        raw = res.content.strip()
        # Strip markdown fences if the model wrapped the JSON
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        topics_map: dict = json.loads(raw)
        # Normalise all keys to strings
        topics_map = {str(k): v for k, v in topics_map.items()}
        return {
            "topics_map": topics_map,
            "n_lessons_parsed": len(topics_map),
            "parse_success": True,
        }
    except Exception as exc:
        # Graceful degradation — lessons will fall back to "general" topics
        return {
            "topics_map": {},
            "n_lessons_parsed": 0,
            "parse_success": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Step 4 — Index course book to ChromaDB
# ---------------------------------------------------------------------------

@traceable(name="index_course_book_to_chromadb", run_type="tool")
async def _traced_index_course_book(course_id: str, book_text: str) -> dict:
    """
    Chunk the entire course book and store embeddings in ChromaDB under
    a dedicated course-level collection (``course_<course_id>``).

    This collection is queried during grading of any lesson in the course
    to pull relevant textbook excerpts as RAG context.

    Inputs:  course_id, n_chars_to_index
    Outputs: n_chunks_indexed, collection_name
    """
    n_chunks = await index_course_book(course_id, book_text)
    collection_name = f"course_{course_id}"
    return {
        "course_id": course_id,
        "n_chars_indexed": len(book_text),
        "n_chunks_indexed": n_chunks,
        "collection_name": collection_name,
    }


# ---------------------------------------------------------------------------
# Step 5 — Save course document to MongoDB
# ---------------------------------------------------------------------------

@traceable(name="save_course_to_mongodb", run_type="tool")
async def _traced_save_course(course_doc: dict) -> dict:
    """
    Upsert the course document in the ``courses`` collection.
    Re-running setup for the same course_id updates the existing record.

    Inputs:  course_id, n_lessons, n_syllabus_topics_extracted
    Outputs: mongodb_id, is_upsert
    """
    db = get_db()
    result = await db.courses.update_one(
        {"course_id": course_doc["course_id"]},
        {
            "$set": course_doc,
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    saved = await db.courses.find_one({"course_id": course_doc["course_id"]})
    return {
        "mongodb_id": str(saved["_id"]),
        "course_id": course_doc["course_id"],
        "is_upsert": result.upserted_id is not None,
    }


# ---------------------------------------------------------------------------
# Parent pipeline — course_setup_pipeline
# ---------------------------------------------------------------------------

@traceable(name="course_setup_pipeline", run_type="chain")
async def course_setup_pipeline(
    course_id: str,
    course_name: str,
    n_lessons: int,
    course_book_bytes: bytes | None,
    course_book_filename: str | None,
    syllabus_bytes: bytes | None,
    syllabus_filename: str | None,
) -> dict:
    """
    Full course initialisation pipeline traced end-to-end in LangSmith.

    This is the top-level span.  Every sub-step appears as a child span so
    you can see at a glance:
      - How large the course book is and how many chunks were indexed
      - What the LLM extracted from the syllabus (prompt + response visible)
      - How long each I/O and LLM step took

    The LangSmith trace_id is stored in MongoDB (``langsmith_setup_trace_id``)
    so you can navigate: MongoDB course doc → LangSmith trace in one click.
    """
    run = get_current_run_tree()
    trace_id = str(run.id) if run else None

    course_doc: dict = {
        "course_id": course_id,
        "course_name": course_name,
        "n_lessons": n_lessons,
        "syllabus_topics": {},
        "course_book_filename": None,
        "course_book_n_chars": 0,
        "course_book_n_chunks": 0,
        "course_book_indexed": False,
        "syllabus_filename": None,
        "syllabus_n_chars": 0,
        "langsmith_setup_trace_id": trace_id,
        "updated_at": datetime.now(timezone.utc),
    }

    # ── Step 1: Extract course book ─────────────────────────────────────────
    book_text = ""
    if course_book_bytes and course_book_filename:
        book_result = await _traced_extract_course_book(
            course_book_bytes, course_book_filename
        )
        book_text = book_result["text"]
        course_doc["course_book_filename"] = course_book_filename
        course_doc["course_book_n_chars"] = book_result["n_chars_extracted"]

    # ── Step 2: Extract syllabus ─────────────────────────────────────────────
    syllabus_text = ""
    if syllabus_bytes and syllabus_filename:
        syl_result = await _traced_extract_syllabus(syllabus_bytes, syllabus_filename)
        syllabus_text = syl_result["text"]
        course_doc["syllabus_filename"] = syllabus_filename
        course_doc["syllabus_n_chars"] = syl_result["n_chars_extracted"]

    # ── Step 3: Extract all lessons' topics (LLM) ────────────────────────────
    if syllabus_text:
        topics_result = await _traced_extract_all_topics(syllabus_text, n_lessons)
        course_doc["syllabus_topics"] = topics_result["topics_map"]

    # ── Step 4: Index course book to ChromaDB ────────────────────────────────
    if book_text:
        index_result = await _traced_index_course_book(course_id, book_text)
        course_doc["course_book_indexed"] = index_result["n_chunks_indexed"] > 0
        course_doc["course_book_n_chunks"] = index_result["n_chunks_indexed"]

    # ── Step 5: Save to MongoDB ──────────────────────────────────────────────
    save_result = await _traced_save_course(course_doc)

    return {
        "course_id": course_id,
        "mongodb_id": save_result["mongodb_id"],
        "is_upsert": save_result["is_upsert"],
        "syllabus_topics_extracted": len(course_doc["syllabus_topics"]),
        "course_book_indexed": course_doc["course_book_indexed"],
        "course_book_n_chunks": course_doc["course_book_n_chunks"],
        "langsmith_trace_id": trace_id,
    }
