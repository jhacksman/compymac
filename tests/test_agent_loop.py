"""
Tests for the AgentLoop and related components.
"""


from compymac.agent_loop import (
    AgentConfig,
    AgentLoop,
    AgentState,
    ScriptedPolicy,
)
from compymac.harness_simulator import create_default_simulator
from compymac.llm import ChatResponse
from compymac.types import Message, ToolCall


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: list[ChatResponse] | None = None):
        self._responses = responses or []
        self._response_index = 0
        self._calls: list[dict] = []

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        self._calls.append({"messages": messages, "tools": tools})

        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            return response

        return ChatResponse(content="Default response", tool_calls=[], finish_reason="stop", raw_response={})


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_config(self):
        config = AgentConfig()
        assert config.max_steps == 50
        assert config.max_tool_calls_per_step == 10
        assert config.system_prompt == ""
        assert config.stop_on_error is False

    def test_custom_config(self):
        config = AgentConfig(
            max_steps=10,
            max_tool_calls_per_step=5,
            system_prompt="You are a helpful assistant.",
            stop_on_error=True,
        )
        assert config.max_steps == 10
        assert config.max_tool_calls_per_step == 5
        assert config.system_prompt == "You are a helpful assistant."
        assert config.stop_on_error is True


class TestAgentState:
    """Tests for AgentState."""

    def test_default_state(self):
        state = AgentState()
        assert state.messages == []
        assert state.step_count == 0
        assert state.tool_call_count == 0
        assert state.is_complete is False
        assert state.final_response == ""


class TestAgentLoop:
    """Tests for AgentLoop."""

    def test_add_user_message(self):
        harness = create_default_simulator()
        llm = MockLLMClient()
        loop = AgentLoop(harness, llm)

        loop.add_user_message("Hello")

        assert len(loop.state.messages) == 1
        assert loop.state.messages[0].role == "user"
        assert loop.state.messages[0].content == "Hello"

    def test_system_prompt_added_on_init(self):
        harness = create_default_simulator()
        llm = MockLLMClient()
        config = AgentConfig(system_prompt="You are helpful.")
        loop = AgentLoop(harness, llm, config)

        assert len(loop.state.messages) == 1
        assert loop.state.messages[0].role == "system"
        assert loop.state.messages[0].content == "You are helpful."

    def test_run_step_with_text_response(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(content="Hello back!", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        loop = AgentLoop(harness, llm)
        loop.add_user_message("Hello")

        text, tool_results = loop.run_step()

        assert text == "Hello back!"
        assert tool_results == []
        assert loop.state.step_count == 1

    def test_run_step_with_tool_calls(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="Read",
                        arguments={"file_path": "/test/file.txt"},
                    ),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        loop = AgentLoop(harness, llm)
        loop.add_user_message("Read a file")

        text, tool_results = loop.run_step()

        assert text is None
        assert len(tool_results) == 1
        assert tool_results[0].success is True
        assert loop.state.tool_call_count == 1

    def test_run_completes_on_text_response(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(content="Task complete!", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        loop = AgentLoop(harness, llm)

        result = loop.run("Do something")

        assert result == "Task complete!"
        assert loop.state.is_complete is True
        assert loop.state.final_response == "Task complete!"

    def test_run_with_tool_then_response(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="Read",
                        arguments={"file_path": "/test/file.txt"},
                    ),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
            ChatResponse(content="I read the file!", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        loop = AgentLoop(harness, llm)

        result = loop.run("Read a file and tell me about it")

        assert result == "I read the file!"
        assert loop.state.step_count == 2
        assert loop.state.tool_call_count == 1

    def test_reset_clears_state(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(content="Done", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        loop = AgentLoop(harness, llm)
        loop.run("Do something")

        loop.reset()

        assert loop.state.messages == []
        assert loop.state.step_count == 0
        assert loop.state.tool_call_count == 0
        assert loop.state.is_complete is False


class TestScriptedPolicy:
    """Tests for ScriptedPolicy."""

    def test_returns_tool_calls_in_order(self):
        calls = [
            ToolCall(id="1", name="Read", arguments={"file_path": "/a.txt"}),
            ToolCall(id="2", name="Read", arguments={"file_path": "/b.txt"}),
        ]
        policy = ScriptedPolicy(calls)
        state = AgentState()

        result1 = policy.get_tool_calls(state)
        result2 = policy.get_tool_calls(state)
        result3 = policy.get_tool_calls(state)

        assert len(result1) == 1
        assert result1[0].id == "1"
        assert len(result2) == 1
        assert result2[0].id == "2"
        assert result3 == []

    def test_final_response(self):
        policy = ScriptedPolicy([], final_response="All done!")
        state = AgentState()

        result = policy.get_final_response(state)

        assert result == "All done!"

    def test_run_with_policy(self):
        harness = create_default_simulator()
        llm = MockLLMClient()  # Not used with policy
        loop = AgentLoop(harness, llm)

        calls = [
            ToolCall(id="1", name="Read", arguments={"file_path": "/test.txt"}),
        ]
        policy = ScriptedPolicy(calls, final_response="Done with policy!")

        result = loop.run_with_policy(policy, "Test input")

        assert result == "Done with policy!"


class TestEventLogging:
    """Tests for event logging in agent loop."""

    def test_events_logged_during_run(self):
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="Read", arguments={"file_path": "/test.txt"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
            ChatResponse(content="Done", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        loop = AgentLoop(harness, llm)

        loop.run("Test")

        events = harness.get_event_log().events
        event_types = [e.event_type.value for e in events]

        # Should have agent turn events and tool events
        assert "agent_turn_start" in event_types
        assert "agent_turn_end" in event_types
        assert "llm_request" in event_types
        assert "llm_response" in event_types
        assert "tool_call_received" in event_types
