"""
Parallel Rollouts - Phase 3 of CompyMac parallelization.

This module implements parallel rollouts (best-of-N independent attempts) where
multiple ManagerAgent instances work on the same goal concurrently, and the
best result is selected.

Key concepts:
- RolloutConfig: Configuration for a single rollout (team configuration)
- RolloutResult: Outcome of a single rollout attempt
- RolloutOrchestrator: Coordinates parallel rollouts and selects the best result

Design decisions:
- Each rollout gets its own fully-contained agent stack (Manager/Planner/Executor/Reflector)
- Each rollout gets its own Workspace instance (deep-copied initial state)
- Each rollout gets its own forked trace context for proper span tracking
- Selection uses deterministic heuristics + optional LLM ranking as tie-breaker
- All rollout traces are preserved in TraceStore for auditability
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.harness import Harness
from compymac.llm import LLMClient
from compymac.multi_agent import ManagerAgent, ManagerState

if TYPE_CHECKING:
    from compymac.trace_store import TraceContext, TraceStore

logger = logging.getLogger(__name__)


class RolloutStatus(Enum):
    """Status of a rollout attempt."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class RolloutConfig:
    """
    Configuration for a single rollout (team configuration).

    Different rollouts can have different configurations to explore
    different approaches to the same goal.
    """
    rollout_id: str
    # LLM configuration
    system_prompt_override: str | None = None
    temperature_override: float | None = None
    # Execution limits
    max_iterations: int = 100
    timeout_seconds: float = 300.0  # 5 minutes default
    # Feature flags
    enable_memory: bool = False
    enable_parallel_steps: bool = True
    # Metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollout_id": self.rollout_id,
            "system_prompt_override": self.system_prompt_override,
            "temperature_override": self.temperature_override,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "enable_memory": self.enable_memory,
            "enable_parallel_steps": self.enable_parallel_steps,
            "description": self.description,
            "tags": self.tags,
        }


@dataclass
class RolloutResult:
    """
    Result of a single rollout attempt.

    Captures the outcome, metrics, and trace information for a rollout.
    """
    rollout_id: str
    config: RolloutConfig
    status: RolloutStatus
    # Outcome
    success: bool
    final_result: str
    error: str = ""
    # Metrics
    execution_time_ms: int = 0
    step_count: int = 0
    retry_count: int = 0
    error_count: int = 0
    # Workspace snapshot (for inspection)
    workspace_snapshot: dict[str, Any] = field(default_factory=dict)
    # Trace information
    trace_id: str = ""
    root_span_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollout_id": self.rollout_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "success": self.success,
            "final_result": self.final_result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "step_count": self.step_count,
            "retry_count": self.retry_count,
            "error_count": self.error_count,
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
        }

    @property
    def score(self) -> float:
        """
        Calculate a score for this rollout for ranking purposes.

        Higher score = better result.
        """
        if not self.success:
            return 0.0

        # Base score for success
        score = 100.0

        # Penalize for errors and retries
        score -= self.error_count * 5.0
        score -= self.retry_count * 2.0

        # Penalize for long execution time (normalize to seconds)
        execution_seconds = self.execution_time_ms / 1000.0
        if execution_seconds > 60:
            score -= (execution_seconds - 60) * 0.1

        # Bonus for fewer steps (more efficient)
        if self.step_count > 0:
            score += max(0, 10 - self.step_count)

        return max(0.0, score)


@dataclass
class RolloutSelectionResult:
    """Result of selecting the best rollout."""
    selected_rollout: RolloutResult
    all_results: list[RolloutResult]
    selection_reason: str
    selection_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_rollout_id": self.selected_rollout.rollout_id,
            "selection_reason": self.selection_reason,
            "selection_confidence": self.selection_confidence,
            "all_results": [r.to_dict() for r in self.all_results],
        }


