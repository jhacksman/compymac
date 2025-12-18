"""Tests for the multi-agent architecture."""

from compymac.multi_agent import (
    AgentRole,
    BaseAgent,
    ExecutorAgent,
    ManagerAgent,
    ManagerState,
    PlannerAgent,
    PlanStep,
    ReflectionAction,
    ReflectionResult,
    ReflectorAgent,
    StepResult,
    Workspace,
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

    def chat(self, messages, tools=None):
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
        planner = PlannerAgent(client)
        ws = Workspace(goal="Test goal")

        plan = planner.create_plan(ws)

        assert len(plan) == 2
        assert plan[0].description == "First step"
        assert plan[1].description == "Second step"
        assert plan[1].dependencies == [0]

    def test_create_plan_fallback_on_invalid_json(self):
        client = MockLLMClient(["This is not JSON, just a description"])
        planner = PlannerAgent(client)
        ws = Workspace(goal="Test goal")

        plan = planner.create_plan(ws)

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
        planner = PlannerAgent(client)
        ws = Workspace(goal="Test goal")
        ws.plan = [PlanStep(index=0, description="Old step", expected_outcome="")]
        ws.current_step_index = 0

        new_steps = planner.revise_plan(ws, "Previous approach failed")

        assert len(new_steps) == 1
        assert new_steps[0].description == "New approach"


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
        manager.state = ManagerState.REFLECTING

        manager._do_reflecting()

        assert manager.state == ManagerState.EXECUTING
        assert manager.workspace.current_step_index == 1

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
