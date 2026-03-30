"""
Shared pytest fixtures for all test modules.
Factory helpers live in helpers.py and are importable directly.
"""
import sys
import os

# Ensure backend/ and tests/ are both on the import path
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_tests_dir)
sys.path.insert(0, _tests_dir)
sys.path.insert(0, _backend_dir)

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional

from helpers import (
    MockTextBlock,
    MockToolUseBlock,
    MockMessage,
    make_search_results,
)


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# API endpoint fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """Fully-configured MagicMock standing in for RAGSystem in endpoint tests."""
    mock = MagicMock()
    mock.session_manager.create_session.return_value = "session-abc123"
    mock.query.return_value = (
        "Here is the answer.",
        [{"label": "Deep Learning - Lesson 1", "url": "https://example.com/lesson/1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 3,
        "course_titles": ["Deep Learning", "NLP", "Computer Vision"],
    }
    return mock


@pytest.fixture
def api_client(mock_rag_system):
    """
    TestClient for a self-contained test FastAPI app.

    Mirrors the routes in app.py (POST /api/query, GET /api/courses) but
    skips the static-files mount that requires the real frontend directory.
    """

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class Source(BaseModel):
        label: str
        url: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Source]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    test_app = FastAPI()

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return TestClient(test_app)


# ---------------------------------------------------------------------------
# VectorStore / Anthropic mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_vector_store():
    """MagicMock satisfying the VectorStore interface used by search tools."""
    store = MagicMock()
    store.get_lesson_link.return_value = "https://example.com/courses/deep-learning/lesson/1"
    store.search.return_value = make_search_results()
    store._resolve_course_name.return_value = "Deep Learning Course"
    store.get_course_outline.return_value = {
        "title": "Deep Learning Course",
        "course_link": "https://example.com/courses/deep-learning",
        "lessons": [
            {"lesson_number": 0, "lesson_title": "Introduction"},
            {"lesson_number": 1, "lesson_title": "Neural Networks"},
            {"lesson_number": 2, "lesson_title": "Backpropagation"},
        ],
    }
    return store


@pytest.fixture
def tool_use_response():
    """A mock Anthropic message whose stop_reason is 'tool_use'."""
    return MockMessage(
        stop_reason="tool_use",
        content=[
            MockTextBlock("Let me search the course content for you."),
            MockToolUseBlock(
                block_id="tool_abc123",
                name="search_course_content",
                input_data={"query": "neural networks", "course_name": "Deep Learning Course"},
            ),
        ],
    )


@pytest.fixture
def text_only_response():
    """A mock Anthropic message with a direct text answer (no tool use)."""
    return MockMessage(
        stop_reason="end_turn",
        content=[MockTextBlock("Python is a high-level programming language.")],
    )


@pytest.fixture
def final_text_response():
    """A mock final Anthropic message after tool results have been supplied."""
    return MockMessage(
        stop_reason="end_turn",
        content=[MockTextBlock("Based on the course materials, neural networks consist of layers.")],
    )


@pytest.fixture
def second_tool_use_response():
    """A mock second-round response that also requests tool use."""
    return MockMessage(
        stop_reason="tool_use",
        content=[
            MockTextBlock("Let me search for related content."),
            MockToolUseBlock(
                block_id="tool_xyz789",
                name="search_course_content",
                input_data={"query": "transformers", "course_name": "NLP Course"},
            ),
        ],
    )