class RolloutOrchestrator:
    """
    Orchestrates parallel rollouts and selects the best result.

    Runs multiple independent ManagerAgent instances concurrently,
    each with its own isolated workspace and trace context.
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        max_workers: int = 3,
        trace_base_path: Path | None = None,
        trace_context: TraceContext | None = None,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.trace_base_path = trace_base_path
        self._trace_context = trace_context
        self._trace_store: TraceStore | None = None

        # Initialize trace store if base path is configured
        if trace_base_path and not trace_context:
            from compymac.trace_store import TraceContext, create_trace_store
            self._trace_store, _ = create_trace_store(trace_base_path)
            self._trace_context = TraceContext(self._trace_store)

        # Thread-local storage for rollout isolation
        self._local = threading.local()

    def run_parallel_rollouts(
        self,
        goal: str,
        configs: list[RolloutConfig],
        constraints: list[str] | None = None,
    ) -> RolloutSelectionResult:
        """
        Run multiple rollouts in parallel and select the best result.

        Args:
            goal: The goal to achieve
            configs: List of rollout configurations (one per rollout)
            constraints: Optional constraints for all rollouts

        Returns:
            RolloutSelectionResult with the selected rollout and all results
        """
        if not configs:
            raise ValueError("At least one rollout config is required")

        # Start orchestrator span if tracing
        orchestrator_span_id = None
        if self._trace_context:
            from compymac.trace_store import SpanKind
            orchestrator_span_id = self._trace_context.start_span(
                kind=SpanKind.AGENT_TURN,
                name="rollout_orchestrator",
                actor_id="orchestrator",
                attributes={
                    "goal": goal[:500],
                    "rollout_count": len(configs),
                    "max_workers": self.max_workers,
                },
            )

        try:
            # Run rollouts in parallel
            results = self._execute_rollouts(goal, configs, constraints, orchestrator_span_id)

            # Select the best result
            selection = self._select_best_rollout(results)

            # Log selection (end the orchestrator span)
            if self._trace_context:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(status=SpanStatus.OK)

            return selection

        except Exception as e:
            if self._trace_context and orchestrator_span_id:
                from compymac.trace_store import SpanStatus
                self._trace_context.end_span(
                    status=SpanStatus.ERROR,
                    error_class=type(e).__name__,
                    error_message=str(e),
                )
            raise

    def _execute_rollouts(
        self,
        goal: str,
        configs: list[RolloutConfig],
        constraints: list[str] | None,
        parent_span_id: str | None,
    ) -> list[RolloutResult]:
        """Execute all rollouts in parallel."""
        results: list[RolloutResult | None] = [None] * len(configs)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(configs))) as executor:
            future_to_index = {
                executor.submit(
                    self._execute_single_rollout,
                    goal,
                    config,
                    constraints,
                    parent_span_id,
                ): i
                for i, config in enumerate(configs)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    # Create error result for failed rollout
                    config = configs[index]
                    results[index] = RolloutResult(
                        rollout_id=config.rollout_id,
                        config=config,
                        status=RolloutStatus.FAILED,
                        success=False,
                        final_result="",
                        error=f"Rollout execution failed: {e}",
                    )

        return [r for r in results if r is not None]

    def _execute_single_rollout(
        self,
        goal: str,
        config: RolloutConfig,
        constraints: list[str] | None,
        parent_span_id: str | None,
    ) -> RolloutResult:
        """Execute a single rollout with its own isolated agent stack."""
        start_time = time.time()

        # Create forked trace context for this rollout
        rollout_trace_context = None
        rollout_span_id = None
        if self._trace_context:
            from compymac.parallel import fork_trace_context
            from compymac.trace_store import SpanKind

            rollout_trace_context = fork_trace_context(self._trace_context, parent_span_id)
            rollout_span_id = rollout_trace_context.start_span(
                kind=SpanKind.AGENT_TURN,
                name=f"rollout_{config.rollout_id}",
                actor_id=f"rollout_{config.rollout_id}",
                attributes={
                    "rollout_id": config.rollout_id,
                    "config": config.to_dict(),
                },
            )

        try:
            # Create isolated ManagerAgent for this rollout
            manager = ManagerAgent(
                harness=self.harness,
                llm_client=self.llm_client,
                enable_memory=config.enable_memory,
                trace_context=rollout_trace_context,
            )

            # Apply config overrides
            manager._enable_parallel_execution = config.enable_parallel_steps

            # Run the workflow
            final_result = manager.run(goal, constraints)

            # Capture workspace state
            workspace = manager.get_workspace()

            # Calculate metrics
            execution_time_ms = int((time.time() - start_time) * 1000)
            step_count = len(workspace.step_results)
            retry_count = sum(workspace.attempt_counts.values()) - step_count
            error_count = len(workspace.error_history)

            # Determine success
            success = manager.get_state() == ManagerState.COMPLETED and workspace.is_complete

            # End rollout span
            if rollout_trace_context and rollout_span_id:
                from compymac.trace_store import SpanStatus
                rollout_trace_context.end_span(
                    status=SpanStatus.OK if success else SpanStatus.ERROR,
                )

            return RolloutResult(
                rollout_id=config.rollout_id,
                config=config,
                status=RolloutStatus.COMPLETED,
                success=success,
                final_result=final_result,
                error=workspace.error,
                execution_time_ms=execution_time_ms,
                step_count=step_count,
                retry_count=retry_count,
                error_count=error_count,
                workspace_snapshot={"goal": workspace.goal, "is_complete": workspace.is_complete},
                trace_id=rollout_trace_context.trace_id if rollout_trace_context else "",
                root_span_id=rollout_span_id or "",
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            # End rollout span with error
            if rollout_trace_context and rollout_span_id:
                from compymac.trace_store import SpanStatus
                rollout_trace_context.end_span(
                    status=SpanStatus.ERROR,
                    error_class=type(e).__name__,
                    error_message=str(e),
                )

            return RolloutResult(
                rollout_id=config.rollout_id,
                config=config,
                status=RolloutStatus.FAILED,
                success=False,
                final_result="",
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def _select_best_rollout(
        self,
        results: list[RolloutResult],
    ) -> RolloutSelectionResult:
        """
        Select the best rollout from the results.

        Selection criteria (in order):
        1. Success > Failure
        2. Higher score (fewer errors, retries, faster execution)
        3. First successful rollout (tie-breaker)
        """
        if not results:
            raise ValueError("No rollout results to select from")

        # Separate successful and failed rollouts
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        if successful:
            # Sort by score (descending)
            successful.sort(key=lambda r: r.score, reverse=True)
            selected = successful[0]

            if len(successful) == 1:
                reason = "Only successful rollout"
                confidence = 1.0
            elif successful[0].score > successful[1].score:
                reason = f"Highest score ({selected.score:.1f}) among {len(successful)} successful rollouts"
                confidence = min(1.0, (successful[0].score - successful[1].score) / 20.0 + 0.5)
            else:
                reason = f"First among {len(successful)} equally-scored successful rollouts"
                confidence = 0.5
        else:
            # All failed - select the one with the least severe failure
            # (most steps completed, fewest errors)
            failed.sort(key=lambda r: (r.step_count, -r.error_count), reverse=True)
            selected = failed[0]
            reason = f"Least severe failure among {len(failed)} failed rollouts"
            confidence = 0.0

        return RolloutSelectionResult(
            selected_rollout=selected,
            all_results=results,
            selection_reason=reason,
            selection_confidence=confidence,
        )

    def create_default_configs(
        self,
        count: int = 3,
        base_id: str = "rollout",
    ) -> list[RolloutConfig]:
        """
        Create default rollout configurations.

        Useful for simple best-of-N scenarios where all rollouts
        use the same configuration.
        """
        return [
            RolloutConfig(
                rollout_id=f"{base_id}_{i}",
                description=f"Default rollout {i}",
            )
            for i in range(count)
        ]

    def create_diverse_configs(
        self,
        base_id: str = "rollout",
    ) -> list[RolloutConfig]:
        """
        Create diverse rollout configurations for exploration.

        Creates rollouts with different settings to explore
        different approaches to the same goal.
        """
        return [
            RolloutConfig(
                rollout_id=f"{base_id}_default",
                description="Default configuration",
                tags=["default"],
            ),
            RolloutConfig(
                rollout_id=f"{base_id}_memory",
                description="With memory enabled",
                enable_memory=True,
                tags=["memory"],
            ),
            RolloutConfig(
                rollout_id=f"{base_id}_sequential",
                description="Sequential execution (no parallel steps)",
                enable_parallel_steps=False,
                tags=["sequential"],
            ),
        ]
