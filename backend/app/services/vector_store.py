"""
ChromaDB vector store service.

Provides two public async functions:
  - index_lesson(lesson_key, texts)     — chunk + embed lesson files → ChromaDB
  - retrieve_context(lesson_key, query) — vector search → relevant text chunks

All ChromaDB / embedding calls are synchronous internally and are offloaded to
a thread pool via asyncio.to_thread so they don’t block the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import re

import chromadb
from langchain_ollama import OllamaEmbeddings

from app.config.settings import (
    CHROMA_CHUNK_OVERLAP,
    CHROMA_CHUNK_SIZE,
    CHROMA_DB_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_client: chromadb.PersistentClient | None = None
_embedder: OllamaEmbeddings | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _client


def _get_embedder() -> OllamaEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    return _embedder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitise_name(key: str, prefix: str = "") -> str:
    """Return a valid ChromaDB collection name (3-63 chars, alphanumeric/-/_)."""
    name = re.sub(r"[^a-zA-Z0-9\-_]", "_", key).strip("-_")
    if prefix:
        name = f"{prefix}_{name}"
    if len(name) < 3:
        name = f"col_{name}"
    return name[:63]


def _chunk(text: str) -> list[str]:
    """Split text into overlapping fixed-size chunks."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHROMA_CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += CHROMA_CHUNK_SIZE - CHROMA_CHUNK_OVERLAP
    return [c for c in chunks if len(c.strip()) > 30]


# ---------------------------------------------------------------------------
# Synchronous workers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------


def _sync_index(
    col_name: str,
    all_docs: list[str],
    all_ids: list[str],
    all_metas: list[dict],
) -> int:
    client = _get_client()
    embedder = _get_embedder()

    # Re-index: delete the stale collection, then recreate fresh.
    try:
        client.delete_collection(col_name)
    except Exception:
        pass

    collection = client.get_or_create_collection(col_name)
    embeddings = embedder.embed_documents(all_docs)
    collection.add(
        documents=all_docs,
        embeddings=embeddings,
        ids=all_ids,
        metadatas=all_metas,
    )
    return len(all_docs)


def _sync_retrieve(col_name: str, query: str, k: int) -> str | None:
    client = _get_client()
    embedder = _get_embedder()

    try:
        collection = client.get_collection(col_name)
    except Exception:
        return None

    count = collection.count()
    if count == 0:
        return None

    q_emb = embedder.embed_query(query)
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(k, count),
        include=["documents", "metadatas"],
    )

    if not results["documents"] or not results["documents"][0]:
        return None

    # Group chunks by source label for a readable formatted context block.
    grouped: dict[str, list[str]] = {}
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        src = meta.get("source", "context")
        grouped.setdefault(src, []).append(doc)

    parts = [
        f"=== {src.upper()} (relevant excerpts) ===\n" + "\n---\n".join(chunks)
        for src, chunks in grouped.items()
    ]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def index_lesson(lesson_key: str, texts: dict[str, str]) -> int:
    """
    Chunk and embed lesson texts into ChromaDB.

    Parameters
    ----------
    lesson_key:
        Unique lesson identifier.  Collection name: ``les_<key>``.
    texts:
        Mapping of label to extracted text, e.g.
        ``{"lecture": "...", "assignment": "...", "solution": "..."}​``.

    Returns
    -------
    int
        Number of chunks indexed.
    """
    col_name = _sanitise_name(lesson_key, prefix="les")
    all_docs, all_ids, all_metas = [], [], []

    for source, text in texts.items():
        if not text:
            continue
        for i, chunk in enumerate(_chunk(text)):
            all_docs.append(chunk)
            all_ids.append(f"{source}_{i}")
            all_metas.append({"source": source, "lesson_key": lesson_key})

    if not all_docs:
        return 0

    count = await asyncio.to_thread(_sync_index, col_name, all_docs, all_ids, all_metas)
    log.info("Indexed %d chunks into collection '%s'", count, col_name)
    return count


async def index_course_book(course_id: str, book_text: str) -> int:
    """
    Chunk and embed the full course book into its own ChromaDB collection.

    The collection is shared across all lessons of the course and provides
    RAG context drawn from the full textbook during grading.

    Parameters
    ----------
    course_id:
        Unique course identifier.  Collection name: ``course_<course_id>``.
    book_text:
        Full extracted text of the course book.

    Returns
    -------
    int
        Number of chunks indexed.
    """
    col_name = _sanitise_name(course_id, prefix="course")
    chunks = _chunk(book_text)
    if not chunks:
        return 0

    all_docs = chunks
    all_ids = [f"chunk_{i}" for i in range(len(chunks))]
    all_metas = [{"source": "course_book", "course_id": course_id}] * len(chunks)

    count = await asyncio.to_thread(_sync_index, col_name, all_docs, all_ids, all_metas)
    log.info("Indexed %d chunks into course collection '%s'", count, col_name)
    return count


async def retrieve_context(lesson_key: str, query: str, k: int = 5) -> str | None:
    """
    Vector-search the lesson collection for the most relevant chunks.

    Parameters
    ----------
    lesson_key:
        Unique lesson identifier.
    query:
        Free-form query string (typically the student’s submitted code).
    k:
        Number of nearest-neighbour chunks to return.

    Returns
    -------
    str | None
        Formatted context string, or None if the collection does not exist.
    """
    col_name = _sanitise_name(lesson_key, prefix="les")
    return await asyncio.to_thread(_sync_retrieve, col_name, query, k)


async def retrieve_course_context(course_id: str, query: str, k: int = 5) -> str | None:
    """
    Vector-search the course book collection for the most relevant chunks.

    Parameters
    ----------
    course_id:
        Unique course identifier.
    query:
        Free-form query string.
    k:
        Number of nearest-neighbour chunks to return.

    Returns
    -------
    str | None
        Formatted context string, or None if the collection does not exist.
    """
    col_name = _sanitise_name(course_id, prefix="course")
    return await asyncio.to_thread(_sync_retrieve, col_name, query, k)

