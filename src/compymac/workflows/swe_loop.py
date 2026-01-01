"""
SWEWorkflow - Full SWE Loop orchestration.

This module implements Gap 3: Workflow Closure by providing:
- Workflow state machine with stages: UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE
- Feedback loop integration (test execution, static analysis)
- Artifact storage for debugging and review

Based on arxiv research - see docs/GAP3_WORKFLOW_CLOSURE_RESEARCH.md

Key papers informing design:
- SWE-agent (arXiv:2405.15793): Agent-Computer Interface design
- HyperAgent (OpenReview): Four-agent architecture patterns
- Meta Engineering Agent (arXiv:2507.18755): ReAct harness, feedback loops
- RepairAgent (arXiv:2403.17134): FSM-guided tool invocation
"""

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowStage(Enum):
    """Stages of the SWE workflow (from HyperAgent + Meta patterns)."""
    UNDERSTAND = "understand"
    PLAN = "plan"
    LOCATE = "locate"
    MODIFY = "modify"
    VALIDATE = "validate"
    DEBUG = "debug"
    PR = "pr"
    CI = "ci"
    ITERATE = "iterate"
    COMPLETE = "complete"
    FAILED = "failed"


class WorkflowStatus(Enum):
    """Overall workflow status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class StageResult:
    """Result of executing a workflow stage."""
    stage: WorkflowStage
    success: bool
    message: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "stage": self.stage.value,
            "success": self.success,
            "message": self.message,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SWEWorkflow:
    """
    Full SWE Loop workflow orchestrator.

    Implements the workflow: UNDERSTAND -> PLAN -> LOCATE -> MODIFY -> VALIDATE -> DEBUG -> PR -> CI -> ITERATE

    Key features:
    - Stage-based state machine with validation criteria
    - Feedback loops for test execution and static analysis
    - Retry logic with backoff
    - Artifact storage for debugging
    """
    task_description: str
    repo_path: Path
    current_stage: WorkflowStage = WorkflowStage.UNDERSTAND
    status: WorkflowStatus = WorkflowStatus.NOT_STARTED
    stage_results: list[StageResult] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Stage-specific data
    understanding: dict[str, Any] = field(default_factory=dict)
    plan: list[str] = field(default_factory=list)
    located_files: list[str] = field(default_factory=list)
    modifications: list[dict[str, Any]] = field(default_factory=list)
    validation_results: dict[str, Any] = field(default_factory=dict)
    debug_info: list[str] = field(default_factory=list)
    pr_info: dict[str, Any] = field(default_factory=dict)
    ci_status: dict[str, Any] = field(default_factory=dict)

    # Stage order for advancement
    STAGE_ORDER = [
        WorkflowStage.UNDERSTAND,
        WorkflowStage.PLAN,
        WorkflowStage.LOCATE,
        WorkflowStage.MODIFY,
        WorkflowStage.VALIDATE,
        WorkflowStage.DEBUG,
        WorkflowStage.PR,
        WorkflowStage.CI,
        WorkflowStage.ITERATE,
        WorkflowStage.COMPLETE,
    ]

    def _get_next_stage(self) -> WorkflowStage | None:
        """Get the next stage in the workflow."""
        try:
            current_idx = self.STAGE_ORDER.index(self.current_stage)
            if current_idx < len(self.STAGE_ORDER) - 1:
                return self.STAGE_ORDER[current_idx + 1]
        except ValueError:
            pass
        return None

    def advance(self, result: StageResult) -> bool:
        """
        Advance to next stage if current stage is complete.

        Args:
            result: Result of the current stage execution

        Returns:
            True if advanced to next stage, False otherwise
        """
        self.stage_results.append(result)
        self.updated_at = datetime.utcnow()

        if not result.success:
            # Check if we should retry or fail
            if self.iteration_count >= self.max_iterations:
                self.status = WorkflowStatus.FAILED
                self.current_stage = WorkflowStage.FAILED
                return False

            # Go to DEBUG stage for failure analysis
            if self.current_stage != WorkflowStage.DEBUG:
                self.current_stage = WorkflowStage.DEBUG
                return True

            return False

        # Special handling for certain stages
        if self.current_stage == WorkflowStage.VALIDATE:
            if not result.artifacts.get("tests_passed", False):
                self.current_stage = WorkflowStage.DEBUG
                return True

        if self.current_stage == WorkflowStage.CI:
            if not result.artifacts.get("ci_passed", False):
                self.current_stage = WorkflowStage.ITERATE
                self.iteration_count += 1
                return True

        if self.current_stage == WorkflowStage.DEBUG:
            # After debugging, go back to MODIFY
            self.current_stage = WorkflowStage.MODIFY
            self.iteration_count += 1
            return True

        if self.current_stage == WorkflowStage.ITERATE:
            # After iteration, go back to MODIFY
            self.current_stage = WorkflowStage.MODIFY
            return True

        # Normal advancement
        next_stage = self._get_next_stage()
        if next_stage:
            self.current_stage = next_stage
            if next_stage == WorkflowStage.COMPLETE:
                self.status = WorkflowStatus.COMPLETE
            return True

        return False

    def retry(self, max_attempts: int = 3) -> bool:
        """
        Retry current stage with different approach.

        Args:
            max_attempts: Maximum retry attempts

        Returns:
            True if retry is allowed, False if max attempts reached
        """
        stage_attempts = sum(
            1 for r in self.stage_results
            if r.stage == self.current_stage
        )

        if stage_attempts >= max_attempts:
            return False

        self.updated_at = datetime.utcnow()
        return True

    def get_artifacts(self) -> dict[str, Any]:
        """Return all artifacts from workflow execution."""
        artifacts = {
            "understanding": self.understanding,
            "plan": self.plan,
            "located_files": self.located_files,
            "modifications": self.modifications,
            "validation_results": self.validation_results,
            "debug_info": self.debug_info,
            "pr_info": self.pr_info,
            "ci_status": self.ci_status,
            "stage_results": [r.to_dict() for r in self.stage_results],
        }
        return artifacts

    def get_stage_prompt(self) -> str:
        """Get the prompt/instructions for the current stage."""
        prompts = {
            WorkflowStage.UNDERSTAND: f"""
