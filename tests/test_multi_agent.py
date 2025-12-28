"""Tests for the multi-agent architecture."""

from compymac.multi_agent import (
    AgentRole,
    BaseAgent,
    ErrorType,
    ExecutorAgent,
    ManagerAgent,
    ManagerState,
    PlannerAgent,
    PlanStep,
    PlanValidationResult,
    PlanValidator,
    ReflectionAction,
    ReflectionResult,
    ReflectorAgent,
    StepResult,
    Workspace,
    calculate_backoff_ms,
    classify_error,
)


class TestPlanStep:
    """Tests for PlanStep dataclass."""

    def test_to_dict(self):
        step = PlanStep(
            index=0,
            description="Test step",
            expected_outcome="Success",
            tools_hint=["tool1"],
            dependencies=[],
        )
        result = step.to_dict()
        assert result["index"] == 0
        assert result["description"] == "Test step"
        assert result["expected_outcome"] == "Success"
        assert result["tools_hint"] == ["tool1"]
        assert result["dependencies"] == []

    def test_from_dict(self):
        data = {
            "index": 1,
            "description": "Another step",
            "expected_outcome": "Done",
            "tools_hint": ["tool2"],
            "dependencies": [0],
        }
        step = PlanStep.from_dict(data)
        assert step.index == 1
        assert step.description == "Another step"
        assert step.expected_outcome == "Done"
        assert step.tools_hint == ["tool2"]
        assert step.dependencies == [0]

    def test_from_dict_minimal(self):
        data = {"index": 0, "description": "Minimal step"}
        step = PlanStep.from_dict(data)
        assert step.index == 0
        assert step.description == "Minimal step"
        assert step.expected_outcome == ""
        assert step.tools_hint == []
        assert step.dependencies == []


class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_to_dict(self):
        result = StepResult(
            step_index=0,
            success=True,
            summary="Completed successfully",
            tool_calls_made=3,
            artifacts={"file": "test.txt"},
            errors=[],
        )
        data = result.to_dict()
        assert data["step_index"] == 0
        assert data["success"] is True
        assert data["summary"] == "Completed successfully"
        assert data["tool_calls_made"] == 3
        assert data["artifacts"] == {"file": "test.txt"}
        assert data["errors"] == []

    def test_defaults(self):
        result = StepResult(step_index=0, success=False, summary="Failed")
        assert result.tool_calls_made == 0
        assert result.artifacts == {}
        assert result.errors == []


class TestReflectionResult:
    """Tests for ReflectionResult dataclass."""

    def test_to_dict(self):
        result = ReflectionResult(
            action=ReflectionAction.CONTINUE,
            reasoning="Step succeeded",
            suggested_changes="",
            confidence=0.9,
        )
        data = result.to_dict()
        assert data["action"] == "continue"
        assert data["reasoning"] == "Step succeeded"
        assert data["suggested_changes"] == ""
        assert data["confidence"] == 0.9


class TestWorkspace:
    """Tests for Workspace dataclass."""

    def test_initial_state(self):
        ws = Workspace()
        assert ws.goal == ""
        assert ws.constraints == []
        assert ws.plan == []
        assert ws.current_step_index == 0
        assert ws.step_results == []
        assert ws.artifacts == {}
        assert ws.is_complete is False

    def test_get_current_step_empty(self):
        ws = Workspace()
        assert ws.get_current_step() is None

    def test_get_current_step(self):
        ws = Workspace()
        step = PlanStep(index=0, description="Step 1", expected_outcome="Done")
        ws.plan = [step]
        assert ws.get_current_step() == step

    def test_get_current_step_out_of_bounds(self):
        ws = Workspace()
        ws.plan = [PlanStep(index=0, description="Step 1", expected_outcome="Done")]
        ws.current_step_index = 5
        assert ws.get_current_step() is None

    def test_get_step_result(self):
        ws = Workspace()
        result = StepResult(step_index=0, success=True, summary="Done")
        ws.step_results = [result]
        assert ws.get_step_result(0) == result
        assert ws.get_step_result(1) is None

    def test_attempt_counting(self):
        ws = Workspace()
        assert ws.get_attempt_count(0) == 0
        assert ws.increment_attempt(0) == 1
        assert ws.get_attempt_count(0) == 1
        assert ws.increment_attempt(0) == 2
        assert ws.get_attempt_count(0) == 2

    def test_to_summary(self):
        ws = Workspace()
        ws.goal = "Test goal"
        ws.plan = [PlanStep(index=0, description="Step", expected_outcome="Done")]
        ws.constraints = ["constraint1"]
        summary = ws.to_summary()
        assert "Test goal" in summary
        assert "Plan steps: 1" in summary
        assert "constraint1" in summary


class TestBaseAgent:
    """Tests for BaseAgent class."""

    def test_init_with_system_prompt(self):
        class MockLLMClient:
            pass

        agent = BaseAgent(
            role=AgentRole.PLANNER,
            llm_client=MockLLMClient(),
            system_prompt="You are a test agent",
        )
        assert agent.role == AgentRole.PLANNER
        assert len(agent.messages) == 1
        assert agent.messages[0].role == "system"
        assert agent.messages[0].content == "You are a test agent"

    def test_init_without_system_prompt(self):
        class MockLLMClient:
            pass

        agent = BaseAgent(
            role=AgentRole.EXECUTOR,
            llm_client=MockLLMClient(),
        )
        assert agent.role == AgentRole.EXECUTOR
        assert len(agent.messages) == 0

    def test_reset(self):
        class MockLLMClient:
            pass

        agent = BaseAgent(
            role=AgentRole.PLANNER,
            llm_client=MockLLMClient(),
            system_prompt="System prompt",
        )
        # Add some messages
        from compymac.types import Message
        agent.messages.append(Message(role="user", content="Hello"))
        agent.messages.append(Message(role="assistant", content="Hi"))
        assert len(agent.messages) == 3

        # Reset
        agent.reset()
        assert len(agent.messages) == 1
        assert agent.messages[0].role == "system"


