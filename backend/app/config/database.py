"""
MongoDB connection lifecycle management.

Opens a motor async client on startup, ensures all required indexes exist
(idempotent), and closes the client cleanly on shutdown.

Design decisions:
  - DNS fix applied before motor initialises its thread pools so SRV records
    resolve correctly in environments with restrictive ISP DNS (8.8.8.8/1.1.1.1).
  - Module-level singletons are set inside lifespan() so the event loop is
    already running when motor performs its first I/O operations.
  - get_db() raises RuntimeError immediately rather than returning None so
    callers get a clear error instead of an AttributeError deep in a query.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import dns.resolver as _dns_resolver
import motor.motor_asyncio
from fastapi import FastAPI

from app.config.settings import DB_NAME, MONGODB_URI

log = logging.getLogger(__name__)

# Fix: ISP DNS servers fail to resolve MongoDB SRV records from background threads.
# Force public DNS before motor/pymongo create their thread pools.
_dns_resolver.default_resolver = _dns_resolver.Resolver(configure=False)
_dns_resolver.default_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

# Module-level singletons — initialised inside lifespan().
_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Return the active database handle; must be called after lifespan starts."""
    if _db is None:
        raise RuntimeError(
            "Database not initialised. Ensure the FastAPI lifespan is wired up."
        )
    return _db


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001  (app unused but required by FastAPI)
    """
    FastAPI lifespan handler.

    Opens the motor client, ensures all required collection indexes exist,
    then yields.  On shutdown, closes the connection pool gracefully.
    """
    global _client, _db

    _client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    _db = _client[DB_NAME]
    log.info("MongoDB client opened (db=%s)", DB_NAME)

    # Create indexes idempotently — safe to run on every restart.
    await _db.courses.create_index("course_id", unique=True)
    await _db.lessons.create_index("lesson_key", unique=True)
    await _db.lessons.create_index("course_id")
    await _db.submissions.create_index("lesson_key")
    await _db.submissions.create_index("student_id")
    await _db.reviews.create_index(
        [("lesson_key", 1), ("student_id", 1)], unique=True
    )
    log.info("MongoDB indexes verified")

    yield

    _client.close()
    log.info("MongoDB client closed")
