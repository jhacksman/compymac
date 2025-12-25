"""
SWE Workflow Runner - Phase 3 + Phase 4

Integrates repo discovery, agent loop, and trace store to execute
canonical SWE workflows as defined in docs/swe-contract.md.

Workflows:
1. Fix Failing Test - Given a repo and failing test, fix it and create PR
2. Implement Feature - Given a repo and spec, implement and create PR

Phase 4 adds actual agent loop integration for real LLM-driven execution.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.repo_discovery import RepoConfig, discover_repo
from compymac.trace_store import (
    SpanKind,
    SpanStatus,
    TraceContext,
    TraceStore,
    create_trace_store,
    generate_trace_id,
)

if TYPE_CHECKING:
    from compymac.agent_loop import AgentLoop
    from compymac.harness import Harness
    from compymac.llm import LLMClient

logger = logging.getLogger(__name__)


# System prompts for SWE workflows
FIX_FAILING_TEST_PROMPT = """You are an expert software engineer tasked with fixing a failing test.

## Repository Information
- Path: {repo_path}
- Language: {language}
- Package Manager: {package_manager}
- Test Command: {test_command}

## Task
Fix the failing test: {test_identifier}

## Workflow
1. First, run the failing test to understand the error
2. Analyze the test code and the code it tests
3. Identify the root cause of the failure
4. Implement a fix (prefer minimal changes)
5. Run the test again to verify the fix
6. Run the full test suite to check for regressions
7. If all tests pass, create a PR with your changes

## Constraints
- Make minimal changes to fix the issue
- Do not change test expectations unless they are clearly wrong
- Ensure no regressions in other tests
- Follow existing code style and conventions
"""

IMPLEMENT_FEATURE_PROMPT = """You are an expert software engineer tasked with implementing a new feature.

## Repository Information
- Path: {repo_path}
- Language: {language}
- Package Manager: {package_manager}
- Lint Command: {lint_command}
- Format Command: {format_command}
- Test Command: {test_command}

## Feature Specification
{feature_spec}

## Workflow
1. Analyze the codebase to understand the architecture
2. Plan the implementation (identify files to create/modify)
3. Implement the feature following existing patterns
4. Write tests for the new functionality
5. Run lint and format commands
6. Run the test suite to verify no regressions
7. Create a PR with your changes

