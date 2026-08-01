import pytest
from unittest.mock import MagicMock, patch, call
from ai_generator import AIGenerator


def make_text_response(text="Final answer"):
    """Build a mock Claude response that ends with plain text."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(
    tool_name="search_course_content", tool_id="tool_1", tool_input=None
):
    """Build a mock Claude response that ends with a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input or {"query": "test query"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def make_generator():
    return AIGenerator(api_key="test-key", model="claude-test")


@pytest.fixture
def generator():
    return make_generator()


@pytest.fixture
def tool_manager():
    mgr = MagicMock()
    mgr.execute_tool.return_value = "search result"
    return mgr


@pytest.fixture
def tools():
    return [{"name": "search_course_content", "description": "Search courses"}]


class TestNoToolCalls:
    def test_single_api_call_when_no_tool_use(self, generator, tools):
        text_response = make_text_response("Direct answer")
        with patch.object(
            generator.client.messages, "create", return_value=text_response
        ) as mock_create:
            result = generator.generate_response("What is ML?", tools=tools)

        assert mock_create.call_count == 1
        assert result == "Direct answer"

    def test_no_tool_executed_when_no_tool_use(self, generator, tool_manager, tools):
        with patch.object(
            generator.client.messages, "create", return_value=make_text_response()
        ):
            generator.generate_response(
                "What is ML?", tools=tools, tool_manager=tool_manager
            )

        tool_manager.execute_tool.assert_not_called()

    def test_works_without_tools(self, generator):
        with patch.object(
            generator.client.messages,
            "create",
            return_value=make_text_response("Hello"),
        ) as mock_create:
            result = generator.generate_response("Hello")

        assert mock_create.call_count == 1
        assert result == "Hello"


class TestOneToolRound:
    def test_two_api_calls_for_one_tool_round(self, generator, tool_manager, tools):
        responses = [
            make_tool_use_response(),
            make_text_response("Answer after search"),
        ]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            result = generator.generate_response(
                "Find course X", tools=tools, tool_manager=tool_manager
            )

        assert mock_create.call_count == 2
        assert result == "Answer after search"

    def test_tool_executed_once(self, generator, tool_manager, tools):
        responses = [
            make_tool_use_response(tool_input={"query": "course X"}),
            make_text_response(),
        ]
        with patch.object(generator.client.messages, "create", side_effect=responses):
            generator.generate_response(
                "Find course X", tools=tools, tool_manager=tool_manager
            )

        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="course X"
        )

    def test_second_call_has_tools_when_more_rounds_possible(
        self, generator, tool_manager, tools
    ):
        """After round 1, tools must still be available so Claude can do a second search."""
        responses = [make_tool_use_response(), make_text_response()]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            generator.generate_response(
                "Find course X", tools=tools, tool_manager=tool_manager
            )

        second_call_kwargs = mock_create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs

    def test_conversation_history_included(self, generator, tool_manager, tools):
        responses = [make_tool_use_response(), make_text_response()]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            generator.generate_response(
                "Find course X",
                conversation_history="User: hi\nAssistant: hello",
                tools=tools,
                tool_manager=tool_manager,
            )

        first_call_kwargs = mock_create.call_args_list[0].kwargs
        assert "Previous conversation:" in first_call_kwargs["system"]


class TestTwoToolRounds:
    def test_three_api_calls_for_two_tool_rounds(self, generator, tool_manager, tools):
        responses = [
            make_tool_use_response(tool_id="t1"),
            make_tool_use_response(tool_id="t2"),
            make_text_response("Final answer after two searches"),
        ]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            result = generator.generate_response(
                "Compare courses", tools=tools, tool_manager=tool_manager
            )

        assert mock_create.call_count == 3
        assert result == "Final answer after two searches"

    def test_tool_executed_twice(self, generator, tool_manager, tools):
        responses = [
            make_tool_use_response(tool_id="t1", tool_input={"query": "first"}),
            make_tool_use_response(tool_id="t2", tool_input={"query": "second"}),
            make_text_response(),
        ]
        with patch.object(generator.client.messages, "create", side_effect=responses):
            generator.generate_response(
                "Compare courses", tools=tools, tool_manager=tool_manager
            )

        assert tool_manager.execute_tool.call_count == 2

    def test_tools_stripped_on_final_call_after_two_rounds(
        self, generator, tool_manager, tools
    ):
        """After exhausting MAX_TOOL_ROUNDS, the final call must not include tools."""
        responses = [
            make_tool_use_response(tool_id="t1"),
            make_tool_use_response(tool_id="t2"),
            make_text_response(),
        ]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            generator.generate_response(
                "Compare courses", tools=tools, tool_manager=tool_manager
            )

        final_call_kwargs = mock_create.call_args_list[2].kwargs
        assert "tools" not in final_call_kwargs

    def test_caps_at_two_rounds_even_if_claude_wants_more(
        self, generator, tool_manager, tools
    ):
        """Claude signals tool_use three times but the system must stop at 2 rounds."""
        responses = [
            make_tool_use_response(tool_id="t1"),
            make_tool_use_response(tool_id="t2"),
            make_tool_use_response(
                tool_id="t3"
            ),  # Would trigger a third round — must be ignored
            make_text_response(),
        ]
        with patch.object(
            generator.client.messages, "create", side_effect=responses
        ) as mock_create:
            # The third response is tool_use but stop_reason=="tool_use" is returned by messages.create
            # When rounds are exhausted, we call without tools and get that third response back,
            # then exit (stop_reason != "tool_use" path or we just return content[0].text).
            # The side_effect list has 4 items but only 3 should be consumed.
            generator.generate_response(
                "Multi search", tools=tools, tool_manager=tool_manager
            )

        assert mock_create.call_count == 3
        assert tool_manager.execute_tool.call_count == 2


class TestErrorHandling:
    def test_tool_exception_aborts_loop_gracefully(
        self, generator, tool_manager, tools
    ):
        """If tool execution raises, the loop exits and the last response's text is returned."""
        tool_use_resp = make_tool_use_response()
        fallback_text_resp = make_text_response("Fallback")
        tool_manager.execute_tool.side_effect = RuntimeError("Search failed")

        with patch.object(
            generator.client.messages,
            "create",
            side_effect=[tool_use_resp, fallback_text_resp],
        ) as mock_create:
            result = generator.generate_response(
                "Find course X", tools=tools, tool_manager=tool_manager
            )

        # Loop aborted after exception; no second API call should have been made
        assert mock_create.call_count == 1
        # Returns the last response held before the exception caused a break
        assert result == tool_use_resp.content[0].text

    def test_no_tool_manager_skips_loop(self, generator, tools):
        """If tool_manager is None, tool_use response is returned as-is (content[0].text)."""
        tool_use_resp = make_tool_use_response()
        tool_use_resp.content[0].text = "tool block text"

        with patch.object(
            generator.client.messages, "create", return_value=tool_use_resp
        ) as mock_create:
            result = generator.generate_response(
                "Find course X", tools=tools, tool_manager=None
            )

        assert mock_create.call_count == 1
        assert result == "tool block text"
