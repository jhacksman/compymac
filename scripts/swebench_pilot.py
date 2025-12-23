#!/usr/bin/env python3
"""
SWE-Bench Pilot Script - Validate the pipeline with 5-10 real tasks.

This script:
1. Downloads SWE-bench lite dataset from HuggingFace
2. Selects a small sample of tasks (5-10)
3. Runs them through the CompyMac agent pipeline
4. Reports results and validates the infrastructure

Usage:
    python scripts/swebench_pilot.py --num-tasks 5 --dry-run
    python scripts/swebench_pilot.py --num-tasks 10
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class PilotConfig:
    """Configuration for the pilot run."""

    num_tasks: int = 5
    seed: int = 42
    dry_run: bool = False
    output_dir: Path = Path("pilot_results")
    workspace_base: Path = Path("/tmp/swebench_pilot")
    parallel: int = 1


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


def select_diverse_sample(
    tasks: list[dict], num_tasks: int, seed: int
) -> list[SWEBenchTask]:
    """Select a diverse sample of tasks across different repos."""
    import random

    random.seed(seed)

    # Group by repo
    by_repo: dict[str, list[dict]] = {}
    for task in tasks:
        repo = task["repo"]
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(task)

    logger.info(f"Found {len(by_repo)} unique repos in dataset")

    # Select tasks from different repos for diversity
    selected = []
    repos = list(by_repo.keys())
    random.shuffle(repos)

    # Round-robin selection from repos
    repo_idx = 0
    while len(selected) < num_tasks and any(by_repo.values()):
        repo = repos[repo_idx % len(repos)]
        if by_repo[repo]:
            task = by_repo[repo].pop(0)
            selected.append(convert_to_swebench_task(task))
        repo_idx += 1

        # Remove empty repos
        repos = [r for r in repos if by_repo[r]]

    logger.info(f"Selected {len(selected)} tasks from {len({t.repo for t in selected})} repos")
    return selected


def print_task_summary(tasks: list[SWEBenchTask]) -> None:
    """Print summary of selected tasks."""
    print("\n" + "=" * 60)
    print("SELECTED TASKS FOR PILOT")
    print("=" * 60)

    for i, task in enumerate(tasks, 1):
        print(f"\n{i}. {task.instance_id}")
        print(f"   Repo: {task.repo}")
        print(f"   Version: {task.version[:8]}...")
        print(f"   Problem: {task.problem_statement[:100]}...")
        print(f"   Tests to fix: {len(task.fail_to_pass)}")
        print(f"   Tests to keep: {len(task.pass_to_pass)}")

    print("\n" + "=" * 60)


async def run_pilot_dry_run(tasks: list[SWEBenchTask], config: PilotConfig) -> None:
    """Run pilot in dry-run mode (no actual execution)."""
    print("\n" + "=" * 60)
    print("DRY RUN MODE - No actual execution")
    print("=" * 60)

    print(f"\nWould run {len(tasks)} tasks:")
    for task in tasks:
        print(f"  - {task.instance_id} ({task.repo})")

    print(f"\nWorkspace: {config.workspace_base}")
    print(f"Output: {config.output_dir}")
    print(f"Parallel: {config.parallel}")

    print("\nTo run for real, remove --dry-run flag")


async def run_pilot(tasks: list[SWEBenchTask], config: PilotConfig) -> list[SWEBenchResult]:
    """Run the pilot with actual task execution."""
    from compymac.config import LLMConfig
    from compymac.llm import LLMClient
    from compymac.local_harness import LocalHarness

    # Validate LLM configuration
    try:
        llm_config = LLMConfig.from_env()
        if not llm_config.model or not llm_config.base_url:
            logger.error("LLM_MODEL and LLM_BASE_URL must be set")
            logger.error("Set these environment variables before running the pilot")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load LLM config: {e}")
        sys.exit(1)

    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.workspace_base.mkdir(parents=True, exist_ok=True)

    # Initialize components
    logger.info("Initializing harness and LLM client...")
    harness = LocalHarness()
    llm_client = LLMClient(config=llm_config, validate_config=True)

    # Create runner
    runner = SWEBenchRunner(
        harness=harness,
        llm_client=llm_client,
        workspace_base=config.workspace_base,
    )

    # Create dashboard for results
    dashboard = SWEBenchDashboard()

    # Run tasks
    print("\n" + "=" * 60)
    print(f"RUNNING {len(tasks)} TASKS")
    print("=" * 60)

    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Running {task.instance_id}...")
        start_time = time.time()

        try:
            result = await runner.run_task(task)
            results.append(result)
            dashboard.add_result(result)

            elapsed = time.time() - start_time
            status = "RESOLVED" if result.resolved else ("PARTIAL" if result.partial else "FAILED")
            print(f"    Status: {status} ({elapsed:.1f}s)")

            if result.error_log:
                print(f"    Error: {result.error_log[:100]}...")

        except Exception as e:
            logger.error(f"Task {task.instance_id} crashed: {e}")
            # Create a failed result
            result = SWEBenchResult(
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
            results.append(result)
            dashboard.add_result(result)

    # Generate and save report
    print("\n" + "=" * 60)
    print("PILOT RESULTS")
    print("=" * 60)

    report = dashboard.generate_report()
    print(f"\nTotal tasks: {report.total_tasks}")
    print(f"Resolved: {report.resolved} ({report.resolve_rate:.1%})")
    print(f"Partial: {report.partial} ({report.partial_rate:.1%})")
    print(f"Failed: {report.failed}")
    print(f"\nAvg tool calls: {report.avg_tool_calls:.1f}")
    print(f"Avg time: {report.avg_time_sec:.1f}s")

    # Save results
    results_file = config.output_dir / "pilot_results.json"
    dashboard.save_results(results_file)
    logger.info(f"Results saved to {results_file}")

    # Save detailed task results
    detailed_file = config.output_dir / "pilot_detailed.json"
    with open(detailed_file, "w") as f:
        json.dump([r.to_dict() for r in results], f, indent=2)
    logger.info(f"Detailed results saved to {detailed_file}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run SWE-bench pilot to validate the pipeline"
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
        default=Path("pilot_results"),
        help="Directory for output files (default: pilot_results)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel tasks (default: 1)",
    )

    args = parser.parse_args()

    config = PilotConfig(
        num_tasks=args.num_tasks,
        seed=args.seed,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        parallel=args.parallel,
    )

    # Download dataset
    raw_tasks = download_swebench_lite()

    # Select diverse sample
    tasks = select_diverse_sample(raw_tasks, config.num_tasks, config.seed)

    # Print summary
    print_task_summary(tasks)

    # Run pilot
    if config.dry_run:
        asyncio.run(run_pilot_dry_run(tasks, config))
    else:
        asyncio.run(run_pilot(tasks, config))


if __name__ == "__main__":
    main()