class TestReflectionAction:
    """Tests for ReflectionAction enum."""

    def test_all_actions_exist(self):
        assert ReflectionAction.CONTINUE.value == "continue"
        assert ReflectionAction.RETRY_SAME.value == "retry_same"
        assert ReflectionAction.RETRY_WITH_CHANGES.value == "retry_with_changes"
        assert ReflectionAction.GATHER_INFO.value == "gather_info"
        assert ReflectionAction.REPLAN.value == "replan"
        assert ReflectionAction.STOP.value == "stop"


class TestManagerState:
    """Tests for ManagerState enum."""

    def test_all_states_exist(self):
        assert ManagerState.INITIAL.value == "initial"
        assert ManagerState.PLANNING.value == "planning"
        assert ManagerState.EXECUTING.value == "executing"
        assert ManagerState.REFLECTING.value == "reflecting"
        assert ManagerState.REPLANNING.value == "replanning"
        assert ManagerState.COMPLETED.value == "completed"
        assert ManagerState.FAILED.value == "failed"


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_all_roles_exist(self):
        assert AgentRole.MANAGER.value == "manager"
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.EXECUTOR.value == "executor"
        assert AgentRole.REFLECTOR.value == "reflector"


class MockLLMResponse:
    """Mock LLM response for testing."""

    def __init__(self, content: str):
        self.content = content
        self.tool_calls = []


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or []
        self.call_count = 0

    def chat(self, messages, tools=None, tool_choice=None):
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            response = "Default response"
        self.call_count += 1
        return MockLLMResponse(response)


class TestPlannerAgent:
    """Tests for PlannerAgent."""

    def test_create_plan_parses_json(self):
        json_response = '''Here's the plan:
{
  "steps": [
    {
      "index": 0,
      "description": "First step",
      "expected_outcome": "Done",
      "tools_hint": ["shell"],
      "dependencies": []
    },
    {
      "index": 1,
      "description": "Second step",
      "expected_outcome": "Complete",
      "tools_hint": [],
      "dependencies": [0]
    }
  ]
}'''
        client = MockLLMClient([json_response])
        planner = PlannerAgent(client, enable_validation=False)
        ws = Workspace(goal="Test goal")

        plan, validation_result = planner.create_plan(ws)

        assert len(plan) == 2
        assert plan[0].description == "First step"
        assert plan[1].description == "Second step"
        assert plan[1].dependencies == [0]
        assert validation_result is None  # Validation disabled

    def test_create_plan_fallback_on_invalid_json(self):
        client = MockLLMClient(["This is not JSON, just a description"])
        planner = PlannerAgent(client, enable_validation=False)
        ws = Workspace(goal="Test goal")

        plan, validation_result = planner.create_plan(ws)

        # Should create a single fallback step
        assert len(plan) == 1
        assert "This is not JSON" in plan[0].description

    def test_revise_plan(self):
        json_response = '''Revised plan:
{
  "steps": [
    {
      "index": 0,
      "description": "New approach",
      "expected_outcome": "Success"
    }
  ]
}'''
        client = MockLLMClient([json_response])
        planner = PlannerAgent(client, enable_validation=False)
        ws = Workspace(goal="Test goal")
        ws.plan = [PlanStep(index=0, description="Old step", expected_outcome="")]
        ws.current_step_index = 0

        new_steps, validation_result = planner.revise_plan(ws, "Previous approach failed")

        assert len(new_steps) == 1
        assert new_steps[0].description == "New approach"
        assert validation_result is None  # Validation disabled


class TestReflectorAgent:
    """Tests for ReflectorAgent."""

    def test_reflect_parses_json(self):
        json_response = '''Analysis:
{
  "action": "CONTINUE",
  "reasoning": "Step completed successfully",
  "suggested_changes": "",
  "confidence": 0.95
}'''
        client = MockLLMClient([json_response])
        reflector = ReflectorAgent(client)
        ws = Workspace(goal="Test goal")
        ws.plan = [PlanStep(index=0, description="Step", expected_outcome="Done")]
        ws.attempt_counts[0] = 1
        step = ws.plan[0]
        result = StepResult(step_index=0, success=True, summary="Done")

        reflection = reflector.reflect(ws, step, result)

        assert reflection.action == ReflectionAction.CONTINUE
        assert reflection.confidence == 0.95

    def test_reflect_default_on_success(self):
        client = MockLLMClient(["Invalid response"])
        reflector = ReflectorAgent(client)
        ws = Workspace(goal="Test goal")
        ws.plan = [PlanStep(index=0, description="Step", expected_outcome="Done")]
        ws.attempt_counts[0] = 1
        step = ws.plan[0]
        result = StepResult(step_index=0, success=True, summary="Done")

        reflection = reflector.reflect(ws, step, result)

        # Should default to CONTINUE on success
        assert reflection.action == ReflectionAction.CONTINUE

    def test_reflect_default_on_failure(self):
        client = MockLLMClient(["Invalid response"])
        reflector = ReflectorAgent(client)
        ws = Workspace(goal="Test goal")
        ws.plan = [PlanStep(index=0, description="Step", expected_outcome="Done")]
        ws.attempt_counts[0] = 1
        step = ws.plan[0]
        result = StepResult(step_index=0, success=False, summary="Failed")

        reflection = reflector.reflect(ws, step, result)

        # Should default to RETRY_SAME on failure
        assert reflection.action == ReflectionAction.RETRY_SAME


