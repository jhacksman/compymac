"""
Multi-Agent Architecture - Manager, Planner, Executor, Reflector pattern.

This module implements a hierarchical multi-agent system where:
- Manager: FSM orchestrator that coordinates the workflow
- Planner: Breaks down goals into executable steps
- Executor: Executes individual steps using the existing AgentLoop
- Reflector: Reviews results and suggests improvements or replanning

The architecture uses a shared Workspace for state and typed outputs
for communication between agents.

Supports optional TraceContext for complete execution capture including:
- Each agent's work (Manager, Planner, Executor, Reflector)
- State transitions
- Planning and replanning phases
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.agent_loop import AgentConfig, AgentLoop
from compymac.harness import EventLog, EventType, Harness
from compymac.llm import LLMClient
from compymac.memory import MemoryFacts, MemoryManager, MemoryState
from compymac.types import Message
from compymac.workflows.agent_handoffs import (
    AgentArtifactType,
    HandoffManager,
)

if TYPE_CHECKING:
    from compymac.parallel import ParallelStepExecutor
    from compymac.trace_store import TraceContext, TraceStore
    from compymac.workflows.artifact_store import ArtifactStore

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
    priority: int = 0  # Higher priority = execute first among parallel steps
    can_parallelize: bool = False  # Whether this step can run in parallel with others
    estimated_complexity: str = "medium"  # low, medium, high - hint for scheduling

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "expected_outcome": self.expected_outcome,
            "tools_hint": self.tools_hint,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "can_parallelize": self.can_parallelize,
            "estimated_complexity": self.estimated_complexity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        return cls(
            index=data["index"],
            description=data["description"],
            expected_outcome=data.get("expected_outcome", ""),
            tools_hint=data.get("tools_hint", []),
            dependencies=data.get("dependencies", []),
            priority=data.get("priority", 0),
            can_parallelize=data.get("can_parallelize", False),
            estimated_complexity=data.get("estimated_complexity", "medium"),
        )


class ErrorType(Enum):
    """Classification of errors for better recovery strategies."""
    TRANSIENT = "transient"  # Temporary errors (network, timeout) - retry likely to help
    PERMANENT = "permanent"  # Permanent errors (invalid input, missing file) - retry won't help
    UNKNOWN = "unknown"  # Cannot classify - use default strategy


@dataclass
class StepResult:
    """Result of executing a step."""
    step_index: int
    success: bool
    summary: str
    tool_calls_made: int = 0
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    error_type: ErrorType | None = None
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "success": self.success,
            "summary": self.summary,
            "tool_calls_made": self.tool_calls_made,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "error_type": self.error_type.value if self.error_type else None,
            "execution_time_ms": self.execution_time_ms,
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


def classify_error(error_message: str) -> ErrorType:
    """
    Classify an error message to determine the appropriate recovery strategy.

    Transient errors (retry likely to help):
    - Network timeouts, connection errors
    - Rate limiting
    - Temporary service unavailability

    Permanent errors (retry won't help):
    - File not found, permission denied
    - Invalid input, syntax errors
    - Missing dependencies
    """
    error_lower = error_message.lower()

    transient_patterns = [
        "timeout", "timed out", "connection", "network",
        "rate limit", "too many requests", "503", "502", "504",
        "temporarily unavailable", "retry", "busy", "overloaded",
    ]

    permanent_patterns = [
        "not found", "no such file", "permission denied", "access denied",
        "invalid", "syntax error", "parse error", "type error",
        "missing", "does not exist", "undefined", "unknown",
        "cannot", "unable to", "failed to parse",
    ]

    for pattern in transient_patterns:
        if pattern in error_lower:
            return ErrorType.TRANSIENT

    for pattern in permanent_patterns:
        if pattern in error_lower:
            return ErrorType.PERMANENT

    return ErrorType.UNKNOWN


def calculate_backoff_ms(attempt: int, base_ms: int = 1000, max_ms: int = 30000) -> int:
    """
    Calculate exponential backoff delay for retries.

    Args:
        attempt: Current attempt number (1-indexed)
        base_ms: Base delay in milliseconds
        max_ms: Maximum delay in milliseconds

    Returns:
        Delay in milliseconds
    """
    delay = base_ms * (2 ** (attempt - 1))
    return min(delay, max_ms)


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
    # Memory integration
    memory_state: MemoryState | None = None
    workflow_facts: MemoryFacts | None = None
    # Error tracking for smarter recovery
    error_history: list[tuple[int, str, ErrorType]] = field(default_factory=list)
    # Timing metrics
    total_execution_time_ms: int = 0
    step_start_time: float = 0.0

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

    def record_error(self, step_index: int, error_message: str) -> ErrorType:
        """Record an error and classify it for recovery strategy."""
        error_type = classify_error(error_message)
        self.error_history.append((step_index, error_message, error_type))
        return error_type

    def get_error_pattern(self, step_index: int) -> list[ErrorType]:
        """Get the pattern of errors for a specific step."""
        return [et for si, _, et in self.error_history if si == step_index]

    def should_retry(self, step_index: int) -> tuple[bool, int]:
        """
        Determine if a step should be retried based on error history.

        Returns:
            Tuple of (should_retry, backoff_ms)
        """
        attempt = self.get_attempt_count(step_index)
        if attempt >= self.max_attempts_per_step:
            return False, 0

        error_pattern = self.get_error_pattern(step_index)
        if not error_pattern:
            return True, 0

        last_error = error_pattern[-1]

        # Don't retry permanent errors
        if last_error == ErrorType.PERMANENT:
            # Unless we've only tried once (might be a fluke)
            if attempt >= 2:
                return False, 0

        # For transient errors, use exponential backoff
        if last_error == ErrorType.TRANSIENT:
            backoff = calculate_backoff_ms(attempt)
            return True, backoff

        # For unknown errors, retry with small backoff
        return True, calculate_backoff_ms(attempt, base_ms=500)

    def start_step_timer(self) -> None:
        """Start timing a step execution."""
        self.step_start_time = time.time()

    def stop_step_timer(self) -> int:
        """Stop timing and return elapsed milliseconds."""
        if self.step_start_time > 0:
            elapsed_ms = int((time.time() - self.step_start_time) * 1000)
            self.total_execution_time_ms += elapsed_ms
            self.step_start_time = 0.0
            return elapsed_ms
        return 0

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
        if self.error_history:
            lines.append(f"Errors encountered: {len(self.error_history)}")
        if self.total_execution_time_ms > 0:
            lines.append(f"Total execution time: {self.total_execution_time_ms}ms")
        return "\n".join(lines)


@dataclass
class PlanValidationResult:
    """Result of plan validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parallel_groups: list[list[int]] = field(default_factory=list)  # Groups of step indices that can run in parallel


class PlanValidator:
    """
    Validates and analyzes execution plans.

    Provides:
    - Dependency validation (valid indices, no cycles)
    - Parallel step detection (find independent steps)
    - Constraint checking (ensure constraints are addressed)
    """

    @staticmethod
    def validate_dependencies(steps: list[PlanStep]) -> tuple[bool, list[str]]:
        """
        Validate that all dependencies reference valid step indices and there are no cycles.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        step_indices = {s.index for s in steps}

        for step in steps:
            for dep in step.dependencies:
                if dep not in step_indices:
                    errors.append(f"Step {step.index} depends on non-existent step {dep}")
                if dep >= step.index:
                    errors.append(f"Step {step.index} depends on step {dep} which comes after it (forward dependency)")

        # Check for cycles using DFS
        def has_cycle(step_index: int, visited: set[int], rec_stack: set[int]) -> bool:
            visited.add(step_index)
            rec_stack.add(step_index)

            step = next((s for s in steps if s.index == step_index), None)
            if step:
                for dep in step.dependencies:
                    if dep not in visited:
                        if has_cycle(dep, visited, rec_stack):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(step_index)
            return False

        visited: set[int] = set()
        for step in steps:
            if step.index not in visited:
                if has_cycle(step.index, visited, set()):
                    errors.append(f"Circular dependency detected involving step {step.index}")

        return len(errors) == 0, errors

    @staticmethod
    def find_parallel_groups(steps: list[PlanStep]) -> list[list[int]]:
        """
        Find groups of steps that can potentially run in parallel.

        Steps can run in parallel if:
        1. They have no dependencies on each other
        2. They are marked as can_parallelize=True
        3. Their dependencies are all satisfied at the same point

        Returns:
            List of groups, where each group is a list of step indices that can run together
        """
        if not steps:
            return []

        groups: list[list[int]] = []
        processed: set[int] = set()

        # Find steps at each "level" (steps whose dependencies are all in previous levels)
        while len(processed) < len(steps):
            # Find all steps whose dependencies are all processed
            ready = []
            for step in steps:
                if step.index not in processed:
                    if all(d in processed for d in step.dependencies):
                        ready.append(step.index)

            if not ready:
                # No progress possible - remaining steps have unresolvable dependencies
                break

            # Group ready steps that can parallelize
            parallel_group = []
            sequential = []

            for idx in ready:
                step = next(s for s in steps if s.index == idx)
                if step.can_parallelize and len(ready) > 1:
                    parallel_group.append(idx)
                else:
                    sequential.append(idx)

            # Add parallel group if it has multiple steps
            if len(parallel_group) > 1:
                groups.append(parallel_group)
                processed.update(parallel_group)
            elif parallel_group:
                # Single parallelizable step - treat as sequential
                sequential.extend(parallel_group)

            # Add sequential steps as individual groups
            for idx in sequential:
                groups.append([idx])
                processed.add(idx)

        return groups

    @staticmethod
    def check_constraints(
        steps: list[PlanStep],
        constraints: list[str],
    ) -> tuple[bool, list[str]]:
        """
        Check if the plan addresses the given constraints.

        This is a heuristic check - it looks for constraint keywords in step descriptions.

        Returns:
            Tuple of (all_addressed, list of warnings for unaddressed constraints)
        """
        warnings = []

        for constraint in constraints:
            # Extract key words from constraint (simple heuristic)
            constraint_lower = constraint.lower()
            key_words = [w for w in constraint_lower.split() if len(w) > 3]

            # Check if any step mentions the constraint
            addressed = False
            for step in steps:
                step_text = f"{step.description} {step.expected_outcome}".lower()
                if any(word in step_text for word in key_words):
                    addressed = True
                    break

            if not addressed:
                warnings.append(f"Constraint may not be addressed: '{constraint}'")

        return len(warnings) == 0, warnings

    @classmethod
    def validate_plan(
        cls,
        steps: list[PlanStep],
        constraints: list[str] | None = None,
    ) -> PlanValidationResult:
        """
        Perform full validation of a plan.

        Returns:
            PlanValidationResult with validation status, errors, warnings, and parallel groups
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Basic validation
        if not steps:
            errors.append("Plan has no steps")
            return PlanValidationResult(is_valid=False, errors=errors)

        # Check for duplicate indices
        indices = [s.index for s in steps]
        if len(indices) != len(set(indices)):
            errors.append("Plan has duplicate step indices")

        # Validate dependencies
        deps_valid, dep_errors = cls.validate_dependencies(steps)
        errors.extend(dep_errors)

        # Check constraints if provided
        if constraints:
            _, constraint_warnings = cls.check_constraints(steps, constraints)
            warnings.extend(constraint_warnings)

        # Find parallel groups
        parallel_groups = cls.find_parallel_groups(steps)

        return PlanValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            parallel_groups=parallel_groups,
        )


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


