"""
API integration tests.

Covers the main route handlers with mocked database and LLM dependencies
so that tests run without a live MongoDB or Ollama instance.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_lessons_empty(client, mock_db):
    mock_db.lessons.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[]))
    )
    response = client.get("/api/lessons")
    assert response.status_code == 200
    assert response.json() == []


def test_get_lesson_invalid_id(client):
    response = client.get("/api/lessons/not-a-valid-id")
    assert response.status_code == 422


def test_get_lesson_not_found(client, mock_db):
    from bson import ObjectId
    valid_oid = str(ObjectId())
    mock_db.lessons.find_one = AsyncMock(return_value=None)
    response = client.get(f"/api/lessons/{valid_oid}")
    assert response.status_code == 404


def test_create_submission_missing_lesson(client, mock_db):
    mock_db.lessons.find_one = AsyncMock(return_value=None)
    response = client.post(
        "/api/submissions",
        data={"student_name": "Alice", "student_id": "s1", "lesson_key": "c1-s1-l1"},
        files={"submission_file": ("hw.txt", b"print('hello')", "text/plain")},
    )
    assert response.status_code == 404
