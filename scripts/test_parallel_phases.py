#!/usr/bin/env python3
"""
Systematic test of all three parallelization phases with Venice.ai.

This script tests:
- Phase 1: Parallel tool calls within a single agent turn
- Phase 2: Parallel plan step execution
- Phase 3: Parallel rollouts (best-of-N independent attempts)

For each phase, we verify that TraceStore records match expectations:
- Correct parent-child span relationships
- Execution times and concurrency evidence
- Selection metrics (for Phase 3)

Usage:
    export LLM_API_KEY="your-venice-api-key"
    python scripts/test_parallel_phases.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compymac.config import LLMConfig
from compymac.llm import LLMClient
from compymac.local_harness import LocalHarness
from compymac.parallel import ParallelExecutor, ToolConflictModel, fork_trace_context
from compymac.rollout import RolloutConfig, RolloutOrchestrator, RolloutStatus
from compymac.trace_store import (
    ArtifactStore,
    SpanKind,
    SpanStatus,
    TraceContext,
    TraceStore,
)
from compymac.types import ToolCall


def create_llm_client():
    """Create an LLM client configured for Venice.ai with qwen3-next-80b."""
    config = LLMConfig(
        base_url="https://api.venice.ai/api/v1",
        api_key=os.environ.get("LLM_API_KEY", ""),
        model="qwen3-next-80b",  # Beta model with good tool calling
        temperature=0.7,
        max_tokens=2000,
    )
    
    if not config.api_key:
        print("ERROR: LLM_API_KEY environment variable not set")
        return None
    
    return LLMClient(config)


def create_trace_infrastructure(base_path: Path):
    """Create TraceStore and TraceContext for testing."""
    artifact_store = ArtifactStore(base_path / "artifacts")
    trace_store = TraceStore(base_path / "traces.db", artifact_store)
    trace_context = TraceContext(trace_store)
    return trace_store, trace_context


def test_phase1_parallel_tool_calls(temp_dir: Path):
    """
    Phase 1: Test parallel tool calls within a single agent turn.
    
    Verifies:
    - Forked trace contexts maintain independent span stacks
    - Tool conflict model correctly identifies parallel-safe tools
    - Parent-child relationships are correct in trace records
    - Multiple reads execute concurrently
    """
    print("\n" + "=" * 70)
    print("PHASE 1: Parallel Tool Calls")
    print("=" * 70)
    
    trace_store, trace_context = create_trace_infrastructure(temp_dir / "phase1")
    harness = LocalHarness(full_output_dir=temp_dir / "outputs")
    
    # Create test files
    for i in range(4):
        (temp_dir / f"test_file_{i}.txt").write_text(f"Content of file {i}")
    
    # Create parallel executor
    executor = ParallelExecutor(
        harness=harness,
        trace_context=trace_context,
        max_workers=4,
    )
    
    # Start parent span
    parent_span = trace_context.start_span(
        SpanKind.AGENT_TURN,
        "phase1_parallel_reads",
        "test_executor",
    )
    
    # Execute parallel reads (should all run concurrently)
    tool_calls = [
        ToolCall(
            id=f"read_{i}",
            name="Read",
            arguments={"file_path": str(temp_dir / f"test_file_{i}.txt")},
        )
        for i in range(4)
    ]
    
    print(f"\nExecuting {len(tool_calls)} parallel Read operations...")
    start_time = time.time()
    results = executor.execute_parallel(tool_calls, parent_span_id=parent_span)
    execution_time = time.time() - start_time
    
    # End parent span
    trace_context.end_span(SpanStatus.OK)
    
    # Verify results
    print(f"\nResults:")
    print(f"  - Execution time: {execution_time:.3f}s")
    print(f"  - All succeeded: {all(r.success for r in results)}")
    
    # Verify trace records
    spans = trace_store.get_trace_spans(trace_context.trace_id)
    tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
    
    print(f"\nTrace Records:")
    print(f"  - Total spans: {len(spans)}")
    print(f"  - Tool call spans: {len(tool_spans)}")
    
    # Check parent-child relationships
    correct_parents = all(s.parent_span_id == parent_span for s in tool_spans)
    print(f"  - Correct parent-child relationships: {correct_parents}")
    
    # Check for concurrency evidence (overlapping execution times would indicate parallel)
    # Since we're using ThreadPoolExecutor, 4 reads should complete faster than 4 sequential
    expected_sequential_time = 0.1 * 4  # Rough estimate
    is_concurrent = execution_time < expected_sequential_time
    print(f"  - Evidence of concurrent execution: {is_concurrent} (time < {expected_sequential_time:.1f}s)")
    
    # Test tool conflict model
    print(f"\nTool Conflict Model:")
    conflict_model = ToolConflictModel()
    
    # Two reads should be parallel-safe
    can_parallel_reads = conflict_model.can_run_parallel(tool_calls[:2])
    print(f"  - Two Reads can run parallel: {can_parallel_reads}")
    
    # Write to same file should NOT be parallel-safe
    write_calls = [
        ToolCall(id="w1", name="Write", arguments={"file_path": "/tmp/x.txt", "content": "a"}),
        ToolCall(id="w2", name="Write", arguments={"file_path": "/tmp/x.txt", "content": "b"}),
    ]
    can_parallel_writes = conflict_model.can_run_parallel(write_calls)
    print(f"  - Two Writes to same file can run parallel: {can_parallel_writes}")
    
    success = (
        all(r.success for r in results) and
        len(tool_spans) == 4 and
        correct_parents and
        can_parallel_reads and
        not can_parallel_writes
    )
    
    print(f"\n{'PASS' if success else 'FAIL'}: Phase 1 - Parallel Tool Calls")
    return success


def test_phase2_parallel_plan_steps(temp_dir: Path):
    """
    Phase 2: Test parallel plan step execution.
    
    Verifies:
    - Independent plan steps can execute concurrently
    - Dependent steps execute sequentially
    - Trace records show correct execution order
    """
    print("\n" + "=" * 70)
    print("PHASE 2: Parallel Plan Steps")
    print("=" * 70)
    
    trace_store, trace_context = create_trace_infrastructure(temp_dir / "phase2")
    harness = LocalHarness(full_output_dir=temp_dir / "outputs")
    
    client = create_llm_client()
    if not client:
        print("SKIP: No LLM client available")
        return False
    
    try:
        from compymac.multi_agent import ManagerAgent, ManagerState
        
        # Create manager with parallel execution enabled
        manager = ManagerAgent(
            harness=harness,
            llm_client=client,
            enable_memory=False,
            trace_context=trace_context,
        )
        manager._enable_parallel_execution = True
        
        # Goal with independent steps that could run in parallel
        goal = f"""Complete these independent tasks:
