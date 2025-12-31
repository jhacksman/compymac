"""
Evaluation Runner for CompyMac.

This runner feeds real tasks to CompyMac using Venice.ai.
No mocking, no scripted responses - just real LLM calls solving real problems.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from compymac.agent_loop import AgentConfig, AgentLoop
from compymac.config import LLMConfig
from compymac.evaluation.tasks import TASK_BANK, Task, TaskCategory
from compymac.harness import HarnessConfig
from compymac.llm import LLMClient
from compymac.local_harness import LocalHarness
from compymac.prompts import load_swe_bench_v5_prompt

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of running a single task."""
    task_id: str
    category: str
    success: bool
    steps_taken: int
    duration_seconds: float
    final_response: str
    error: str | None = None
    trace_path: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Summary report of an evaluation run."""
    timestamp: str
    total_tasks: int
    successful: int
    failed: int
    success_rate: float
    avg_steps: float
    avg_duration: float
    results: list[TaskResult]
    by_category: dict[str, dict[str, int | float]]


class EvaluationRunner:
    """
    Runs evaluation tasks against CompyMac using Venice.ai.

    This is a thin wrapper that:
    1. Sets up the LLM client with Venice.ai
    2. Creates a LocalHarness for tool execution
    3. Runs each task through AgentLoop
    4. Records results

    No mocking, no scripted tests - just real execution.
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        model: str = "qwen3-235b-a22b-instruct-2507",
        base_url: str = "https://api.venice.ai/api/v1",
        api_key: str | None = None,
    ):
        self.output_dir = output_dir or Path("/tmp/compymac_eval")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("LLM_API_KEY")

        if not self.api_key:
            raise ValueError("LLM_API_KEY environment variable required")

        self.results: list[TaskResult] = []

    def _create_llm_client(self) -> LLMClient:
        """Create LLM client configured for Venice.ai."""
        config = LLMConfig(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0.0,  # Deterministic for evaluation
            max_tokens=4096,
        )
        return LLMClient(config=config)

    def _create_harness(self, task_id: str) -> LocalHarness:
        """Create a LocalHarness for task execution."""
        config = HarnessConfig()
        config.enable_safety_policies = True
        output_dir = self.output_dir / task_id / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        return LocalHarness(config=config, full_output_dir=output_dir)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for evaluation tasks."""
        # Use the V5 prompt as base, but simplified for evaluation
        base_prompt = load_swe_bench_v5_prompt()

        # Add evaluation-specific instructions
        eval_instructions = """

## Evaluation Mode

