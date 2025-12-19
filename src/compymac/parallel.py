"""
Parallel execution support for CompyMac.

This module provides:
1. ForkedTraceContext - Independent span stacks for parallel workers
2. ToolConflictModel - Classification of tools as parallel_safe vs exclusive
3. ParallelExecutor - ThreadPoolExecutor-based parallel tool execution

Key design decisions:
- Forked contexts share trace_store and trace_id but have independent span stacks
- Tool conflicts are determined by resource keys (file paths, session IDs)
- Exclusive tools use per-resource locks to prevent concurrent access
- All parallel spans link to a common parent for proper trace reconstruction
"""

from __future__ import annotations

import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from compymac.trace_store import (
    SpanKind,
    SpanStatus,
    ToolProvenance,
    TraceContext,
    TraceStore,
)
from compymac.types import ToolCall, ToolResult

if TYPE_CHECKING:
    from compymac.local_harness import LocalHarness
    from compymac.multi_agent import ExecutorAgent, PlanStep, StepResult, Workspace


class ConflictClass(Enum):
    """Classification of tool conflict behavior."""

    PARALLEL_SAFE = "parallel_safe"  # Can run concurrently with any tool
    EXCLUSIVE = "exclusive"  # Requires exclusive access to a resource


@dataclass
class ResourceLock:
    """A lock for a specific resource."""

    resource_key: str
    lock: threading.Lock = field(default_factory=threading.Lock)