PLANNER_SYSTEM_PROMPT = """You are a Planner agent. Your job is to break down goals into clear, executable steps with proper dependency analysis.

When given a goal, create a plan with numbered steps. Each step should be:
- Specific and actionable
- Have a clear expected outcome
- List any tools that might be needed
- Specify dependencies on previous steps (by index)
- Indicate if the step can run in parallel with other independent steps

DEPENDENCY RULES:
- A step's dependencies array should list indices of steps that MUST complete before this step can start
- Dependencies must reference earlier steps (lower indices) - no forward dependencies
- Steps with no dependencies can potentially run in parallel if marked as can_parallelize=true
- Consider data flow: if step B uses output from step A, B depends on A

PARALLEL EXECUTION:
- Mark can_parallelize=true for steps that are independent and could run concurrently
- Examples of parallelizable steps: reading multiple files, making independent API calls
- Examples of non-parallelizable steps: sequential file modifications, operations with side effects

Output your plan as JSON in this format:
{
  "steps": [
    {
      "index": 0,
      "description": "What to do",
      "expected_outcome": "What success looks like",
      "tools_hint": ["tool1", "tool2"],
      "dependencies": [],
      "can_parallelize": false,
      "priority": 0,
      "estimated_complexity": "medium"
    }
  ]
}

Priority: Higher numbers = execute first among parallel steps (0-10 scale)
Estimated complexity: "low", "medium", or "high" - helps with scheduling

Keep plans concise - prefer fewer, well-defined steps over many small ones."""


