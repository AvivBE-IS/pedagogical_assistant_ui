"""
Pydantic HTTP request / response schemas.

This module is strictly for API boundary serialisation and validation.
Internal graph state lives in app.graph.state (TypedDict).
Database document shapes are not modelled here; they are built inline in
the route handlers since MongoDB is schemaless and the shapes evolve frequently.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class LessonCreate(BaseModel):
    """Body fields accepted when creating a lesson via JSON (non-multipart)."""

    lessonKey: str
    assignmentText: str
    officialSolution: str
    gradingRubric: str
    syllabusText: Optional[str] = None


class SubmissionCreate(BaseModel):
    """Body fields accepted when creating a submission via JSON (non-multipart)."""

    lessonKey: str
    studentId: str
    studentName: str
    fileName: str
    code: str


class ReviewCreate(BaseModel):
    """Body fields for saving an instructor-approved review."""

    lessonKey: str
    studentId: str
    studentName: str
    fileName: str
    score: Optional[float] = None
    cheatingRisk: Optional[str] = None
    feedback: str


class ApproveSubmission(BaseModel):
    """Body fields for the instructor approval endpoint."""

    final_feedback: str = Field(..., min_length=1)
    final_score: int = Field(..., ge=0, le=100)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
