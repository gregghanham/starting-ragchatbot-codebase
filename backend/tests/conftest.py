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

from helpers import (
    MockTextBlock,
    MockToolUseBlock,
    MockMessage,
    make_search_results,
)


# ---------------------------------------------------------------------------
# Shared pytest fixtures
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