STAGE: UNDERSTAND
Task: {self.task_description}

Analyze the task and identify:
1. What needs to be changed/implemented
2. What files/components are likely involved
3. What tests need to pass
4. Any constraints or requirements

Output your understanding as structured data.
""",
            WorkflowStage.PLAN: f"""
STAGE: PLAN
Understanding: {self.understanding}

Create a step-by-step plan:
1. List specific files to modify
2. List specific changes to make
3. List tests to run
4. Identify potential issues

Output as a numbered list of actionable steps.
""",
            WorkflowStage.LOCATE: f"""
STAGE: LOCATE
Plan: {self.plan}

Find the relevant files in the repository:
1. Search for files mentioned in the plan
2. Identify related files that may need changes
3. Find test files

Output the list of file paths.
""",
            WorkflowStage.MODIFY: f"""
STAGE: MODIFY
Files to modify: {self.located_files}
Plan: {self.plan}
Previous debug info: {self.debug_info}

Make the code changes using search-replace format:
<<<<<<< SEARCH
old code
=======
new code
>>>>>>> REPLACE

Apply changes to implement the plan.
""",
            WorkflowStage.VALIDATE: f"""
STAGE: VALIDATE
Modifications: {len(self.modifications)} changes made

Run validation:
1. Run tests: pytest or appropriate test runner
2. Run linter: ruff check or appropriate linter
3. Run type checker: mypy or pyright if applicable

Report results for each validation step.
""",
            WorkflowStage.DEBUG: f"""
STAGE: DEBUG
Validation results: {self.validation_results}
Errors: {[r.errors for r in self.stage_results if r.errors]}

Analyze failures:
1. Parse error messages
2. Identify root cause
3. Determine fix approach

Output debug analysis and recommended fixes.
""",
            WorkflowStage.PR: """
STAGE: PR
All validations passed.

Create pull request:
1. Create descriptive branch name
2. Commit changes with clear message
3. Push to remote
4. Create PR with description

Output PR URL and number.
""",
            WorkflowStage.CI: f"""
STAGE: CI
PR created: {self.pr_info}

Monitor CI:
1. Poll CI status
2. Parse CI logs if failed
3. Identify actionable errors

Output CI status and any errors.
""",
            WorkflowStage.ITERATE: f"""
STAGE: ITERATE
CI Status: {self.ci_status}
Iteration: {self.iteration_count}/{self.max_iterations}

Fix CI failures:
1. Parse CI error logs
2. Apply fixes
3. Push new commit

