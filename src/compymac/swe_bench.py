"""
SWE-Bench Integration - Benchmark runner for measuring agent performance.

This module provides integration with the SWE-bench benchmark suite,
enabling systematic evaluation of CompyMac's ability to solve real
GitHub issues from popular Python repositories.

Gap 4 from docs/real-gaps-implementation-plans.md
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from compymac.harness import Harness
    from compymac.llm import LLMClient


@dataclass
class SWEBenchTask:
    """A single SWE-bench task representing a GitHub issue to solve."""

    instance_id: str  # e.g., "django__django-12345"
    repo: str  # e.g., "django/django"
    version: str  # Git commit hash of base version

    # The task
    problem_statement: str  # GitHub issue description
    hints_text: str = ""  # Optional hints

    # Ground truth
    gold_patch: str = ""  # The actual fix (for reference)
    test_patch: str = ""  # Test patch to apply

    # Evaluation
    fail_to_pass: list[str] = field(default_factory=list)  # Tests that should start failing, then pass
    pass_to_pass: list[str] = field(default_factory=list)  # Tests that should keep passing

    # Metadata
    created_at: str = ""
    difficulty: str = "medium"  # "easy", "medium", "hard"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "instance_id": self.instance_id,
            "repo": self.repo,
            "version": self.version,
            "problem_statement": self.problem_statement,
            "hints_text": self.hints_text,
            "gold_patch": self.gold_patch,
            "test_patch": self.test_patch,
            "fail_to_pass": self.fail_to_pass,
            "pass_to_pass": self.pass_to_pass,
            "created_at": self.created_at,
            "difficulty": self.difficulty,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SWEBenchTask:
        """Create from dictionary."""
        return cls(
            instance_id=data["instance_id"],
            repo=data["repo"],
            version=data["version"],
            problem_statement=data["problem_statement"],
            hints_text=data.get("hints_text", ""),
            gold_patch=data.get("gold_patch", ""),
            test_patch=data.get("test_patch", ""),
            fail_to_pass=data.get("fail_to_pass", []),
            pass_to_pass=data.get("pass_to_pass", []),
            created_at=data.get("created_at", ""),
            difficulty=data.get("difficulty", "medium"),
        )


@dataclass
class TestResults:
    """Results of running tests on a patched repository."""

    fail_to_pass: dict[str, bool]  # {test_name: passed}
    pass_to_pass: dict[str, bool]  # {test_name: passed}

    @property
    def all_fail_to_pass_passed(self) -> bool:
        """Check if all fail_to_pass tests now pass."""
        return all(self.fail_to_pass.values()) if self.fail_to_pass else False

    @property
    def all_pass_to_pass_passed(self) -> bool:
        """Check if all pass_to_pass tests still pass."""
        return all(self.pass_to_pass.values()) if self.pass_to_pass else True


@dataclass
class SWEBenchResult:
    """Result of running a single SWE-bench task."""

    instance_id: str

    # Outcome
    resolved: bool  # All fail_to_pass now pass, all pass_to_pass still pass
    partial: bool  # Some fail_to_pass pass
    failed: bool  # No improvement or broke existing tests

    # Metrics
    fail_to_pass_results: dict[str, bool]  # {test_name: passed}
    pass_to_pass_results: dict[str, bool]

    # Execution info
    patch_generated: str  # The patch our agent created
    tool_calls_made: int
    tokens_used: int
    time_elapsed_sec: float

    # Trace info
    trace_id: str  # Link to TraceStore
    error_log: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "instance_id": self.instance_id,
            "resolved": self.resolved,
            "partial": self.partial,
            "failed": self.failed,
            "fail_to_pass_results": self.fail_to_pass_results,
            "pass_to_pass_results": self.pass_to_pass_results,
            "patch_generated": self.patch_generated,
            "tool_calls_made": self.tool_calls_made,
            "tokens_used": self.tokens_used,
            "time_elapsed_sec": self.time_elapsed_sec,
            "trace_id": self.trace_id,
            "error_log": self.error_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SWEBenchResult:
        """Create from dictionary."""
        return cls(
            instance_id=data["instance_id"],
            resolved=data["resolved"],
            partial=data["partial"],
            failed=data["failed"],
            fail_to_pass_results=data["fail_to_pass_results"],
            pass_to_pass_results=data["pass_to_pass_results"],
            patch_generated=data["patch_generated"],
            tool_calls_made=data["tool_calls_made"],
            tokens_used=data["tokens_used"],
            time_elapsed_sec=data["time_elapsed_sec"],
            trace_id=data["trace_id"],
            error_log=data.get("error_log", ""),
        )


@dataclass
class SWEBenchEvaluation:
    """Aggregated results across multiple tasks."""

    total_tasks: int
    resolved: int
    partial: int
    failed: int

    # Metrics
    resolve_rate: float  # resolved / total
    partial_rate: float  # partial / total

    # Breakdowns
    by_difficulty: dict[str, dict[str, int]]  # {difficulty: {outcome: count}}
    by_repo: dict[str, dict[str, int]]  # {repo: {outcome: count}}

    # Resource usage
    avg_tool_calls: float
    avg_tokens: float
    avg_time_sec: float

    # Comparison
    baseline_resolve_rate: float | None = None
    improvement: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_tasks": self.total_tasks,
            "resolved": self.resolved,
            "partial": self.partial,
            "failed": self.failed,
            "resolve_rate": self.resolve_rate,
            "partial_rate": self.partial_rate,
            "by_difficulty": self.by_difficulty,
            "by_repo": self.by_repo,
            "avg_tool_calls": self.avg_tool_calls,
            "avg_tokens": self.avg_tokens,
            "avg_time_sec": self.avg_time_sec,
            "baseline_resolve_rate": self.baseline_resolve_rate,
            "improvement": self.improvement,
        }


class SWEBenchDataset:
    """Loader for SWE-bench dataset."""

    def __init__(self, dataset_path: Path | None = None):
        """
        Initialize dataset loader.

        Args:
            dataset_path: Path to the dataset JSON file.
                         If None, uses default location.
        """
        self.dataset_path = dataset_path
        self._tasks: list[SWEBenchTask] = []
        self._loaded = False

    def load(self) -> list[SWEBenchTask]:
        """Load tasks from dataset file."""
        if self._loaded:
            return self._tasks

        if self.dataset_path is None or not self.dataset_path.exists():
            # Return empty list if no dataset available
            self._loaded = True
            return self._tasks

        with open(self.dataset_path) as f:
            data = json.load(f)

        self._tasks = [SWEBenchTask.from_dict(item) for item in data]
        self._loaded = True
        return self._tasks

    def get_by_id(self, instance_id: str) -> SWEBenchTask | None:
        """Get a specific task by instance ID."""
        if not self._loaded:
            self.load()
        for task in self._tasks:
            if task.instance_id == instance_id:
                return task
        return None

    def get_by_difficulty(self, difficulty: str) -> list[SWEBenchTask]:
        """Get tasks filtered by difficulty."""
        if not self._loaded:
            self.load()
        return [t for t in self._tasks if t.difficulty == difficulty]

    def get_by_repo(self, repo: str) -> list[SWEBenchTask]:
        """Get tasks filtered by repository."""
        if not self._loaded:
            self.load()
        return [t for t in self._tasks if t.repo == repo]

    def sample(self, n: int, seed: int | None = None) -> list[SWEBenchTask]:
        """Get a random sample of tasks."""
        import random

        if not self._loaded:
            self.load()

        if seed is not None:
            random.seed(seed)

        return random.sample(self._tasks, min(n, len(self._tasks)))


class SWEBenchRunner:
    """Runs SWE-bench tasks with CompyMac agent."""

    def __init__(
        self,
        harness: Harness,
        llm_client: LLMClient,
        workspace_base: Path | None = None,
        max_verification_attempts: int = 3,
        require_source_modification: bool = True,
    ):
        """
        Initialize runner.

        Args:
            harness: The harness for tool execution
            llm_client: The LLM client for agent
            workspace_base: Base directory for task workspaces
            max_verification_attempts: Max times to retry if tests fail (default: 3)
            require_source_modification: Require patch to modify source, not just tests
        """
        self.harness = harness
        self.llm_client = llm_client
        self.workspace_base = workspace_base or Path("/tmp/swebench")
        self.results: list[SWEBenchResult] = []
        self.max_verification_attempts = max_verification_attempts
        self.require_source_modification = require_source_modification

    async def run_task(self, task: SWEBenchTask) -> SWEBenchResult:
        """
        Run a single SWE-bench task.

        Args:
            task: The task to run

        Returns:
            SWEBenchResult with outcome and metrics
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        # Phase 1: Setup repository
        try:
            repo_path = await self._setup_repository(task)
        except Exception as e:
            return self._create_failed_result(
                task, trace_id, start_time, f"Repository setup failed: {e}"
            )

        # Phase 2: Run agent
        try:
            agent_result = await self._run_agent(task, repo_path, trace_id)
            patch_generated = agent_result.get("patch", "")
            tool_calls = agent_result.get("tool_calls", 0)
            tokens = agent_result.get("tokens", 0)
            error_log = ""
        except Exception as e:
            patch_generated = ""
            tool_calls = 0
            tokens = 0
            error_log = str(e)

        elapsed = time.time() - start_time

        # Phase 3: Evaluate patch
        try:
            test_results = await self._evaluate_patch(repo_path, task, patch_generated)
        except Exception as e:
            test_results = TestResults(
                fail_to_pass=dict.fromkeys(task.fail_to_pass, False),
                pass_to_pass=dict.fromkeys(task.pass_to_pass, False),
            )
            error_log += f"\nEvaluation failed: {e}"

        # Phase 4: Cleanup
        await self._cleanup_repository(repo_path)

        # Phase 5: Compute outcome
        resolved = test_results.all_fail_to_pass_passed and test_results.all_pass_to_pass_passed
        partial = (
            any(test_results.fail_to_pass.values())
            and test_results.all_pass_to_pass_passed
            and not resolved
        )
        failed = not (resolved or partial)

        result = SWEBenchResult(
            instance_id=task.instance_id,
            resolved=resolved,
            partial=partial,
            failed=failed,
            fail_to_pass_results=test_results.fail_to_pass,
            pass_to_pass_results=test_results.pass_to_pass,
            patch_generated=patch_generated,
            tool_calls_made=tool_calls,
            tokens_used=tokens,
            time_elapsed_sec=elapsed,
            trace_id=trace_id,
            error_log=error_log,
        )

        self.results.append(result)
        return result

    async def run_batch(
        self, tasks: list[SWEBenchTask], parallel: int = 1
    ) -> list[SWEBenchResult]:
        """
        Run multiple tasks.

        Args:
            tasks: List of tasks to run
            parallel: Number of tasks to run in parallel (default: 1)

        Returns:
            List of results
        """
        if parallel <= 1:
            # Sequential execution
            results = []
            for task in tasks:
                result = await self.run_task(task)
                results.append(result)
            return results

        # Parallel execution with semaphore
        semaphore = asyncio.Semaphore(parallel)

        async def run_with_semaphore(task: SWEBenchTask) -> SWEBenchResult:
            async with semaphore:
                return await self.run_task(task)

        results = await asyncio.gather(*[run_with_semaphore(t) for t in tasks])
        return list(results)

    async def _setup_repository(self, task: SWEBenchTask) -> Path:
        """Clone repo and checkout correct version."""
        repo_path = self.workspace_base / task.instance_id
        repo_path.mkdir(parents=True, exist_ok=True)

        # Clone repo
        clone_result = subprocess.run(
            ["git", "clone", f"https://github.com/{task.repo}", str(repo_path)],
            capture_output=True,
            text=True,
        )
        if clone_result.returncode != 0:
            raise RuntimeError(f"Clone failed: {clone_result.stderr}")

        # Checkout base version
        checkout_result = subprocess.run(
            ["git", "-C", str(repo_path), "checkout", task.version],
            capture_output=True,
            text=True,
        )
        if checkout_result.returncode != 0:
            raise RuntimeError(f"Checkout failed: {checkout_result.stderr}")

        # Apply test patch if provided
        if task.test_patch:
            apply_result = subprocess.run(
                ["git", "-C", str(repo_path), "apply", "--"],
                input=task.test_patch,
                capture_output=True,
                text=True,
            )
            if apply_result.returncode != 0:
                raise RuntimeError(f"Test patch apply failed: {apply_result.stderr}")

        return repo_path

    async def _run_agent(
        self, task: SWEBenchTask, repo_path: Path, trace_id: str
    ) -> dict[str, Any]:
        """Run agent on the task with verification loop.

        The agent runs iteratively:
        1. Agent attempts to fix the bug
        2. We verify by running fail_to_pass tests
        3. If tests fail, we tell the agent and let it try again
        4. Repeat until tests pass or max_verification_attempts reached
        """
        # Import here to avoid circular imports
        from compymac.agent_loop import AgentConfig, AgentLoop

        # Build test names for the prompt
        test_names = ", ".join(task.fail_to_pass[:3])  # Show first 3 tests
        if len(task.fail_to_pass) > 3:
            test_names += f" (and {len(task.fail_to_pass) - 3} more)"

        # Prompt-guided approach: All tools available, but prompt directs agent to use only relevant ones
        prompt = f'''You are a code-fixing agent. Respond ONLY with tool calls in JSON format.

TASK: {json.dumps({
    "repo": task.repo,
    "repo_path": str(repo_path),
    "problem": task.problem_statement[:500],
    "failing_tests": task.fail_to_pass[:3],
})}

PRIMARY TOOLS (use ONLY these for this task):
- grep: Search for patterns in files
- glob: Find files by pattern
- Read: View file contents (REQUIRED before Edit)
- Edit: Modify file (old_string -> new_string)
- bash: Run shell commands (e.g., pytest)
- complete: Signal task done (call when tests pass)

DO NOT USE these tools - they will not help you fix code:
- message_user (no human to message)
- web_search, web_get_contents (no internet needed)
- list_repos, git_* (repo already cloned)
- request_tools, TodoWrite, think (unnecessary overhead)
- deploy, recording_*, browser_* (not relevant)

RULES:
1. Respond ONLY with a tool call - no prose
2. Read a file BEFORE editing it
3. Run tests after editing: bash(command="python -m pytest {task.fail_to_pass[0]} -v", exec_dir="{repo_path}", bash_id="test")
4. Call complete(final_answer="description of fix") when tests pass
5. If tests fail, analyze output and try a different fix
6. Stay focused: grep -> Read -> Edit -> bash(test) -> complete

Tests that must pass: {test_names}
'''

        # Create agent config with system prompt
        # Use action-gated mode for MUD-style control:
        # - Agent must call a tool every turn (no prose-only responses)
        # - Agent must call 'complete' tool to finish
        # ACI-style grounding (based on SWE-agent research):
        # - Force complete on last step
        # - Re-ground every turn with repo_path, failing_tests, steps_remaining
        config = AgentConfig(
            system_prompt=prompt,
            max_steps=50,
            action_gated=True,
            require_complete_tool=True,
            max_invalid_moves=5,
            force_complete_on_last_step=True,
            grounding_context={
                "repo_path": str(repo_path),
                "failing_tests": task.fail_to_pass[:3],
            },
            # All tools available - prompt guides agent to use only relevant ones
        )

        total_tool_calls = 0
        last_error = ""
        import logging
        logger = logging.getLogger(__name__)

        # All tools available - prompt guides agent to use only relevant ones
        # (No artificial tool restriction - agent has full access but prompt directs behavior)

        for attempt in range(self.max_verification_attempts):
            logger.info(f"Starting attempt {attempt + 1}/{self.max_verification_attempts}")

            # Create fresh agent for each attempt (but repo state persists)
            agent = AgentLoop(
                harness=self.harness,
                llm_client=self.llm_client,
                config=config,
            )

            # Run agent
            try:
                if attempt == 0:
                    user_input = "Please analyze the repository and fix the bug described above."
                else:
                    # Provide feedback from previous attempt
                    user_input = f"""Your previous fix attempt did not pass the tests.

VERIFICATION FAILED (attempt {attempt}/{self.max_verification_attempts}):
{last_error}

Please analyze what went wrong and try a different approach.
Remember: You MUST use the Edit tool to modify SOURCE CODE files.
"""
                agent.run(user_input)
                total_tool_calls += len(agent.state.messages)

                # Log tool usage summary
                tool_counts: dict[str, int] = {}
                for msg in agent.state.messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = tc.get('function', {}).get('name', 'unknown')
                            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                logger.info(f"Attempt {attempt + 1} tool usage: {tool_counts}")

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with error: {e}")
                last_error = str(e)
                continue

            # Get current patch
            diff_result = subprocess.run(
                ["git", "-C", str(repo_path), "diff"],
                capture_output=True,
                text=True,
            )
            patch = diff_result.stdout if diff_result.returncode == 0 else ""

            # Verify patch modifies source code (not just tests)
            if self.require_source_modification and patch:
                if not self._patch_modifies_source(patch, task):
                    last_error = (
                        "Patch only modifies test files. "
                        "You must fix the SOURCE CODE, not just add tests."
                    )
                    continue

            # Run verification tests
            verification_results = await self._verify_tests(repo_path, task)
            if verification_results["all_passed"]:
                # Success! Return the patch
                return {
                    "patch": patch,
                    "tool_calls": total_tool_calls,
                    "tokens": 0,
                    "attempts": attempt + 1,
                }

            # Build error message for next attempt
            failed_tests = verification_results["failed_tests"]
            last_error = f"Tests still failing: {', '.join(failed_tests)}"

        # All attempts exhausted
        diff_result = subprocess.run(
            ["git", "-C", str(repo_path), "diff"],
            capture_output=True,
            text=True,
        )
        patch = diff_result.stdout if diff_result.returncode == 0 else ""

        return {
            "patch": patch,
            "tool_calls": total_tool_calls,
            "tokens": 0,
            "error": f"Failed after {self.max_verification_attempts} attempts: {last_error}",
        }

    def _patch_modifies_source(self, patch: str, task: SWEBenchTask) -> bool:
        """Check if patch modifies source code, not just test files."""
        # Parse diff to find modified files
        modified_files = []
        for line in patch.split("\n"):
            if line.startswith("diff --git"):
                # Extract filename from "diff --git a/path/file b/path/file"
                parts = line.split()
                if len(parts) >= 4:
                    filename = parts[2].lstrip("a/")
                    modified_files.append(filename)

        # Check if any non-test file is modified
        for f in modified_files:
            # Common test file patterns
            is_test = (
                "test" in f.lower()
                or f.startswith("tests/")
                or f.startswith("test_")
                or "_test.py" in f
            )
            if not is_test:
                return True

        return False

    async def _verify_tests(
        self, repo_path: Path, task: SWEBenchTask
    ) -> dict[str, Any]:
        """Run fail_to_pass tests and return verification results."""
        failed_tests = []
        passed_tests = []

        for test in task.fail_to_pass:
            passed = await self._run_test(repo_path, test, log_output=True)
            if passed:
                passed_tests.append(test)
            else:
                failed_tests.append(test)

        return {
            "all_passed": len(failed_tests) == 0 and len(passed_tests) > 0,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
        }

    async def _evaluate_patch(
        self, repo_path: Path, task: SWEBenchTask, patch: str
    ) -> TestResults:
        """Run tests on the current repo state.

        Note: The agent already made changes to the working tree, so we don't
        need to apply the patch again. We just run tests on the current state.
        The patch parameter is kept for logging/verification purposes.
        """
        if not patch:
            return TestResults(
                fail_to_pass=dict.fromkeys(task.fail_to_pass, False),
                pass_to_pass=dict.fromkeys(task.pass_to_pass, False),
            )

        # Note: We do NOT apply the patch here because the agent already made
        # the changes directly to the working tree. The patch was captured via
        # `git diff` after the agent finished, so it's already applied.
        # Trying to `git apply` again would fail with "patch already applied".

        # Run fail_to_pass tests
        fail_to_pass_results = {}
        for test in task.fail_to_pass:
            passed = await self._run_test(repo_path, test)
            fail_to_pass_results[test] = passed

        # Run pass_to_pass tests
        pass_to_pass_results = {}
        for test in task.pass_to_pass:
            passed = await self._run_test(repo_path, test)
            pass_to_pass_results[test] = passed

        return TestResults(
            fail_to_pass=fail_to_pass_results,
            pass_to_pass=pass_to_pass_results,
        )

    async def _run_test(
        self, repo_path: Path, test_name: str, log_output: bool = True
    ) -> bool:
        """Run a single test and return whether it passed.

        Args:
            repo_path: Path to the repository
            test_name: Name of the test to run (pytest format)
            log_output: Whether to log test output for debugging

        Returns:
            True if the test passed, False otherwise
        """
        result = subprocess.run(
            ["python", "-m", "pytest", test_name, "-v", "--tb=short"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )

        # Log test output for debugging
        if log_output and result.returncode != 0:
            log_dir = repo_path / ".swebench_logs"
            log_dir.mkdir(exist_ok=True)

            # Sanitize test name for filename
            safe_name = test_name.replace("/", "_").replace("::", "__")
            log_file = log_dir / f"{safe_name}.log"

            with open(log_file, "w") as f:
                f.write(f"=== Test: {test_name} ===\n")
                f.write(f"Return code: {result.returncode}\n\n")
                f.write("=== STDOUT ===\n")
                f.write(result.stdout or "(empty)\n")
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr or "(empty)\n")

        return result.returncode == 0

    async def _cleanup_repository(self, repo_path: Path) -> None:
        """Clean up repository after task completion."""
        import shutil

        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)

    def _create_failed_result(
        self, task: SWEBenchTask, trace_id: str, start_time: float, error: str
    ) -> SWEBenchResult:
        """Create a failed result for error cases."""
        return SWEBenchResult(
            instance_id=task.instance_id,
            resolved=False,
            partial=False,
            failed=True,
            fail_to_pass_results=dict.fromkeys(task.fail_to_pass, False),
            pass_to_pass_results=dict.fromkeys(task.pass_to_pass, False),
            patch_generated="",
            tool_calls_made=0,
            tokens_used=0,
            time_elapsed_sec=time.time() - start_time,
            trace_id=trace_id,
            error_log=error,
        )


