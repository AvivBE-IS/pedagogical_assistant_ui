"""
Pedagogical Assistant — FastAPI application entry point.

Responsibilities of this file:
  - Load .env and configure the logging stack BEFORE any app module is imported.
  - Create the FastAPI app instance and wire the lifespan context manager.
  - Register CORS middleware (origins loaded from env to avoid hardcoded wildcard).
  - Include the four API routers.
  - Expose a /health liveness probe.

All business logic lives in dedicated sub-packages:
  app/api/       — HTTP route handlers
  app/graph/     — LangGraph grading pipeline
  app/services/  — file processing, course/lesson pipelines
  app/config/    — database and LLM singletons
  app/prompts/   — all LLM prompt strings
"""

from __future__ import annotations

import logging
import logging.config
import os

from dotenv import load_dotenv

# Load .env BEFORE importing any app module so that all os.getenv() calls
# inside config/settings.py, config/database.py, etc. see the final values.
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True,
)

# ---------------------------------------------------------------------------
# Logging configuration
# Must be called before FastAPI / uvicorn import so all loggers inherit the format.
# ---------------------------------------------------------------------------

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
        # Quieten noisy third-party loggers that pollute startup output.
        "loggers": {
            "httpx": {"level": "WARNING"},
            "chromadb": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
        },
    }
)

log = logging.getLogger("app.startup")

# ---------------------------------------------------------------------------
# LangSmith startup verification
# Logged at INFO so it appears in the startup banner alongside uvicorn logs.
# ---------------------------------------------------------------------------

log.info(
    "LangSmith | TRACING=%s LANGCHAIN_TRACING_V2=%s PROJECT=%s KEY_SET=%s",
    os.environ.get("LANGSMITH_TRACING"),
    os.environ.get("LANGCHAIN_TRACING_V2"),
    os.environ.get("LANGSMITH_PROJECT"),
    bool(os.environ.get("LANGSMITH_API_KEY")),
)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

from fastapi import FastAPI  # noqa: E402  (imports after env/logging setup)
from fastapi.middleware.cors import CORSMiddleware

from app.api.courses import router as courses_router
from app.api.lessons import router as lessons_router
from app.api.reviews import router as reviews_router
from app.api.submissions import router as submissions_router
from app.config.database import lifespan

app = FastAPI(
    title="Pedagogical Assistant API",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# Allow-list is read from CORS_ORIGINS env var (comma-separated).
# Falls back to ["*"] only when the env var is absent or empty.
# ---------------------------------------------------------------------------

_cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins: list[str] = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(courses_router)
app.include_router(lessons_router)
app.include_router(submissions_router)
app.include_router(reviews_router)

# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"], summary="Liveness probe")
async def health():
    return {"status": "ok"}