class MockHarness:
    """Mock harness for testing."""

    def __init__(self):
        from compymac.harness import EventLog
        self._event_log = EventLog()
        self._schemas = []

    def get_event_log(self):
        return self._event_log

    def get_tool_schemas(self):
        return self._schemas

    def execute_tool(self, tool_call):
        from compymac.types import ToolResult
        return ToolResult(
            tool_call_id=tool_call.id,
            content="Mock result",
            success=True,
        )


class TestExecutorAgent:
    """Tests for ExecutorAgent."""

    def test_init(self):
        harness = MockHarness()
        client = MockLLMClient()
        executor = ExecutorAgent(harness, client)

        assert executor.harness == harness
        assert executor.llm_client == client
        assert executor.config.max_steps == 20

    def test_execute_step_success(self):
        harness = MockHarness()
        client = MockLLMClient(["Task completed successfully"])
        executor = ExecutorAgent(harness, client)

        step = PlanStep(index=0, description="Do something", expected_outcome="Done")
        ws = Workspace(goal="Test goal")

        result = executor.execute_step(step, ws)

        assert result.step_index == 0
        assert result.success is True
        assert "completed" in result.summary.lower()

    def test_execute_step_failure_keywords(self):
        harness = MockHarness()
        client = MockLLMClient(["Error: something went wrong"])
        executor = ExecutorAgent(harness, client)

        step = PlanStep(index=0, description="Do something", expected_outcome="Done")
        ws = Workspace(goal="Test goal")

        result = executor.execute_step(step, ws)

        assert result.step_index == 0
        assert result.success is False


