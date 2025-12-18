"""
Multi-Agent Architecture - Manager, Planner, Executor, Reflector pattern.

This module implements a hierarchical multi-agent system where:
- Manager: FSM orchestrator that coordinates the workflow
- Planner: Breaks down goals into executable steps
- Executor: Executes individual steps using the existing AgentLoop
- Reflector: Reviews results and suggests improvements or replanning

The architecture uses a shared Workspace for state and typed outputs
for communication between agents.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from compymac.agent_loop import AgentConfig, AgentLoop
from compymac.harness import EventLog, EventType, Harness
from compymac.llm import LLMClient
from compymac.types import Message

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles in the multi-agent system."""
    MANAGER = "manager"
    PLANNER = "planner"
    EXECUTOR = "executor"
    REFLECTOR = "reflector"


class ManagerState(Enum):
    """States in the Manager FSM."""
    INITIAL = "initial"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanStep:
    """A single step in a plan."""
    index: int
    description: str
    expected_outcome: str
    tools_hint: list[str] = field(default_factory=list)
    dependencies: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "tools_hint": self.tools_hint,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        return cls(
            index=data["index"],
            description=data["description"],
            expected_outcome=data.get("expected_outcome", ""),
            tools_hint=data.get("tools_hint", []),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class StepResult:
    """Result of executing a step."""
    step_index: int
    success: bool
    summary: str
    tool_calls_made: int = 0
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "success": self.success,
            "summary": self.summary,
            "tool_calls_made": self.tool_calls_made,
            "artifacts": self.artifacts,
            "errors": self.errors,
        }


class ReflectionAction(Enum):
    """Actions recommended by the Reflector."""
    CONTINUE = "continue"  # Move to next step
    RETRY_SAME = "retry_same"  # Retry the same step
    RETRY_WITH_CHANGES = "retry_with_changes"  # Retry with modified instruction
    GATHER_INFO = "gather_info"  # Run a diagnostic step
    REPLAN = "replan"  # Create a new plan
    COMPLETE = "complete"  # Goal achieved, workflow complete
    STOP = "stop"  # Task cannot be completed (failure)


@dataclass
class ReflectionResult:
    """Result of reflection on a step."""
    action: ReflectionAction
    reasoning: str
    suggested_changes: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "reasoning": self.reasoning,
            "suggested_changes": self.suggested_changes,
            "confidence": self.confidence,
        }


@dataclass
class Workspace:
    """
    Shared state between agents.

    The Workspace is the only shared state - each agent receives a read-only
    snapshot and returns typed outputs. Only the Manager mutates the Workspace.
    """
    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    current_step_index: int = 0
    step_results: list[StepResult] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    attempt_counts: dict[int, int] = field(default_factory=dict)
    max_attempts_per_step: int = 3
    is_complete: bool = False
    final_result: str = ""
    error: str = ""

    def get_current_step(self) -> PlanStep | None:
        """Get the current step to execute."""
        if 0 <= self.current_step_index < len(self.plan):
            return self.plan[self.current_step_index]
        return None

    def get_step_result(self, index: int) -> StepResult | None:
        """Get the result for a specific step."""
        for result in self.step_results:
            if result.step_index == index:
                return result
        return None

    def get_attempt_count(self, step_index: int) -> int:
        """Get the number of attempts for a step."""
        return self.attempt_counts.get(step_index, 0)

    def increment_attempt(self, step_index: int) -> int:
        """Increment and return the attempt count for a step."""
        self.attempt_counts[step_index] = self.get_attempt_count(step_index) + 1
        return self.attempt_counts[step_index]

    def to_summary(self) -> str:
        """Generate a summary of the workspace state."""
        lines = [
            f"Goal: {self.goal}",
            f"Plan steps: {len(self.plan)}",
            f"Current step: {self.current_step_index + 1}/{len(self.plan)}",
            f"Completed steps: {len(self.step_results)}",
        ]
        if self.constraints:
            lines.append(f"Constraints: {', '.join(self.constraints)}")
        return "\n".join(lines)


class BaseAgent:
    """Base class for all agents with LLM chat capabilities."""

    def __init__(
        self,
        role: AgentRole,
        llm_client: LLMClient,
        system_prompt: str = "",
    ):
        self.role = role
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.messages: list[Message] = []

        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))

    def _chat(self, user_message: str, tools: list[dict] | None = None) -> str:
        """Send a message to the LLM and get a response."""
        self.messages.append(Message(role="user", content=user_message))

        messages_for_api = [msg.to_dict() for msg in self.messages]
        response = self.llm_client.chat(messages=messages_for_api, tools=tools)

        self.messages.append(Message(role="assistant", content=response.content or ""))
        return response.content or ""

    def reset(self) -> None:
        """Reset the agent's conversation history."""
        self.messages = []
        if self.system_prompt:
            self.messages.append(Message(role="system", content=self.system_prompt))


