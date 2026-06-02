"""
File processing utilities.

Provides synchronous text extraction from PDF, DOCX, and plain-text files.
All public functions raise ValueError on unrecoverable parse failures so that
callers can decide whether to propagate an HTTP 422 or silently log and skip.
"""

from __future__ import annotations

import io
import logging
import re

import fitz  # PyMuPDF
from docx import Document as DocxDocument

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------


def clean_text(raw: str) -> str:
    """
    Normalise extracted text before embedding or prompting:
      - Normalise line endings (CRLF / CR → LF).
      - Collapse whitespace runs within a line to a single space.
      - Drop lines with no Hebrew/Latin letters or digits (separators, page numbers).
      - Collapse 3+ consecutive blank lines to a single blank line.
    """
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in raw.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        # Discard lines that carry no readable content.
        if line and not re.search(r"[\u05d0-\u05eaa-zA-Z0-9]", line):
            continue
        lines.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return text.strip()


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF byte stream using PyMuPDF.

    Returns a single cleaned concatenated string.
    Raises ValueError if the bytes are not a valid PDF.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        return clean_text("\n\n".join(pages))
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF: {exc}") from exc


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Dispatch text extraction based on the uploaded filename extension.

    Supported: .pdf, .txt, .docx, .doc
    Fallback:  tries PDF parse, then UTF-8 plain text decode.

    Raises
    ------
    ValueError
        When the file cannot be parsed by any supported strategy.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)

    if ext == "txt":
        try:
            raw = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = file_bytes.decode("latin-1")
        return clean_text(raw)

    if ext in ("docx", "doc"):
        try:
            doc = DocxDocument(io.BytesIO(file_bytes))
            raw = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return clean_text(raw)
        except Exception as exc:
            raise ValueError(f"Failed to parse DOCX: {exc}") from exc

    # Unknown extension: try PDF heuristic, then UTF-8 plain text.
    log.warning("Unknown extension '%s' for file '%s'; attempting PDF parse", ext, filename)
    try:
        return extract_text_from_pdf(file_bytes)
    except ValueError:
        try:
            raw = file_bytes.decode("utf-8")
            return clean_text(raw)
        except Exception as inner_exc:
            raise ValueError(f"Unsupported file type: {filename}") from inner_exc

# ---------------------------------------------------------------------------

async def extract_topics_from_syllabus(syllabus_text: str, lesson_number: int) -> str:
    """
    Use the LLM to infer the topics taught up to lesson_number from a syllabus.
    Returns a comma-separated Hebrew list of topic names, or 'general' on failure.
    """
    llm = get_llm()
    chain = topic_extraction_prompt | llm
    try:
        res = await chain.ainvoke({"syllabus": syllabus_text[:8000], "n": lesson_number})
        topics = res.content.strip()
        # Keep only Hebrew characters, digits, commas, and spaces
        topics = re.sub(r"[^\u05d0-\u05ea\u05f0-\u05f4\s,\d]", "", topics).strip()
        return topics if topics else "general"
    except Exception:
        return "general"