class TestManagerAgent:
    """Tests for ManagerAgent FSM orchestration."""

    def test_init(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)

        assert manager.state == ManagerState.INITIAL
        assert manager.workspace.goal == ""
        assert manager.planner is not None
        assert manager.executor is not None
        assert manager.reflector is not None

    def test_transition_to_planning(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)

        manager._transition_to_planning()

        assert manager.state == ManagerState.PLANNING

    def test_do_planning_success(self):
        harness = MockHarness()
        plan_response = '''{"steps": [{"index": 0, "description": "Step 1", "expected_outcome": "Done"}]}'''
        client = MockLLMClient([plan_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.state = ManagerState.PLANNING

        manager._do_planning()

        assert manager.state == ManagerState.EXECUTING
        assert len(manager.workspace.plan) == 1

    def test_do_planning_failure(self):
        harness = MockHarness()
        # Empty steps will cause planning to fail
        client = MockLLMClient(['{"steps": []}'])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.state = ManagerState.PLANNING

        manager._do_planning()

        assert manager.state == ManagerState.FAILED

    def test_do_executing_all_steps_complete(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.workspace.plan = []  # No steps
        manager.state = ManagerState.EXECUTING

        manager._do_executing()

        assert manager.state == ManagerState.COMPLETED
        assert manager.workspace.is_complete is True

    def test_do_reflecting_continue(self):
        harness = MockHarness()
        reflect_response = '''{"action": "CONTINUE", "reasoning": "Done", "confidence": 0.9}'''
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step 1", expected_outcome="Done"),
            PlanStep(index=1, description="Step 2", expected_outcome="Done"),
        ]
        manager.workspace.step_results = [
            StepResult(step_index=0, success=True, summary="Done")
        ]
        manager.workspace.current_step_index = 0
        # Set up parallel groups (each step in its own group for sequential execution)
        manager._parallel_groups = [[0], [1]]
        manager._current_group_index = 0
        manager._last_group_results = [StepResult(step_index=0, success=True, summary="Done")]
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        assert manager.state == ManagerState.EXECUTING
        # With parallel groups, we now track group index instead of step index
        assert manager._current_group_index == 1

    def test_do_reflecting_replan(self):
        harness = MockHarness()
        reflect_response = '''{"action": "REPLAN", "reasoning": "Need new approach", "confidence": 0.8}'''
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step 1", expected_outcome="Done")
        ]
        manager.workspace.step_results = [
            StepResult(step_index=0, success=False, summary="Failed")
        ]
        manager.workspace.current_step_index = 0
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        assert manager.state == ManagerState.REPLANNING

    def test_do_reflecting_stop(self):
        harness = MockHarness()
        reflect_response = '''{"action": "STOP", "reasoning": "Cannot proceed", "confidence": 0.9}'''
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step 1", expected_outcome="Done")
        ]
        manager.workspace.step_results = [
            StepResult(step_index=0, success=False, summary="Failed")
        ]
        manager.workspace.current_step_index = 0
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        assert manager.state == ManagerState.FAILED

    def test_get_workspace(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test"

        ws = manager.get_workspace()

        assert ws.goal == "Test"

    def test_get_state(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)

        assert manager.get_state() == ManagerState.INITIAL

    def test_generate_final_result(self):
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test goal"
        manager.workspace.step_results = [
            StepResult(step_index=0, success=True, summary="Step 1 done"),
            StepResult(step_index=1, success=True, summary="Step 2 done"),
        ]

        result = manager._generate_final_result()

        assert "Test goal" in result
        assert "2/2" in result
        assert "Step 1 done" in result


class TestManagerAgentIntegration:
    """Integration tests for the full Manager workflow."""

    def test_simple_workflow_completes(self):
        """Test a simple workflow that plans, executes, reflects, and completes."""
        harness = MockHarness()

        # Responses: plan, execute, reflect (continue), execute, reflect (continue)
        responses = [
            # Planner creates 2-step plan
            '''{"steps": [
                {"index": 0, "description": "Step 1", "expected_outcome": "Done"},
                {"index": 1, "description": "Step 2", "expected_outcome": "Complete"}
            ]}''',
            # Executor runs step 1
            "Step 1 completed successfully",
            # Reflector says continue
            '''{"action": "CONTINUE", "reasoning": "Good", "confidence": 0.9}''',
            # Executor runs step 2
            "Step 2 completed successfully",
            # Reflector says continue
            '''{"action": "CONTINUE", "reasoning": "All done", "confidence": 0.95}''',
        ]
        client = MockLLMClient(responses)
        manager = ManagerAgent(harness, client)

        result = manager.run("Complete a simple task")

        assert manager.state == ManagerState.COMPLETED
        assert manager.workspace.is_complete is True
        assert "Complete a simple task" in result

    def test_workflow_with_retry(self):
        """Test workflow that retries a failed step."""
        harness = MockHarness()

        responses = [
            # Planner creates 1-step plan
            '''{"steps": [{"index": 0, "description": "Step 1", "expected_outcome": "Done"}]}''',
            # Executor fails step 1
            "Error: something went wrong",
            # Reflector says retry
            '''{"action": "RETRY_SAME", "reasoning": "Temporary failure", "confidence": 0.7}''',
            # Executor succeeds on retry
            "Step 1 completed successfully",
            # Reflector says continue
            '''{"action": "CONTINUE", "reasoning": "Done", "confidence": 0.9}''',
        ]
        client = MockLLMClient(responses)
        manager = ManagerAgent(harness, client)

        manager.run("Task with retry")

        assert manager.state == ManagerState.COMPLETED
        # Should have 2 attempts for step 0
        assert manager.workspace.get_attempt_count(0) == 2


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_all_error_types_exist(self):
        assert ErrorType.TRANSIENT.value == "transient"
        assert ErrorType.PERMANENT.value == "permanent"
        assert ErrorType.UNKNOWN.value == "unknown"


class TestClassifyError:
    """Tests for the classify_error function."""

    def test_transient_errors(self):
        """Test that transient errors are correctly classified."""
        transient_messages = [
            "Connection timeout after 30 seconds",
            "Network error: connection refused",
            "Rate limit exceeded, please retry",
            "503 Service Unavailable",
            "Server is temporarily unavailable",
        ]
        for msg in transient_messages:
            assert classify_error(msg) == ErrorType.TRANSIENT, f"Expected TRANSIENT for: {msg}"

    def test_permanent_errors(self):
        """Test that permanent errors are correctly classified."""
        permanent_messages = [
            "File not found: /path/to/file.txt",
            "Permission denied: cannot access directory",
            "Invalid syntax in configuration file",
            "Type error: expected string, got int",
            "Missing required dependency: numpy",
        ]
        for msg in permanent_messages:
            assert classify_error(msg) == ErrorType.PERMANENT, f"Expected PERMANENT for: {msg}"

    def test_unknown_errors(self):
        """Test that unclassifiable errors return UNKNOWN."""
        unknown_messages = [
            "Something went wrong",
            "Unexpected result",
            "Operation completed with warnings",
        ]
        for msg in unknown_messages:
            assert classify_error(msg) == ErrorType.UNKNOWN, f"Expected UNKNOWN for: {msg}"


class TestCalculateBackoff:
    """Tests for the calculate_backoff_ms function."""

    def test_first_attempt(self):
        """First attempt should have base delay."""
        assert calculate_backoff_ms(1) == 1000

    def test_exponential_growth(self):
        """Backoff should grow exponentially."""
        assert calculate_backoff_ms(1) == 1000
        assert calculate_backoff_ms(2) == 2000
        assert calculate_backoff_ms(3) == 4000
        assert calculate_backoff_ms(4) == 8000

    def test_max_cap(self):
        """Backoff should be capped at max_ms."""
        assert calculate_backoff_ms(10, max_ms=30000) == 30000
        assert calculate_backoff_ms(100, max_ms=30000) == 30000

    def test_custom_base(self):
        """Custom base delay should work."""
        assert calculate_backoff_ms(1, base_ms=500) == 500
        assert calculate_backoff_ms(2, base_ms=500) == 1000


class TestWorkspaceErrorRecovery:
    """Tests for Workspace error recovery features."""

    def test_record_error(self):
        """Test error recording and classification."""
        workspace = Workspace()
        error_type = workspace.record_error(0, "Connection timeout")
        assert error_type == ErrorType.TRANSIENT
        assert len(workspace.error_history) == 1
        assert workspace.error_history[0] == (0, "Connection timeout", ErrorType.TRANSIENT)

    def test_get_error_pattern(self):
        """Test getting error pattern for a step."""
        workspace = Workspace()
        workspace.record_error(0, "Connection timeout")
        workspace.record_error(0, "Network error")
        workspace.record_error(1, "File not found")

        pattern = workspace.get_error_pattern(0)
        assert len(pattern) == 2
        assert pattern[0] == ErrorType.TRANSIENT
        assert pattern[1] == ErrorType.TRANSIENT

        pattern = workspace.get_error_pattern(1)
        assert len(pattern) == 1
        assert pattern[0] == ErrorType.PERMANENT

    def test_should_retry_no_errors(self):
        """Test should_retry with no errors."""
        workspace = Workspace()
        workspace.increment_attempt(0)
        should_retry, backoff = workspace.should_retry(0)
        assert should_retry is True
        assert backoff == 0

    def test_should_retry_transient_error(self):
        """Test should_retry with transient error."""
        workspace = Workspace()
        workspace.increment_attempt(0)
        workspace.record_error(0, "Connection timeout")
        should_retry, backoff = workspace.should_retry(0)
        assert should_retry is True
        assert backoff > 0  # Should have backoff for transient errors

    def test_should_retry_permanent_error(self):
        """Test should_retry with permanent error after multiple attempts."""
        workspace = Workspace()
        workspace.increment_attempt(0)
        workspace.increment_attempt(0)
        workspace.record_error(0, "File not found")
        should_retry, backoff = workspace.should_retry(0)
        assert should_retry is False  # Should not retry permanent errors after 2 attempts

    def test_should_retry_max_attempts(self):
        """Test should_retry at max attempts."""
        workspace = Workspace()
        workspace.max_attempts_per_step = 3
        workspace.increment_attempt(0)
        workspace.increment_attempt(0)
        workspace.increment_attempt(0)
        should_retry, backoff = workspace.should_retry(0)
        assert should_retry is False


class TestWorkspaceTiming:
    """Tests for Workspace timing features."""

    def test_step_timer(self):
        """Test step timing."""
        import time
        workspace = Workspace()
        workspace.start_step_timer()
        time.sleep(0.01)  # 10ms
        elapsed = workspace.stop_step_timer()
        assert elapsed >= 10  # At least 10ms
        assert workspace.total_execution_time_ms >= 10

    def test_stop_timer_without_start(self):
        """Test stopping timer without starting."""
        workspace = Workspace()
        elapsed = workspace.stop_step_timer()
        assert elapsed == 0


class TestStepResultWithErrorType:
    """Tests for StepResult with error type."""

    def test_to_dict_with_error_type(self):
        """Test StepResult.to_dict includes error_type."""
        result = StepResult(
            step_index=0,
            success=False,
            summary="Failed",
            errors=["Connection timeout"],
            error_type=ErrorType.TRANSIENT,
            execution_time_ms=1500,
        )
        d = result.to_dict()
        assert d["error_type"] == "transient"
        assert d["execution_time_ms"] == 1500

    def test_to_dict_without_error_type(self):
        """Test StepResult.to_dict with no error_type."""
        result = StepResult(
            step_index=0,
            success=True,
            summary="Success",
        )
        d = result.to_dict()
        assert d["error_type"] is None
        assert d["execution_time_ms"] == 0


class TestManagerAgentWithMemory:
    """Tests for ManagerAgent with memory enabled."""

    def test_init_with_memory_disabled(self):
        """Test ManagerAgent initialization with memory disabled."""
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client, enable_memory=False)
        assert manager.memory_manager is None
        assert manager.enable_memory is False

    def test_init_with_memory_enabled(self):
        """Test ManagerAgent initialization with memory enabled."""
        harness = MockHarness()
        client = MockLLMClient()
        manager = ManagerAgent(harness, client, enable_memory=True)
        assert manager.memory_manager is not None
        assert manager.enable_memory is True


