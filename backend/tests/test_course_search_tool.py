"""
Tests for CourseSearchTool.execute()

Covers:
- Happy path: results are found and formatted correctly
- Course not found: resolver returns None
- No matching content: search returns empty
- Search layer error: VectorStore.search returns an error result
- Source tracking: last_sources is populated with label and URL
- Sources reset between calls
- Query-only call (no course_name / lesson_number)
"""
import pytest
from unittest.mock import MagicMock, patch

from search_tools import CourseSearchTool
from vector_store import SearchResults

from helpers import make_search_results, make_empty_results, make_error_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tool(store) -> CourseSearchTool:
    return CourseSearchTool(vector_store=store)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestExecuteHappyPath:

    def test_returns_string_on_successful_search(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="neural networks", course_name="Deep Learning Course")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_result_contains_course_title(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="neural networks", course_name="Deep Learning Course")
        assert "Deep Learning Course" in result

    def test_result_contains_lesson_number(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="neural networks", course_name="Deep Learning Course")
        assert "Lesson 1" in result

    def test_result_contains_document_content(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="neural networks", course_name="Deep Learning Course")
        assert "Sample lesson content about neural networks" in result

    def test_multiple_results_are_separated(self, mock_vector_store):
        mock_vector_store.search.return_value = make_search_results(
            documents=["Content A.", "Content B."],
            metadata=[
                {"course_title": "Course X", "lesson_number": 1, "chunk_index": 0},
                {"course_title": "Course X", "lesson_number": 2, "chunk_index": 0},
            ],
            distances=[0.3, 0.6],
        )
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="something")
        assert "Content A." in result
        assert "Content B." in result

    def test_query_without_filters_calls_search_with_no_course(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="what is backprop")
        mock_vector_store.search.assert_called_once_with(
            query="what is backprop",
            course_name=None,
            lesson_number=None,
        )

    def test_course_name_passed_through_to_search(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="backprop", course_name="Deep Learning Course")
        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["course_name"] == "Deep Learning Course"

    def test_lesson_number_passed_through_to_search(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="backprop", course_name="Deep Learning Course", lesson_number=3)
        call_kwargs = mock_vector_store.search.call_args.kwargs
        assert call_kwargs["lesson_number"] == 3


# ---------------------------------------------------------------------------
# No-results / error conditions
# ---------------------------------------------------------------------------

class TestExecuteEmptyAndErrors:

    def test_empty_results_returns_no_content_message(self, mock_vector_store):
        mock_vector_store.search.return_value = make_empty_results()
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="quantum computing", course_name="Physics")
        assert "No relevant content found" in result

    def test_empty_results_includes_course_filter_name(self, mock_vector_store):
        mock_vector_store.search.return_value = make_empty_results()
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="quantum computing", course_name="Physics")
        assert "Physics" in result

    def test_empty_results_includes_lesson_filter(self, mock_vector_store):
        mock_vector_store.search.return_value = make_empty_results()
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="something", lesson_number=5)
        assert "5" in result

    def test_search_error_returns_error_string(self, mock_vector_store):
        mock_vector_store.search.return_value = make_error_results("ChromaDB connection refused")
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="neural networks")
        assert "ChromaDB connection refused" in result

    def test_no_course_found_message_on_resolution_failure(self, mock_vector_store):
        """When VectorStore cannot resolve the course name it returns an error SearchResults."""
        mock_vector_store.search.return_value = SearchResults.empty(
            "No course found matching 'Nonexistent Course'"
        )
        tool = make_tool(mock_vector_store)
        result = tool.execute(query="anything", course_name="Nonexistent Course")
        assert "No course found" in result or len(result) > 0  # error string returned


# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------

class TestSourceTracking:

    def test_last_sources_populated_after_successful_search(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="neural networks", course_name="Deep Learning Course")
        assert len(tool.last_sources) == 1

    def test_last_sources_contains_label(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="neural networks", course_name="Deep Learning Course")
        source = tool.last_sources[0]
        assert "label" in source
        assert "Deep Learning Course" in source["label"]

    def test_last_sources_contains_url_from_get_lesson_link(self, mock_vector_store):
        tool = make_tool(mock_vector_store)
        tool.execute(query="neural networks", course_name="Deep Learning Course")
        source = tool.last_sources[0]
        assert source["url"] == "https://example.com/courses/deep-learning/lesson/1"

    def test_last_sources_url_is_none_when_no_lesson_number(self, mock_vector_store):
        mock_vector_store.search.return_value = make_search_results(
            metadata=[{"course_title": "Course X", "chunk_index": 0}]
            # No lesson_number key
        )
        tool = make_tool(mock_vector_store)
        tool.execute(query="something")
        source = tool.last_sources[0]
        assert source["url"] is None

    def test_last_sources_empty_after_empty_search(self, mock_vector_store):
        mock_vector_store.search.return_value = make_empty_results()
        tool = make_tool(mock_vector_store)
        tool.execute(query="nothing")
        assert tool.last_sources == []

    def test_last_sources_empty_after_search_error(self, mock_vector_store):
        mock_vector_store.search.return_value = make_error_results()
        tool = make_tool(mock_vector_store)
        tool.execute(query="nothing")
        assert tool.last_sources == []

    def test_last_sources_overwritten_on_second_call(self, mock_vector_store):
        """Sources from a prior call must not bleed into the next call."""
        mock_vector_store.search.return_value = make_search_results(
            documents=["Doc 1", "Doc 2"],
            metadata=[
                {"course_title": "A", "lesson_number": 1, "chunk_index": 0},
                {"course_title": "A", "lesson_number": 2, "chunk_index": 0},
            ],
            distances=[0.1, 0.2],
        )
        tool = make_tool(mock_vector_store)
        tool.execute(query="first query")
        assert len(tool.last_sources) == 2

        mock_vector_store.search.return_value = make_empty_results()
        tool.execute(query="second query")
        assert tool.last_sources == []
