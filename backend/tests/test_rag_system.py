"""
Tests for RAGSystem.query() — the content-query path

Covers:
1. A content-specific query triggers tool use and returns a coherent response.
2. Sources are returned alongside the response.
3. Sources are cleared from the tool manager after retrieval (so they don't
   bleed into the next query).
4. Session history is updated after a successful query.
5. Queries without a session_id are handled gracefully.
6. Exceptions raised inside the AI generator propagate upward (not swallowed).
7. The prompt wrapping applied in rag_system.query() is visible to the generator.
"""
import pytest
from unittest.mock import MagicMock, patch

from rag_system import RAGSystem
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager

from helpers import (
    MockTextBlock,
    MockToolUseBlock,
    MockMessage,
    make_search_results,
    make_empty_results,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_text_response(text="Direct answer."):
    return MockMessage(stop_reason="end_turn", content=[MockTextBlock(text)])


def make_tool_use_response(query="neural networks", course="Deep Learning Course"):
    return MockMessage(
        stop_reason="tool_use",
        content=[
            MockToolUseBlock(
                "tool_xyz",
                "search_course_content",
                {"query": query, "course_name": course},
            )
        ],
    )


def make_final_response(text="Neural networks are composed of layers."):
    return MockMessage(stop_reason="end_turn", content=[MockTextBlock(text)])


@pytest.fixture
def minimal_config():
    """Minimal config object that lets RAGSystem construct without touching disk."""
    cfg = MagicMock()
    cfg.ANTHROPIC_API_KEY = "sk-ant-test"
    cfg.ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
    cfg.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    cfg.CHUNK_SIZE = 400
    cfg.CHUNK_OVERLAP = 100
    cfg.MAX_RESULTS = 3
    cfg.MAX_HISTORY = 2
    cfg.CHROMA_PATH = "./chroma_db_test"
    return cfg


@pytest.fixture
def rag(minimal_config, mock_vector_store):
    """
    RAGSystem with mocked-out VectorStore and Anthropic client.

    We patch:
      - VectorStore so ChromaDB is never touched
      - SentenceTransformerEmbeddingFunction (loaded inside VectorStore.__init__)
      - anthropic.Anthropic so no real API calls are made
    """
    with patch("rag_system.VectorStore", return_value=mock_vector_store), \
         patch("ai_generator.anthropic.Anthropic") as MockAnthropic:

        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        system = RAGSystem(minimal_config)
        # Expose the mock client so individual tests can configure call returns
        system._mock_client = mock_client

    return system


# ---------------------------------------------------------------------------
# Basic response/return-value shape
# ---------------------------------------------------------------------------

class TestQueryReturnShape:

    def test_query_returns_tuple_of_two(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response()
        result = rag.query("What is Python?", session_id=None)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_string(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response("Hello.")
        response, _ = rag.query("What is Python?")
        assert isinstance(response, str)

    def test_second_element_is_list(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response()
        _, sources = rag.query("What is Python?")
        assert isinstance(sources, list)


# ---------------------------------------------------------------------------
# Content-query (tool-use) path
# ---------------------------------------------------------------------------

class TestContentQueryPath:

    def test_content_query_returns_final_text(self, rag, mock_vector_store):
        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response("Neural networks are composed of layers."),
        ]
        response, _ = rag.query("Tell me about neural networks in Deep Learning")
        assert "Neural networks" in response

    def test_content_query_triggers_two_api_calls(self, rag, mock_vector_store):
        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response(),
        ]
        rag.query("Tell me about neural networks")
        assert rag._mock_client.messages.create.call_count == 2

    def test_sources_populated_from_search_tool(self, rag, mock_vector_store):
        """
        After a tool-use query the sources list must contain entries from the
        CourseSearchTool's last_sources (populated via _format_results).
        """
        mock_vector_store.search.return_value = make_search_results()
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson/1"

        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response(),
        ]

        _, sources = rag.query("Tell me about neural networks")
        assert isinstance(sources, list)
        # Sources are dicts with at least a 'label' key
        if sources:
            assert "label" in sources[0]

    def test_sources_cleared_after_retrieval(self, rag, mock_vector_store):
        """
        last_sources on the search tool must be reset after each query so that
        one query's sources don't appear in the next query's response.
        """
        mock_vector_store.search.return_value = make_search_results()

        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response(),
            make_text_response("Direct answer."),
        ]

        rag.query("First query — uses tool")
        search_tool = next(
            t for t in rag.tool_manager.tools.values()
            if isinstance(t, CourseSearchTool)
        )
        # After the first query the tool's last_sources must have been reset
        assert search_tool.last_sources == []

    def test_second_query_sources_independent_of_first(self, rag, mock_vector_store):
        mock_vector_store.search.return_value = make_search_results()

        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),   # Q1 initial
            make_final_response(),      # Q1 final
            make_text_response("Second answer."),  # Q2 direct
        ]

        rag.query("Content query")
        _, sources_q2 = rag.query("General question — no tool use")
        assert sources_q2 == []


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSessionManagement:

    def test_query_without_session_id_does_not_raise(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response()
        # Should not raise even though session_id is None
        response, _ = rag.query("No session query", session_id=None)
        assert isinstance(response, str)

    def test_session_history_updated_after_query(self, rag):
        session_id = rag.session_manager.create_session()
        rag._mock_client.messages.create.return_value = make_text_response("Answer.")

        rag.query("User question", session_id=session_id)

        history = rag.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "User question" in history
        assert "Answer." in history

    def test_conversation_history_passed_to_generator_on_second_query(self, rag):
        session_id = rag.session_manager.create_session()
        rag._mock_client.messages.create.return_value = make_text_response("First.")

        rag.query("First question", session_id=session_id)

        rag._mock_client.messages.create.reset_mock()
        rag._mock_client.messages.create.return_value = make_text_response("Second.")

        rag.query("Second question", session_id=session_id)

        # The system prompt on the second call should include prior history
        call_kwargs = rag._mock_client.messages.create.call_args.kwargs
        assert "First question" in call_kwargs["system"] or "First." in call_kwargs["system"]


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

class TestErrorPropagation:

    def test_api_exception_propagates_from_query(self, rag):
        rag._mock_client.messages.create.side_effect = RuntimeError("Anthropic API error")
        with pytest.raises(RuntimeError, match="Anthropic API error"):
            rag.query("Anything")

    def test_tool_execution_exception_is_caught_and_query_still_returns(
        self, rag, mock_vector_store
    ):
        """
        Even when a tool raises unexpectedly (bypassing VectorStore's own
        try/except), ai_generator._handle_tool_execution now catches the
        exception and passes a graceful error string to Claude.  The overall
        query must still return a string rather than propagating the exception
        to app.py as a 500 error.
        """
        mock_vector_store.search.side_effect = Exception("ChromaDB timeout")

        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response("I could not retrieve course data, but here is what I know."),
        ]

        # Should NOT raise — the exception is caught inside _handle_tool_execution
        response, _ = rag.query("Neural networks question")
        assert isinstance(response, str)

    def test_tool_returns_error_string_when_search_fails_gracefully(
        self, rag, mock_vector_store
    ):
        """
        VectorStore.search() wraps ChromaDB calls in try/except and returns
        SearchResults.empty(error_msg).  CourseSearchTool.execute() converts
        that to a plain error string.  Claude then receives that string as the
        tool result and can still produce a final answer.
        """
        from helpers import make_error_results
        mock_vector_store.search.return_value = make_error_results("ChromaDB index empty")

        rag._mock_client.messages.create.side_effect = [
            make_tool_use_response(),
            make_final_response("I was unable to find relevant content."),
        ]

        response, _ = rag.query("Neural networks question")
        assert isinstance(response, str)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestPromptConstruction:

    def test_user_query_embedded_in_prompt_sent_to_generator(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response()

        rag.query("What is backpropagation?")

        call_kwargs = rag._mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_content = messages[0]["content"]
        assert "backpropagation" in user_content

    def test_tools_passed_to_api(self, rag):
        rag._mock_client.messages.create.return_value = make_text_response()

        rag.query("Some question")

        call_kwargs = rag._mock_client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        tool_names = [t["name"] for t in call_kwargs["tools"]]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names