class TestPlanStepEnhanced:
    """Tests for enhanced PlanStep with priority and parallel execution hints."""

    def test_to_dict_with_new_fields(self):
        """Test PlanStep.to_dict includes new fields."""
        step = PlanStep(
            index=0,
            description="Test step",
            expected_outcome="Success",
            tools_hint=["tool1"],
            dependencies=[],
            priority=5,
            can_parallelize=True,
            estimated_complexity="high",
        )
        result = step.to_dict()
        assert result["priority"] == 5
        assert result["can_parallelize"] is True
        assert result["estimated_complexity"] == "high"

    def test_from_dict_with_new_fields(self):
        """Test PlanStep.from_dict parses new fields."""
        data = {
            "index": 1,
            "description": "Another step",
            "expected_outcome": "Done",
            "tools_hint": ["tool2"],
            "dependencies": [0],
            "priority": 3,
            "can_parallelize": True,
            "estimated_complexity": "low",
        }
        step = PlanStep.from_dict(data)
        assert step.priority == 3
        assert step.can_parallelize is True
        assert step.estimated_complexity == "low"

    def test_from_dict_defaults_new_fields(self):
        """Test PlanStep.from_dict uses defaults for missing new fields."""
        data = {
            "index": 0,
            "description": "Minimal step",
        }
        step = PlanStep.from_dict(data)
        assert step.priority == 0
        assert step.can_parallelize is False
        assert step.estimated_complexity == "medium"


class TestPlanValidationResult:
    """Tests for PlanValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = PlanValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            parallel_groups=[[0], [1, 2], [3]],
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.parallel_groups) == 3

    def test_invalid_result(self):
        """Test creating an invalid result."""
        result = PlanValidationResult(
            is_valid=False,
            errors=["Circular dependency detected"],
            warnings=["Constraint may not be addressed"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


class TestPlanValidatorDependencies:
    """Tests for PlanValidator dependency validation."""

    def test_valid_dependencies(self):
        """Test validation of valid dependencies."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[]),
            PlanStep(index=1, description="Step 1", expected_outcome="Done", dependencies=[0]),
            PlanStep(index=2, description="Step 2", expected_outcome="Done", dependencies=[0, 1]),
        ]
        is_valid, errors = PlanValidator.validate_dependencies(steps)
        assert is_valid is True
        assert len(errors) == 0

    def test_invalid_dependency_nonexistent_step(self):
        """Test detection of dependency on non-existent step."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[]),
            PlanStep(index=1, description="Step 1", expected_outcome="Done", dependencies=[5]),  # Step 5 doesn't exist
        ]
        is_valid, errors = PlanValidator.validate_dependencies(steps)
        assert is_valid is False
        assert any("non-existent step 5" in e for e in errors)

    def test_invalid_forward_dependency(self):
        """Test detection of forward dependency."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[1]),  # Forward dependency
            PlanStep(index=1, description="Step 1", expected_outcome="Done", dependencies=[]),
        ]
        is_valid, errors = PlanValidator.validate_dependencies(steps)
        assert is_valid is False
        assert any("forward dependency" in e for e in errors)

    def test_no_steps(self):
        """Test validation with empty step list."""
        is_valid, errors = PlanValidator.validate_dependencies([])
        assert is_valid is True
        assert len(errors) == 0