class ForkedTraceContext:
    """
    A forked trace context for parallel execution.

    Shares trace_store and trace_id with the parent context,
    but maintains an independent span stack seeded with a known parent.
    """

    def __init__(
        self,
        trace_store: TraceStore,
        trace_id: str,
        parent_span_id: str | None = None,
    ):
        self.trace_store = trace_store
        self.trace_id = trace_id
        self._parent_span_id = parent_span_id
        self._span_stack: list[str] = []

    @property
    def current_span_id(self) -> str | None:
        """Get the current span ID (top of stack)."""
        return self._span_stack[-1] if self._span_stack else None

    def start_span(
        self,
        kind: SpanKind,
        name: str,
        actor_id: str,
        attributes: dict[str, Any] | None = None,
        tool_provenance: ToolProvenance | None = None,
        input_artifact_hash: str | None = None,
    ) -> str:
        """Start a span with automatic parent linking."""
        # Use current span if we have one, otherwise use the seeded parent
        parent = self.current_span_id or self._parent_span_id

        span_id = self.trace_store.start_span(
            trace_id=self.trace_id,
            kind=kind,
            name=name,
            actor_id=actor_id,
            parent_span_id=parent,
            attributes=attributes,
            tool_provenance=tool_provenance,
            input_artifact_hash=input_artifact_hash,
        )
        self._span_stack.append(span_id)
        return span_id

    def end_span(
        self,
        status: SpanStatus,
        output_artifact_hash: str | None = None,
        error_class: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """End the current span."""
        if not self._span_stack:
            return

        span_id = self._span_stack.pop()
        self.trace_store.end_span(
            trace_id=self.trace_id,
            span_id=span_id,
            status=status,
            output_artifact_hash=output_artifact_hash,
            error_class=error_class,
            error_message=error_message,
        )

    def store_artifact(
        self,
        data: bytes,
        artifact_type: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ):
        """Store an artifact."""
        return self.trace_store.store_artifact(data, artifact_type, content_type, metadata)


def fork_trace_context(
    parent_context: TraceContext,
    parent_span_id: str | None = None,
) -> ForkedTraceContext:
    """
    Create a forked trace context for parallel execution.

    The forked context shares trace_store and trace_id with the parent,
    but has an independent span stack seeded with the given parent span.

    Args:
        parent_context: The parent TraceContext to fork from
        parent_span_id: The span ID to use as parent for new spans in this fork

    Returns:
        A new ForkedTraceContext with independent span stack
    """
    return ForkedTraceContext(
        trace_store=parent_context.trace_store,
        trace_id=parent_context.trace_id,
        parent_span_id=parent_span_id,
    )


class ToolConflictModel:
    """
    Model for determining which tools can run in parallel.

    Tools are classified into conflict classes:
    - PARALLEL_SAFE: Can run concurrently (e.g., Read)
    - EXCLUSIVE: Requires exclusive access to a resource (e.g., Write, Bash)

    For exclusive tools, we track resource keys to allow parallel execution
    when operating on different resources (e.g., writing to different files).
    """

    # Default conflict classes for known tools
    DEFAULT_CLASSES: dict[str, ConflictClass] = {
        "Read": ConflictClass.PARALLEL_SAFE,
        "Write": ConflictClass.EXCLUSIVE,
        "Bash": ConflictClass.EXCLUSIVE,
        "browser.navigate": ConflictClass.EXCLUSIVE,
        "browser.click": ConflictClass.EXCLUSIVE,
        "browser.type": ConflictClass.EXCLUSIVE,
        "browser.extract": ConflictClass.EXCLUSIVE,
    }

    def __init__(self):
        self._classes = dict(self.DEFAULT_CLASSES)
        self._resource_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

    def get_conflict_class(self, tool_name: str) -> ConflictClass:
        """Get the conflict class for a tool."""
        return self._classes.get(tool_name, ConflictClass.EXCLUSIVE)

    def register_tool(self, tool_name: str, conflict_class: ConflictClass) -> None:
        """Register a tool's conflict class."""
        self._classes[tool_name] = conflict_class

    def get_resource_key(self, tool_call: ToolCall) -> str | None:
        """
        Get the resource key for a tool call.

        Returns None for parallel_safe tools.
        Returns a resource identifier for exclusive tools.
        """
        conflict_class = self.get_conflict_class(tool_call.name)

        if conflict_class == ConflictClass.PARALLEL_SAFE:
            return None

        # For file operations, use the file path as resource key
        if tool_call.name in ("Read", "Write"):
            return f"file:{tool_call.arguments.get('file_path', 'unknown')}"

        # For Bash, use a global lock (stateful shell)
        if tool_call.name == "Bash":
            bash_id = tool_call.arguments.get("bash_id", "default")
            return f"bash:{bash_id}"

        # For browser operations, use session ID
        if tool_call.name.startswith("browser."):
            session_id = tool_call.arguments.get("session_id", "default")
            return f"browser:{session_id}"

        # Default: use tool name as resource key (global lock per tool)
        return f"tool:{tool_call.name}"

    def get_lock(self, resource_key: str) -> threading.Lock:
        """Get the lock for a resource key."""
        return self._resource_locks[resource_key]

    def can_run_parallel(self, tool_calls: list[ToolCall]) -> bool:
        """
        Check if a set of tool calls can run in parallel.

        Returns True if:
        - All tools are parallel_safe, OR
        - All exclusive tools operate on different resources
        """
        resource_keys: set[str] = set()

        for call in tool_calls:
            resource_key = self.get_resource_key(call)
            if resource_key is not None:
                if resource_key in resource_keys:
                    # Two tools want the same resource
                    return False
                resource_keys.add(resource_key)

        return True

    def partition_by_conflicts(
        self, tool_calls: list[ToolCall]
    ) -> list[list[ToolCall]]:
        """
        Partition tool calls into groups that can run in parallel.

        Each group contains tools that don't conflict with each other.
        Groups must be executed sequentially, but tools within a group
        can be executed in parallel.
        """
        if not tool_calls:
            return []

        groups: list[list[ToolCall]] = []
        current_group: list[ToolCall] = []
        current_resources: set[str] = set()

        for call in tool_calls:
            resource_key = self.get_resource_key(call)

            if resource_key is None:
                # Parallel-safe, can go in current group
                current_group.append(call)
            elif resource_key in current_resources:
                # Conflict! Start new group
                if current_group:
                    groups.append(current_group)
                current_group = [call]
                current_resources = {resource_key}
            else:
                # No conflict, add to current group
                current_group.append(call)
                current_resources.add(resource_key)

        if current_group:
            groups.append(current_group)

        return groups


class ParallelExecutor:
    """
    Executor for parallel tool calls with proper trace context handling.

    Uses ThreadPoolExecutor for parallel execution and ForkedTraceContext
    to maintain correct parent-child relationships in traces.
    """

    def __init__(
        self,
        harness: LocalHarness,
        trace_context: TraceContext | None = None,
        max_workers: int = 4,
        conflict_model: ToolConflictModel | None = None,
    ):
        self.harness = harness
        self.trace_context = trace_context
        self.max_workers = max_workers
        self.conflict_model = conflict_model or ToolConflictModel()

    def execute_parallel(
        self,
        tool_calls: list[ToolCall],
        parent_span_id: str | None = None,
    ) -> list[ToolResult]:
        """
        Execute tool calls in parallel where possible.

        Tool calls are partitioned by conflicts - conflicting tools run
        sequentially, non-conflicting tools run in parallel.

        Args:
            tool_calls: List of tool calls to execute
            parent_span_id: Parent span ID for trace context

        Returns:
            List of ToolResults in the same order as input tool_calls
        """
        if not tool_calls:
            return []

        # Partition into parallel groups
        groups = self.conflict_model.partition_by_conflicts(tool_calls)

        # Track results by call ID to preserve order
        results_by_id: dict[str, ToolResult] = {}

        for group in groups:
            if len(group) == 1:
                # Single tool, execute directly
                result = self._execute_single(group[0], parent_span_id)
                results_by_id[group[0].id] = result
            else:
                # Multiple tools, execute in parallel
                group_results = self._execute_group_parallel(group, parent_span_id)
                for call, result in zip(group, group_results, strict=True):
                    results_by_id[call.id] = result

        # Return results in original order
        return [results_by_id[call.id] for call in tool_calls]

    def _execute_single(
        self,
        tool_call: ToolCall,
        parent_span_id: str | None,
    ) -> ToolResult:
        """Execute a single tool call with optional trace context."""
        # Get resource lock if needed
        resource_key = self.conflict_model.get_resource_key(tool_call)

        if resource_key:
            lock = self.conflict_model.get_lock(resource_key)
            with lock:
                return self._execute_with_context(tool_call, parent_span_id)
        else:
            return self._execute_with_context(tool_call, parent_span_id)

    def _execute_with_context(
        self,
        tool_call: ToolCall,
        parent_span_id: str | None,
    ) -> ToolResult:
        """Execute a tool call with forked trace context."""
        if self.trace_context is None:
            # No tracing, execute directly
            return self.harness.execute(tool_call)

        # Create forked context for this execution
        forked_ctx = fork_trace_context(self.trace_context, parent_span_id)

        # Set thread-local context for this worker thread
        # This avoids race conditions when multiple threads execute in parallel
        self.harness.set_thread_local_context(forked_ctx)

        try:
            return self.harness.execute(tool_call)
        finally:
            # Clear thread-local context after execution
            self.harness.clear_thread_local_context()

    def _execute_group_parallel(
        self,
        tool_calls: list[ToolCall],
        parent_span_id: str | None,
    ) -> list[ToolResult]:
        """Execute a group of non-conflicting tool calls in parallel."""
        results: list[ToolResult | None] = [None] * len(tool_calls)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tool_calls))) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(
                    self._execute_single, call, parent_span_id
                ): i
                for i, call in enumerate(tool_calls)
            }

            # Collect results
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    # Create error result
                    results[index] = ToolResult(
                        tool_call_id=tool_calls[index].id,
                        content=f"Error: {e}",
                        success=False,
                        error=str(e),
                    )

        return results  # type: ignore