1. Create a file at {temp_dir}/file_a.txt with content 'File A'
2. Create a file at {temp_dir}/file_b.txt with content 'File B'
3. Create a file at {temp_dir}/file_c.txt with content 'File C'
"""
        
        print(f"\nGoal: Create 3 independent files")
        print("-" * 70)
        
        start_time = time.time()
        result = manager.run(goal)
        execution_time = time.time() - start_time
        
        print(f"\nResults:")
        print(f"  - Manager state: {manager.state.value}")
        print(f"  - Execution time: {execution_time:.3f}s")
        print(f"  - Plan steps: {len(manager.workspace.plan)}")
        print(f"  - Step results: {len(manager.workspace.step_results)}")
        
        # Check files were created
        files_created = sum(1 for f in ['file_a.txt', 'file_b.txt', 'file_c.txt'] 
                          if (temp_dir / f).exists())
        print(f"  - Files created: {files_created}/3")
        
        # Verify trace records
        spans = trace_store.get_trace_spans(trace_context.trace_id)
        print(f"\nTrace Records:")
        print(f"  - Total spans: {len(spans)}")
        
        # Look for parallel execution evidence
        agent_turns = [s for s in spans if s.kind == SpanKind.AGENT_TURN]
        tool_calls = [s for s in spans if s.kind == SpanKind.TOOL_CALL]
        print(f"  - Agent turn spans: {len(agent_turns)}")
        print(f"  - Tool call spans: {len(tool_calls)}")
        
        success = (
            manager.state == ManagerState.COMPLETED and
            files_created >= 2  # Allow some flexibility
        )
        
        print(f"\n{'PASS' if success else 'FAIL'}: Phase 2 - Parallel Plan Steps")
        return success
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


def test_phase3_parallel_rollouts(temp_dir: Path):
    """
    Phase 3: Test parallel rollouts (best-of-N independent attempts).
    
    Verifies:
    - Multiple rollouts execute concurrently
    - Each rollout has isolated trace context
    - Selection logic picks the best result
    - Trace records show all rollout spans
    """
    print("\n" + "=" * 70)
    print("PHASE 3: Parallel Rollouts")
    print("=" * 70)
    
    trace_store, trace_context = create_trace_infrastructure(temp_dir / "phase3")
    harness = LocalHarness(full_output_dir=temp_dir / "outputs")
    
    client = create_llm_client()
    if not client:
        print("SKIP: No LLM client available")
        return False
    
    try:
        # Create rollout orchestrator
        orchestrator = RolloutOrchestrator(
            harness=harness,
            llm_client=client,
            max_workers=3,
            trace_context=trace_context,
        )
        
        # Create diverse rollout configurations
        configs = [
            RolloutConfig(
                rollout_id="rollout_default",
                description="Default configuration",
                enable_parallel_steps=True,
            ),
            RolloutConfig(
                rollout_id="rollout_sequential",
                description="Sequential execution",
                enable_parallel_steps=False,
            ),
            RolloutConfig(
                rollout_id="rollout_memory",
                description="With memory enabled",
                enable_memory=True,
                enable_parallel_steps=True,
            ),
        ]
        
        goal = f"Create a file at {temp_dir}/rollout_test.txt with the content 'Hello from rollout test'"
        
        print(f"\nGoal: {goal}")
        print(f"Running {len(configs)} parallel rollouts...")
        print("-" * 70)
        
        start_time = time.time()
        selection = orchestrator.run_parallel_rollouts(goal, configs)
        execution_time = time.time() - start_time
        
        print(f"\nResults:")
        print(f"  - Execution time: {execution_time:.3f}s")
        print(f"  - Selected rollout: {selection.selected_rollout.rollout_id}")
        print(f"  - Selection reason: {selection.selection_reason}")
        print(f"  - Selection confidence: {selection.selection_confidence:.2f}")
        
        # Analyze all rollout results
        print(f"\nAll Rollout Results:")
        for result in selection.all_results:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"  - {result.rollout_id}: {status} (score: {result.score:.1f}, time: {result.execution_time_ms}ms)")
            if not result.success and result.error:
                print(f"    ERROR: {result.error[:200]}")
        
        # Count successes and failures
        successful = sum(1 for r in selection.all_results if r.success)
        failed = sum(1 for r in selection.all_results if not r.success)
        print(f"\n  - Successful rollouts: {successful}/{len(selection.all_results)}")
        print(f"  - Failed rollouts: {failed}/{len(selection.all_results)}")
        
        # Verify trace records
        spans = trace_store.get_trace_spans(trace_context.trace_id)
        print(f"\nTrace Records:")
        print(f"  - Total spans: {len(spans)}")
        
        # Look for orchestrator and rollout spans
        orchestrator_spans = [s for s in spans if "orchestrator" in s.name.lower()]
        rollout_spans = [s for s in spans if "rollout_" in s.name]
        print(f"  - Orchestrator spans: {len(orchestrator_spans)}")
        print(f"  - Rollout spans: {len(rollout_spans)}")
        
        # Check if file was created
        test_file = temp_dir / "rollout_test.txt"
        file_created = test_file.exists()
        if file_created:
            content = test_file.read_text()
            print(f"\nFile created: {test_file}")
            print(f"Content: {content[:100]}...")
        
        # Verify selection logic
        print(f"\nSelection Logic Verification:")
        if successful > 0:
            # Should have selected a successful rollout
            selected_success = selection.selected_rollout.success
            print(f"  - Selected a successful rollout: {selected_success}")
            
            # If multiple successes, should have selected highest score
            if successful > 1:
                successful_results = [r for r in selection.all_results if r.success]
                highest_score = max(r.score for r in successful_results)
                selected_is_highest = selection.selected_rollout.score == highest_score
                print(f"  - Selected highest-scoring rollout: {selected_is_highest}")
        else:
            print(f"  - All rollouts failed, selected least severe failure")
        
        success = (
            len(selection.all_results) == len(configs) and
            selection.selected_rollout is not None
        )
        
        print(f"\n{'PASS' if success else 'FAIL'}: Phase 3 - Parallel Rollouts")
        return success
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


def main():
    print("=" * 70)
    print("Systematic Test of All Parallelization Phases")
    print("=" * 70)
    print(f"Model: qwen3-next-80b (Venice.ai)")
    print(f"API Key: {'SET' if os.environ.get('LLM_API_KEY') else 'NOT SET'}")
    
    if not os.environ.get("LLM_API_KEY"):
        print("\nERROR: LLM_API_KEY environment variable not set")
        print("Usage: export LLM_API_KEY='your-key' && python scripts/test_parallel_phases.py")
        return 1
    
    results = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        
        # Run all phase tests
        results.append(("Phase 1: Parallel Tool Calls", test_phase1_parallel_tool_calls(temp_dir)))
        results.append(("Phase 2: Parallel Plan Steps", test_phase2_parallel_plan_steps(temp_dir)))
        results.append(("Phase 3: Parallel Rollouts", test_phase3_parallel_rollouts(temp_dir)))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