class TestPlanValidatorParallelGroups:
    """Tests for PlanValidator parallel group detection."""

    def test_all_sequential(self):
        """Test with all sequential steps (no parallelization)."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[], can_parallelize=False),
            PlanStep(index=1, description="Step 1", expected_outcome="Done", dependencies=[0], can_parallelize=False),
            PlanStep(index=2, description="Step 2", expected_outcome="Done", dependencies=[1], can_parallelize=False),
        ]
        groups = PlanValidator.find_parallel_groups(steps)
        # Each step should be in its own group
        assert len(groups) == 3
        assert all(len(g) == 1 for g in groups)

    def test_parallel_independent_steps(self):
        """Test detection of parallel independent steps."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[], can_parallelize=True),
            PlanStep(index=1, description="Step 1", expected_outcome="Done", dependencies=[], can_parallelize=True),
            PlanStep(index=2, description="Step 2", expected_outcome="Done", dependencies=[0, 1], can_parallelize=False),
        ]
        groups = PlanValidator.find_parallel_groups(steps)
        # Steps 0 and 1 should be in a parallel group
        assert any(len(g) == 2 and 0 in g and 1 in g for g in groups)

    def test_empty_steps(self):
        """Test with empty step list."""
        groups = PlanValidator.find_parallel_groups([])
        assert groups == []

    def test_single_step(self):
        """Test with single step."""
        steps = [
            PlanStep(index=0, description="Step 0", expected_outcome="Done", dependencies=[], can_parallelize=True),
        ]
        groups = PlanValidator.find_parallel_groups(steps)
        assert len(groups) == 1
        assert groups[0] == [0]


class TestPlanValidatorConstraints:
    """Tests for PlanValidator constraint checking."""

    def test_constraint_addressed(self):
        """Test that addressed constraints don't generate warnings."""
        steps = [
            PlanStep(index=0, description="Create backup of database", expected_outcome="Backup created"),
            PlanStep(index=1, description="Run migration", expected_outcome="Migration complete"),
        ]
        constraints = ["Must create backup before migration"]
        all_addressed, warnings = PlanValidator.check_constraints(steps, constraints)
        assert all_addressed is True
        assert len(warnings) == 0

    def test_constraint_not_addressed(self):
        """Test that unaddressed constraints generate warnings."""
        steps = [
            PlanStep(index=0, description="Run migration", expected_outcome="Migration complete"),
        ]
        constraints = ["Must notify users before deployment"]
        all_addressed, warnings = PlanValidator.check_constraints(steps, constraints)
        assert all_addressed is False
        assert len(warnings) == 1
        assert "notify" in warnings[0].lower() or "users" in warnings[0].lower()

    def test_empty_constraints(self):
        """Test with no constraints."""
        steps = [
            PlanStep(index=0, description="Do something", expected_outcome="Done"),
        ]
        all_addressed, warnings = PlanValidator.check_constraints(steps, [])
        assert all_addressed is True
        assert len(warnings) == 0


class TestPlanValidatorFullValidation:
    """Tests for PlanValidator.validate_plan full validation."""

    def test_valid_plan(self):
        """Test validation of a valid plan."""
        steps = [
            PlanStep(index=0, description="Read config file", expected_outcome="Config loaded", dependencies=[]),
            PlanStep(index=1, description="Parse config", expected_outcome="Config parsed", dependencies=[0]),
        ]
        result = PlanValidator.validate_plan(steps)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_empty_plan(self):
        """Test validation of empty plan."""
        result = PlanValidator.validate_plan([])
        assert result.is_valid is False
        assert any("no steps" in e.lower() for e in result.errors)

    def test_duplicate_indices(self):
        """Test detection of duplicate step indices."""
        steps = [
            PlanStep(index=0, description="Step A", expected_outcome="Done"),
            PlanStep(index=0, description="Step B", expected_outcome="Done"),  # Duplicate index
        ]
        result = PlanValidator.validate_plan(steps)
        assert result.is_valid is False
        assert any("duplicate" in e.lower() for e in result.errors)

    def test_validation_with_constraints(self):
        """Test validation includes constraint checking."""
        steps = [
            PlanStep(index=0, description="Deploy application", expected_outcome="Deployed"),
        ]
        constraints = ["Must run tests before deployment"]
        result = PlanValidator.validate_plan(steps, constraints)
        # Plan is structurally valid but has constraint warnings
        assert result.is_valid is True  # No structural errors
        assert len(result.warnings) > 0  # But has constraint warnings


class TestPlannerAgentWithValidation:
    """Tests for PlannerAgent with validation enabled."""

    def test_create_plan_returns_validation_result(self):
        """Test that create_plan returns validation result when enabled."""
        json_response = """{
            "steps": [
                {"index": 0, "description": "Step 1", "expected_outcome": "Done", "dependencies": []},
                {"index": 1, "description": "Step 2", "expected_outcome": "Done", "dependencies": [0]}
            ]
        }"""
        client = MockLLMClient([json_response])
        planner = PlannerAgent(client, enable_validation=True)

        workspace = Workspace(goal="Test goal")
        steps, validation_result = planner.create_plan(workspace)

        assert len(steps) == 2
        assert validation_result is not None
        assert validation_result.is_valid is True

    def test_create_plan_without_validation(self):
        """Test that create_plan returns None validation result when disabled."""
        json_response = """{
            "steps": [
                {"index": 0, "description": "Step 1", "expected_outcome": "Done"}
            ]
        }"""
        client = MockLLMClient([json_response])
        planner = PlannerAgent(client, enable_validation=False)

        workspace = Workspace(goal="Test goal")
        steps, validation_result = planner.create_plan(workspace)

        assert len(steps) == 1
        assert validation_result is None

    def test_revise_plan_returns_validation_result(self):
        """Test that revise_plan returns validation result."""
        json_response = """{
            "steps": [
                {"index": 0, "description": "Revised step", "expected_outcome": "Done"}
            ]
        }"""
        client = MockLLMClient([json_response])
        planner = PlannerAgent(client, enable_validation=True)

        workspace = Workspace(goal="Test goal")
        workspace.plan = [PlanStep(index=0, description="Original", expected_outcome="Done")]
        workspace.current_step_index = 0

        steps, validation_result = planner.revise_plan(workspace, "Need revision")

        assert len(steps) == 1
        assert validation_result is not None


