"""
Shared pytest fixtures for all tests.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db():
    """Return a mock MongoDB database object."""
    db = MagicMock()
    db.lessons.find_one = AsyncMock(return_value=None)
    db.lessons.update_one = AsyncMock()
    db.submissions.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc123"))
    db.submissions.find_one = AsyncMock(return_value=None)
    db.reviews.update_one = AsyncMock()
    db.reviews.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    return db


@pytest.fixture
def client(mock_db):
    """
    Return a TestClient with the database dependency overridden.
    Patches get_db() so no real MongoDB connection is required.
    """
    with patch("app.config.database.get_db", return_value=mock_db):
        from app.main import app
        with TestClient(app) as c:
            yield c