PLANNER_SYSTEM_PROMPT = """You are a Planner agent. Your job is to break down goals into clear, executable steps.

When given a goal, create a plan with numbered steps. Each step should be:
- Specific and actionable
- Have a clear expected outcome
- List any tools that might be needed

Output your plan as JSON in this format:
{
  "steps": [
    {
      "index": 0,
      "description": "What to do",
      "expected_outcome": "What success looks like",
      "tools_hint": ["tool1", "tool2"],
      "dependencies": []
    }
  ]
}

Keep plans concise - prefer fewer, well-defined steps over many small ones."""


class PlannerAgent(BaseAgent):
    """Agent that creates plans from goals."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(
            role=AgentRole.PLANNER,
            llm_client=llm_client,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )

    def create_plan(self, workspace: Workspace) -> list[PlanStep]:
        """Create a plan for the given goal."""
        prompt = f"""Create a plan for this goal:

Goal: {workspace.goal}

Constraints: {', '.join(workspace.constraints) if workspace.constraints else 'None'}

Previous context: {workspace.to_summary() if workspace.step_results else 'Starting fresh'}

Output your plan as JSON."""

        response = self._chat(prompt)

        # Parse the JSON response
        try:
            # Find JSON in the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
                return steps
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse plan JSON: {e}")

        # Fallback: create a single step from the response
        return [PlanStep(
            index=0,
            description=response[:500],
            expected_outcome="Complete the goal",
        )]

    def revise_plan(
        self,
        workspace: Workspace,
        reason: str,
    ) -> list[PlanStep]:
        """Revise the plan based on feedback."""
        prompt = f"""The current plan needs revision.

Goal: {workspace.goal}
Current step: {workspace.current_step_index + 1}/{len(workspace.plan)}
Reason for revision: {reason}

Previous results:
{self._format_results(workspace.step_results[-3:])}

Create a revised plan starting from the current point. Output as JSON."""

        response = self._chat(prompt)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
                # Renumber steps starting from current index
                for i, step in enumerate(steps):
                    step.index = workspace.current_step_index + i
                return steps
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse revised plan JSON: {e}")

        return []

    def _format_results(self, results: list[StepResult]) -> str:
        """Format step results for the prompt."""
        if not results:
            return "No previous results"
        lines = []
        for r in results:
            status = "SUCCESS" if r.success else "FAILED"
            lines.append(f"Step {r.step_index + 1} [{status}]: {r.summary}")
        return "\n".join(lines)


REFLECTOR_SYSTEM_PROMPT = """You are a Reflector agent. Your job is to analyze step results and recommend next actions.

After each step execution, you will receive:
- The step that was attempted
- The result (success/failure, summary, errors)
- The overall goal and progress

Your job is to recommend one of these actions:
- CONTINUE: The step succeeded, move to the next step
- RETRY_SAME: The step failed but might succeed if retried
- RETRY_WITH_CHANGES: The step failed and needs a modified approach
- GATHER_INFO: We need more information before proceeding
- REPLAN: The plan is fundamentally wrong and needs revision
- COMPLETE: The goal has been fully achieved, workflow is done (use this on the LAST step when successful)
- STOP: The task cannot be completed due to unrecoverable errors

IMPORTANT: Use COMPLETE (not STOP) when the goal is achieved. Use STOP only for failures.

Output your recommendation as JSON:
{
  "action": "CONTINUE",
  "reasoning": "Why this action",
  "suggested_changes": "If RETRY_WITH_CHANGES, what to change",
  "confidence": 0.9
}"""


class ReflectorAgent(BaseAgent):
    """Agent that reviews results and suggests improvements."""

    def __init__(self, llm_client: LLMClient):
        super().__init__(
            role=AgentRole.REFLECTOR,
            llm_client=llm_client,
            system_prompt=REFLECTOR_SYSTEM_PROMPT,
        )

    def reflect(
        self,
        workspace: Workspace,
        step: PlanStep,
        result: StepResult,
    ) -> ReflectionResult:
        """Reflect on a step result and recommend an action."""
        prompt = f"""Analyze this step result:

Goal: {workspace.goal}
Step {step.index + 1}: {step.description}
Expected outcome: {step.expected_outcome}

Result:
- Success: {result.success}
- Summary: {result.summary}
- Tool calls: {result.tool_calls_made}
- Errors: {', '.join(result.errors) if result.errors else 'None'}

Attempt {workspace.get_attempt_count(step.index)} of {workspace.max_attempts_per_step}
Progress: Step {workspace.current_step_index + 1} of {len(workspace.plan)}