class TestParallelPlanStepExecution:
    """Tests for Phase 2: Parallel plan step execution."""

    def test_manager_stores_parallel_groups(self):
        """Test that manager stores parallel groups from validation result."""
        harness = MockHarness()
        # Plan with parallel groups: steps 0,1 can run in parallel, step 2 depends on both
        plan_response = """{
            "steps": [
                {"index": 0, "description": "Step A", "expected_outcome": "Done", "dependencies": [], "can_parallelize": true},
                {"index": 1, "description": "Step B", "expected_outcome": "Done", "dependencies": [], "can_parallelize": true},
                {"index": 2, "description": "Step C", "expected_outcome": "Done", "dependencies": [0, 1]}
            ]
        }"""
        client = MockLLMClient([plan_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test parallel execution"
        manager.state = ManagerState.PLANNING

        manager._do_planning()

        assert manager.state == ManagerState.EXECUTING
        assert len(manager.workspace.plan) == 3
        # Parallel groups should be set
        assert len(manager._parallel_groups) > 0

    def test_manager_parallel_groups_default_sequential(self):
        """Test that manager defaults to sequential groups when no parallel groups."""
        harness = MockHarness()
        # Plan with sequential dependencies
        plan_response = """{
            "steps": [
                {"index": 0, "description": "Step 1", "expected_outcome": "Done", "dependencies": []},
                {"index": 1, "description": "Step 2", "expected_outcome": "Done", "dependencies": [0]},
                {"index": 2, "description": "Step 3", "expected_outcome": "Done", "dependencies": [1]}
            ]
        }"""
        client = MockLLMClient([plan_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test sequential execution"
        manager.state = ManagerState.PLANNING

        manager._do_planning()

        assert manager.state == ManagerState.EXECUTING
        # Each step should be in its own group (sequential)
        assert len(manager._parallel_groups) == 3
        for group in manager._parallel_groups:
            assert len(group) == 1

    def test_manager_executes_parallel_group(self):
        """Test that manager executes steps in a parallel group."""
        harness = MockHarness()
        client = MockLLMClient(["Step A done", "Step B done"])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test parallel group execution"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step A", expected_outcome="Done", dependencies=[], can_parallelize=True),
            PlanStep(index=1, description="Step B", expected_outcome="Done", dependencies=[], can_parallelize=True),
        ]
        # Set up parallel groups: both steps in one group
        manager._parallel_groups = [[0, 1]]
        manager._current_group_index = 0
        manager.state = ManagerState.EXECUTING

        manager._do_executing()

        # Should have executed both steps and moved to reflecting
        assert manager.state == ManagerState.REFLECTING
        assert len(manager.workspace.step_results) == 2
        assert len(manager._last_group_results) == 2

    def test_manager_reflecting_on_parallel_group_all_success(self):
        """Test reflection on parallel group where all steps succeed."""
        harness = MockHarness()
        reflect_response = '{"action": "CONTINUE", "reasoning": "All steps succeeded", "confidence": 0.95}'
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test parallel reflection"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step A", expected_outcome="Done"),
            PlanStep(index=1, description="Step B", expected_outcome="Done"),
            PlanStep(index=2, description="Step C", expected_outcome="Done"),
        ]
        manager._parallel_groups = [[0, 1], [2]]
        manager._current_group_index = 0
        manager._last_group_results = [
            StepResult(step_index=0, success=True, summary="A done"),
            StepResult(step_index=1, success=True, summary="B done"),
        ]
        manager.workspace.step_results = manager._last_group_results.copy()
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        # Should continue to next group
        assert manager.state == ManagerState.EXECUTING
        assert manager._current_group_index == 1
        assert manager._last_group_results == []

    def test_manager_reflecting_on_parallel_group_partial_failure(self):
        """Test reflection on parallel group where some steps fail."""
        harness = MockHarness()
        # Reflector should be asked about the failed step
        reflect_response = '{"action": "RETRY_SAME", "reasoning": "Step B failed, retry", "confidence": 0.7}'
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test parallel reflection with failure"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step A", expected_outcome="Done"),
            PlanStep(index=1, description="Step B", expected_outcome="Done"),
        ]
        manager._parallel_groups = [[0, 1]]
        manager._current_group_index = 0
        manager._last_group_results = [
            StepResult(step_index=0, success=True, summary="A done"),
            StepResult(step_index=1, success=False, summary="B failed", errors=["Error"]),
        ]
        manager.workspace.step_results = manager._last_group_results.copy()
        manager.workspace.attempt_counts[1] = 1
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        # Should retry the group
        assert manager.state == ManagerState.EXECUTING
        assert manager._last_group_results == []

    def test_manager_reflecting_complete_action(self):
        """Test that COMPLETE action works with parallel groups."""
        harness = MockHarness()
        reflect_response = '{"action": "COMPLETE", "reasoning": "Goal achieved", "confidence": 0.99}'
        client = MockLLMClient([reflect_response])
        manager = ManagerAgent(harness, client)
        manager.workspace.goal = "Test completion"
        manager.workspace.plan = [
            PlanStep(index=0, description="Final step", expected_outcome="Done"),
        ]
        manager._parallel_groups = [[0]]
        manager._current_group_index = 0
        manager._last_group_results = [
            StepResult(step_index=0, success=True, summary="Done"),
        ]
        manager.workspace.step_results = manager._last_group_results.copy()
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        assert manager.state == ManagerState.COMPLETED
        assert manager.workspace.is_complete is True

    def test_parallel_step_executor_single_step(self):
        """Test ParallelStepExecutor with a single step (no parallelism)."""
        from compymac.parallel import ParallelStepExecutor

        harness = MockHarness()
        client = MockLLMClient(["Step done"])
        executor = ExecutorAgent(harness, client)
        workspace = Workspace(goal="Test single step")

        parallel_executor = ParallelStepExecutor(executor_agent=executor)
        step = PlanStep(index=0, description="Single step", expected_outcome="Done")

        results = parallel_executor.execute_parallel_group([step], workspace)

        assert len(results) == 1
        assert results[0].step_index == 0

    def test_parallel_step_executor_multiple_steps(self):
        """Test ParallelStepExecutor with multiple steps."""
        from compymac.parallel import ParallelStepExecutor

        harness = MockHarness()
        client = MockLLMClient(["Step A done", "Step B done", "Step C done"])
        executor = ExecutorAgent(harness, client)
        workspace = Workspace(goal="Test multiple steps")

        parallel_executor = ParallelStepExecutor(executor_agent=executor, max_workers=3)
        steps = [
            PlanStep(index=0, description="Step A", expected_outcome="Done"),
            PlanStep(index=1, description="Step B", expected_outcome="Done"),
            PlanStep(index=2, description="Step C", expected_outcome="Done"),
        ]

        results = parallel_executor.execute_parallel_group(steps, workspace)

        assert len(results) == 3
        # Results should be in order by step index
        assert results[0].step_index == 0
        assert results[1].step_index == 1
        assert results[2].step_index == 2

    def test_parallel_step_executor_empty_group(self):
        """Test ParallelStepExecutor with empty step list."""
        from compymac.parallel import ParallelStepExecutor

        harness = MockHarness()
        client = MockLLMClient()
        executor = ExecutorAgent(harness, client)
        workspace = Workspace(goal="Test empty group")

        parallel_executor = ParallelStepExecutor(executor_agent=executor)

        results = parallel_executor.execute_parallel_group([], workspace)

        assert len(results) == 0

    def test_parallel_group_result_all_success(self):
        """Test ParallelGroupResult with all successful steps."""
        from compymac.parallel import ParallelGroupResult

        results = [
            StepResult(step_index=0, success=True, summary="A done"),
            StepResult(step_index=1, success=True, summary="B done"),
            StepResult(step_index=2, success=True, summary="C done"),
        ]
        group_result = ParallelGroupResult(results)

        assert group_result.all_success is True
        assert group_result.any_success is True
        assert group_result.success_count == 3
        assert group_result.failure_count == 0
        assert len(group_result.successful_steps) == 3
        assert len(group_result.failed_steps) == 0

    def test_parallel_group_result_partial_failure(self):
        """Test ParallelGroupResult with some failed steps."""
        from compymac.parallel import ParallelGroupResult

        results = [
            StepResult(step_index=0, success=True, summary="A done"),
            StepResult(step_index=1, success=False, summary="B failed"),
            StepResult(step_index=2, success=True, summary="C done"),
        ]
        group_result = ParallelGroupResult(results)

        assert group_result.all_success is False
        assert group_result.any_success is True
        assert group_result.success_count == 2
        assert group_result.failure_count == 1
        assert len(group_result.successful_steps) == 2
        assert len(group_result.failed_steps) == 1
        assert group_result.failed_steps[0].step_index == 1

    def test_parallel_group_result_all_failure(self):
        """Test ParallelGroupResult with all failed steps."""
        from compymac.parallel import ParallelGroupResult

        results = [
            StepResult(step_index=0, success=False, summary="A failed"),
            StepResult(step_index=1, success=False, summary="B failed"),
        ]
        group_result = ParallelGroupResult(results)

        assert group_result.all_success is False
        assert group_result.any_success is False
        assert group_result.success_count == 0
        assert group_result.failure_count == 2

    def test_parallel_group_result_get_result(self):
        """Test ParallelGroupResult.get_result() method."""
        from compymac.parallel import ParallelGroupResult

        results = [
            StepResult(step_index=0, success=True, summary="A done"),
            StepResult(step_index=2, success=True, summary="C done"),
        ]
        group_result = ParallelGroupResult(results)

        assert group_result.get_result(0) is not None
        assert group_result.get_result(0).summary == "A done"
        assert group_result.get_result(2) is not None
        assert group_result.get_result(2).summary == "C done"
        assert group_result.get_result(1) is None  # Not in results
        assert group_result.get_result(99) is None  # Not in results

    def test_manager_disable_parallel_execution(self):
        """Test that parallel execution can be disabled."""
        harness = MockHarness()
        client = MockLLMClient(["Step done"])
        manager = ManagerAgent(harness, client)
        manager._enable_parallel_execution = False
        manager.workspace.goal = "Test disabled parallel"
        manager.workspace.plan = [
            PlanStep(index=0, description="Step A", expected_outcome="Done"),
            PlanStep(index=1, description="Step B", expected_outcome="Done"),
        ]
        manager._parallel_groups = [[0, 1]]  # Would be parallel
        manager._current_group_index = 0
        manager.state = ManagerState.EXECUTING

        # Should not create parallel executor
        assert manager._parallel_step_executor is None