Continue until CI passes or max iterations reached.
""",
        }
        return prompts.get(self.current_stage, "Unknown stage")

    def set_understanding(self, understanding: dict[str, Any]) -> None:
        """Set the task understanding."""
        self.understanding = understanding
        self.updated_at = datetime.utcnow()

    def set_plan(self, plan: list[str]) -> None:
        """Set the execution plan."""
        self.plan = plan
        self.updated_at = datetime.utcnow()

    def set_located_files(self, files: list[str]) -> None:
        """Set the located files."""
        self.located_files = files
        self.updated_at = datetime.utcnow()

    def add_modification(self, file_path: str, change: dict[str, Any]) -> None:
        """Add a code modification."""
        self.modifications.append({
            "file": file_path,
            "change": change,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.updated_at = datetime.utcnow()

    def set_validation_results(self, results: dict[str, Any]) -> None:
        """Set validation results."""
        self.validation_results = results
        self.updated_at = datetime.utcnow()

    def add_debug_info(self, info: str) -> None:
        """Add debug information."""
        self.debug_info.append(info)
        self.updated_at = datetime.utcnow()

    def set_pr_info(self, pr_url: str, pr_number: int, branch: str) -> None:
        """Set PR information."""
        self.pr_info = {
            "url": pr_url,
            "number": pr_number,
            "branch": branch,
        }
        self.updated_at = datetime.utcnow()

    def set_ci_status(self, passed: bool, details: dict[str, Any] | None = None) -> None:
        """Set CI status."""
        self.ci_status = {
            "passed": passed,
            "details": details or {},
            "checked_at": datetime.utcnow().isoformat(),
        }
        self.updated_at = datetime.utcnow()

    def run_tests(self, test_command: str | None = None) -> tuple[bool, str, list[str]]:
        """
        Run tests and return results.

        Args:
            test_command: Custom test command (defaults to pytest)

        Returns:
            Tuple of (passed, output, errors)
        """
        cmd = test_command or "pytest"
        try:
            result = subprocess.run(
                cmd.split(),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            errors = self._parse_test_errors(output) if not passed else []
            return passed, output, errors
        except subprocess.TimeoutExpired:
            return False, "Test execution timed out", ["timeout"]
        except Exception as e:
            return False, str(e), [str(e)]

    def run_lint(self, lint_command: str | None = None) -> tuple[bool, str, list[str]]:
        """
        Run linter and return results.

        Args:
            lint_command: Custom lint command (defaults to ruff check)

        Returns:
            Tuple of (passed, output, errors)
        """
        cmd = lint_command or "ruff check ."
        try:
            result = subprocess.run(
                cmd.split(),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            passed = result.returncode == 0
            errors = self._parse_lint_errors(output) if not passed else []
            return passed, output, errors
        except subprocess.TimeoutExpired:
            return False, "Lint execution timed out", ["timeout"]
        except Exception as e:
            return False, str(e), [str(e)]

    def _parse_test_errors(self, output: str) -> list[str]:
        """Parse test output for actionable errors."""
        errors = []
        lines = output.split("\n")
        for i, line in enumerate(lines):
            if "FAILED" in line or "ERROR" in line:
                errors.append(line.strip())
            if "AssertionError" in line or "Exception" in line:
                # Include context
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = "\n".join(lines[start:end])
                errors.append(context)
        return errors[:10]  # Limit to 10 errors

    def _parse_lint_errors(self, output: str) -> list[str]:
        """Parse lint output for actionable errors."""
        errors = []
        for line in output.split("\n"):
            line = line.strip()
            if line and ":" in line and not line.startswith("Found"):
                errors.append(line)
        return errors[:20]  # Limit to 20 errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize workflow to dictionary."""
        return {
            "task_description": self.task_description,
            "repo_path": str(self.repo_path),
            "current_stage": self.current_stage.value,
            "status": self.status.value,
            "stage_results": [r.to_dict() for r in self.stage_results],
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "understanding": self.understanding,
            "plan": self.plan,
            "located_files": self.located_files,
            "modifications": self.modifications,
            "validation_results": self.validation_results,
            "debug_info": self.debug_info,
            "pr_info": self.pr_info,
            "ci_status": self.ci_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SWEWorkflow":
        """Deserialize workflow from dictionary."""
        workflow = cls(
            task_description=data["task_description"],
            repo_path=Path(data["repo_path"]),
            current_stage=WorkflowStage(data.get("current_stage", "understand")),
            status=WorkflowStatus(data.get("status", "not_started")),
            iteration_count=data.get("iteration_count", 0),
            max_iterations=data.get("max_iterations", 5),
            understanding=data.get("understanding", {}),
            plan=data.get("plan", []),
            located_files=data.get("located_files", []),
            modifications=data.get("modifications", []),
            validation_results=data.get("validation_results", {}),
            debug_info=data.get("debug_info", []),
            pr_info=data.get("pr_info", {}),
            ci_status=data.get("ci_status", {}),
        )

        # Parse timestamps
        if data.get("created_at"):
            workflow.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            workflow.updated_at = datetime.fromisoformat(data["updated_at"])

        # Parse stage results
        for result_data in data.get("stage_results", []):
            result = StageResult(
                stage=WorkflowStage(result_data["stage"]),
                success=result_data["success"],
                message=result_data["message"],
                artifacts=result_data.get("artifacts", {}),
                errors=result_data.get("errors", []),
                duration_ms=result_data.get("duration_ms", 0),
            )
            if result_data.get("timestamp"):
                result.timestamp = datetime.fromisoformat(result_data["timestamp"])
            workflow.stage_results.append(result)

        return workflow