What should we do next? Output as JSON."""

        response = self._chat(prompt)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                action = ReflectionAction(data.get("action", "continue").lower())
                return ReflectionResult(
                    action=action,
                    reasoning=data.get("reasoning", ""),
                    suggested_changes=data.get("suggested_changes", ""),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse reflection JSON: {e}")

        # Default: continue if success, retry if failure
        if result.success:
            return ReflectionResult(
                action=ReflectionAction.CONTINUE,
                reasoning="Step completed successfully",
                confidence=0.8,
            )
        else:
            return ReflectionResult(
                action=ReflectionAction.RETRY_SAME,
                reasoning="Step failed, attempting retry",
                confidence=0.5,
            )


class ExecutorAgent:
    """
    Agent that executes individual steps using the existing AgentLoop.

    Unlike other agents, the Executor wraps AgentLoop and has access to tools.
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.config = config or AgentConfig(
            max_steps=20,
            system_prompt="You are an Executor agent. Execute the given step precisely and report the result.",
        )

    def execute_step(
        self,
        step: PlanStep,
        workspace: Workspace,
        modified_instruction: str = "",
    ) -> StepResult:
        """Execute a single step and return the result."""
        # Create a fresh AgentLoop for this step
        loop = AgentLoop(
            harness=self.harness,
            llm_client=self.llm_client,
            config=self.config,
        )

        # Build the execution prompt
        instruction = modified_instruction or step.description
        prompt = f"""Execute this step:

Step {step.index + 1}: {instruction}
Expected outcome: {step.expected_outcome}

Context:
- Goal: {workspace.goal}
- Previous artifacts: {list(workspace.artifacts.keys()) if workspace.artifacts else 'None'}

Execute the step using the available tools. When done, summarize what you accomplished."""

        try:
            # Run the agent loop
            response = loop.run(prompt)
            state = loop.get_state()

            # Determine success based on response content
            success = not any(
                word in response.lower()
                for word in ["error", "failed", "cannot", "unable"]
            )

            return StepResult(
                step_index=step.index,
                success=success,
                summary=response[:500],
                tool_calls_made=state.tool_call_count,
                artifacts={},
                errors=[],
            )

        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return StepResult(
                step_index=step.index,
                success=False,
                summary=f"Execution failed: {str(e)}",
                tool_calls_made=0,
                errors=[str(e)],
            )


