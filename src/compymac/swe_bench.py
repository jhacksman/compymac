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
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from compymac.prompts import load_swe_bench_v5_prompt
from compymac.swe_workflow import AttemptState, SWEPhaseState
from compymac.trace_store import TraceContext, TraceStore

if TYPE_CHECKING:
    from compymac.harness import Harness
    from compymac.llm import LLMClient

logger = logging.getLogger(__name__)


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
        trace_store: TraceStore | None = None,
    ):
        """
        Initialize runner.

        Args:
            harness: The harness for tool execution
            llm_client: The LLM client for agent
            workspace_base: Base directory for task workspaces
            max_verification_attempts: Max times to retry if tests fail (default: 3)
            require_source_modification: Require patch to modify source, not just tests
            trace_store: Optional TraceStore for cognitive event capture (V5)
        """
        self.harness = harness
        self.llm_client = llm_client
        self.workspace_base = workspace_base or Path("/tmp/swebench")
        self.results: list[SWEBenchResult] = []
        self.max_verification_attempts = max_verification_attempts
        self.require_source_modification = require_source_modification
        self.trace_store = trace_store

    def _build_system_prompt(
        self, task: SWEBenchTask, repo_path: Path, tool_schemas: str = ""
    ) -> str:
        """Build system prompt with V5 metacognitive scaffolding.

        V5: Loads the enhanced system prompt template with thinking scenarios,
        temptation awareness, and principle blocks. Injects task-specific context.

        Args:
            task: The SWE-bench task being run
            repo_path: Path to the cloned repository
            tool_schemas: Optional tool schema documentation to inject

        Returns:
            The formatted system prompt with task context
        """
        template = load_swe_bench_v5_prompt()

        prompt = template.format(
            instance_id=task.instance_id,
            problem_statement=task.problem_statement,
            repo_path=str(repo_path),
            tool_schemas=tool_schemas,
        )

        return prompt

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

        # V5: Create TraceContext for cognitive event capture
        trace_context: TraceContext | None = None
        if self.trace_store:
            trace_context = TraceContext(self.trace_store, trace_id)
            # Set trace context on harness so cognitive events are captured
            if hasattr(self.harness, 'set_trace_context'):
                self.harness.set_trace_context(trace_context)

        # Phase 1: Setup repository (includes venv creation and dependency installation)
        try:
            repo_path, venv_python = await self._setup_repository(task)
        except Exception as e:
            # Clear trace context on failure
            if hasattr(self.harness, 'set_trace_context'):
                self.harness.set_trace_context(None)
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

        # Phase 3: Evaluate patch (using venv python for test execution)
        try:
            test_results = await self._evaluate_patch(repo_path, task, patch_generated, venv_python)
        except Exception as e:
            test_results = TestResults(
                fail_to_pass=dict.fromkeys(task.fail_to_pass, False),
                pass_to_pass=dict.fromkeys(task.pass_to_pass, False),
            )
            error_log += f"\nEvaluation failed: {e}"

        # Phase 4: Cleanup
        await self._cleanup_repository(repo_path)

        # V5: Clear trace context after task completes
        if hasattr(self.harness, 'set_trace_context'):
            self.harness.set_trace_context(None)

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

    async def _setup_repository(self, task: SWEBenchTask) -> tuple[Path, Path]:
        """Clone repo, checkout correct version, create venv, and install dependencies.

        Returns:
            Tuple of (repo_path, venv_python_path)
        """
        repo_path = self.workspace_base / task.instance_id

        # Force cleanup if directory already exists (from previous failed run)
        if repo_path.exists():
            # Safety check: only delete if it's inside workspace_base
            try:
                repo_path.resolve().relative_to(self.workspace_base.resolve())
                logger.info(f"Cleaning up existing directory: {repo_path}")
                shutil.rmtree(repo_path, ignore_errors=True)
            except ValueError as e:
                raise RuntimeError(f"Refusing to delete {repo_path} - not inside workspace_base") from e

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

        # Create isolated virtual environment to avoid global environment contamination
        venv_path = repo_path / ".venv"
        logger.info(f"Creating isolated virtual environment at {venv_path}")
        venv_result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
        )
        if venv_result.returncode != 0:
            raise RuntimeError(f"Venv creation failed: {venv_result.stderr}")

        # Get path to venv python
        venv_python = venv_path / "bin" / "python"
        if not venv_python.exists():
            # Windows fallback
            venv_python = venv_path / "Scripts" / "python.exe"

        if not venv_python.exists():
            raise RuntimeError(f"Venv python not found at {venv_python}")

        # Install project dependencies using venv python
        await self._install_dependencies(repo_path, task, venv_python)

        return repo_path, venv_python

    async def _install_dependencies(
        self, repo_path: Path, task: SWEBenchTask, venv_python: Path
    ) -> None:
        """Install project dependencies in isolated virtual environment.

        Uses a robust installation ladder:
        1. Upgrade pip/setuptools/wheel
        2. Try test extras if pyproject.toml exists
        3. Install requirements files
        4. Always ensure pytest is installed
        5. Handle repo-specific build requirements (e.g., scikit-learn)
        6. Verify installation
        """
        logger.info(f"Installing dependencies for {task.repo} using {venv_python}...")

        # 1. Upgrade pip/setuptools/wheel first
        logger.info("Upgrading pip, setuptools, wheel...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Check for common dependency files
        setup_py = repo_path / "setup.py"
        setup_cfg = repo_path / "setup.cfg"
        pyproject_toml = repo_path / "pyproject.toml"
        requirements_txt = repo_path / "requirements.txt"

        # 2. Try test extras if pyproject.toml or setup.py exists
        installed_editable = False
        if pyproject_toml.exists() or setup_py.exists() or setup_cfg.exists():
            # Try common test extra names
            for extra in ["test", "dev", "tests", "testing", "all"]:
                logger.info(f"Trying: pip install -e '.[{extra}]'")
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", f".[{extra}]"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    logger.info(f"Successfully installed with [{extra}] extra")
                    installed_editable = True
                    break

            # Fallback to plain editable install
            if not installed_editable:
                logger.info("Trying: pip install -e .")
                result = subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-e", "."],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    installed_editable = True
                else:
                    logger.warning(f"Editable install failed: {result.stderr[:300]}")

        # 3. Install requirements files if they exist
        req_files = [
            "requirements.txt",
            "requirements-dev.txt",
            "requirements-test.txt",
            "dev-requirements.txt",
            "test-requirements.txt",
            "requirements/dev.txt",
            "requirements/test.txt",
        ]
        for req_file in req_files:
            req_path = repo_path / req_file
            if req_path.exists():
                logger.info(f"Installing {req_file}...")
                subprocess.run(
                    [str(venv_python), "-m", "pip", "install", "-r", str(req_path)],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

        # If no setup.py/pyproject.toml and only requirements.txt
        if not installed_editable and requirements_txt.exists():
            logger.info("Installing requirements.txt...")
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=300,
            )

        # 4. ALWAYS ensure pytest is installed for test execution
        logger.info("Ensuring pytest is installed...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "pytest", "pytest-xdist"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # 5. Handle repo-specific build requirements
        repo_lower = task.repo.lower()

        # Scikit-learn needs C extension compilation
        if "scikit-learn" in repo_lower or "sklearn" in repo_lower:
            logger.info("Building scikit-learn C extensions...")
            if setup_py.exists():
                subprocess.run(
                    [str(venv_python), "setup.py", "build_ext", "--inplace"],
                    cwd=str(repo_path),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            # Also try installing build dependencies
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "numpy", "scipy", "cython"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

        # Matplotlib/seaborn need matplotlib
        if "matplotlib" in repo_lower or "seaborn" in repo_lower:
            logger.info("Installing matplotlib for visualization repos...")
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "matplotlib", "numpy", "pandas"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

        # 6. Verify pytest installation
        verify = subprocess.run(
            [str(venv_python), "-c", "import pytest; print(f'pytest {pytest.__version__}')"],
            capture_output=True,
            text=True,
        )
        if verify.returncode != 0:
            logger.warning(f"pytest verification failed: {verify.stderr}")
        else:
            logger.info(f"Verified: {verify.stdout.strip()}")

    async def _run_agent(
        self, task: SWEBenchTask, repo_path: Path, trace_id: str
    ) -> dict[str, Any]:
        """Run agent on the task with verification loop.

        The agent runs iteratively:
        1. Agent attempts to fix the bug
        2. We verify by running fail_to_pass tests
        3. If tests fail, we tell the agent and let it try again
        4. Repeat until tests pass or max_verification_attempts reached

        Uses the standard CompyMac agent with menu system - no hardcoded tools.
        The agent must discover and navigate to the appropriate mode on its own.
        """
        # Import here to avoid circular imports
        from compymac.agent_loop import AgentConfig, AgentLoop

        # V5: Build system prompt with metacognitive scaffolding
        # Includes thinking scenarios, temptation awareness, and principle blocks
        prompt = self._build_system_prompt(task, repo_path)

        # Standard CompyMac agent config with menu system DISABLED for SWE-bench
        # Phase enforcement controls the tool set - menu system would bypass phase restrictions
        # grounding_context will be set per-attempt to inject AttemptState for attempt 2+
        base_config = AgentConfig(
            system_prompt=prompt,
            max_steps=50,
            use_menu_system=False,  # DISABLED: Phase enforcement controls tools, not menu
            action_gated=True,  # REQUIRED: Enables termination on complete() tool call
            require_complete_tool=True,
            force_complete_on_last_step=True,
        )

        total_tool_calls = 0
        last_error = ""
        attempt_state: AttemptState | None = None  # Persists across attempts

        # Enable phase enforcement in harness (Mechanism 1)
        # This enables intra-attempt budget enforcement
        if hasattr(self.harness, 'enable_swe_phase_enforcement'):
            self.harness.enable_swe_phase_enforcement()
            logger.info("Phase enforcement enabled for SWE-bench task")

        try:
            for attempt in range(self.max_verification_attempts):
                logger.info(f"Starting attempt {attempt + 1}/{self.max_verification_attempts}")

                # Reset phase state for each attempt (fresh budget)
                if hasattr(self.harness, 'enable_swe_phase_enforcement'):
                    self.harness.enable_swe_phase_enforcement()

                # Build grounding_context for this attempt
                # For attempt 2+, inject AttemptState to enable cross-attempt learning
                grounding_context: dict[str, Any] = {
                    "repo_path": str(repo_path),
                    "failing_tests": task.fail_to_pass[:3],
                    "attempt_number": attempt + 1,
                    "max_attempts": self.max_verification_attempts,
                }

                if attempt_state is not None:
                    # Inject previous attempt findings (Mechanism 2: inter-attempt state persistence)
                    grounding_context["previous_attempt"] = attempt_state.to_grounding_context()
                    logger.info(f"Injecting previous attempt state: hypothesis='{attempt_state.hypothesis[:50]}...'")

                # Create config with grounding_context for this attempt
                config = AgentConfig(
                    system_prompt=base_config.system_prompt,
                    max_steps=base_config.max_steps,
                    use_menu_system=base_config.use_menu_system,
                    action_gated=base_config.action_gated,  # CRITICAL: Must pass through for complete() termination
                    require_complete_tool=base_config.require_complete_tool,
                    force_complete_on_last_step=base_config.force_complete_on_last_step,
                    grounding_context=grounding_context,
                )

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
                        # Provide feedback from previous attempt + structured state
                        previous_summary = attempt_state.to_prompt_injection() if attempt_state else ""
                        user_input = f"""Your previous fix attempt did not pass the tests.

VERIFICATION FAILED (attempt {attempt}/{self.max_verification_attempts}):
{last_error}

{previous_summary}

Please analyze what went wrong and try a different approach.
Remember: You MUST use the Edit tool to modify SOURCE CODE files.
DO NOT repeat the same approach that failed.
"""
                    agent.run(user_input)
                    total_tool_calls += agent.state.tool_call_count

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
                    # Still capture state for next attempt
                    attempt_state = self._capture_attempt_state(
                        attempt + 1, str(e), "", repo_path
                    )
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
                        attempt_state = self._capture_attempt_state(
                            attempt + 1, last_error, "", repo_path
                        )
                        continue

                # Run verification tests
                verification_results = await self._verify_tests(repo_path, task)
                if verification_results["all_passed"]:
                    # Success! Disable phase enforcement and return the patch
                    if hasattr(self.harness, 'disable_swe_phase_enforcement'):
                        self.harness.disable_swe_phase_enforcement()
                    return {
                        "patch": patch,
                        "tool_calls": total_tool_calls,
                        "tokens": 0,
                        "attempts": attempt + 1,
                    }

                # Build error message for next attempt
                failed_tests = verification_results["failed_tests"]
                last_error = f"Tests still failing: {', '.join(failed_tests)}"

                # Capture state for next attempt (Mechanism 2: inter-attempt state persistence)
                # This is CRITICAL - enables learning from previous attempt
                attempt_state = self._capture_attempt_state(
                    attempt + 1, last_error, patch, repo_path
                )
                logger.info(f"Captured attempt state for attempt {attempt + 2}")

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

        finally:
            # Always disable phase enforcement when done
            if hasattr(self.harness, 'disable_swe_phase_enforcement'):
                self.harness.disable_swe_phase_enforcement()

    def _capture_attempt_state(
        self,
        attempt_number: int,
        what_failed: str,
        patch: str,
        repo_path: Path,
        test_results: TestResults | None = None,
    ) -> AttemptState:
        """Capture state from a failed attempt for cross-attempt learning.

        This is CRITICAL for Mechanism 2 (inter-attempt state persistence).
        It captures what was learned and what failed so attempt 2+ can build
        on previous work instead of repeating it.

        V2 (regression-aware): Now accepts test_results to capture fail_to_pass
        and pass_to_pass results for regression-aware learning.
        """
        # Get current phase state from harness (if available)
        phase_state: SWEPhaseState | None = None
        if hasattr(self.harness, 'get_swe_phase_state'):
            phase_state = self.harness.get_swe_phase_state()

        # Get modified files from git
        modified_files: list[str] = []
        git_diff_summary = ""
        try:
            diff_result = subprocess.run(
                ["git", "-C", str(repo_path), "diff", "--name-only"],
                capture_output=True,
                text=True,
            )
            if diff_result.returncode == 0:
                modified_files = [f.strip() for f in diff_result.stdout.split("\n") if f.strip()]

            # Get short diff summary
            stat_result = subprocess.run(
                ["git", "-C", str(repo_path), "diff", "--stat"],
                capture_output=True,
                text=True,
            )
            if stat_result.returncode == 0:
                git_diff_summary = stat_result.stdout[:500]  # Truncate for context size
        except Exception as e:
            logger.warning(f"Failed to get git diff: {e}")

        # V2: Extract regression-aware test results
        fail_to_pass_results: dict[str, bool] = {}
        pass_to_pass_results: dict[str, bool] = {}
        regression_summary = ""
        changes_that_caused_regression = ""

        if test_results:
            fail_to_pass_results = test_results.fail_to_pass
            pass_to_pass_results = test_results.pass_to_pass

            # Calculate regression summary
            broke_tests = [t for t, passed in pass_to_pass_results.items() if not passed]
            if broke_tests:
                regression_summary = f"Broke {len(broke_tests)} pass_to_pass tests"
                # Suggest what to avoid based on modified files
                if modified_files:
                    changes_that_caused_regression = (
                        f"Changes to {', '.join(modified_files[:3])} may have caused regressions. "
                        f"Consider a more targeted fix that doesn't affect existing functionality."
                    )

        # Build AttemptState
        if phase_state:
            return AttemptState.from_phase_state(
                phase_state=phase_state,
                attempt_number=attempt_number,
                what_failed=what_failed,
                failing_test_output=what_failed,  # Use error as test output for now
                next_approach="Try a different approach based on the error message.",
                modified_files=modified_files,
                git_diff_summary=git_diff_summary,
                # V2: Regression-aware parameters
                fail_to_pass_results=fail_to_pass_results,
                pass_to_pass_results=pass_to_pass_results,
                regression_summary=regression_summary,
                changes_that_caused_regression=changes_that_caused_regression,
            )
        else:
            # No phase state available, create minimal AttemptState
            return AttemptState(
                attempt_number=attempt_number + 1,
                what_failed=what_failed,
                failing_test_output=what_failed,
                next_approach="Try a different approach based on the error message.",
                modified_files=modified_files,
                git_diff_summary=git_diff_summary,
                # V2: Regression-aware fields
                fail_to_pass_results=fail_to_pass_results,
                pass_to_pass_results=pass_to_pass_results,
                broke_pass_to_pass=[t for t, p in pass_to_pass_results.items() if not p],
                regression_summary=regression_summary,
                changes_that_caused_regression=changes_that_caused_regression,
            )

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
        self, repo_path: Path, task: SWEBenchTask, venv_python: Path | None = None
    ) -> dict[str, Any]:
        """Run fail_to_pass tests and return verification results.

        Args:
            repo_path: Path to the repository
            task: The SWE-bench task
            venv_python: Path to venv python interpreter

        Returns:
            Dict with all_passed, passed_tests, failed_tests, and harness_errors
        """
        failed_tests = []
        passed_tests = []
        harness_errors = []

        for test in task.fail_to_pass:
            passed, is_harness_error = await self._run_test(
                repo_path, test, log_output=True, task=task, venv_python=venv_python
            )
            if passed:
                passed_tests.append(test)
            else:
                failed_tests.append(test)
                if is_harness_error:
                    harness_errors.append(test)

        return {
            "all_passed": len(failed_tests) == 0 and len(passed_tests) > 0,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "harness_errors": harness_errors,
        }

    async def _evaluate_patch(
        self, repo_path: Path, task: SWEBenchTask, patch: str, venv_python: Path
    ) -> TestResults:
        """Run tests on the current repo state using isolated venv.

        Note: The agent already made changes to the working tree, so we don't
        need to apply the patch again. We just run tests on the current state.
        The patch parameter is kept for logging/verification purposes.

        Args:
            repo_path: Path to the repository
            task: The SWE-bench task
            patch: The generated patch (for logging only)
            venv_python: Path to the venv python interpreter
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
            passed, is_harness_error = await self._run_test(repo_path, test, task=task, venv_python=venv_python)
            fail_to_pass_results[test] = passed
            if is_harness_error:
                logger.warning(f"Harness error detected for {test} - infrastructure issue, not agent failure")

        # Run pass_to_pass tests
        pass_to_pass_results = {}
        for test in task.pass_to_pass:
            passed, is_harness_error = await self._run_test(repo_path, test, task=task, venv_python=venv_python)
            pass_to_pass_results[test] = passed
            if is_harness_error:
                logger.warning(f"Harness error detected for {test} - infrastructure issue, not agent failure")

        return TestResults(
            fail_to_pass=fail_to_pass_results,
            pass_to_pass=pass_to_pass_results,
        )

    def _convert_test_name(self, test_name: str) -> str | None:
        """Convert SWE-bench test name format to standard test identifier.

        SWE-bench uses format: "method_name (module.path.ClassName)"
        We need to convert to: "module.path.ClassName.method_name"

        Args:
            test_name: Test name in SWE-bench format

        Returns:
            Test name in standard format (module.ClassName.method), or None if invalid
        """
        # Check if it's in SWE-bench format: "method_name (module.ClassName)"
        match = re.match(r'^(\w+)\s+\(([^)]+)\)$', test_name)
        if match:
            method_name = match.group(1)
            module_class = match.group(2)
            # Convert to standard format: module.ClassName.method_name
            return f"{module_class}.{method_name}"

        # Check if it's already in valid module.path format (dotted identifier)
        # Valid: "tests.test_foo.TestClass.test_method" or "test_foo::TestClass::test_method"
        if re.match(r'^[\w./:]+$', test_name):
            return test_name

        # Check for descriptive test names that aren't valid module paths
        # These are Django's descriptive test names like "An exception is setUp()..."
        # They contain spaces, special chars, or start with articles/descriptions
        if ' ' in test_name or test_name[0].isupper() and not re.match(r'^[A-Z][a-z]+[A-Z]', test_name):
            # Looks like a descriptive name, not a module path
            logger.warning(f"Invalid test name format (descriptive, not module path): {test_name[:50]}...")
            return None

        # Unknown format - return as-is and let the test runner handle it
        return test_name

    def _get_test_command(
        self, repo_path: Path, test_name: str | None, task: SWEBenchTask | None = None,
        venv_python: Path | None = None
    ) -> tuple[list[str], str] | None:
        """Get the appropriate test command for the repository.

        Different repositories use different test runners:
        - Django: tests/runtests.py with module.ClassName.method format
        - Most others: pytest with various formats

        Args:
            repo_path: Path to the repository
            test_name: Test name (already converted to standard format), or None if invalid
            task: Optional task for repo detection
            venv_python: Path to venv python interpreter (uses "python" if not provided)

        Returns:
            Tuple of (command list, working directory), or None if test_name is invalid
        """
        # If test_name is None (invalid format), skip this test
        if test_name is None:
            return None

        # Use venv python if provided, otherwise fall back to system python
        python_cmd = str(venv_python) if venv_python else "python"

        # Detect Django repository
        is_django = (
            (task and "django" in task.repo.lower())
            or (repo_path / "tests" / "runtests.py").exists()
        )

        if is_django:
            # Django uses its own test runner
            # Format: python tests/runtests.py module.ClassName.method_name
            return (
                [python_cmd, "tests/runtests.py", test_name, "--verbosity=1"],
                str(repo_path),
            )

        # Default to pytest
        # Try to convert module.ClassName.method to pytest format
        # pytest format: path/to/test.py::ClassName::method
        parts = test_name.rsplit(".", 2)
        if len(parts) >= 3:
            # module.path.ClassName.method -> try to find the file
            module_path = parts[0]
            class_name = parts[1] if len(parts) > 2 else ""
            method_name = parts[-1]

            # Try common test file locations
            possible_paths = [
                repo_path / module_path.replace(".", "/") / f"test_{method_name}.py",
                repo_path / "tests" / module_path.replace(".", "/") / f"test_{class_name.lower()}.py",
                repo_path / "tests" / f"{module_path.replace('.', '/')}.py",
                repo_path / module_path.replace(".", "/") / "tests.py",
            ]

            for test_file in possible_paths:
                if test_file.exists():
                    pytest_name = f"{test_file}::{class_name}::{method_name}"
                    return (
                        [python_cmd, "-m", "pytest", pytest_name, "-v", "--tb=short"],
                        str(repo_path),
                    )

        # Fallback: try running pytest with the test name as-is
        return (
            [python_cmd, "-m", "pytest", test_name, "-v", "--tb=short"],
            str(repo_path),
        )

    def _classify_test_failure(self, stdout: str, stderr: str, returncode: int) -> bool:
        """Classify whether a test failure is a harness/infrastructure error.

        Harness errors are infrastructure issues (missing deps, import errors, etc.)
        that should be distinguished from actual test failures.

        Args:
            stdout: Test stdout
            stderr: Test stderr
            returncode: Test return code

        Returns:
            True if this is a harness error, False if it's a real test failure
        """
        combined = (stdout + stderr).lower()

        # Patterns that indicate harness/infrastructure errors
        harness_error_patterns = [
            "no module named",
            "modulenotfounderror",
            "importerror",
            "cannot import name",
            "error processing line",  # .pth file corruption
            "attributeerror: 'nonetype' object has no attribute 'loader'",  # matplotlib .pth
            "pytest: error: unrecognized arguments",
            "error: invalid choice",
            "command not found",
            "no such file or directory",
            "permission denied",
            "syntaxerror",
            "indentationerror",
            "error collecting",  # pytest collection error
            "collection error",
            "fixture.*not found",
            "plugin.*not found",
        ]

        for pattern in harness_error_patterns:
            if pattern in combined:
                return True

        return False

    async def _run_test(
        self, repo_path: Path, test_name: str, log_output: bool = True,
        task: SWEBenchTask | None = None, venv_python: Path | None = None
    ) -> tuple[bool, bool]:
        """Run a single test and return whether it passed.

        Args:
            repo_path: Path to the repository
            test_name: Name of the test to run (SWE-bench format)
            log_output: Whether to log test output for debugging
            task: Optional task for repo-specific test runner detection
            venv_python: Path to venv python interpreter

        Returns:
            Tuple of (passed: bool, is_harness_error: bool)
            - passed: True if the test passed
            - is_harness_error: True if failure was due to infrastructure issue
        """
        # Convert SWE-bench test name format to standard format
        converted_name = self._convert_test_name(test_name)

        # Get the appropriate test command for this repo
        cmd_result = self._get_test_command(repo_path, converted_name, task, venv_python)

        # If test name was invalid, skip this test
        if cmd_result is None:
            logger.warning(f"Skipping test with invalid name format: {test_name}")
            # Return False (not passed) but True (harness error) since it's an infrastructure issue
            return False, True

        cmd, cwd = cmd_result

        logger.info(f"Running test: {test_name} -> {converted_name}")
        logger.info(f"Command: {' '.join(cmd)} (cwd: {cwd})")

        # Set up environment to avoid plugin conflicts and global env contamination
        test_env = os.environ.copy()
        test_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"  # Prevent third-party plugin conflicts
        test_env["PYTHONNOUSERSITE"] = "1"  # Ignore user site-packages

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per test
                env=test_env,
            )
            returncode = result.returncode
            stdout = result.stdout or "(empty)"
            stderr = result.stderr or "(empty)"
        except subprocess.TimeoutExpired as e:
            returncode = -1
            stdout = e.stdout.decode() if e.stdout else "(timeout - no stdout)"
            stderr = e.stderr.decode() if e.stderr else "(timeout - no stderr)"
            logger.warning(f"Test timed out: {test_name}")
        except Exception as e:
            returncode = -1
            stdout = "(exception - no stdout)"
            stderr = str(e)
            logger.warning(f"Test execution failed: {test_name} - {e}")

        # Classify the failure type
        is_harness_error = False
        if returncode != 0:
            is_harness_error = self._classify_test_failure(stdout, stderr, returncode)

        # Save logs to a stable location OUTSIDE repo_path so they survive cleanup
        # Use workspace_base/logs/{instance_id}/ instead of repo_path/.swebench_logs/
        instance_id = task.instance_id if task else "unknown"
        log_dir = self.workspace_base / "logs" / instance_id
        log_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize test name for filename
        safe_name = test_name.replace("/", "_").replace("::", "__").replace(" ", "_").replace("(", "").replace(")", "")
        log_file = log_dir / f"{safe_name}.log"

        with open(log_file, "w") as f:
            f.write(f"=== Test: {test_name} ===\n")
            f.write(f"Converted: {converted_name}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Working dir: {cwd}\n")
            f.write(f"Return code: {returncode}\n")
            f.write(f"Is harness error: {is_harness_error}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(stdout)
            f.write("\n=== STDERR ===\n")
            f.write(stderr)

        if returncode != 0:
            if is_harness_error:
                logger.warning(f"HARNESS ERROR: {test_name} (infrastructure issue, not agent failure)")
            else:
                logger.warning(f"Test failed: {test_name} (return code: {returncode})")
            # Log first 500 chars of stderr for debugging
            logger.warning(f"Stderr: {stderr[:500]}")

        return returncode == 0, is_harness_error

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