class SWEBenchDashboard:
    """Dashboard for analyzing SWE-bench results."""

    def __init__(self, results: list[SWEBenchResult] | None = None):
        """Initialize dashboard with optional results."""
        self.results = results or []

    def add_result(self, result: SWEBenchResult) -> None:
        """Add a result to the dashboard."""
        self.results.append(result)

    def generate_report(self, results: list[SWEBenchResult] | None = None) -> SWEBenchEvaluation:
        """Generate evaluation report from results."""
        results = results or self.results
        if not results:
            return SWEBenchEvaluation(
                total_tasks=0,
                resolved=0,
                partial=0,
                failed=0,
                resolve_rate=0.0,
                partial_rate=0.0,
                by_difficulty={},
                by_repo={},
                avg_tool_calls=0.0,
                avg_tokens=0.0,
                avg_time_sec=0.0,
            )

        total = len(results)
        resolved = sum(1 for r in results if r.resolved)
        partial = sum(1 for r in results if r.partial)
        failed = sum(1 for r in results if r.failed)

        return SWEBenchEvaluation(
            total_tasks=total,
            resolved=resolved,
            partial=partial,
            failed=failed,
            resolve_rate=resolved / total if total > 0 else 0.0,
            partial_rate=partial / total if total > 0 else 0.0,
            by_difficulty=self._breakdown_by_difficulty(results),
            by_repo=self._breakdown_by_repo(results),
            avg_tool_calls=sum(r.tool_calls_made for r in results) / total,
            avg_tokens=sum(r.tokens_used for r in results) / total,
            avg_time_sec=sum(r.time_elapsed_sec for r in results) / total,
        )

    def _breakdown_by_difficulty(
        self, results: list[SWEBenchResult]
    ) -> dict[str, dict[str, int]]:
        """Break down results by difficulty level."""
        breakdown: dict[str, dict[str, int]] = {}
        # Would need task metadata to implement fully
        # For now, return empty breakdown
        return breakdown

    def _breakdown_by_repo(self, results: list[SWEBenchResult]) -> dict[str, dict[str, int]]:
        """Break down results by repository."""
        breakdown: dict[str, dict[str, int]] = {}
        for result in results:
            # Extract repo from instance_id (e.g., "django__django-12345" -> "django/django")
            parts = result.instance_id.split("__")
            if len(parts) >= 2:
                repo = parts[0].replace("_", "/")
            else:
                repo = "unknown"

            if repo not in breakdown:
                breakdown[repo] = {"resolved": 0, "partial": 0, "failed": 0}

            if result.resolved:
                breakdown[repo]["resolved"] += 1
            elif result.partial:
                breakdown[repo]["partial"] += 1
            else:
                breakdown[repo]["failed"] += 1

        return breakdown

    def save_results(self, path: Path) -> None:
        """Save results to JSON file."""
        with open(path, "w") as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2)

    def load_results(self, path: Path) -> None:
        """Load results from JSON file."""
        with open(path) as f:
            data = json.load(f)
        self.results = [SWEBenchResult.from_dict(item) for item in data]