class PlannerAgent(BaseAgent):
    """Agent that creates plans from goals with validation and dependency analysis."""

    def __init__(self, llm_client: LLMClient, enable_validation: bool = True):
        super().__init__(
            role=AgentRole.PLANNER,
            llm_client=llm_client,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )
        self.enable_validation = enable_validation

    def create_plan(
        self,
        workspace: Workspace,
        validate: bool | None = None,
    ) -> tuple[list[PlanStep], PlanValidationResult | None]:
        """
        Create a plan for the given goal.

        Args:
            workspace: The workspace containing goal and constraints
            validate: Whether to validate the plan (defaults to self.enable_validation)

        Returns:
            Tuple of (steps, validation_result). validation_result is None if validation disabled.
        """
        should_validate = validate if validate is not None else self.enable_validation

        prompt = f"""Create a plan for this goal:

Goal: {workspace.goal}

Constraints: {', '.join(workspace.constraints) if workspace.constraints else 'None'}

Previous context: {workspace.to_summary() if workspace.step_results else 'Starting fresh'}

Remember to:
- Specify dependencies between steps (which steps must complete before others)
- Mark steps that can run in parallel with can_parallelize=true
- Set priority for parallel steps (higher = execute first)

Output your plan as JSON."""

        response = self._chat(prompt)
        steps = self._parse_plan_response(response)

        # Validate if enabled
        validation_result = None
        if should_validate and steps:
            validation_result = PlanValidator.validate_plan(steps, workspace.constraints)

            # Log validation results
            if validation_result.errors:
                logger.warning(f"Plan validation errors: {validation_result.errors}")
            if validation_result.warnings:
                logger.info(f"Plan validation warnings: {validation_result.warnings}")
            if validation_result.parallel_groups:
                parallel_count = sum(1 for g in validation_result.parallel_groups if len(g) > 1)
                logger.info(f"Found {parallel_count} parallel execution groups")

        return steps, validation_result

    def _parse_plan_response(self, response: str) -> list[PlanStep]:
        """Parse the LLM response into PlanStep objects."""
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
        validate: bool | None = None,
    ) -> tuple[list[PlanStep], PlanValidationResult | None]:
        """
        Revise the plan based on feedback.

        Args:
            workspace: The workspace containing current state
            reason: Reason for revision
            validate: Whether to validate the plan (defaults to self.enable_validation)

        Returns:
            Tuple of (steps, validation_result). validation_result is None if validation disabled.
        """
        should_validate = validate if validate is not None else self.enable_validation

        prompt = f"""The current plan needs revision.

Goal: {workspace.goal}
Current step: {workspace.current_step_index + 1}/{len(workspace.plan)}
Reason for revision: {reason}

Previous results:
{self._format_results(workspace.step_results[-3:])}

Create a revised plan starting from the current point.
Remember to specify dependencies and mark parallelizable steps.
Output as JSON."""

        response = self._chat(prompt)
        steps = self._parse_plan_response(response)

        # Renumber steps starting from current index
        for i, step in enumerate(steps):
            step.index = workspace.current_step_index + i

        # Validate if enabled
        validation_result = None
        if should_validate and steps:
            validation_result = PlanValidator.validate_plan(steps, workspace.constraints)
            if validation_result.errors:
                logger.warning(f"Revised plan validation errors: {validation_result.errors}")

        return steps, validation_result

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
    Supports optional TraceContext for complete execution capture.
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
        trace_context: "TraceContext | None" = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.config = config or AgentConfig(
            max_steps=20,
            system_prompt="You are an Executor agent. Execute the given step precisely and report the result.",
        )
        self._trace_context: TraceContext | None = trace_context

    def execute_step(
        self,
        step: PlanStep,
        workspace: Workspace,
        modified_instruction: str = "",
    ) -> StepResult:
        """Execute a single step and return the result."""
        # Start executor span if tracing is enabled
        executor_span_id: str | None = None
        if self._trace_context:
            from compymac.trace_store import SpanKind
            executor_span_id = self._trace_context.start_span(
                kind=SpanKind.AGENT_TURN,
                name=f"executor_step_{step.index}",
                actor_id="executor",
                attributes={
                    "step_index": step.index,
                    "step_description": step.description[:200],
                },
            )

        # Create a fresh AgentLoop for this step
        loop = AgentLoop(
            harness=self.harness,
            llm_client=self.llm_client,
            config=self.config,
            trace_context=self._trace_context,
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

            # End executor span with success if tracing
            if self._trace_context and executor_span_id:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(
                    status=SpanStatus.OK if success else SpanStatus.ERROR,
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

            # End executor span with error if tracing
            if self._trace_context and executor_span_id:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(
                    status=SpanStatus.ERROR,
                    error_class=type(e).__name__,
                    error_message=str(e),
                )

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

    Supports optional TraceContext for complete execution capture.

    Gap 6 Phase 1: Uses structured artifact handoffs between agents via HandoffManager.
    This reduces error propagation by validating artifacts at each transition point.
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        event_log: EventLog | None = None,
        enable_memory: bool = False,
        trace_base_path: Path | None = None,
        trace_context: "TraceContext | None" = None,
        artifact_store: "ArtifactStore | None" = None,
        enable_structured_handoffs: bool = True,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.event_log = event_log or harness.get_event_log()
        self.enable_memory = enable_memory
        self._trace_context: "TraceContext | None" = trace_context  # noqa: UP037
        self._trace_store: "TraceStore | None" = None  # noqa: UP037

        # Initialize tracing if base path is configured
        if trace_base_path and not self._trace_context:
            from compymac.trace_store import TraceContext, create_trace_store
            self._trace_store, _ = create_trace_store(trace_base_path)
            self._trace_context = TraceContext(self._trace_store)

        # Pass trace context to harness if available
        if self._trace_context:
            self.harness.set_trace_context(self._trace_context)

        # Initialize sub-agents
        self.planner = PlannerAgent(llm_client)
        self.executor = ExecutorAgent(harness, llm_client, trace_context=self._trace_context)
        self.reflector = ReflectorAgent(llm_client)

        # Initialize memory manager if enabled
        self.memory_manager: MemoryManager | None = None
        if enable_memory:
            self.memory_manager = MemoryManager(
                llm_client=llm_client,
            )

        # Gap 6 Phase 1: Structured handoffs between agents
        self._enable_structured_handoffs = enable_structured_handoffs
        self._handoff_manager: HandoffManager | None = None
        if enable_structured_handoffs:
            self._handoff_manager = HandoffManager(artifact_store=artifact_store)

        # State
        self.workspace = Workspace()
        self.state = ManagerState.INITIAL

        # Parallel execution state
        self._parallel_groups: list[list[int]] = []  # Groups of step indices
        self._current_group_index: int = 0  # Which group we're executing
        self._parallel_step_executor: ParallelStepExecutor | None = None
        self._enable_parallel_execution: bool = True  # Can be disabled for testing
        self._last_group_results: list[StepResult] = []  # Results from last executed group

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

        # Initialize memory state if memory is enabled
        if self.memory_manager:
            self.workspace.memory_state = self.memory_manager.get_memory_state()
            self.workspace.workflow_facts = MemoryFacts()

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

        plan, validation_result = self.planner.create_plan(self.workspace)

        if not plan:
            self.state = ManagerState.FAILED
            self.workspace.error = "Planner failed to create a plan"
            return

        # Log validation results
        if validation_result:
            if validation_result.errors:
                self._log_event(
                    "plan_validation_errors",
                    errors=validation_result.errors,
                )
            if validation_result.warnings:
                self._log_event(
                    "plan_validation_warnings",
                    warnings=validation_result.warnings,
                )
            if validation_result.parallel_groups:
                parallel_count = sum(1 for g in validation_result.parallel_groups if len(g) > 1)
                self._log_event(
                    "plan_parallel_groups",
                    parallel_group_count=parallel_count,
                    groups=validation_result.parallel_groups,
                )

        self.workspace.plan = plan
        self.workspace.current_step_index = 0
        self.state = ManagerState.EXECUTING

        # Gap 6 Phase 1: Create structured handoff from planner to executor
        if self._handoff_manager:
            self._handoff_manager.create_handoff(
                from_agent="planner",
                to_agent="executor",
                artifact_type=AgentArtifactType.EXECUTION_PLAN,
                content={
                    "steps": [s.to_dict() for s in plan],
                    "goal": self.workspace.goal,
                    "constraints": self.workspace.constraints,
                    "is_valid": validation_result.is_valid if validation_result else True,
                },
            )

        # Store parallel groups for parallel execution
        if validation_result and validation_result.parallel_groups:
            self._parallel_groups = validation_result.parallel_groups
        else:
            # Default: each step is its own group (sequential execution)
            self._parallel_groups = [[s.index] for s in plan]
        self._current_group_index = 0

        # Initialize parallel step executor if we have parallel groups
        if self._enable_parallel_execution and any(len(g) > 1 for g in self._parallel_groups):
            from compymac.parallel import ParallelStepExecutor
            self._parallel_step_executor = ParallelStepExecutor(
                executor_agent=self.executor,
                trace_context=self._trace_context,
                max_workers=4,
            )

        self._log_event(
            "planning_complete",
            step_count=len(plan),
            steps=[s.description[:100] for s in plan],
            has_validation=validation_result is not None,
            is_valid=validation_result.is_valid if validation_result else None,
            parallel_groups=self._parallel_groups,
        )

    def _do_executing(self) -> None:
        """Execute the current step or parallel group."""
        # Check if we've completed all groups
        if self._current_group_index >= len(self._parallel_groups):
            self.state = ManagerState.COMPLETED
            self.workspace.is_complete = True
            self.workspace.final_result = self._generate_final_result()
            return

        # Get the current group of step indices
        current_group = self._parallel_groups[self._current_group_index]

        # Get the actual PlanStep objects for this group
        steps_in_group = [
            step for step in self.workspace.plan
            if step.index in current_group
        ]

        if not steps_in_group:
            # No steps in this group, move to next
            self._current_group_index += 1
            return

        is_parallel = len(steps_in_group) > 1

        self._log_event(
            "executing_group",
            group_index=self._current_group_index,
            step_indices=current_group,
            is_parallel=is_parallel,
        )

        # Start timing the group execution
        self.workspace.start_step_timer()

        if is_parallel and self._parallel_step_executor:
            # Execute steps in parallel
            results = self._parallel_step_executor.execute_parallel_group(
                steps_in_group,
                self.workspace,
                parent_span_id=self._trace_context.current_span_id if self._trace_context else None,
            )
        else:
            # Execute steps sequentially (single step or no parallel executor)
            results = []
            for step in steps_in_group:
                # Increment attempt count
                attempt = self.workspace.increment_attempt(step.index)

                # Check if we should apply backoff before retrying
                if attempt > 1:
                    should_retry, backoff_ms = self.workspace.should_retry(step.index)
                    if not should_retry:
                        # Skip to replanning if we shouldn't retry
                        self.state = ManagerState.REPLANNING
                        return
                    if backoff_ms > 0:
                        self._log_event("backoff_wait", backoff_ms=backoff_ms, attempt=attempt)
                        time.sleep(backoff_ms / 1000.0)

                result = self.executor.execute_step(step, self.workspace)
                results.append(result)

        # Stop timing and record execution time
        execution_time_ms = self.workspace.stop_step_timer()

        # Process results
        for result in results:
            result.execution_time_ms = execution_time_ms // len(results)  # Distribute time

            # Record any errors for classification
            if not result.success and result.errors:
                for error in result.errors:
                    error_type = self.workspace.record_error(result.step_index, error)
                    result.error_type = error_type

            self.workspace.step_results.append(result)

            # Extract facts from the result for memory
            self._extract_facts_from_result(result)

        # Log results
        for result in results:
            self._log_event(
                "step_result",
                step_index=result.step_index,
                success=result.success,
                execution_time_ms=result.execution_time_ms,
                error_type=result.error_type.value if result.error_type else None,
                parallel=is_parallel,
            )

        # Store results for reflection (we'll reflect on the whole group)
        self._last_group_results = results

        # Gap 6 Phase 1: Create structured handoff from executor to reflector
        if self._handoff_manager:
            all_success = all(r.success for r in results)
            self._handoff_manager.create_handoff(
                from_agent="executor",
                to_agent="reflector",
                artifact_type=AgentArtifactType.TEST_RESULT if all_success else AgentArtifactType.FAILURE_ANALYSIS,
                content={
                    "passed": all_success,
                    "output": "; ".join(r.summary for r in results),
                    "step_indices": [r.step_index for r in results],
                    "errors": [e for r in results for e in r.errors],
                    "failure_type": "execution" if not all_success else None,
                    "error_message": results[0].errors[0] if results and results[0].errors else None,
                },
            )

        # Update workspace current_step_index to the last step in the group
        max_step_index = max(s.index for s in steps_in_group)
        self.workspace.current_step_index = max_step_index

        # Transition to reflecting
        self.state = ManagerState.REFLECTING

    def _extract_facts_from_result(self, result: StepResult) -> None:
        """Extract facts from a step result and store in workflow memory."""
        if not self.workspace.workflow_facts:
            return

        # Extract file paths from artifacts
        if result.artifacts:
            for _key, value in result.artifacts.items():
                if isinstance(value, str) and ("/" in value or "\\" in value):
                    # Looks like a file path
                    self.workspace.workflow_facts.files_mentioned.add(value)

        # Extract errors
        if result.errors:
            for error in result.errors:
                self.workspace.workflow_facts.errors_seen.append(error)

        # Extract commands from summary (simple heuristic)
        summary_lower = result.summary.lower()
        if "ran" in summary_lower or "executed" in summary_lower:
            # Try to extract command-like patterns
            words = result.summary.split()
            for i, word in enumerate(words):
                if word in ("ran", "executed", "running") and i + 1 < len(words):
                    # Next word might be a command
                    cmd = words[i + 1].strip("'\"")
                    if cmd and not cmd.startswith("-"):
                        self.workspace.workflow_facts.commands_run.append(cmd)

    def _do_reflecting(self) -> None:
        """Reflect on the last step result or parallel group results."""
        if not self._last_group_results:
            # Fall back to workspace step_results if no group results
            if not self.workspace.step_results:
                self.state = ManagerState.FAILED
                self.workspace.error = "No step results to reflect on"
                return
            self._last_group_results = [self.workspace.step_results[-1]]

        # For parallel groups, we need to aggregate results
        is_parallel_group = len(self._last_group_results) > 1
        all_success = all(r.success for r in self._last_group_results)
        any_success = any(r.success for r in self._last_group_results)
        failed_results = [r for r in self._last_group_results if not r.success]

        self._log_event(
            "reflecting_start",
            group_size=len(self._last_group_results),
            is_parallel=is_parallel_group,
            all_success=all_success,
            any_success=any_success,
        )

        # For parallel groups, reflect on the first failed result (if any) or the first result
        if failed_results:
            result_to_reflect = failed_results[0]
        else:
            result_to_reflect = self._last_group_results[0]

        step = self.workspace.plan[result_to_reflect.step_index]
        reflection = self.reflector.reflect(self.workspace, step, result_to_reflect)

        # Gap 6 Phase 1: Create structured handoff from reflector to manager
        if self._handoff_manager:
            self._handoff_manager.create_handoff(
                from_agent="reflector",
                to_agent="manager",
                artifact_type=AgentArtifactType.REFLECTION,
                content={
                    "action": reflection.action.value,
                    "reasoning": reflection.reasoning,
                    "suggested_changes": reflection.suggested_changes,
                    "step_index": result_to_reflect.step_index,
                    "all_success": all_success,
                },
            )

        self._log_event(
            "reflection_result",
            action=reflection.action.value,
            reasoning=reflection.reasoning[:200],
            reflected_on_step=result_to_reflect.step_index,
        )

        # Handle the reflection action
        if reflection.action == ReflectionAction.CONTINUE:
            # Move to next group
            self._current_group_index += 1
            self._last_group_results = []
            self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.RETRY_SAME:
            # For parallel groups, retry the whole group
            if self.workspace.get_attempt_count(step.index) >= self.workspace.max_attempts_per_step:
                # Max attempts reached, force replan
                self.state = ManagerState.REPLANNING
            else:
                self._last_group_results = []
                self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.RETRY_WITH_CHANGES:
            if self.workspace.get_attempt_count(step.index) >= self.workspace.max_attempts_per_step:
                self.state = ManagerState.REPLANNING
            else:
                # Modify the step description
                step.description = f"{step.description}\n\nModification: {reflection.suggested_changes}"
                self._last_group_results = []
                self.state = ManagerState.EXECUTING

        elif reflection.action == ReflectionAction.REPLAN:
            self._last_group_results = []
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
            self._current_group_index += 1
            self._last_group_results = []
            self.state = ManagerState.EXECUTING

    def _do_replanning(self) -> None:
        """Revise the plan based on current state."""
        self._log_event("replanning_start")

        reason = "Previous approach failed, need new strategy"
        if self.workspace.step_results:
            last_result = self.workspace.step_results[-1]
            if last_result.errors:
                reason = f"Errors encountered: {', '.join(last_result.errors[:3])}"

        new_steps, validation_result = self.planner.revise_plan(self.workspace, reason)

        if not new_steps:
            self.state = ManagerState.FAILED
            self.workspace.error = "Replanning failed to produce new steps"
            return

        # Log validation results for revised plan
        if validation_result and validation_result.errors:
            self._log_event(
                "revised_plan_validation_errors",
                errors=validation_result.errors,
            )

        # Replace remaining steps with new plan
        completed_steps = self.workspace.plan[:self.workspace.current_step_index]
        self.workspace.plan = completed_steps + new_steps

        self._log_event(
            "replanning_complete",
            new_step_count=len(new_steps),
            is_valid=validation_result.is_valid if validation_result else None,
        )

        self.state = ManagerState.EXECUTING

    def _generate_final_result(self) -> str:
        """Generate a summary of the completed workflow."""
        successful_steps = sum(1 for r in self.workspace.step_results if r.success)
        total_steps = len(self.workspace.step_results)

        lines = [
            f"Goal achieved: {self.workspace.goal}",
            f"Steps completed: {successful_steps}/{total_steps}",
        ]

        # Add timing metrics
        if self.workspace.total_execution_time_ms > 0:
            total_sec = self.workspace.total_execution_time_ms / 1000.0
            lines.append(f"Total execution time: {total_sec:.2f}s")

        # Add error summary
        if self.workspace.error_history:
            error_count = len(self.workspace.error_history)
            transient = sum(1 for _, _, et in self.workspace.error_history if et == ErrorType.TRANSIENT)
            permanent = sum(1 for _, _, et in self.workspace.error_history if et == ErrorType.PERMANENT)
            lines.append(f"Errors encountered: {error_count} (transient: {transient}, permanent: {permanent})")

        lines.append("")
        lines.append("Summary:")

        for result in self.workspace.step_results:
            status = "OK" if result.success else "FAILED"
            time_str = f" ({result.execution_time_ms}ms)" if result.execution_time_ms > 0 else ""
            lines.append(f"  Step {result.step_index + 1} [{status}]{time_str}: {result.summary[:100]}")

        return "\n".join(lines)

    def get_workspace(self) -> Workspace:
        """Get the current workspace state."""
        return self.workspace

    def get_state(self) -> ManagerState:
        """Get the current manager state."""
        return self.state

    def get_handoff_manager(self) -> HandoffManager | None:
        """Get the handoff manager for debugging/testing."""
        return self._handoff_manager

    def get_handoff_stats(self) -> dict[str, Any]:
        """Get statistics about structured handoffs."""
        if not self._handoff_manager:
            return {"enabled": False}
        stats = self._handoff_manager.get_validation_stats()
        stats["enabled"] = True
        return stats
