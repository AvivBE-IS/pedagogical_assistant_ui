"""
Centralised application settings.

All environment variables are read exactly once from this module.
Every other module imports from here instead of calling os.getenv directly.
This gives a single, auditable view of every external dependency the app needs.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017").strip()
DB_NAME: str = os.getenv("DB_NAME", "pedagogical_assistant")

# ---------------------------------------------------------------------------
# Google / Gemini LLM
# ---------------------------------------------------------------------------
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Ollama (local fallback LLM + embeddings)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------
CHROMA_DB_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
)
CHROMA_CHUNK_SIZE: int = int(os.getenv("CHROMA_CHUNK_SIZE", "800"))
CHROMA_CHUNK_OVERLAP: int = int(os.getenv("CHROMA_CHUNK_OVERLAP", "100"))

# ---------------------------------------------------------------------------
# LangSmith observability
# ---------------------------------------------------------------------------
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "pedagogical_assistant")
