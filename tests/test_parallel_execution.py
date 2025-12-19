"""
Tests for parallel execution support.

These tests verify:
1. TraceContext parentage isn't corrupted under parallel execution
2. SQLite TraceStore handles concurrent writes without "database is locked" errors
3. Tool conflict model correctly identifies parallel-safe vs exclusive tools
4. Forked TraceContext maintains independent span stacks
"""

import tempfile
import threading
import time
from pathlib import Path

import pytest

from compymac.local_harness import LocalHarness
from compymac.trace_store import (
    ArtifactStore,
    SpanKind,
    SpanStatus,
    TraceContext,
    TraceStore,
    generate_trace_id,
)
from compymac.types import ToolCall


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def trace_store(temp_dir: Path) -> TraceStore:
    """Create a TraceStore for testing."""
    artifact_store = ArtifactStore(temp_dir / "artifacts")
    return TraceStore(temp_dir / "traces.db", artifact_store)


class TestTraceStoreConcurrency:
    """Test SQLite TraceStore under concurrent writes."""

    def test_concurrent_span_writes_no_lock_errors(self, trace_store: TraceStore):
        """Verify that concurrent span writes don't cause 'database is locked' errors."""
        trace_id = generate_trace_id()
        num_threads = 10
        spans_per_thread = 20
        errors: list[Exception] = []
        span_ids: list[str] = []
        lock = threading.Lock()

        def write_spans(thread_id: int) -> None:
            try:
                for i in range(spans_per_thread):
                    span_id = trace_store.start_span(
                        trace_id=trace_id,
                        kind=SpanKind.TOOL_CALL,
                        name=f"task_{thread_id}_{i}",
                        actor_id=f"executor-{thread_id}",
                    )
                    with lock:
                        span_ids.append(span_id)
                    # Small delay to increase chance of contention
                    time.sleep(0.001)
                    trace_store.end_span(trace_id, span_id, SpanStatus.OK)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=write_spans, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        # Verify all spans were written
        spans = trace_store.get_trace_spans(trace_id)
        assert len(spans) == num_threads * spans_per_thread

    def test_concurrent_artifact_storage(self, trace_store: TraceStore):
        """Verify that concurrent artifact storage works correctly."""
        num_threads = 10
        artifacts_per_thread = 10
        errors: list[Exception] = []
        artifact_hashes: list[str] = []
        lock = threading.Lock()

        def store_artifacts(thread_id: int) -> None:
            try:
                for i in range(artifacts_per_thread):
                    data = f"artifact_{thread_id}_{i}_{time.time()}".encode()
                    artifact = trace_store.store_artifact(
                        data=data,
                        artifact_type="test",
                        content_type="text/plain",
                    )
                    with lock:
                        artifact_hashes.append(artifact.artifact_hash)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [
            threading.Thread(target=store_artifacts, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during concurrent artifact storage: {errors}"

        # Verify all artifacts were stored (unique hashes since data is unique)
        assert len(artifact_hashes) == num_threads * artifacts_per_thread


class TestTraceContextConcurrency:
    """Test TraceContext behavior under concurrent access."""

    def test_shared_context_corrupts_parentage(self, trace_store: TraceStore):
        """
        Demonstrate that sharing a single TraceContext across threads
        corrupts parent-child relationships.

        This test documents the CURRENT BROKEN behavior that we need to fix.
        """
        ctx = TraceContext(trace_store)
        num_threads = 5
        results: dict[int, list[str]] = {}
        lock = threading.Lock()

        def create_nested_spans(thread_id: int) -> None:
            """Each thread creates parent -> child spans."""
            with lock:
                results[thread_id] = []

            # Start parent span
            parent_id = ctx.start_span(
                SpanKind.AGENT_TURN,
                f"parent_{thread_id}",
                f"agent-{thread_id}",
            )
            with lock:
                results[thread_id].append(("parent", parent_id, ctx.current_span_id))

            time.sleep(0.01)  # Increase chance of interleaving

            # Start child span
            child_id = ctx.start_span(
                SpanKind.TOOL_CALL,
                f"child_{thread_id}",
                f"executor-{thread_id}",
            )
            with lock:
                results[thread_id].append(("child", child_id, ctx.current_span_id))

            time.sleep(0.01)

            # End child
            ctx.end_span(SpanStatus.OK)
            with lock:
                results[thread_id].append(("after_child_end", None, ctx.current_span_id))

            # End parent
            ctx.end_span(SpanStatus.OK)

        threads = [
            threading.Thread(target=create_nested_spans, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check for corruption: after ending child, current_span_id should be parent
        # But with shared context, it will likely be wrong
        corrupted = False
        for _thread_id, events in results.items():
            parent_event = next(e for e in events if e[0] == "parent")
            after_child = next(e for e in events if e[0] == "after_child_end")
            parent_id = parent_event[1]
            current_after_child = after_child[2]

            # In correct behavior, current_span_id after ending child should be parent_id
            # With shared context corruption, this will often be wrong
            if current_after_child != parent_id:
                corrupted = True
                break

        # We EXPECT corruption with the current implementation
        # This test documents the problem we're fixing
        # Once we implement forked contexts, this test should be updated
        # to verify NO corruption occurs
        assert corrupted, (
            "Expected parentage corruption with shared TraceContext, "
            "but none detected. Either the test didn't trigger interleaving, "
            "or the implementation has changed."
        )


class TestForkedTraceContext:
    """Test the forked TraceContext implementation for parallel execution."""

    def test_forked_context_independent_stacks(self, trace_store: TraceStore):
        """Verify that forked contexts have independent span stacks."""
        # Create main context with a parent span
        main_ctx = TraceContext(trace_store)
        parent_span = main_ctx.start_span(
            SpanKind.AGENT_TURN,
            "main_turn",
            "manager",
        )

        # Fork contexts for parallel workers
        from compymac.parallel import fork_trace_context

        forked_ctx_1 = fork_trace_context(main_ctx, parent_span)
        forked_ctx_2 = fork_trace_context(main_ctx, parent_span)

        # Each forked context should have the same trace_id but independent stacks
        assert forked_ctx_1.trace_id == main_ctx.trace_id
        assert forked_ctx_2.trace_id == main_ctx.trace_id

        # Start spans in forked contexts
        span_1 = forked_ctx_1.start_span(
            SpanKind.TOOL_CALL,
            "task_1",
            "executor-1",
        )
        span_2 = forked_ctx_2.start_span(
            SpanKind.TOOL_CALL,
            "task_2",
            "executor-2",
        )

        # Each forked context should track its own current span
        assert forked_ctx_1.current_span_id == span_1
        assert forked_ctx_2.current_span_id == span_2

        # Main context should still have parent as current
        assert main_ctx.current_span_id == parent_span

        # End spans
        forked_ctx_1.end_span(SpanStatus.OK)
        forked_ctx_2.end_span(SpanStatus.OK)

        # Verify parent relationships
        spans = trace_store.get_trace_spans(main_ctx.trace_id)
        task_spans = [s for s in spans if s.name in ("task_1", "task_2")]

        for span in task_spans:
            assert span.parent_span_id == parent_span

        # End main span
        main_ctx.end_span(SpanStatus.OK)

    def test_forked_context_parallel_execution_no_corruption(
        self, trace_store: TraceStore
    ):
        """Verify that forked contexts prevent parentage corruption under parallel execution."""
        from compymac.parallel import fork_trace_context

        main_ctx = TraceContext(trace_store)
        parent_span = main_ctx.start_span(
            SpanKind.AGENT_TURN,
            "parallel_parent",
            "manager",
        )

        num_workers = 10
        spans_per_worker = 5
        errors: list[Exception] = []
        worker_spans: dict[int, list[str]] = {}
        lock = threading.Lock()

        def worker_task(worker_id: int, forked_ctx: TraceContext) -> None:
            try:
                with lock:
                    worker_spans[worker_id] = []

                for i in range(spans_per_worker):
                    span_id = forked_ctx.start_span(
                        SpanKind.TOOL_CALL,
                        f"task_{worker_id}_{i}",
                        f"executor-{worker_id}",
                    )
                    with lock:
                        worker_spans[worker_id].append(span_id)

                    time.sleep(0.005)  # Simulate work

                    forked_ctx.end_span(SpanStatus.OK)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Create forked contexts for each worker
        forked_contexts = [
            fork_trace_context(main_ctx, parent_span)
            for _ in range(num_workers)
        ]

        # Run workers in parallel
        threads = [
            threading.Thread(target=worker_task, args=(i, forked_contexts[i]))
            for i in range(num_workers)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0, f"Errors during parallel execution: {errors}"

        # End parent span
        main_ctx.end_span(SpanStatus.OK)

        # Verify all spans have correct parent
        spans = trace_store.get_trace_spans(main_ctx.trace_id)
        task_spans = [s for s in spans if s.name.startswith("task_")]

        assert len(task_spans) == num_workers * spans_per_worker

        for span in task_spans:
            assert span.parent_span_id == parent_span, (
                f"Span {span.name} has wrong parent: "
                f"expected {parent_span}, got {span.parent_span_id}"
            )


class TestToolConflictModel:
    """Test the tool conflict model for parallel execution."""

    def test_tool_classification(self):
        """Verify tools are correctly classified as parallel_safe or exclusive."""
        from compymac.parallel import ConflictClass, ToolConflictModel

        model = ToolConflictModel()

        # Read should be parallel_safe
        assert model.get_conflict_class("Read") == ConflictClass.PARALLEL_SAFE

        # Write should be exclusive (per-path)
        assert model.get_conflict_class("Write") == ConflictClass.EXCLUSIVE

        # Bash should be exclusive (stateful)
        assert model.get_conflict_class("Bash") == ConflictClass.EXCLUSIVE

    def test_can_run_parallel(self):
        """Verify parallel execution decisions are correct."""
        from compymac.parallel import ToolConflictModel

        model = ToolConflictModel()

        # Two reads can run in parallel
        read1 = ToolCall(id="1", name="Read", arguments={"file_path": "/a.txt"})
        read2 = ToolCall(id="2", name="Read", arguments={"file_path": "/b.txt"})
        assert model.can_run_parallel([read1, read2])

        # Read and write to different files can run in parallel
        write1 = ToolCall(
            id="3", name="Write", arguments={"file_path": "/c.txt", "content": "x"}
        )
        assert model.can_run_parallel([read1, write1])

        # Two writes to same file cannot run in parallel
        write2 = ToolCall(
            id="4", name="Write", arguments={"file_path": "/c.txt", "content": "y"}
        )
        assert not model.can_run_parallel([write1, write2])

        # Bash commands cannot run in parallel (stateful)
        bash1 = ToolCall(
            id="5", name="Bash", arguments={"command": "ls", "exec_dir": "/"}
        )
        bash2 = ToolCall(
            id="6", name="Bash", arguments={"command": "pwd", "exec_dir": "/"}
        )
        assert not model.can_run_parallel([bash1, bash2])


class TestParallelExecution:
    """Test actual parallel tool execution."""

    def test_execute_parallel_with_forked_contexts(self, temp_dir: Path):
        """Verify parallel execution with proper trace context forking."""
        from compymac.parallel import ParallelExecutor

        # Set up tracing
        artifact_store = ArtifactStore(temp_dir / "artifacts")
        trace_store = TraceStore(temp_dir / "traces.db", artifact_store)
        trace_context = TraceContext(trace_store)

        # Set up harness
        harness = LocalHarness(full_output_dir=temp_dir / "outputs")

        # Create executor
        executor = ParallelExecutor(
            harness=harness,
            trace_context=trace_context,
            max_workers=4,
        )

        # Create test files
        for i in range(4):
            (temp_dir / f"test_{i}.txt").write_text(f"Content {i}")

        # Start parent span
        parent_span = trace_context.start_span(
            SpanKind.AGENT_TURN,
            "parallel_test",
            "manager",
        )

        # Execute parallel reads
        tool_calls = [
            ToolCall(
                id=f"read_{i}",
                name="Read",
                arguments={"file_path": str(temp_dir / f"test_{i}.txt")},
            )
            for i in range(4)
        ]

        results = executor.execute_parallel(tool_calls, parent_span_id=parent_span)

        # End parent span
        trace_context.end_span(SpanStatus.OK)

        # Verify all succeeded
        assert len(results) == 4
        for result in results:
            assert result.success

        # Verify trace structure
        spans = trace_store.get_trace_spans(trace_context.trace_id)
        tool_spans = [s for s in spans if s.kind == SpanKind.TOOL_CALL]

        assert len(tool_spans) == 4
        for span in tool_spans:
            assert span.parent_span_id == parent_span

    def test_execute_parallel_respects_conflicts(self, temp_dir: Path):
        """Verify that conflicting tools are executed sequentially."""
        from compymac.parallel import ParallelExecutor

        # Set up
        artifact_store = ArtifactStore(temp_dir / "artifacts")
        trace_store = TraceStore(temp_dir / "traces.db", artifact_store)
        trace_context = TraceContext(trace_store)
        harness = LocalHarness(full_output_dir=temp_dir / "outputs")

        executor = ParallelExecutor(
            harness=harness,
            trace_context=trace_context,
            max_workers=4,
        )

        # Start parent span
        parent_span = trace_context.start_span(
            SpanKind.AGENT_TURN,
            "conflict_test",
            "manager",
        )

        # Execute writes to same file (should be sequential)
        target_file = temp_dir / "shared.txt"
        tool_calls = [
            ToolCall(
                id=f"write_{i}",
                name="Write",
                arguments={"file_path": str(target_file), "content": f"Content {i}"},
            )
            for i in range(3)
        ]

        results = executor.execute_parallel(tool_calls, parent_span_id=parent_span)

        # End parent span
        trace_context.end_span(SpanStatus.OK)

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result.success

        # File should have last write's content
        assert target_file.read_text() == "Content 2"
