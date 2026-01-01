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


class TestActionGatedProtocol:
    """Tests for action-gated dialogue protocol (MUD-style agent control)."""

    def test_action_gated_config_defaults(self):
        """Test that action-gated config options have correct defaults."""
        config = AgentConfig()
        assert config.action_gated is False
        assert config.max_invalid_moves == 5
        assert config.require_complete_tool is False

    def test_action_gated_with_complete_tool_success(self):
        """Test that calling complete tool ends the loop successfully."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Task done!"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert result == "Task done!"
        assert loop.state.is_complete is True

    def test_action_gated_prose_only_triggers_invalid_move(self):
        """Test that prose-only response triggers invalid move and corrective message."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            # First response: prose only (invalid)
            ChatResponse(content="I'm thinking...", tool_calls=[], finish_reason="stop", raw_response={}),
            # Second response: valid tool call
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done after retry"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        # Should succeed after retry
        assert result == "Done after retry"
        # Check that corrective message was injected
        user_messages = [m for m in loop.state.messages if m.role == "user"]
        assert any("Invalid move" in m.content for m in user_messages)

    def test_action_gated_max_invalid_moves_fails(self):
        """Test that exceeding max_invalid_moves returns failure."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        # All responses are prose-only (invalid)
        llm = MockLLMClient(responses=[
            ChatResponse(content="Thinking 1", tool_calls=[], finish_reason="stop", raw_response={}),
            ChatResponse(content="Thinking 2", tool_calls=[], finish_reason="stop", raw_response={}),
            ChatResponse(content="Thinking 3", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True, max_invalid_moves=3)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert "Failed" in result
        assert "3 consecutive invalid moves" in result

    def test_action_gated_valid_tool_resets_invalid_count(self):
        """Test that valid tool call resets invalid move counter."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            # Invalid move 1
            ChatResponse(content="Thinking 1", tool_calls=[], finish_reason="stop", raw_response={}),
            # Invalid move 2
            ChatResponse(content="Thinking 2", tool_calls=[], finish_reason="stop", raw_response={}),
            # Valid tool call (resets counter)
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="think", arguments={"thought": "Let me think"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
            # Invalid move 1 (counter reset)
            ChatResponse(content="Thinking 3", tool_calls=[], finish_reason="stop", raw_response={}),
            # Invalid move 2
            ChatResponse(content="Thinking 4", tool_calls=[], finish_reason="stop", raw_response={}),
            # Complete
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_2", name="complete", arguments={"final_answer": "Finally done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True, max_invalid_moves=3)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        # Should succeed because counter was reset
        assert result == "Finally done"

    def test_action_gated_without_require_complete_tool(self):
        """Test action-gated mode without require_complete_tool still enforces tool usage."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            # Invalid move
            ChatResponse(content="Thinking", tool_calls=[], finish_reason="stop", raw_response={}),
            # Valid tool call then complete
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=False)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert result == "Done"
        # Check that corrective message was injected for the invalid move
        user_messages = [m for m in loop.state.messages if m.role == "user"]
        assert any("Invalid move" in m.content for m in user_messages)

    def test_action_gated_max_steps_returns_failure(self):
        """Test that hitting max_steps in action-gated mode returns failure message."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        # Keep making valid tool calls but never call complete
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id=f"call_{i}", name="think", arguments={"thought": f"Thought {i}"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            )
            for i in range(10)
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True, max_steps=3)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert "Failed" in result
        assert "Max steps reached" in result

    def test_standard_mode_prose_completes(self):
        """Test that standard mode (non-action-gated) completes on prose response."""
        harness = create_default_simulator()
        llm = MockLLMClient(responses=[
            ChatResponse(content="All done!", tool_calls=[], finish_reason="stop", raw_response={}),
        ])
        config = AgentConfig(action_gated=False)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert result == "All done!"
        assert loop.state.is_complete is True

    def test_complete_tool_with_status(self):
        """Test that complete tool accepts status parameter."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="complete",
                        arguments={"final_answer": "Partial result", "status": "partial"},
                    ),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(action_gated=True, require_complete_tool=True)
        loop = AgentLoop(harness, llm, config)

        result = loop.run("Do something")

        assert result == "Partial result"
        assert harness._completion_status == "partial"


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


class TestToolFiltering:
    """Tests for ACI-style tool filtering (use_active_toolset config)."""

    def test_use_active_toolset_filters_tools(self):
        """Test that use_active_toolset=True sends only active tools to LLM."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        # Configure SWE-bench toolset (Read, Edit, bash, grep, glob, complete + research/navigation tools)
        enabled_tools = harness.set_swe_bench_toolset()
        assert set(enabled_tools) == {
            "Read", "Edit", "bash", "grep", "glob", "complete",
            "web_search", "web_get_contents", "lsp_tool",
        }

        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(
            action_gated=True,
            require_complete_tool=True,
            use_active_toolset=True,  # This is the key config
        )
        loop = AgentLoop(harness, llm, config)

        loop.run("Test task")

        # Check what tools were sent to the LLM
        assert len(llm._calls) == 1
        tools_sent = llm._calls[0]["tools"]
        tool_names = {t["function"]["name"] for t in tools_sent}

        # Should only have SWE-bench tools (including research/navigation tools)
        assert tool_names == {
            "Read", "Edit", "bash", "grep", "glob", "complete",
            "web_search", "web_get_contents", "lsp_tool",
        }

        # Should NOT have these tools (non-SWE-bench tools)
        forbidden_tools = {"message_user", "list_repos", "request_tools", "think", "TodoWrite"}
        assert tool_names.isdisjoint(forbidden_tools), f"Found forbidden tools: {tool_names & forbidden_tools}"

    def test_use_active_toolset_false_sends_all_tools(self):
        """Test that use_active_toolset=False sends all tools to LLM."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        # Even if we configure SWE-bench toolset, without use_active_toolset=True
        # the agent loop should still send all tools
        harness.set_swe_bench_toolset()

        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(
            action_gated=True,
            require_complete_tool=True,
            use_active_toolset=False,  # Default - sends all tools
        )
        loop = AgentLoop(harness, llm, config)

        loop.run("Test task")

        # Check what tools were sent to the LLM
        assert len(llm._calls) == 1
        tools_sent = llm._calls[0]["tools"]
        tool_names = {t["function"]["name"] for t in tools_sent}

        # Should have more than just SWE-bench tools
        assert len(tool_names) > 6, f"Expected more than 6 tools, got {len(tool_names)}: {tool_names}"
        # Should include some of the "forbidden" tools
        assert "message_user" in tool_names or "think" in tool_names or "TodoWrite" in tool_names

    def test_swe_bench_toolset_configuration(self):
        """Test that set_swe_bench_toolset correctly configures the harness."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()

        # Before configuration, get_active_tool_schemas should return all tools
        all_schemas = harness.get_tool_schemas()
        all_tool_names = {t["function"]["name"] for t in all_schemas}
        assert len(all_tool_names) > 6

        # Configure SWE-bench toolset (includes research/navigation tools)
        enabled = harness.set_swe_bench_toolset()
        expected_tools = {
            "Read", "Edit", "bash", "grep", "glob", "complete",
            "web_search", "web_get_contents", "lsp_tool",
        }
        assert set(enabled) == expected_tools

        # After configuration, get_active_tool_schemas should return only SWE-bench tools
        active_schemas = harness.get_active_tool_schemas()
        active_tool_names = {t["function"]["name"] for t in active_schemas}
        assert active_tool_names == expected_tools


