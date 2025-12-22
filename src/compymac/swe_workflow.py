"""
SWE Workflow Runner - Phase 3

Integrates repo discovery, agent loop, and trace store to execute
canonical SWE workflows as defined in docs/swe-contract.md.

Workflows:
1. Fix Failing Test - Given a repo and failing test, fix it and create PR
2. Implement Feature - Given a repo and spec, implement and create PR
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from compymac.repo_discovery import RepoConfig, discover_repo
from compymac.trace_store import (
    SpanKind,
    SpanStatus,
    TraceContext,
    TraceStore,
    create_trace_store,
    generate_trace_id,
)

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    PAUSED = "paused"


class WorkflowType(str, Enum):
    """Type of SWE workflow."""

    FIX_FAILING_TEST = "fix_failing_test"
    IMPLEMENT_FEATURE = "implement_feature"


@dataclass
class TestResults:
    """Results from running tests."""

    target_test: str  # "pass" | "fail"
    regression_tests: str  # "pass" | "fail"
    new_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_test": self.target_test,
            "regression_tests": self.regression_tests,
            "new_failures": self.new_failures,
        }


@dataclass
class ImplementationDetails:
    """Details about a feature implementation."""

    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    tests_added: int = 0
    lines_added: int = 0
    lines_removed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "tests_added": self.tests_added,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
        }


@dataclass
class CaptureMetrics:
    """Metrics about execution capture."""

    session_id: str
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    checkpoints: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens": self.total_tokens,
            "checkpoints": self.checkpoints,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    workflow: WorkflowType
    status: WorkflowStatus
    pr_url: str | None = None
    ci_status: str | None = None  # "pass" | "fail" | None
    test_results: TestResults | None = None
    implementation: ImplementationDetails | None = None
    capture: CaptureMetrics | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow.value,
            "status": self.status.value,
            "pr_url": self.pr_url,
            "ci_status": self.ci_status,
            "test_results": self.test_results.to_dict() if self.test_results else None,
            "implementation": self.implementation.to_dict() if self.implementation else None,
            "capture": self.capture.to_dict() if self.capture else None,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class WorkflowConfig:
    """Configuration for a workflow execution."""

    repo_path: Path
    workflow_type: WorkflowType
    test_identifier: str | None = None  # For fix_failing_test
    feature_spec: str | None = None  # For implement_feature
    target_files: list[str] = field(default_factory=list)
    branch: str | None = None
    trace_dir: Path | None = None

    def validate(self) -> list[str]:
        """Validate the configuration. Returns list of errors."""
        errors = []
        if not self.repo_path.exists():
            errors.append(f"Repository path does not exist: {self.repo_path}")

        if self.workflow_type == WorkflowType.FIX_FAILING_TEST:
            if not self.test_identifier:
                errors.append("test_identifier is required for fix_failing_test workflow")

        if self.workflow_type == WorkflowType.IMPLEMENT_FEATURE:
            if not self.feature_spec:
                errors.append("feature_spec is required for implement_feature workflow")

        return errors


class SWEWorkflow:
    """
    Executes SWE workflows with full execution capture.

    This is the main entry point for running canonical SWE tasks.
    It integrates:
    - Repo discovery (Phase 2) for understanding the repo
    - Trace store (Phase 1) for execution capture
    - Agent loop for LLM-driven execution
    """

    def __init__(
        self,
        config: WorkflowConfig,
        trace_store: TraceStore | None = None,
    ):
        self.config = config
        self.repo_config: RepoConfig | None = None
        self.trace_id = generate_trace_id()
        self.result = WorkflowResult(
            workflow=config.workflow_type,
            status=WorkflowStatus.PENDING,
        )

        # Set up trace store
        if trace_store:
            self.trace_store = trace_store
        else:
            trace_dir = config.trace_dir or (config.repo_path / ".compymac" / "traces")
            self.trace_store, _ = create_trace_store(trace_dir)

        self.trace_context = TraceContext(self.trace_store, self.trace_id)

    def discover_repo(self) -> RepoConfig:
        """Discover repository configuration."""
        _span_id = self.trace_context.start_span(
            kind=SpanKind.TOOL_CALL,
            name="discover_repo",
            actor_id="swe_workflow",
            attributes={"repo_path": str(self.config.repo_path)},
        )

        try:
            self.repo_config = discover_repo(self.config.repo_path)
            self.trace_context.end_span(status=SpanStatus.OK)
            return self.repo_config
        except Exception as e:
            self.trace_context.end_span(
                status=SpanStatus.ERROR,
                error_class=type(e).__name__,
                error_message=str(e),
            )
            raise

    def create_checkpoint(self, description: str, state: dict[str, Any]) -> str:
        """Create a checkpoint for pause/resume."""
        state_data = json.dumps(state).encode()
        checkpoint = self.trace_store.create_checkpoint(
            trace_id=self.trace_id,
            step_number=self.result.capture.total_tool_calls if self.result.capture else 0,
            description=description,
            state_data=state_data,
        )
        if self.result.capture:
            self.result.capture.checkpoints += 1
        return checkpoint.checkpoint_id

    def run(self) -> WorkflowResult:
        """
        Execute the workflow.

        This is the main entry point that orchestrates the entire workflow.
        """
        # Validate configuration
        errors = self.config.validate()
        if errors:
            self.result.status = WorkflowStatus.FAILURE
            self.result.error = "; ".join(errors)
            return self.result

        self.result.status = WorkflowStatus.RUNNING
        self.result.started_at = datetime.now(UTC)
        self.result.capture = CaptureMetrics(session_id=self.trace_id)

        # Start workflow span
        _workflow_span_id = self.trace_context.start_span(
            kind=SpanKind.AGENT_TURN,
            name=f"workflow:{self.config.workflow_type.value}",
            actor_id="swe_workflow",
            attributes={
                "repo_path": str(self.config.repo_path),
                "workflow_type": self.config.workflow_type.value,
            },
        )

        try:
            # Step 1: Discover repo configuration
            self.discover_repo()

            # Create initial checkpoint
            self.create_checkpoint(
                description="Initial state after repo discovery",
                state={
                    "step": "repo_discovery_complete",
                    "repo_config": self.repo_config.to_dict() if self.repo_config else None,
                },
            )

            # Step 2: Execute workflow-specific logic
            if self.config.workflow_type == WorkflowType.FIX_FAILING_TEST:
                self._run_fix_failing_test()
            elif self.config.workflow_type == WorkflowType.IMPLEMENT_FEATURE:
                self._run_implement_feature()

            # Mark success if we got here
            if self.result.status == WorkflowStatus.RUNNING:
                self.result.status = WorkflowStatus.SUCCESS

            self.trace_context.end_span(status=SpanStatus.OK)

        except Exception as e:
            logger.exception(f"Workflow failed: {e}")
            self.result.status = WorkflowStatus.FAILURE
            self.result.error = str(e)
            self.trace_context.end_span(
                status=SpanStatus.ERROR,
                error_class=type(e).__name__,
                error_message=str(e),
            )

        finally:
            self.result.completed_at = datetime.now(UTC)
            if self.result.capture and self.result.started_at:
                self.result.capture.duration_seconds = (
                    self.result.completed_at - self.result.started_at
                ).total_seconds()

            # Get final metrics from trace store
            self._update_capture_metrics()

        return self.result

    def _run_fix_failing_test(self) -> None:
        """Execute the fix_failing_test workflow."""
        # This is a placeholder for the full implementation
        # In a complete implementation, this would:
        # 1. Run the failing test to understand the failure
        # 2. Analyze the test and related code
        # 3. Implement a fix
        # 4. Run tests to verify
        # 5. Create PR

        _span_id = self.trace_context.start_span(
            kind=SpanKind.AGENT_TURN,
            name="fix_failing_test",
            actor_id="swe_workflow",
            attributes={"test_identifier": self.config.test_identifier},
        )

        try:
            # Get test command from repo config
            test_cmd = None
            if self.repo_config:
                test_cmd_obj = self.repo_config.get_test_command()
                if test_cmd_obj:
                    test_cmd = test_cmd_obj.command

            # Create checkpoint before running tests
            self.create_checkpoint(
                description="Before running failing test",
                state={
                    "step": "pre_test_run",
                    "test_identifier": self.config.test_identifier,
                    "test_command": test_cmd,
                },
            )

            # Initialize test results (placeholder)
            self.result.test_results = TestResults(
                target_test="pending",
                regression_tests="pending",
            )

            # TODO: Integrate with agent loop to actually:
            # 1. Run the test and capture output
            # 2. Analyze the failure
            # 3. Find and fix the code
            # 4. Re-run tests
            # 5. Create PR

            logger.info(f"Would run test: {self.config.test_identifier}")
            logger.info(f"Using test command: {test_cmd}")

            self.trace_context.end_span(status=SpanStatus.OK)

        except Exception as e:
            self.trace_context.end_span(
                status=SpanStatus.ERROR,
                error_class=type(e).__name__,
                error_message=str(e),
            )
            raise

    def _run_implement_feature(self) -> None:
        """Execute the implement_feature workflow."""
        # This is a placeholder for the full implementation
        # In a complete implementation, this would:
        # 1. Understand the codebase structure
        # 2. Plan the implementation
        # 3. Implement the feature
        # 4. Write tests
        # 5. Run lint/format
        # 6. Create PR

        _span_id = self.trace_context.start_span(
            kind=SpanKind.AGENT_TURN,
            name="implement_feature",
            actor_id="swe_workflow",
            attributes={"feature_spec": self.config.feature_spec},
        )

        try:
            # Get lint/format commands from repo config
            lint_cmd = None
            format_cmd = None
            if self.repo_config:
                lint_cmd_obj = self.repo_config.get_lint_command()
                if lint_cmd_obj:
                    lint_cmd = lint_cmd_obj.command
                format_cmd_obj = self.repo_config.get_format_command()
                if format_cmd_obj:
                    format_cmd = format_cmd_obj.command

            # Create checkpoint before implementation
            self.create_checkpoint(
                description="Before implementing feature",
                state={
                    "step": "pre_implementation",
                    "feature_spec": self.config.feature_spec,
                    "lint_command": lint_cmd,
                    "format_command": format_cmd,
                },
            )

            # Initialize implementation details (placeholder)
            self.result.implementation = ImplementationDetails()

            # TODO: Integrate with agent loop to actually:
            # 1. Analyze codebase
            # 2. Plan implementation
            # 3. Write code
            # 4. Write tests
            # 5. Run lint/format
            # 6. Create PR

            logger.info(f"Would implement feature: {self.config.feature_spec}")
            logger.info(f"Using lint command: {lint_cmd}")
            logger.info(f"Using format command: {format_cmd}")

            self.trace_context.end_span(status=SpanStatus.OK)

        except Exception as e:
            self.trace_context.end_span(
                status=SpanStatus.ERROR,
                error_class=type(e).__name__,
                error_message=str(e),
            )
            raise

    def _update_capture_metrics(self) -> None:
        """Update capture metrics from trace store."""
        if not self.result.capture:
            return

        try:
            overview = self.trace_store.get_session_overview(self.trace_id)
            self.result.capture.total_llm_calls = overview.total_llm_calls
            self.result.capture.total_tool_calls = overview.total_tool_calls
            self.result.capture.total_tokens = overview.total_tokens
            self.result.capture.checkpoints = overview.checkpoints_available
        except Exception as e:
            logger.warning(f"Failed to get capture metrics: {e}")

    def pause(self) -> str:
        """Pause the workflow and return checkpoint ID for resume."""
        checkpoint_id = self.create_checkpoint(
            description="Manual pause",
            state={
                "step": "paused",
                "result": self.result.to_dict(),
            },
        )
        self.result.status = WorkflowStatus.PAUSED
        return checkpoint_id

    @classmethod
    def resume(
        cls,
        checkpoint_id: str,
        trace_store: TraceStore,
    ) -> "SWEWorkflow":
        """Resume a workflow from a checkpoint."""
        checkpoint = trace_store.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        state_data = trace_store.get_checkpoint_state(checkpoint_id)
        if not state_data:
            raise ValueError(f"Checkpoint state not found: {checkpoint_id}")

        state = json.loads(state_data.decode())

        # Reconstruct workflow from state
        # This is a simplified version - full implementation would
        # restore all state including message history
        result_dict = state.get("result", {})
        workflow_type = WorkflowType(result_dict.get("workflow", "fix_failing_test"))

        config = WorkflowConfig(
            repo_path=Path(state.get("repo_path", ".")),
            workflow_type=workflow_type,
        )

        workflow = cls(config, trace_store)
        workflow.trace_id = checkpoint.trace_id
        workflow.result.status = WorkflowStatus.RUNNING

        return workflow


def run_workflow(
    workflow_type: str,
    repo: str | Path,
    test: str | None = None,
    spec: str | None = None,
    trace_dir: Path | None = None,
) -> WorkflowResult:
    """
    Convenience function to run a workflow.

    This matches the interface defined in docs/swe-contract.md.

    Args:
        workflow_type: "fix_failing_test" or "implement_feature"
        repo: Path to the repository
        test: Test identifier (for fix_failing_test)
        spec: Feature specification (for implement_feature)
        trace_dir: Optional directory for trace storage

    Returns:
        WorkflowResult with status, PR URL, test results, etc.
    """
    config = WorkflowConfig(
        repo_path=Path(repo),
        workflow_type=WorkflowType(workflow_type),
        test_identifier=test,
        feature_spec=spec,
        trace_dir=trace_dir,
    )

    workflow = SWEWorkflow(config)
    return workflow.run()