## Constraints
- Follow existing code patterns and conventions
- Write comprehensive tests
- Ensure all lint checks pass
- Document public APIs
"""


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


class SWEPhase(str, Enum):
    """Phases of the SWE-bench workflow with programmatic enforcement.

    Based on analysis: natural language prompts are advisory, not constraints.
    Agents deviate under cognitive load. This enum enables hard enforcement
    of phase transitions via the advance_phase() tool.

    V2 (regression-aware): Split VERIFICATION into REGRESSION_CHECK + TARGET_FIX_VERIFICATION
    to prevent test overfitting (fixing target bug but breaking existing tests).
    Research: https://arxiv.org/html/2511.16858v1 shows LLMs overfit on fail_to_pass tests.
    """

    LOCALIZATION = "localization"  # Find suspect files, form hypothesis
    UNDERSTANDING = "understanding"  # Read code, understand root cause
    FIX = "fix"  # Edit files to implement fix
    REGRESSION_CHECK = "regression_check"  # Run pass_to_pass tests (no regressions)
    TARGET_FIX_VERIFICATION = "target_fix_verification"  # Run fail_to_pass tests (bug fixed)
    COMPLETE = "complete"  # Task finished


# Phase budget configuration: max tool calls and allowed tools per phase
# Budget-neutral tools (not counted): menu_*, think, git_diff_*, git_commit, complete, advance_phase
#
# V2 changes (regression-aware verification):
# - FIX: 10 -> 15 (more room for regression fixes)
# - VERIFICATION split into REGRESSION_CHECK (10) + TARGET_FIX_VERIFICATION (5)
# - REGRESSION_CHECK requires pass_to_pass_status output (mandatory)
# - TARGET_FIX_VERIFICATION requires fail_to_pass_status output (mandatory)
PHASE_BUDGETS: dict[SWEPhase, dict[str, Any]] = {
    SWEPhase.LOCALIZATION: {
        "max_tool_calls": 15,
        "required_outputs": ["suspect_files", "hypothesis"],
        "allowed_tools": ["grep", "glob", "web_search", "Read", "lsp_tool"],
        "description": "Find suspect files and form a hypothesis about the bug location",
    },
    SWEPhase.UNDERSTANDING: {
        "max_tool_calls": 20,
        "required_outputs": ["root_cause"],
        "allowed_tools": ["Read", "lsp_tool", "web_get_contents", "grep", "glob"],
        "description": "Read code to understand the root cause of the bug",
    },
    SWEPhase.FIX: {
        "max_tool_calls": 15,  # Increased from 10 for regression fixes
        "required_outputs": ["modified_files"],
        "allowed_tools": ["Edit", "Read"],
        "description": "Edit files to implement the fix",
    },
    SWEPhase.REGRESSION_CHECK: {
        "max_tool_calls": 10,
        "required_outputs": ["pass_to_pass_status"],  # MANDATORY: must verify no regressions
        "allowed_tools": ["bash", "Read", "analyze_test_failure"],
        "description": "Run pass_to_pass tests to verify no regressions. If any fail, return to FIX phase.",
    },
    SWEPhase.TARGET_FIX_VERIFICATION: {
        "max_tool_calls": 5,
        "required_outputs": ["fail_to_pass_status"],  # MANDATORY: must verify bug is fixed
        "allowed_tools": ["bash"],
        "description": "Run fail_to_pass tests to verify the bug is fixed",
    },
    SWEPhase.COMPLETE: {
        "max_tool_calls": 0,
        "required_outputs": [],
        "allowed_tools": ["complete"],
        "description": "Task finished",
    },
}

# Tools that don't count against phase budgets (budget accounting only)
# These tools can be called without consuming the phase's tool call budget.
# NOTE: This is separate from PHASE_NEUTRAL_TOOLS - budget-neutral != phase-neutral
BUDGET_NEUTRAL_TOOLS = [
    "think",  # Thinking doesn't consume budget
    "advance_phase",  # Phase transitions
    "get_phase_status",  # Phase inspection
    "return_to_fix_phase",  # Regression recovery
]

# Tools that can be called from ANY phase (phase-neutral)
# These bypass phase allowlist checking entirely.
# Keep this list minimal - most tools should be phase-restricted.
PHASE_NEUTRAL_TOOLS = [
    "think",  # Always allowed
    "advance_phase",  # Phase transitions must work from any phase
    "get_phase_status",  # Phase inspection always allowed
    "complete",  # CRITICAL: Must be callable from any phase to terminate agent loop
]


@dataclass
class SWEPhaseState:
    """Tracks current phase and tool call counts within an attempt.

    This enables intra-attempt budget enforcement: hard limits on tool calls
    per phase to prevent endless wandering.

    V2 (regression-aware): Added pass_to_pass_status and fail_to_pass_status
    to track verification results and prevent test overfitting.
    """

    current_phase: SWEPhase = SWEPhase.LOCALIZATION
    phase_tool_calls: dict[SWEPhase, int] = field(
        default_factory=lambda: dict.fromkeys(SWEPhase, 0)
    )

    # Outputs collected during phases (validated by advance_phase)
    suspect_files: list[str] = field(default_factory=list)
    hypothesis: str = ""
    root_cause: str = ""
    modified_files: list[str] = field(default_factory=list)

    # V2: Regression-aware verification outputs
    pass_to_pass_status: str = ""  # "all_passed" | "N_failed" (from REGRESSION_CHECK)
    fail_to_pass_status: str = ""  # "all_passed" | "N_failed" (from TARGET_FIX_VERIFICATION)
    broke_pass_to_pass: list[str] = field(default_factory=list)  # Tests that regressed

    def increment_tool_call(self, tool_name: str) -> None:
        """Increment tool call count for current phase (if not budget-neutral)."""
        if tool_name not in BUDGET_NEUTRAL_TOOLS:
            self.phase_tool_calls[self.current_phase] += 1

    def get_remaining_budget(self) -> int:
        """Get remaining tool calls for current phase."""
        budget = PHASE_BUDGETS[self.current_phase]["max_tool_calls"]
        used = self.phase_tool_calls[self.current_phase]
        return max(0, budget - used)

    def is_budget_exhausted(self) -> bool:
        """Check if current phase budget is exhausted."""
        return self.get_remaining_budget() <= 0

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed in the current phase.

        Uses PHASE_NEUTRAL_TOOLS (not BUDGET_NEUTRAL_TOOLS) to determine
        which tools bypass phase restrictions. Budget-neutrality is a
        separate concept handled by increment_tool_call().
        """
        if tool_name in PHASE_NEUTRAL_TOOLS:
            return True
        allowed = PHASE_BUDGETS[self.current_phase]["allowed_tools"]
        return tool_name in allowed

    def get_required_outputs(self) -> list[str]:
        """Get required outputs for current phase."""
        return PHASE_BUDGETS[self.current_phase]["required_outputs"]

    def validate_phase_outputs(self) -> tuple[bool, list[str]]:
        """Validate that required outputs are present for current phase.

        Returns (is_valid, missing_outputs).

        V2 (regression-aware): Added validation for pass_to_pass_status and fail_to_pass_status.
        """
        required = self.get_required_outputs()
        missing = []

        for output in required:
            if output == "suspect_files" and not self.suspect_files:
                missing.append("suspect_files")
            elif output == "hypothesis" and not self.hypothesis:
                missing.append("hypothesis")
            elif output == "root_cause" and not self.root_cause:
                missing.append("root_cause")
            elif output == "modified_files" and not self.modified_files:
                missing.append("modified_files")
            # V2: Regression-aware verification outputs
            elif output == "pass_to_pass_status" and not self.pass_to_pass_status:
                missing.append("pass_to_pass_status")
            elif output == "fail_to_pass_status" and not self.fail_to_pass_status:
                missing.append("fail_to_pass_status")

        return len(missing) == 0, missing

    def advance_to_next_phase(self) -> tuple[bool, str]:
        """Advance to the next phase if outputs are valid.

        Returns (success, message).

        V2 (regression-aware): Updated phase order to include REGRESSION_CHECK and
        TARGET_FIX_VERIFICATION. Also supports returning to FIX phase if regressions detected.
        """
        is_valid, missing = self.validate_phase_outputs()
        if not is_valid:
            return False, f"Cannot advance: missing required outputs: {', '.join(missing)}"

        # V2: Updated phase order with split verification
        phase_order = [
            SWEPhase.LOCALIZATION,
            SWEPhase.UNDERSTANDING,
            SWEPhase.FIX,
            SWEPhase.REGRESSION_CHECK,
            SWEPhase.TARGET_FIX_VERIFICATION,
            SWEPhase.COMPLETE,
        ]

        current_idx = phase_order.index(self.current_phase)
        if current_idx >= len(phase_order) - 1:
            return False, "Already at final phase (COMPLETE)"

        next_phase = phase_order[current_idx + 1]
        self.current_phase = next_phase
        budget = PHASE_BUDGETS[next_phase]["max_tool_calls"]
        return True, f"Advanced to {next_phase.value} phase. Budget: {budget} tool calls."

    def return_to_fix_phase(self, reason: str) -> tuple[bool, str]:
        """Return to FIX phase when regressions are detected.

        This is called when REGRESSION_CHECK finds broken pass_to_pass tests.
        The agent must fix the regression before proceeding.

        Args:
            reason: Description of why we're returning to FIX (e.g., which tests broke)

        Returns (success, message).
        """
        if self.current_phase != SWEPhase.REGRESSION_CHECK:
            return False, "Can only return to FIX from REGRESSION_CHECK phase"

        self.current_phase = SWEPhase.FIX
        # Reset FIX phase budget for regression fix
        self.phase_tool_calls[SWEPhase.FIX] = 0
        budget = PHASE_BUDGETS[SWEPhase.FIX]["max_tool_calls"]
        return True, f"Returned to FIX phase to address regression: {reason}. Budget: {budget} tool calls."

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "current_phase": self.current_phase.value,
            "phase_tool_calls": {k.value: v for k, v in self.phase_tool_calls.items()},
            "suspect_files": self.suspect_files,
            "hypothesis": self.hypothesis,
            "root_cause": self.root_cause,
            "modified_files": self.modified_files,
            # V2: Regression-aware verification outputs
            "pass_to_pass_status": self.pass_to_pass_status,
            "fail_to_pass_status": self.fail_to_pass_status,
            "broke_pass_to_pass": self.broke_pass_to_pass,
        }