You are being evaluated on your ability to complete tasks correctly.
- Complete the task as specified in the prompt
- Use tools to verify your work
- Call complete() when done with a summary of what you did
"""
        return base_prompt + eval_instructions

    def run_task(self, task: Task) -> TaskResult:
        """Run a single evaluation task."""
        logger.info(f"Running task: {task.id} - {task.description}")

        start_time = time.time()
        error: str | None = None
        final_response = ""
        steps_taken = 0

        try:
            # Create fresh LLM client and harness for each task
            llm_client = self._create_llm_client()
            harness = self._create_harness(task.id)

            # Configure agent
            config = AgentConfig(
                max_steps=task.max_steps,
                system_prompt=self._get_system_prompt(),
                action_gated=True,
                require_complete_tool=True,
                max_invalid_moves=5,
            )

            # Create and run agent loop
            agent = AgentLoop(
                harness=harness,
                llm_client=llm_client,
                config=config,
            )

            # Run the task
            final_response = agent.run(task.prompt)
            steps_taken = agent.state.step_count

            # Close LLM client
            llm_client.close()

        except Exception as e:
            error = str(e)
            logger.error(f"Task {task.id} failed with error: {e}")

        duration = time.time() - start_time

        # Determine success (for now, just check if completed without error)
        # Real success criteria would need human verification or specific checks
        success = error is None and "Failed:" not in final_response

        result = TaskResult(
            task_id=task.id,
            category=task.category.value,
            success=success,
            steps_taken=steps_taken,
            duration_seconds=duration,
            final_response=final_response,
            error=error,
        )

        self.results.append(result)

        # Save individual result
        result_path = self.output_dir / task.id / "result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with open(result_path, "w") as f:
            json.dump({
                "task_id": result.task_id,
                "category": result.category,
                "success": result.success,
                "steps_taken": result.steps_taken,
                "duration_seconds": result.duration_seconds,
                "final_response": result.final_response,
                "error": result.error,
            }, f, indent=2)

        logger.info(f"Task {task.id}: {'SUCCESS' if success else 'FAILED'} in {steps_taken} steps ({duration:.1f}s)")

        return result

    def run_all(self, tasks: list[Task] | None = None) -> EvaluationReport:
        """Run all tasks and generate a report."""
        tasks = tasks or TASK_BANK

        logger.info(f"Starting evaluation of {len(tasks)} tasks")

        for task in tasks:
            self.run_task(task)

        return self.generate_report()

    def run_category(self, category: TaskCategory) -> EvaluationReport:
        """Run all tasks in a specific category."""
        tasks = [t for t in TASK_BANK if t.category == category]
        return self.run_all(tasks)

    def run_by_ids(self, task_ids: list[str]) -> EvaluationReport:
        """Run specific tasks by ID."""
        tasks = [t for t in TASK_BANK if t.id in task_ids]
        return self.run_all(tasks)

    def generate_report(self) -> EvaluationReport:
        """Generate evaluation report from results."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        failed = total - successful

        avg_steps = sum(r.steps_taken for r in self.results) / total if total > 0 else 0
        avg_duration = sum(r.duration_seconds for r in self.results) / total if total > 0 else 0

        # Group by category
        by_category: dict[str, dict[str, int | float]] = {}
        for result in self.results:
            cat = result.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "success": 0, "failed": 0}
            by_category[cat]["total"] += 1
            if result.success:
                by_category[cat]["success"] += 1
            else:
                by_category[cat]["failed"] += 1

        # Calculate success rate per category
        for cat in by_category:
            total_cat = by_category[cat]["total"]
            by_category[cat]["success_rate"] = by_category[cat]["success"] / total_cat if total_cat > 0 else 0

        report = EvaluationReport(
            timestamp=datetime.now(UTC).isoformat(),
            total_tasks=total,
            successful=successful,
            failed=failed,
            success_rate=successful / total if total > 0 else 0,
            avg_steps=avg_steps,
            avg_duration=avg_duration,
            results=self.results,
            by_category=by_category,
        )

        # Save report
        report_path = self.output_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": report.timestamp,
                "total_tasks": report.total_tasks,
                "successful": report.successful,
                "failed": report.failed,
                "success_rate": report.success_rate,
                "avg_steps": report.avg_steps,
                "avg_duration": report.avg_duration,
                "by_category": report.by_category,
                "results": [
                    {
                        "task_id": r.task_id,
                        "category": r.category,
                        "success": r.success,
                        "steps_taken": r.steps_taken,
                        "duration_seconds": r.duration_seconds,
                        "error": r.error,
                    }
                    for r in report.results
                ],
            }, f, indent=2)

        # Print summary
        print("\n" + "=" * 60)
        print("COMPYMAC EVALUATION REPORT")
        print("=" * 60)
        print(f"Timestamp: {report.timestamp}")
        print(f"Total Tasks: {report.total_tasks}")
        print(f"Successful: {report.successful}")
        print(f"Failed: {report.failed}")
        print(f"Success Rate: {report.success_rate:.1%}")
        print(f"Avg Steps: {report.avg_steps:.1f}")
        print(f"Avg Duration: {report.avg_duration:.1f}s")
        print("\nBy Category:")
        for cat, stats in report.by_category.items():
            print(f"  {cat}: {stats['success']}/{stats['total']} ({stats['success_rate']:.1%})")
        print("=" * 60)

        return report


def main():
    """Run evaluation from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Run CompyMac evaluation")
    parser.add_argument("--tasks", nargs="+", help="Specific task IDs to run")
    parser.add_argument("--category", help="Run all tasks in a category")
    parser.add_argument("--output", default="/tmp/compymac_eval", help="Output directory")
    parser.add_argument("--model", default="qwen3-235b-a22b-instruct-2507", help="Model to use")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    runner = EvaluationRunner(
        output_dir=Path(args.output),
        model=args.model,
    )

    if args.tasks:
        runner.run_by_ids(args.tasks)
    elif args.category:
        category = TaskCategory(args.category)
        runner.run_category(category)
    else:
        runner.run_all()


if __name__ == "__main__":
    main()
