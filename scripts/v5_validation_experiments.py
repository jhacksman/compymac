#!/usr/bin/env python3
"""
V5 Metacognitive Architecture Validation Experiments

This script runs SWE-bench tasks with the V5 metacognitive scaffolding
and analyzes cognitive compliance for each task.

Phase 4.2 from ROADMAP.md:
- Run CompyMac V5 on 5-10 diverse SWE-bench tasks
- Capture full reasoning traces
- Analyze compliance reports
- Review thinking content for coherence
- Identify failure modes

Usage:
    python scripts/v5_validation_experiments.py --num-tasks 5 --dry-run
    python scripts/v5_validation_experiments.py --num-tasks 10
    python scripts/v5_validation_experiments.py --task-id pylint-dev__pylint-5859
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datasets import load_dataset

from compymac.swe_bench import (
    SWEBenchDashboard,
    SWEBenchResult,
    SWEBenchRunner,
    SWEBenchTask,
)
from compymac.trace_store import create_trace_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Recommended tasks from ROADMAP.md Phase 4.2
RECOMMENDED_TASKS = {
    "easy": [
        "pylint-dev__pylint-5859",  # Already solved with V4
    ],
    "medium": [
        "django__django-11099",
        "sympy__sympy-13146",
        "scikit-learn__scikit-learn-13779",
    ],
    "hard": [
        "matplotlib__matplotlib-23314",
        "django__django-13933",
        "sphinx-doc__sphinx-8595",
    ],
}


@dataclass
class V5ValidationConfig:
    """Configuration for V5 validation experiments."""

    num_tasks: int = 5
    seed: int = 42
    dry_run: bool = False
    output_dir: Path = Path("v5_validation_results")
    workspace_base: Path = Path("/tmp/v5_validation")
    specific_task_id: str | None = None
    use_recommended: bool = True


@dataclass
class CognitiveComplianceReport:
    """Report on cognitive compliance for a single task."""

    trace_id: str
    task_id: str
    total_thinking_events: int = 0
    total_temptation_events: int = 0
    thinking_compliance_rate: float = 0.0
    temptation_resistance_rate: float = 0.0
    required_scenarios_satisfied: dict = field(default_factory=dict)
    thinking_samples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "total_thinking_events": self.total_thinking_events,
            "total_temptation_events": self.total_temptation_events,
            "thinking_compliance_rate": self.thinking_compliance_rate,
            "temptation_resistance_rate": self.temptation_resistance_rate,
            "required_scenarios_satisfied": self.required_scenarios_satisfied,
            "thinking_samples": self.thinking_samples,
        }


def analyze_cognitive_compliance(trace_id: str, task_id: str, trace_base_path: Path | None = None) -> CognitiveComplianceReport:
    """Analyze cognitive compliance for a completed task.

    Args:
        trace_id: The trace ID from the task run
        task_id: The SWE-bench task instance ID
        trace_base_path: Base path for trace store (defaults to /tmp/compymac_traces)

    Returns:
        CognitiveComplianceReport with analysis results
    """
    base_path = trace_base_path or Path("/tmp/compymac_traces")
    store, _ = create_trace_store(base_path)
    events = store.get_cognitive_events(trace_id)

    # Categorize events
    thinking_events = [e for e in events if e.event_type == "think"]
    temptation_events = [e for e in events if e.event_type == "temptation_awareness"]

    # Check required scenarios
    required_scenarios = [
        "before_claiming_completion",
        "before_advancing_to_fix",
        "before_git_operations",
    ]

    scenario_compliance = {}
    for scenario in required_scenarios:
        satisfied = any(
            scenario in (e.metadata.get("trigger", "") or "")
            for e in thinking_events
            if e.metadata
        )
        scenario_compliance[scenario] = satisfied

    # Calculate compliance rate
    satisfied_count = sum(1 for v in scenario_compliance.values() if v)
    compliance_rate = satisfied_count / len(required_scenarios) if required_scenarios else 1.0

    # Calculate temptation resistance rate
    resisted_count = sum(
        1 for e in temptation_events
        if e.metadata and e.metadata.get("resisted", False)
    )
    resistance_rate = resisted_count / len(temptation_events) if temptation_events else 1.0

    # Get thinking samples for manual review
    thinking_samples = []
    for e in thinking_events[:5]:  # First 5 samples
        thinking_samples.append({
            "content": e.content[:500] if e.content else "",
            "trigger": e.metadata.get("trigger", "unspecified") if e.metadata else "unspecified",
            "phase": e.phase,
        })

    return CognitiveComplianceReport(
        trace_id=trace_id,
        task_id=task_id,
        total_thinking_events=len(thinking_events),
        total_temptation_events=len(temptation_events),
        thinking_compliance_rate=compliance_rate,
        temptation_resistance_rate=resistance_rate,
        required_scenarios_satisfied=scenario_compliance,
        thinking_samples=thinking_samples,
    )


def download_swebench_lite() -> list[dict]:
    """Download SWE-bench lite dataset from HuggingFace."""
    logger.info("Downloading SWE-bench lite dataset from HuggingFace...")

    try:
        dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        logger.info(f"Downloaded {len(dataset)} tasks from SWE-bench lite")
        return list(dataset)
    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        raise


def convert_to_swebench_task(item: dict) -> SWEBenchTask:
    """Convert HuggingFace dataset item to SWEBenchTask."""
    return SWEBenchTask(
        instance_id=item["instance_id"],
        repo=item["repo"],
        version=item["base_commit"],
        problem_statement=item["problem_statement"],
        hints_text=item.get("hints_text", ""),
        gold_patch=item.get("patch", ""),
        test_patch=item.get("test_patch", ""),
        fail_to_pass=json.loads(item.get("FAIL_TO_PASS", "[]")),
        pass_to_pass=json.loads(item.get("PASS_TO_PASS", "[]")),
        created_at=item.get("created_at", ""),
        difficulty="medium",
    )


def select_tasks(
    all_tasks: list[dict],
    config: V5ValidationConfig,
) -> list[SWEBenchTask]:
    """Select tasks for validation experiments."""
    import random

    random.seed(config.seed)

    # If specific task requested
    if config.specific_task_id:
        for task in all_tasks:
            if task["instance_id"] == config.specific_task_id:
                return [convert_to_swebench_task(task)]
        logger.error(f"Task {config.specific_task_id} not found in dataset")
        return []

    # If using recommended tasks
    if config.use_recommended:
        selected = []
        all_recommended = (
            RECOMMENDED_TASKS["easy"] +
            RECOMMENDED_TASKS["medium"] +
            RECOMMENDED_TASKS["hard"]
        )

        for task in all_tasks:
            if task["instance_id"] in all_recommended:
                selected.append(convert_to_swebench_task(task))
                if len(selected) >= config.num_tasks:
                    break

        if selected:
            logger.info(f"Selected {len(selected)} recommended tasks")
            return selected[:config.num_tasks]

    # Fall back to diverse selection
    by_repo: dict[str, list[dict]] = {}
    for task in all_tasks:
        repo = task["repo"]
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(task)

    selected = []
    repos = list(by_repo.keys())
    random.shuffle(repos)

    repo_idx = 0
    while len(selected) < config.num_tasks and any(by_repo.values()):
        repo = repos[repo_idx % len(repos)]
        if by_repo[repo]:
            task = by_repo[repo].pop(0)
            selected.append(convert_to_swebench_task(task))
        repo_idx += 1
        repos = [r for r in repos if by_repo[r]]

    return selected


def print_task_summary(tasks: list[SWEBenchTask]) -> None:
    """Print summary of selected tasks."""
    print("\n" + "=" * 60)
    print("V5 VALIDATION EXPERIMENT TASKS")
    print("=" * 60)

    for i, task in enumerate(tasks, 1):
        difficulty = "unknown"
        if task.instance_id in RECOMMENDED_TASKS["easy"]:
            difficulty = "easy"
        elif task.instance_id in RECOMMENDED_TASKS["medium"]:
            difficulty = "medium"
        elif task.instance_id in RECOMMENDED_TASKS["hard"]:
            difficulty = "hard"

        print(f"\n{i}. {task.instance_id} [{difficulty}]")
        print(f"   Repo: {task.repo}")
        print(f"   Problem: {task.problem_statement[:100]}...")
        print(f"   Tests to fix: {len(task.fail_to_pass)}")

    print("\n" + "=" * 60)


async def run_validation_dry_run(tasks: list[SWEBenchTask], config: V5ValidationConfig) -> None:
    """Run validation in dry-run mode."""
    print("\n" + "=" * 60)
    print("DRY RUN MODE - No actual execution")
    print("=" * 60)

    print(f"\nWould run {len(tasks)} tasks with V5 metacognitive scaffolding:")
    for task in tasks:
        print(f"  - {task.instance_id} ({task.repo})")

    print(f"\nWorkspace: {config.workspace_base}")
    print(f"Output: {config.output_dir}")

    print("\nFor each task, would:")
    print("  1. Run with V5 metacognitive scaffolding")
    print("  2. Capture full reasoning traces")
    print("  3. Analyze compliance report")
    print("  4. Review thinking content for coherence")
    print("  5. Identify failure modes (if task failed)")

    print("\nTo run for real, remove --dry-run flag")


@dataclass
class V5ValidationResult:
    """Combined result for a V5 validation experiment."""

    task_result: SWEBenchResult
    compliance_report: CognitiveComplianceReport | None

    def to_dict(self) -> dict:
        return {
            "task_result": self.task_result.to_dict(),
            "compliance_report": self.compliance_report.to_dict() if self.compliance_report else None,
        }


async def run_validation(
    tasks: list[SWEBenchTask],
    config: V5ValidationConfig,
) -> list[V5ValidationResult]:
    """Run V5 validation experiments."""
    from compymac.config import LLMConfig
    from compymac.llm import LLMClient
    from compymac.local_harness import LocalHarness

    # Validate LLM configuration
    # Use deterministic config (temperature=0) for consistent tool calling
    try:
        llm_config = LLMConfig.from_env_deterministic()
        if not llm_config.model or not llm_config.base_url:
            logger.error("LLM_MODEL and LLM_BASE_URL must be set")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load LLM config: {e}")
        sys.exit(1)

    # Create directories
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.workspace_base.mkdir(parents=True, exist_ok=True)

    # Initialize components
    logger.info("Initializing harness and LLM client...")
    harness = LocalHarness()
    llm_client = LLMClient(config=llm_config, validate_config=True)

    # V5: Create trace store for cognitive event capture
    from compymac.trace_store import create_trace_store
    trace_store, artifact_store = create_trace_store(config.output_dir / "traces")
    logger.info(f"Trace store initialized at {config.output_dir / 'traces'}")

    # Create runner with trace store for V5 cognitive event capture
    runner = SWEBenchRunner(
        harness=harness,
        llm_client=llm_client,
        workspace_base=config.workspace_base,
        trace_store=trace_store,
    )

    # Create dashboard
    dashboard = SWEBenchDashboard()

    # Results file
    results_file = config.output_dir / "v5_validation_results.jsonl"

    print("\n" + "=" * 60)
    print(f"RUNNING V5 VALIDATION EXPERIMENTS ({len(tasks)} tasks)")
    print("=" * 60)

    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Running {task.instance_id}...")
        start_time = time.time()

        try:
            task_result = await runner.run_task(task)
            dashboard.add_result(task_result)

            elapsed = time.time() - start_time
            status = "RESOLVED" if task_result.resolved else ("PARTIAL" if task_result.partial else "FAILED")
            print(f"    Status: {status} ({elapsed:.1f}s)")

            # Analyze cognitive compliance
            compliance_report = None
            if task_result.trace_id:
                print("    Analyzing cognitive compliance...")
                compliance_report = analyze_cognitive_compliance(
                    task_result.trace_id,
                    task.instance_id,
                    trace_base_path=config.output_dir / "traces",
                )
                print(f"    Thinking events: {compliance_report.total_thinking_events}")
                print(f"    Compliance rate: {compliance_report.thinking_compliance_rate:.1%}")
                print(f"    Temptation resistance: {compliance_report.temptation_resistance_rate:.1%}")

            v5_result = V5ValidationResult(
                task_result=task_result,
                compliance_report=compliance_report,
            )
            results.append(v5_result)

            # Save incrementally
            with open(results_file, "a") as f:
                f.write(json.dumps(v5_result.to_dict()) + "\n")

        except Exception as e:
            logger.error(f"Task {task.instance_id} crashed: {e}")
            task_result = SWEBenchResult(
                instance_id=task.instance_id,
                resolved=False,
                partial=False,
                failed=True,
                fail_to_pass_results={},
                pass_to_pass_results={},
                patch_generated="",
                tool_calls_made=0,
                tokens_used=0,
                time_elapsed_sec=time.time() - start_time,
                trace_id="",
                error_log=str(e),
            )
            v5_result = V5ValidationResult(
                task_result=task_result,
                compliance_report=None,
            )
            results.append(v5_result)

            with open(results_file, "a") as f:
                f.write(json.dumps(v5_result.to_dict()) + "\n")

    # Generate summary report
    print("\n" + "=" * 60)
    print("V5 VALIDATION EXPERIMENT RESULTS")
    print("=" * 60)

    report = dashboard.generate_report()
    print("\nTask Performance:")
    print(f"  Total tasks: {report.total_tasks}")
    print(f"  Resolved: {report.resolved} ({report.resolve_rate:.1%})")
    print(f"  Partial: {report.partial} ({report.partial_rate:.1%})")
    print(f"  Failed: {report.failed}")

    # Cognitive compliance summary
    compliance_reports = [r.compliance_report for r in results if r.compliance_report]
    if compliance_reports:
        avg_thinking = sum(r.total_thinking_events for r in compliance_reports) / len(compliance_reports)
        avg_compliance = sum(r.thinking_compliance_rate for r in compliance_reports) / len(compliance_reports)
        avg_resistance = sum(r.temptation_resistance_rate for r in compliance_reports) / len(compliance_reports)

        print("\nCognitive Compliance:")
        print(f"  Avg thinking events: {avg_thinking:.1f}")
        print(f"  Avg compliance rate: {avg_compliance:.1%}")
        print(f"  Avg temptation resistance: {avg_resistance:.1%}")

    # Save final summary
    summary_file = config.output_dir / "v5_validation_summary.json"
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {
            "num_tasks": config.num_tasks,
            "seed": config.seed,
            "use_recommended": config.use_recommended,
        },
        "task_performance": {
            "total": report.total_tasks,
            "resolved": report.resolved,
            "partial": report.partial,
            "failed": report.failed,
            "resolve_rate": report.resolve_rate,
        },
        "cognitive_compliance": {
            "avg_thinking_events": avg_thinking if compliance_reports else 0,
            "avg_compliance_rate": avg_compliance if compliance_reports else 0,
            "avg_temptation_resistance": avg_resistance if compliance_reports else 0,
        },
    }

    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to {config.output_dir}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run V5 metacognitive validation experiments"
    )
    parser.add_argument(
        "--num-tasks",
        type=int,
        default=5,
        help="Number of tasks to run (default: 5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for task selection (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("v5_validation_results"),
        help="Directory for output files",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Run a specific task by instance_id",
    )
    parser.add_argument(
        "--no-recommended",
        action="store_true",
        help="Don't prioritize recommended tasks",
    )

    args = parser.parse_args()

    config = V5ValidationConfig(
        num_tasks=args.num_tasks,
        seed=args.seed,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        specific_task_id=args.task_id,
        use_recommended=not args.no_recommended,
    )

    # Download dataset
    raw_tasks = download_swebench_lite()

    # Select tasks
    tasks = select_tasks(raw_tasks, config)

    if not tasks:
        logger.error("No tasks selected")
        sys.exit(1)

    # Print summary
    print_task_summary(tasks)

    # Run validation
    if config.dry_run:
        asyncio.run(run_validation_dry_run(tasks, config))
    else:
        asyncio.run(run_validation(tasks, config))


if __name__ == "__main__":
    main()