@dataclass
class AttemptState:
    """Persists state across attempts for inter-attempt learning.

    This is CRITICAL: the real problem is multi-attempt failure where each
    attempt restarts from scratch without learning from previous findings.
    This dataclass captures what was learned and what failed so attempt 2+
    can build on previous work instead of repeating it.

    V2 (regression-aware): Added fail_to_pass_results, pass_to_pass_results,
    broke_pass_to_pass, regression_summary, and changes_that_caused_regression
    to enable learning from regressions across attempts.
    """

    attempt_number: int = 1

    # Localization findings from previous attempts
    localization_findings: list[str] = field(default_factory=list)
    hypothesis: str = ""
    suspect_files: list[str] = field(default_factory=list)

    # What went wrong in previous attempt
    what_failed: str = ""
    failing_test_output: str = ""

    # What to try differently
    next_approach: str = ""

    # Current state of the repo (for awareness of accumulated changes)
    modified_files: list[str] = field(default_factory=list)
    git_diff_summary: str = ""

    # V2: Regression-aware tracking - separate fail_to_pass vs pass_to_pass
    fail_to_pass_results: dict[str, bool] = field(default_factory=dict)  # {test: passed}
    pass_to_pass_results: dict[str, bool] = field(default_factory=dict)  # {test: passed}

    # V2: Regression analysis
    broke_pass_to_pass: list[str] = field(default_factory=list)  # Tests that regressed
    regression_summary: str = ""  # e.g., "Broke 17 tests related to pytest parsing"
    changes_that_caused_regression: str = ""  # What to avoid in next attempt

    def to_grounding_context(self) -> dict[str, Any]:
        """Convert to grounding context for injection into agent prompt.

        This is injected into attempt 2+ to provide cross-attempt learning.

        V2: Now includes regression-aware test results to help agent understand
        which tests broke and why, enabling targeted fixes without re-breaking.
        """
        # V2: Calculate pass/fail summary for fail_to_pass and pass_to_pass
        f2p_passed = sum(1 for v in self.fail_to_pass_results.values() if v)
        f2p_total = len(self.fail_to_pass_results)
        p2p_passed = sum(1 for v in self.pass_to_pass_results.values() if v)
        p2p_total = len(self.pass_to_pass_results)

        return {
            "attempt_number": self.attempt_number,
            "previous_findings": {
                "localization": self.localization_findings,
                "hypothesis": self.hypothesis,
                "suspect_files": self.suspect_files,
            },
            "previous_failure": {
                "what_failed": self.what_failed,
                "test_output": self.failing_test_output[:500] if self.failing_test_output else "",
            },
            "suggested_approach": self.next_approach,
            "repo_state": {
                "modified_files": self.modified_files,
                "has_uncommitted_changes": bool(self.git_diff_summary),
            },
            # V2: Regression-aware test results
            "test_results": {
                "fail_to_pass": f"{f2p_passed}/{f2p_total} passed" if f2p_total else "not run",
                "pass_to_pass": f"{p2p_passed}/{p2p_total} passed" if p2p_total else "not run",
                "broke_tests": self.broke_pass_to_pass[:10],  # Limit to 10 for context
                "regression_summary": self.regression_summary,
            },
            # V2: What to avoid in next attempt
            "avoid": self.changes_that_caused_regression if self.changes_that_caused_regression else None,
        }

    def to_prompt_injection(self) -> str:
        """Format as a prompt injection for the agent.

        This is a compact, structured summary that helps the agent
        avoid repeating previous mistakes.

        V2: Now includes regression-aware test results with specific guidance
        on which tests broke and what changes to avoid.
        """
        lines = [
            f"## Previous Attempt Summary (Attempt {self.attempt_number - 1})",
            "",
        ]

        if self.localization_findings:
            lines.append("### Localization Findings")
            for finding in self.localization_findings:
                lines.append(f"- {finding}")
            lines.append("")

        if self.hypothesis:
            lines.append(f"### Hypothesis: {self.hypothesis}")
            lines.append("")

        if self.suspect_files:
            lines.append(f"### Suspect Files: {', '.join(self.suspect_files)}")
            lines.append("")

        if self.what_failed:
            lines.append(f"### What Failed: {self.what_failed}")
            lines.append("")

        # V2: Add regression-aware test results
        if self.fail_to_pass_results or self.pass_to_pass_results:
            lines.append("### Test Results from Previous Attempt")
            if self.fail_to_pass_results:
                f2p_passed = sum(1 for v in self.fail_to_pass_results.values() if v)
                f2p_total = len(self.fail_to_pass_results)
                status = "PASSED" if f2p_passed == f2p_total else "FAILED"
                lines.append(f"- fail_to_pass: {f2p_passed}/{f2p_total} {status}")
            if self.pass_to_pass_results:
                p2p_passed = sum(1 for v in self.pass_to_pass_results.values() if v)
                p2p_total = len(self.pass_to_pass_results)
                status = "PASSED" if p2p_passed == p2p_total else "REGRESSION"
                lines.append(f"- pass_to_pass: {p2p_passed}/{p2p_total} {status}")
            lines.append("")

        # V2: Highlight broken tests (regressions)
        if self.broke_pass_to_pass:
            lines.append("### REGRESSIONS DETECTED - Tests That Broke")
            for test in self.broke_pass_to_pass[:10]:  # Limit to 10
                lines.append(f"- {test}")
            if len(self.broke_pass_to_pass) > 10:
                lines.append(f"- ... and {len(self.broke_pass_to_pass) - 10} more")
            lines.append("")

        # V2: Add regression summary
        if self.regression_summary:
            lines.append(f"### Regression Summary: {self.regression_summary}")
            lines.append("")

        # V2: Add specific guidance on what to avoid
        if self.changes_that_caused_regression:
            lines.append("### AVOID THESE CHANGES (caused regressions)")
            lines.append(self.changes_that_caused_regression)
            lines.append("")

        if self.next_approach:
            lines.append(f"### Suggested Next Approach: {self.next_approach}")
            lines.append("")

        if self.modified_files:
            lines.append(f"### Currently Modified Files: {', '.join(self.modified_files)}")
            lines.append("(These changes persist from previous attempt)")
            lines.append("")

        lines.append("DO NOT repeat the same approach that failed. Try something different.")
        if self.broke_pass_to_pass:
            lines.append("CRITICAL: Your fix must NOT break any pass_to_pass tests.")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "attempt_number": self.attempt_number,
            "localization_findings": self.localization_findings,
            "hypothesis": self.hypothesis,
            "suspect_files": self.suspect_files,
            "what_failed": self.what_failed,
            "failing_test_output": self.failing_test_output,
            "next_approach": self.next_approach,
            "modified_files": self.modified_files,
            "git_diff_summary": self.git_diff_summary,
            # V2: Regression-aware fields
            "fail_to_pass_results": self.fail_to_pass_results,
            "pass_to_pass_results": self.pass_to_pass_results,
            "broke_pass_to_pass": self.broke_pass_to_pass,
            "regression_summary": self.regression_summary,
            "changes_that_caused_regression": self.changes_that_caused_regression,
        }

    @classmethod
    def from_phase_state(
        cls,
        phase_state: "SWEPhaseState",
        attempt_number: int,
        what_failed: str,
        failing_test_output: str,
        next_approach: str,
        modified_files: list[str],
        git_diff_summary: str,
        # V2: Regression-aware parameters
        fail_to_pass_results: dict[str, bool] | None = None,
        pass_to_pass_results: dict[str, bool] | None = None,
        regression_summary: str = "",
        changes_that_caused_regression: str = "",
    ) -> "AttemptState":
        """Create AttemptState from a completed SWEPhaseState.

        This is called at the end of each failed attempt to capture
        what was learned for the next attempt.

        V2: Now accepts regression-aware parameters to track which tests
        broke and why, enabling targeted fixes in subsequent attempts.
        """
        # V2: Calculate broke_pass_to_pass from pass_to_pass_results
        broke_tests = []
        if pass_to_pass_results:
            broke_tests = [test for test, passed in pass_to_pass_results.items() if not passed]

        return cls(
            attempt_number=attempt_number + 1,
            localization_findings=[
                f"Suspect files: {', '.join(phase_state.suspect_files)}",
                f"Hypothesis: {phase_state.hypothesis}",
            ] if phase_state.suspect_files else [],
            hypothesis=phase_state.hypothesis,
            suspect_files=phase_state.suspect_files,
            what_failed=what_failed,
            failing_test_output=failing_test_output,
            next_approach=next_approach,
            modified_files=modified_files,
            git_diff_summary=git_diff_summary,
            # V2: Regression-aware fields
            fail_to_pass_results=fail_to_pass_results or {},
            pass_to_pass_results=pass_to_pass_results or {},
            broke_pass_to_pass=broke_tests,
            regression_summary=regression_summary,
            changes_that_caused_regression=changes_that_caused_regression,
        )


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
    max_steps: int = 50  # Max agent loop steps
    use_agent_loop: bool = True  # Whether to use agent loop for execution

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
    - Agent loop (Phase 4) for LLM-driven execution
    """

    def __init__(
        self,
        config: WorkflowConfig,
        trace_store: TraceStore | None = None,
        harness: "Harness | None" = None,
        llm_client: "LLMClient | None" = None,
    ):
        self.config = config
        self.repo_config: RepoConfig | None = None
        self.trace_id = generate_trace_id()
        self.result = WorkflowResult(
            workflow=config.workflow_type,
            status=WorkflowStatus.PENDING,
        )

        # Store harness and LLM client for agent loop
        self._harness = harness
        self._llm_client = llm_client
        self._agent_loop: AgentLoop | None = None

        # Set up trace store
        if trace_store:
            self.trace_store = trace_store
        else:
            trace_dir = config.trace_dir or (config.repo_path / ".compymac" / "traces")
            self.trace_store, _ = create_trace_store(trace_dir)

        self.trace_context = TraceContext(self.trace_store, self.trace_id)

    def _create_agent_loop(self, system_prompt: str) -> "AgentLoop":
        """Create an agent loop with the given system prompt."""
        from compymac.agent_loop import AgentConfig, AgentLoop

        if not self._harness:
            raise ValueError("Harness is required for agent loop execution")
        if not self._llm_client:
            raise ValueError("LLM client is required for agent loop execution")

        config = AgentConfig(
            max_steps=self.config.max_steps,
            system_prompt=system_prompt,
            stop_on_error=False,
            use_memory=True,
        )

        self._agent_loop = AgentLoop(
            harness=self._harness,
            llm_client=self._llm_client,
            config=config,
            trace_context=self.trace_context,
        )

        return self._agent_loop

    def _run_with_agent(self, task_description: str) -> str:
        """Run a task using the agent loop and return the final response."""
        if not self._agent_loop:
            raise ValueError("Agent loop not initialized")

        # Create checkpoint before agent execution
        self.create_checkpoint(
            description=f"Before agent execution: {task_description[:50]}...",
            state={
                "step": "pre_agent_execution",
                "task": task_description,
            },
        )

        # Run the agent loop
        response = self._agent_loop.run(task_description)

        # Create checkpoint after agent execution
        self.create_checkpoint(
            description="After agent execution",
            state={
                "step": "post_agent_execution",
                "response": response[:500] if response else "",
                "step_count": self._agent_loop.state.step_count,
                "tool_call_count": self._agent_loop.state.tool_call_count,
            },
        )

        return response

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

            # Initialize test results
            self.result.test_results = TestResults(
                target_test="pending",
                regression_tests="pending",
            )

            # Use agent loop if available and enabled
            if self.config.use_agent_loop and self._harness and self._llm_client:
                # Build system prompt with repo context
                system_prompt = FIX_FAILING_TEST_PROMPT.format(
                    repo_path=str(self.config.repo_path),
                    language=self.repo_config.language if self.repo_config else "unknown",
                    package_manager=self.repo_config.package_manager
                    if self.repo_config
                    else "unknown",
                    test_command=test_cmd or "unknown",
                    test_identifier=self.config.test_identifier,
                )

                # Create agent loop and run
                self._create_agent_loop(system_prompt)
                task = f"Fix the failing test: {self.config.test_identifier}"
                response = self._run_with_agent(task)

                # Parse response to determine test results
                # (In a full implementation, we'd parse structured output)
                if "all tests pass" in response.lower() or "fixed" in response.lower():
                    self.result.test_results.target_test = "pass"
                    self.result.test_results.regression_tests = "pass"
                else:
                    self.result.test_results.target_test = "fail"

                logger.info(f"Agent completed fix_failing_test: {response[:200]}...")
            else:
                # Fallback: log what would happen (for testing without LLM)
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
        _span_id = self.trace_context.start_span(
            kind=SpanKind.AGENT_TURN,
            name="implement_feature",
            actor_id="swe_workflow",
            attributes={"feature_spec": self.config.feature_spec},
        )

        try:
            # Get lint/format/test commands from repo config
            lint_cmd = None
            format_cmd = None
            test_cmd = None
            if self.repo_config:
                lint_cmd_obj = self.repo_config.get_lint_command()
                if lint_cmd_obj:
                    lint_cmd = lint_cmd_obj.command
                format_cmd_obj = self.repo_config.get_format_command()
                if format_cmd_obj:
                    format_cmd = format_cmd_obj.command
                test_cmd_obj = self.repo_config.get_test_command()
                if test_cmd_obj:
                    test_cmd = test_cmd_obj.command

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

            # Initialize implementation details
            self.result.implementation = ImplementationDetails()

            # Use agent loop if available and enabled
            if self.config.use_agent_loop and self._harness and self._llm_client:
                # Build system prompt with repo context
                system_prompt = IMPLEMENT_FEATURE_PROMPT.format(
                    repo_path=str(self.config.repo_path),
                    language=self.repo_config.language if self.repo_config else "unknown",
                    package_manager=self.repo_config.package_manager
                    if self.repo_config
                    else "unknown",
                    lint_command=lint_cmd or "unknown",
                    format_command=format_cmd or "unknown",
                    test_command=test_cmd or "unknown",
                    feature_spec=self.config.feature_spec,
                )

                # Create agent loop and run
                self._create_agent_loop(system_prompt)
                task = f"Implement the following feature:\n\n{self.config.feature_spec}"
                response = self._run_with_agent(task)

                # Parse response to extract implementation details
                # (In a full implementation, we'd parse structured output)
                if "created" in response.lower():
                    # Try to count files mentioned
                    self.result.implementation.files_created = []
                if "modified" in response.lower():
                    self.result.implementation.files_modified = []

                logger.info(f"Agent completed implement_feature: {response[:200]}...")
            else:
                # Fallback: log what would happen (for testing without LLM)
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
    harness: "Harness | None" = None,
    llm_client: "LLMClient | None" = None,
    max_steps: int = 50,
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
        harness: Optional harness for tool execution (enables agent loop)
        llm_client: Optional LLM client (enables agent loop)
        max_steps: Maximum agent loop steps (default 50)

    Returns:
        WorkflowResult with status, PR URL, test results, etc.

    Note:
        If harness and llm_client are not provided, the workflow will run
        in "dry run" mode, logging what it would do without actually
        executing any LLM-driven actions.
    """
    config = WorkflowConfig(
        repo_path=Path(repo),
        workflow_type=WorkflowType(workflow_type),
        test_identifier=test,
        feature_spec=spec,
        trace_dir=trace_dir,
        max_steps=max_steps,
        use_agent_loop=harness is not None and llm_client is not None,
    )

    workflow = SWEWorkflow(config, harness=harness, llm_client=llm_client)
    return workflow.run()
