"""
Unit tests for the LangGraph pipeline.

Mocks the LLM so that tests are fast and deterministic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.models import GraphState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> GraphState:
    base: GraphState = {
        "code": "print('hello')",
        "assignment_text": "Write a hello-world program.",
        "official_solution": "print('hello')",
        "grading_rubric": "Check correctness.",
        "allowed_topics": "print",
        "lesson_number": 1,
        "analysis": "",
        "retrieved_context": "",
        "evaluation": "",
        "feedback": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Node unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_assembles_context():
    from app.graph.nodes import retrieve

    state = _make_state(allowed_topics="loops, variables", lesson_number=3)
    result = await retrieve(state)

    ctx = result["retrieved_context"]
    assert "loops, variables" in ctx
    assert "OFFICIAL SOLUTION" in ctx
    assert "GRADING RUBRIC" in ctx


@pytest.mark.asyncio
async def test_analyze_calls_llm():
    from app.graph.nodes import analyze

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="  structure is clear  "))

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        with patch("app.graph.nodes.analyze_prompt.__or__", return_value=mock_llm):
            # Just verify the node returns an 'analysis' key
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(return_value=MagicMock(content="structure is clear"))
            with patch("app.prompts.system_prompts.analyze_prompt.__or__", return_value=mock_chain):
                result = await analyze(_make_state())
    assert "analysis" in result


# ---------------------------------------------------------------------------
# Workflow runner tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_grading_graph_returns_tuple():
    from app.graph.workflow import run_grading_graph

    fake_feedback = "### דברים טובים בפתרון\nטוב.\n### נקודות לשיפור\nשפר.\n### המשך עבודה\nהמשך.\nCHEATING_VERDICT: NO"

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"feedback": fake_feedback})

    with patch("app.graph.workflow.grading_graph", mock_graph):
        text, flag = await run_grading_graph(
            student_code="x = 1",
            assignment_text="Assign a variable.",
            official_solution="x = 1",
            grading_rubric="Correct variable assignment.",
        )

    assert isinstance(text, str)
    assert isinstance(flag, bool)
    assert flag is False
    assert "CHEATING_VERDICT" not in text


@pytest.mark.asyncio
async def test_run_grading_graph_detects_cheating():
    from app.graph.workflow import run_grading_graph

    fake_feedback = "### דברים טובים\nטוב.\n### נקודות\nרע.\n### המשך\nהמשך.\nCHEATING_VERDICT: YES"

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"feedback": fake_feedback})

    with patch("app.graph.workflow.grading_graph", mock_graph):
        _, flag = await run_grading_graph(
            student_code="copied code",
            assignment_text="Write something.",
            official_solution="solution",
            grading_rubric="rubric",
        )

    assert flag is True