class ManagerAgent:
    """
    FSM orchestrator that coordinates the multi-agent workflow.

    The Manager is the only component that mutates the Workspace directly.
    It drives the workflow: Plan → Execute → Reflect → (repeat or replan).
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        event_log: EventLog | None = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.event_log = event_log or harness.get_event_log()

        # Initialize sub-agents
        self.planner = PlannerAgent(llm_client)
        self.executor = ExecutorAgent(harness, llm_client)
        self.reflector = ReflectorAgent(llm_client)

        # State
        self.workspace = Workspace()
        self.state = ManagerState.INITIAL

    def _log_event(self, event_type: str, **data: Any) -> None:
        """Log a manager event."""
        self.event_log.log_event(
            EventType.AGENT_TURN_START,  # Reuse existing event type
            tool_call_id=f"manager_{self.state.value}",
            manager_event=event_type,
            **data,
        )

    def run(self, goal: str, constraints: list[str] | None = None) -> str:
        """
        Run the multi-agent workflow to achieve a goal.

        Returns the final result or error message.
        """
        self.workspace.goal = goal
        self.workspace.constraints = constraints or []
        self.state = ManagerState.INITIAL

        self._log_event("workflow_start", goal=goal)

        max_iterations = 100  # Safety limit
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if self.state == ManagerState.INITIAL:
                self._transition_to_planning()

            elif self.state == ManagerState.PLANNING:
                self._do_planning()

            elif self.state == ManagerState.EXECUTING:
                self._do_executing()

            elif self.state == ManagerState.REFLECTING:
                self._do_reflecting()

            elif self.state == ManagerState.REPLANNING:
                self._do_replanning()

            elif self.state in (ManagerState.COMPLETED, ManagerState.FAILED):
                break

        self._log_event(
            "workflow_end",
            state=self.state.value,
            iterations=iteration,
            success=self.state == ManagerState.COMPLETED,
        )

        if self.state == ManagerState.COMPLETED:
            return self.workspace.final_result
        else:
            return f"Workflow failed: {self.workspace.error}"

    def _transition_to_planning(self) -> None:
        """Transition to planning state."""
        self.state = ManagerState.PLANNING
        self._log_event("state_transition", new_state="planning")

    def _do_planning(self) -> None:
        """Execute the planning phase."""
        self._log_event("planning_start")

        plan = self.planner.create_plan(self.workspace)

        if not plan:
            self.state = ManagerState.FAILED
            self.workspace.error = "Planner failed to create a plan"
            return

        self.workspace.plan = plan
        self.workspace.current_step_index = 0
        self.state = ManagerState.EXECUTING

        self._log_event(
            "planning_complete",
            step_count=len(plan),
            steps=[s.description[:100] for s in plan],
        )

    def _do_executing(self) -> None:
        """Execute the current step."""
        step = self.workspace.get_current_step()

        if step is None:
            # All steps completed
            self.state = ManagerState.COMPLETED
            self.workspace.is_complete = True
            self.workspace.final_result = self._generate_final_result()
            return

        self._log_event(
            "executing_step",
            step_index=step.index,
            description=step.description[:100],
        )

        # Increment attempt count
        attempt = self.workspace.increment_attempt(step.index)

        # Execute the step
        result = self.executor.execute_step(step, self.workspace)
        self.workspace.step_results.append(result)

        self._log_event(
            "step_result",
            step_index=step.index,
            success=result.success,
            attempt=attempt,
        )

        # Transition to reflecting
        self.state = ManagerState.REFLECTING

    def _do_reflecting(self) -> None:
        """Reflect on the last step result."""
        if not self.workspace.step_results:
            self.state = ManagerState.FAILED
            self.workspace.error = "No step results to reflect on"
            return

        last_result = self.workspace.step_results[-1]
        step = self.workspace.plan[last_result.step_index]

        self._log_event("reflecting_start", step_index=step.index)

        reflection = self.reflector.reflect(self.workspace, step, last_result)

        self._log_event(
            "reflection_result",
            action=reflection.action.value,
            reasoning=reflection.reasoning[:200],
        )

        # Handle the reflection action
        if reflection.action == ReflectionAction.CONTINUE:
            self.workspace.current_step_index += 1
            self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.RETRY_SAME:
            if self.workspace.get_attempt_count(step.index) >= self.workspace.max_attempts_per_step:
                # Max attempts reached, force replan
                self.state = ManagerState.REPLANNING
            else:
                self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.RETRY_WITH_CHANGES:
            if self.workspace.get_attempt_count(step.index) >= self.workspace.max_attempts_per_step:
                self.state = ManagerState.REPLANNING
            else:
                # Modify the step description
                step.description = f"{step.description}\n\nModification: {reflection.suggested_changes}"
                self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.REPLAN:
            self.state = ManagerState.REPLANNING

        elif reflection.action == ReflectionAction.COMPLETE:
            # Goal achieved - mark as completed
            self.state = ManagerState.COMPLETED
            self.workspace.is_complete = True
            self.workspace.final_result = self._generate_final_result()

        elif reflection.action == ReflectionAction.STOP:
            self.state = ManagerState.FAILED
            self.workspace.error = f"Reflector recommended stopping: {reflection.reasoning}"

        else:  # GATHER_INFO or unknown
            # Treat as continue for now
            self.workspace.current_step_index += 1
            self.state = ManagerState.EXECUTING

    def _do_replanning(self) -> None:
        """Revise the plan based on current state."""
        self._log_event("replanning_start")

        reason = "Previous approach failed, need new strategy"
        if self.workspace.step_results:
            last_result = self.workspace.step_results[-1]
            if last_result.errors:
                reason = f"Errors encountered: {', '.join(last_result.errors[:3])}"

        new_steps = self.planner.revise_plan(self.workspace, reason)

        if not new_steps:
            self.state = ManagerState.FAILED
            self.workspace.error = "Replanning failed to produce new steps"
            return

        # Replace remaining steps with new plan
        completed_steps = self.workspace.plan[:self.workspace.current_step_index]
        self.workspace.plan = completed_steps + new_steps

        self._log_event(
            "replanning_complete",
            new_step_count=len(new_steps),
        )

        self.state = ManagerState.EXECUTING

    def _generate_final_result(self) -> str:
        """Generate a summary of the completed workflow."""
        successful_steps = sum(1 for r in self.workspace.step_results if r.success)
        total_steps = len(self.workspace.step_results)

        lines = [
            f"Goal achieved: {self.workspace.goal}",
            f"Steps completed: {successful_steps}/{total_steps}",
            "",
            "Summary:",
        ]

        for result in self.workspace.step_results:
            status = "OK" if result.success else "FAILED"
            lines.append(f"  Step {result.step_index + 1} [{status}]: {result.summary[:100]}")

        return "\n".join(lines)

    def get_workspace(self) -> Workspace:
        """Get the current workspace state."""
        return self.workspace

    def get_state(self) -> ManagerState:
        """Get the current manager state."""
        return self.state