class TestSWEWorkflowIntegration:
    """Tests for Gap 3: SWE Workflow Closure integration."""

    def test_swe_workflow_config_defaults(self):
        """Test that SWE workflow config options have correct defaults."""
        config = AgentConfig()
        assert config.use_swe_workflow is False
        assert config.swe_task_description == ""
        assert config.swe_repo_path == ""
        assert config.swe_max_iterations == 5

    def test_swe_workflow_initialization(self):
        """Test that SWE workflow is initialized when enabled."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Fix the bug in calculator.py",
            swe_repo_path="/tmp/test-repo",
            action_gated=True,
            require_complete_tool=True,
        )
        loop = AgentLoop(harness, llm, config)

        assert loop._swe_workflow is not None
        assert loop._failure_recovery is not None
        assert loop._ci_integration is not None
        assert loop._swe_workflow.task_description == "Fix the bug in calculator.py"

    def test_swe_workflow_stage_prompt_injected(self):
        """Test that stage prompts are injected into messages."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Fix the bug",
            action_gated=True,
            require_complete_tool=True,
        )
        loop = AgentLoop(harness, llm, config)

        loop.run("Start task")

        user_messages = [m for m in loop.state.messages if m.role == "user"]
        stage_messages = [m for m in user_messages if "[SWE_WORKFLOW_STAGE:" in m.content]
        assert len(stage_messages) > 0
        assert "UNDERSTAND" in stage_messages[0].content

    def test_swe_workflow_not_initialized_when_disabled(self):
        """Test that SWE workflow is not initialized when disabled."""
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient()
        config = AgentConfig(use_swe_workflow=False)
        loop = AgentLoop(harness, llm, config)

        assert loop._swe_workflow is None
        assert loop._failure_recovery is None
        assert loop._ci_integration is None

    def test_swe_workflow_advances_on_success(self):
        """Test that workflow advances stages on successful tool execution."""
        from compymac.local_harness import LocalHarness
        from compymac.workflows.swe_loop import WorkflowStage

        harness = LocalHarness()
        llm = MockLLMClient(responses=[
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="think", arguments={"thought": "Understanding the task"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
            ChatResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_2", name="complete", arguments={"final_answer": "Done"}),
                ],
                finish_reason="tool_calls",
                raw_response={},
            ),
        ])
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Test task",
            action_gated=True,
            require_complete_tool=True,
        )
        loop = AgentLoop(harness, llm, config)

        initial_stage = loop._swe_workflow.current_stage
        assert initial_stage == WorkflowStage.UNDERSTAND

        loop.run("Start task")

        assert len(loop._swe_workflow.stage_results) > 0

    def test_detect_pr_url_from_results(self):
        """Test Phase 3: PR URL detection from tool results."""
        from compymac.harness import ToolResult
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient()
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Test task",
        )
        loop = AgentLoop(harness, llm, config)

        tool_results = [
            ToolResult(
                tool_call_id="call_1",
                success=True,
                content="Created PR: https://github.com/owner/repo/pull/123",
            ),
        ]

        pr_url = loop._detect_pr_url_from_results(tool_results)
        assert pr_url == "https://github.com/owner/repo/pull/123"
        assert loop._swe_workflow.pr_info["url"] == pr_url
        assert loop._swe_workflow.pr_info["number"] == 123

    def test_detect_pr_url_no_match(self):
        """Test Phase 3: No PR URL when not present in results."""
        from compymac.harness import ToolResult
        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient()
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Test task",
        )
        loop = AgentLoop(harness, llm, config)

        tool_results = [
            ToolResult(
                tool_call_id="call_1",
                success=True,
                content="Some other output without PR URL",
            ),
        ]

        pr_url = loop._detect_pr_url_from_results(tool_results)
        assert pr_url is None

    def test_handle_validation_stage(self):
        """Test Phase 4: Validation stage runs tests and lint."""
        from unittest.mock import patch

        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient()
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Test task",
            swe_repo_path="/tmp/test-repo",
        )
        loop = AgentLoop(harness, llm, config)

        with patch.object(loop._swe_workflow, 'run_tests', return_value=(True, "All tests passed", [])):
            with patch.object(loop._swe_workflow, 'run_lint', return_value=(True, "No lint errors", [])):
                loop._handle_validation_stage()

        assert loop._swe_workflow.validation_results["tests"]["passed"] is True
        assert loop._swe_workflow.validation_results["lint"]["passed"] is True

        validation_messages = [m for m in loop.state.messages if "[SWE_WORKFLOW_VALIDATION]" in m.content]
        assert len(validation_messages) == 1
        assert "Tests: PASSED" in validation_messages[0].content
        assert "Lint: PASSED" in validation_messages[0].content

    def test_handle_validation_stage_with_failures(self):
        """Test Phase 4: Validation stage reports failures."""
        from unittest.mock import patch

        from compymac.local_harness import LocalHarness

        harness = LocalHarness()
        llm = MockLLMClient()
        config = AgentConfig(
            use_swe_workflow=True,
            swe_task_description="Test task",
            swe_repo_path="/tmp/test-repo",
        )
        loop = AgentLoop(harness, llm, config)

        with patch.object(loop._swe_workflow, 'run_tests', return_value=(False, "Test failed", ["AssertionError"])):
            with patch.object(loop._swe_workflow, 'run_lint', return_value=(False, "Lint error", ["E501 line too long"])):
                loop._handle_validation_stage()

        assert loop._swe_workflow.validation_results["tests"]["passed"] is False
        assert loop._swe_workflow.validation_results["lint"]["passed"] is False

        validation_messages = [m for m in loop.state.messages if "[SWE_WORKFLOW_VALIDATION]" in m.content]
        assert len(validation_messages) == 1
        assert "Tests: FAILED" in validation_messages[0].content
        assert "Lint: FAILED" in validation_messages[0].content