class JoinSpan:
    """
    Helper for creating JOIN spans that aggregate parallel results.

    A JOIN span links to all child spans from parallel execution
    and records the merge policy used.
    """

    def __init__(
        self,
        trace_context: TraceContext,
        name: str,
        actor_id: str,
        merge_policy: str = "aggregate_all",
    ):
        self.trace_context = trace_context
        self.name = name
        self.actor_id = actor_id
        self.merge_policy = merge_policy
        self._child_span_ids: list[str] = []
        self._span_id: str | None = None

    def add_child(self, span_id: str) -> None:
        """Add a child span ID to link."""
        self._child_span_ids.append(span_id)

    def __enter__(self) -> JoinSpan:
        """Start the JOIN span."""
        self._span_id = self.trace_context.start_span(
            kind=SpanKind.REASONING,
            name=self.name,
            actor_id=self.actor_id,
            attributes={
                "join_type": "fan_in",
                "merge_policy": self.merge_policy,
                "child_count": len(self._child_span_ids),
            },
        )

        # Add links to all child spans
        for child_id in self._child_span_ids:
            self.trace_context.trace_store.add_span_link(
                self.trace_context.trace_id,
                self._span_id,
                child_id,
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the JOIN span."""
        if exc_type is not None:
            self.trace_context.end_span(
                status=SpanStatus.ERROR,
                error_class=exc_type.__name__ if exc_type else None,
                error_message=str(exc_val) if exc_val else None,
            )
        else:
            self.trace_context.end_span(status=SpanStatus.OK)


# Type imports for ParallelStepExecutor
if TYPE_CHECKING:
    from compymac.multi_agent import ExecutorAgent, PlanStep, StepResult, Workspace


class ParallelStepExecutor:
    """
    Executor for parallel plan steps.

    Uses ThreadPoolExecutor to run multiple plan steps in parallel when
    they have no dependencies on each other. Each parallel step gets its
    own forked trace context to maintain proper parent-child relationships.
    """

    def __init__(
        self,
        executor_agent: ExecutorAgent,
        trace_context: TraceContext | None = None,
        max_workers: int = 4,
    ):
        """
        Initialize the parallel step executor.

        Args:
            executor_agent: The ExecutorAgent to use for step execution
            trace_context: Optional trace context for execution capture
            max_workers: Maximum number of parallel workers (default: 4)
        """
        self.executor_agent = executor_agent
        self.trace_context = trace_context
        self.max_workers = max_workers

    def execute_parallel_group(
        self,
        steps: list[PlanStep],
        workspace: Workspace,
        parent_span_id: str | None = None,
    ) -> list[StepResult]:
        """
        Execute a group of steps in parallel.

        All steps in the group are assumed to have no dependencies on each other
        and can safely run concurrently.

        Args:
            steps: List of PlanStep objects to execute in parallel
            workspace: The shared workspace (read-only during parallel execution)
            parent_span_id: Parent span ID for trace context

        Returns:
            List of StepResult objects in the same order as input steps
        """
        if not steps:
            return []

        if len(steps) == 1:
            # Single step, execute directly
            return [self._execute_step_with_context(steps[0], workspace, parent_span_id)]

        # Multiple steps, execute in parallel
        results: list[StepResult | None] = [None] * len(steps)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(steps))) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(
                    self._execute_step_with_context,
                    step,
                    workspace,
                    parent_span_id,
                ): i
                for i, step in enumerate(steps)
            }

            # Collect results
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    # Create error result for failed step
                    from compymac.multi_agent import StepResult
                    results[index] = StepResult(
                        step_index=steps[index].index,
                        success=False,
                        summary=f"Parallel execution failed: {e}",
                        errors=[str(e)],
                    )

        return results  # type: ignore

    def _execute_step_with_context(
        self,
        step: PlanStep,
        workspace: Workspace,
        parent_span_id: str | None,
    ) -> StepResult:
        """Execute a single step with proper trace context handling."""
        if self.trace_context is None:
            # No tracing, execute directly
            return self.executor_agent.execute_step(step, workspace)

        # Create forked context for this step
        forked_ctx = fork_trace_context(self.trace_context, parent_span_id)

        # Start a span for this parallel step
        forked_ctx.start_span(
            kind=SpanKind.AGENT_TURN,
            name=f"parallel_step_{step.index}",
            actor_id="parallel_executor",
            attributes={
                "step_index": step.index,
                "step_description": step.description[:200],
                "parallel": True,
            },
        )

        try:
            # Execute the step
            # Note: We need to temporarily set the executor's trace context
            # to our forked context for proper nested span tracking
            original_ctx = self.executor_agent._trace_context
            self.executor_agent._trace_context = forked_ctx  # type: ignore

            try:
                result = self.executor_agent.execute_step(step, workspace)
            finally:
                # Restore original context
                self.executor_agent._trace_context = original_ctx

            # End the parallel step span
            forked_ctx.end_span(
                status=SpanStatus.OK if result.success else SpanStatus.ERROR,
            )

            return result

        except Exception as e:
            # End span with error
            forked_ctx.end_span(
                status=SpanStatus.ERROR,
                error_class=type(e).__name__,
                error_message=str(e),
            )
            raise


class ParallelGroupResult:
    """
    Result of executing a parallel group of steps.

    Aggregates results from multiple steps executed in parallel,
    providing summary statistics and access to individual results.
    """

    def __init__(self, step_results: list[StepResult]):
        self.step_results = step_results

    @property
    def all_success(self) -> bool:
        """Check if all steps succeeded."""
        return all(r.success for r in self.step_results)

    @property
    def any_success(self) -> bool:
        """Check if any step succeeded."""
        return any(r.success for r in self.step_results)

    @property
    def success_count(self) -> int:
        """Count of successful steps."""
        return sum(1 for r in self.step_results if r.success)

    @property
    def failure_count(self) -> int:
        """Count of failed steps."""
        return sum(1 for r in self.step_results if not r.success)

    @property
    def failed_steps(self) -> list[StepResult]:
        """Get list of failed step results."""
        return [r for r in self.step_results if not r.success]

    @property
    def successful_steps(self) -> list[StepResult]:
        """Get list of successful step results."""
        return [r for r in self.step_results if r.success]

    def get_result(self, step_index: int) -> StepResult | None:
        """Get result for a specific step index."""
        for r in self.step_results:
            if r.step_index == step_index:
                return r
        return None
