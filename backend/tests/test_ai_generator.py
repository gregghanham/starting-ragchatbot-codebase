"""
Tests for AIGenerator

Focus areas:
1. Direct text response path (no tool use) — generate_response returns text immediately.
2. Tool-use path — generate_response calls _handle_tool_execution when stop_reason=="tool_use".
3. _handle_tool_execution constructs the follow-up message array correctly:
   - assistant message must carry the initial response's content blocks.
   - user message must carry the tool results with correct structure.
4. Final API call is made WITHOUT the tools parameter.
5. Text is extracted from the first content block of the final response.
6. Multiple content blocks in the initial response are all iterated for tool calls.
7. System prompt is passed on every API call.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from ai_generator import AIGenerator

from helpers import (
    MockTextBlock,
    MockToolUseBlock,
    MockMessage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_API_KEY = "sk-ant-test-key"
FAKE_MODEL = "claude-haiku-4-5-20251001"


def make_generator(mock_client=None):
    """Return an AIGenerator whose Anthropic client is replaced with a mock."""
    with patch("ai_generator.anthropic.Anthropic") as MockAnthropic:
        if mock_client is None:
            mock_client = MagicMock()
        MockAnthropic.return_value = mock_client
        gen = AIGenerator(api_key=FAKE_API_KEY, model=FAKE_MODEL)
    # Inject the mock directly so tests can configure it after construction
    gen.client = mock_client
    return gen, mock_client


def make_tool_manager(tool_result="Tool returned this result."):
    """Return a ToolManager mock that always returns a fixed string."""
    tm = MagicMock()
    tm.execute_tool.return_value = tool_result
    return tm


# ---------------------------------------------------------------------------
# Direct text-response path (no tool use)
# ---------------------------------------------------------------------------

class TestDirectTextResponse:

    def test_returns_text_when_stop_reason_is_end_turn(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        result = gen.generate_response(query="What is Python?")

        assert result == "Python is a high-level programming language."

    def test_api_called_once_when_no_tool_use(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        gen.generate_response(query="What is Python?")

        assert mock_client.messages.create.call_count == 1

    def test_system_prompt_included_in_api_call(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        gen.generate_response(query="What is Python?")

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" in kwargs
        assert len(kwargs["system"]) > 0

    def test_query_included_as_user_message(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        gen.generate_response(query="What is Python?")

        kwargs = mock_client.messages.create.call_args.kwargs
        messages = kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert "What is Python?" in messages[0]["content"]

    def test_conversation_history_appended_to_system_prompt(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        gen.generate_response(
            query="Follow-up question",
            conversation_history="User: Hello\nAssistant: Hi there",
        )

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "Hello" in kwargs["system"]
        assert "Hi there" in kwargs["system"]

    def test_tools_passed_to_api_when_provided(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response
        fake_tools = [{"name": "search_course_content", "description": "..."}]

        gen.generate_response(query="Search something", tools=fake_tools)

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["tools"] == fake_tools
        assert kwargs["tool_choice"] == {"type": "auto"}

    def test_no_tools_key_when_tools_not_provided(self, text_only_response):
        gen, mock_client = make_generator()
        mock_client.messages.create.return_value = text_only_response

        gen.generate_response(query="General question")

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" not in kwargs


# ---------------------------------------------------------------------------
# Tool-use path — routing to _handle_tool_execution
# ---------------------------------------------------------------------------

class TestToolUseRouting:

    def test_handle_tool_execution_called_when_stop_reason_is_tool_use(
        self, tool_use_response, final_text_response
    ):
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, final_text_response]

        gen.generate_response(
            query="Tell me about neural networks",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        # Two API calls: initial + follow-up after tool execution
        assert mock_client.messages.create.call_count == 2

    def test_returns_final_text_after_tool_execution(
        self, tool_use_response, final_text_response
    ):
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, final_text_response]

        result = gen.generate_response(
            query="Tell me about neural networks",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        assert result == "Based on the course materials, neural networks consist of layers."

    def test_tool_manager_execute_tool_called_with_correct_args(
        self, tool_use_response, final_text_response
    ):
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, final_text_response]
        tm = make_tool_manager()

        gen.generate_response(
            query="Tell me about neural networks",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        tm.execute_tool.assert_called_once_with(
            "search_course_content",
            query="neural networks",
            course_name="Deep Learning Course",
        )


# ---------------------------------------------------------------------------
# _handle_tool_execution — message construction
# ---------------------------------------------------------------------------

class TestHandleToolExecutionMessageConstruction:

    def _run_tool_execution(self, tool_use_response, final_text_response, tool_result="Tool result text"):
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, final_text_response]
        tm = make_tool_manager(tool_result=tool_result)

        gen.generate_response(
            query="What are neural networks?",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        # Return kwargs of the SECOND (final) API call
        return mock_client.messages.create.call_args_list[1].kwargs

    def test_assistant_message_added_to_follow_up_messages(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert "assistant" in roles

    def test_assistant_message_content_is_initial_response_content(
        self, tool_use_response, final_text_response
    ):
        """
        The assistant turn in the follow-up call must contain the original
        content blocks (including the tool_use block). This is required by the
        Anthropic API — omitting the tool_use block causes a validation error.
        """
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        assistant_msg = next(m for m in messages if m["role"] == "assistant")
        # content must be the raw content list from the initial response
        assert assistant_msg["content"] is tool_use_response.content

    def test_tool_result_message_added_as_user_turn(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        # Last message before the final API call should be the tool result (user turn)
        last_msg = messages[-1]
        assert last_msg["role"] == "user"

    def test_tool_result_has_correct_type_field(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        tool_result_msg = messages[-1]
        tool_results = tool_result_msg["content"]
        assert isinstance(tool_results, list)
        assert tool_results[0]["type"] == "tool_result"

    def test_tool_result_references_correct_tool_use_id(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        tool_result_msg = messages[-1]
        tool_result = tool_result_msg["content"][0]
        assert tool_result["tool_use_id"] == "tool_abc123"

    def test_tool_result_content_matches_execute_output(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(
            tool_use_response, final_text_response, tool_result="Lesson content: backprop updates weights."
        )
        messages = final_kwargs["messages"]
        tool_result = messages[-1]["content"][0]
        assert tool_result["content"] == "Lesson content: backprop updates weights."

    def test_round_two_api_call_includes_tools(
        self, tool_use_response, final_text_response
    ):
        """
        The round-2 API call must include 'tools' so Claude can decide
        whether to search again or produce a final answer.
        """
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        assert "tools" in final_kwargs

    def test_system_prompt_preserved_in_final_api_call(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        assert "system" in final_kwargs
        assert len(final_kwargs["system"]) > 0

    def test_message_order_is_user_then_assistant_then_tool_result(
        self, tool_use_response, final_text_response
    ):
        final_kwargs = self._run_tool_execution(tool_use_response, final_text_response)
        messages = final_kwargs["messages"]
        assert messages[0]["role"] == "user"        # original query
        assert messages[1]["role"] == "assistant"   # Claude's tool_use response
        assert messages[2]["role"] == "user"        # tool result


# ---------------------------------------------------------------------------
# Multiple tool-use blocks in a single response
# ---------------------------------------------------------------------------

class TestMultipleToolCalls:

    def test_all_tool_use_blocks_are_executed(self, final_text_response):
        """When Claude returns two tool_use blocks, both must be executed."""
        multi_tool_response = MockMessage(
            stop_reason="tool_use",
            content=[
                MockToolUseBlock("id_1", "search_course_content", {"query": "backprop"}),
                MockToolUseBlock("id_2", "search_course_content", {"query": "gradient descent"}),
            ],
        )

        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [multi_tool_response, final_text_response]
        tm = make_tool_manager()

        gen.generate_response(
            query="Explain training",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        assert tm.execute_tool.call_count == 2

    def test_two_tool_results_in_follow_up_message(self, final_text_response):
        multi_tool_response = MockMessage(
            stop_reason="tool_use",
            content=[
                MockToolUseBlock("id_1", "search_course_content", {"query": "backprop"}),
                MockToolUseBlock("id_2", "search_course_content", {"query": "gradient descent"}),
            ],
        )

        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [multi_tool_response, final_text_response]

        gen.generate_response(
            query="Explain training",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        final_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        tool_result_content = final_kwargs["messages"][-1]["content"]
        assert len(tool_result_content) == 2
        ids = {r["tool_use_id"] for r in tool_result_content}
        assert ids == {"id_1", "id_2"}


# ---------------------------------------------------------------------------
# Text extraction from final response
# ---------------------------------------------------------------------------

class TestFinalResponseTextExtraction:

    def test_text_extracted_from_first_content_block(self, tool_use_response):
        expected_text = "Here is what I found about neural networks."
        final_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock(expected_text)],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, final_response]

        result = gen.generate_response(
            query="neural networks",
            tools=[{}],
            tool_manager=make_tool_manager(),
        )

        assert result == expected_text

    def test_raises_or_fails_when_final_content_is_empty(self, tool_use_response):
        """
        If the final response has no content blocks, content[0] raises IndexError.
        This test documents the current behaviour — the caller should handle it.
        """
        empty_response = MockMessage(stop_reason="end_turn", content=[])
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, empty_response]

        with pytest.raises((IndexError, AttributeError)):
            gen.generate_response(
                query="neural networks",
                tools=[{}],
                tool_manager=make_tool_manager(),
            )


# ---------------------------------------------------------------------------
# Sequential tool calling — up to 2 rounds
# ---------------------------------------------------------------------------

class TestSequentialToolCalling:

    def _two_round_setup(self, second_tool_use_response, final_text_response, synthesis_text=None):
        """
        Helper: returns (gen, mock_client, tm) configured for a two-round tool-use scenario.
        Calls: round1=tool_use, round2=tool_use, synthesis=end_turn.
        """
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock(synthesis_text or "Synthesized answer after two searches.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [
            second_tool_use_response,  # first call → tool_use (round 1)
            final_text_response,        # second call → tool_use... wait
        ]
        # Reset: use proper two-round mock
        mock_client.messages.create.side_effect = [
            MockMessage(
                stop_reason="tool_use",
                content=[MockToolUseBlock("id_r1", "search_course_content", {"query": "lesson 4"})],
            ),
            second_tool_use_response,   # second call → still tool_use (round 2 result)
            synthesis_response,         # third call → synthesis, end_turn
        ]
        tm = make_tool_manager()
        return gen, mock_client, tm, synthesis_response

    def test_two_round_tool_use_makes_three_api_calls(
        self, second_tool_use_response, final_text_response
    ):
        gen, mock_client, tm, _ = self._two_round_setup(second_tool_use_response, final_text_response)

        gen.generate_response(
            query="Find a course on the same topic as lesson 4 of course X",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        assert mock_client.messages.create.call_count == 3

    def test_two_round_tool_use_executes_both_tools(
        self, second_tool_use_response, final_text_response
    ):
        gen, mock_client, tm, _ = self._two_round_setup(second_tool_use_response, final_text_response)

        gen.generate_response(
            query="Find a course on the same topic as lesson 4 of course X",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        assert tm.execute_tool.call_count == 2

    def test_two_round_tool_use_returns_synthesis_text(
        self, second_tool_use_response, final_text_response
    ):
        gen, mock_client, tm, synthesis_response = self._two_round_setup(
            second_tool_use_response, final_text_response, synthesis_text="Final synthesized answer."
        )

        result = gen.generate_response(
            query="Find a course on the same topic as lesson 4 of course X",
            tools=[{"name": "search_course_content"}],
            tool_manager=tm,
        )

        assert result == "Final synthesized answer."

    def test_round_limit_enforced_at_two(self, second_tool_use_response):
        """Even if Claude keeps requesting tools, stop at 2 rounds and synthesize."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("Here is my answer.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [
            MockMessage(
                stop_reason="tool_use",
                content=[MockToolUseBlock("id_r1", "search_course_content", {"query": "q1"})],
            ),
            second_tool_use_response,  # round 2 also wants more tools
            synthesis_response,        # synthesis call — no tools
        ]

        gen.generate_response(
            query="Multi-step query",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        assert mock_client.messages.create.call_count == 3

    def test_tools_present_in_round_two_api_call(self, second_tool_use_response, final_text_response):
        """The second API call (round 2) must include tools so Claude can search again."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("Answer.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [
            MockMessage(
                stop_reason="tool_use",
                content=[MockToolUseBlock("id_r1", "search_course_content", {"query": "q1"})],
            ),
            second_tool_use_response,
            synthesis_response,
        ]

        gen.generate_response(
            query="Multi-step query",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs

    def test_synthesis_call_has_no_tools_on_round_limit(self, second_tool_use_response):
        """After hitting the round limit, the synthesis call must NOT include tools."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("Answer.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [
            MockMessage(
                stop_reason="tool_use",
                content=[MockToolUseBlock("id_r1", "search_course_content", {"query": "q1"})],
            ),
            second_tool_use_response,
            synthesis_response,
        ]

        gen.generate_response(
            query="Multi-step query",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        synthesis_kwargs = mock_client.messages.create.call_args_list[2].kwargs
        assert "tools" not in synthesis_kwargs

    def test_message_history_has_five_entries_after_two_rounds(self, second_tool_use_response):
        """Synthesis call receives full 5-message history: user, assistant, user, assistant, user."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("Answer.")],
        )
        gen, mock_client = make_generator()
        round1_response = MockMessage(
            stop_reason="tool_use",
            content=[MockToolUseBlock("id_r1", "search_course_content", {"query": "q1"})],
        )
        mock_client.messages.create.side_effect = [
            round1_response,
            second_tool_use_response,
            synthesis_response,
        ]

        gen.generate_response(
            query="Multi-step query",
            tools=[{"name": "search_course_content"}],
            tool_manager=make_tool_manager(),
        )

        synthesis_messages = mock_client.messages.create.call_args_list[2].kwargs["messages"]
        assert len(synthesis_messages) == 5
        roles = [m["role"] for m in synthesis_messages]
        assert roles == ["user", "assistant", "user", "assistant", "user"]

    def test_tool_error_terminates_loop(self, tool_use_response, final_text_response):
        """On tool execution error, no second tool-use round is attempted."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("Could not complete the search.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, synthesis_response]

        failing_tm = MagicMock()
        failing_tm.execute_tool.side_effect = RuntimeError("Search service unavailable")

        gen.generate_response(
            query="Tell me about neural networks",
            tools=[{"name": "search_course_content"}],
            tool_manager=failing_tm,
        )

        # Initial call + synthesis call only — no round 2 tool call
        assert mock_client.messages.create.call_count == 2

    def test_tool_error_returns_text_not_exception(self, tool_use_response):
        """Tool execution errors are handled gracefully — a string is returned, not raised."""
        synthesis_response = MockMessage(
            stop_reason="end_turn",
            content=[MockTextBlock("I encountered an issue retrieving the information.")],
        )
        gen, mock_client = make_generator()
        mock_client.messages.create.side_effect = [tool_use_response, synthesis_response]

        failing_tm = MagicMock()
        failing_tm.execute_tool.side_effect = RuntimeError("Search service unavailable")

        result = gen.generate_response(
            query="Tell me about neural networks",
            tools=[{"name": "search_course_content"}],
            tool_manager=failing_tm,
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_system_prompt_allows_two_searches(self):
        """SYSTEM_PROMPT must advertise up to 2 searches, not 'one search per query'."""
        from ai_generator import AIGenerator
        prompt = AIGenerator.SYSTEM_PROMPT.lower()
        assert "2 searches" in prompt
        assert "one search per query" not in prompt
