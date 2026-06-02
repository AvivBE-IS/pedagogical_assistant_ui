"""
LLM configuration and singleton factory.

Primary:  Gemini 2.5 Flash via GOOGLE_API_KEY.
Fallback: ChatOllama (local) — fires automatically on any runtime Gemini error
          (quota exceeded, network failure, missing key) via LangChain's
          .with_fallbacks() mechanism.

Design decision: lazy initialisation avoids importing heavy torch/grpc
dependencies at import time; the singleton is created on first use.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config.settings import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

log = logging.getLogger(__name__)

_llm: Any = None  # Typed as Any to avoid importing heavy deps at module level.


def get_llm() -> Any:
    """
    Return the shared LLM instance (Gemini → Ollama fallback chain).

    Thread-safety note: FastAPI runs in a single async thread; the global
    assignment here is safe without a lock.
    """
    global _llm
    if _llm is not None:
        return _llm

    from langchain_ollama import ChatOllama

    ollama = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=16384,
    )

    if GOOGLE_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            gemini = ChatGoogleGenerativeAI(
                model=GEMINI_MODEL,
                google_api_key=GOOGLE_API_KEY,
                temperature=0.0,
            )
            # .with_fallbacks() fires on ANY exception, including HTTP 429.
            _llm = gemini.with_fallbacks([ollama])
            log.info("LLM: Gemini (%s) with Ollama (%s) fallback", GEMINI_MODEL, OLLAMA_MODEL)
            return _llm
        except Exception as exc:
            log.warning("Gemini initialisation failed (%s); falling back to Ollama", exc)

    _llm = ollama
    log.info("LLM: Ollama only (%s)", OLLAMA_MODEL)
    return _llm
