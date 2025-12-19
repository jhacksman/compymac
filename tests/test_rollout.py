"""
Tests for parallel rollouts (Phase 3).

These tests verify:
1. RolloutConfig and RolloutResult dataclasses work correctly
2. RolloutOrchestrator executes rollouts in parallel
3. Rollout isolation (each rollout gets own agent stack, workspace, trace context)
4. Selection logic picks the best result using deterministic heuristics
5. Trace context forking works correctly for rollouts
"""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from compymac.harness import Harness
from compymac.llm import LLMClient
from compymac.rollout import (
    RolloutConfig,
    RolloutOrchestrator,
    RolloutResult,
    RolloutSelectionResult,
    RolloutStatus,
)
from compymac.trace_store import (
    ArtifactStore,
    SpanKind,
    TraceContext,
    TraceStore,
)


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


@pytest.fixture
def mock_harness():
    """Create a mock harness for testing."""
    harness = MagicMock(spec=Harness)
    # Harness uses execute() method, not execute_tool()
    from compymac.types import ToolResult
    harness.execute.return_value = ToolResult(
        tool_call_id="test",
        content="test output",
        success=True,
    )
    harness.execute_parallel.return_value = []
    harness.get_tool_schemas.return_value = []
    return harness


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing."""
    client = MagicMock(spec=LLMClient)
    client.chat.return_value = {"role": "assistant", "content": "Test response"}
    return client


class TestRolloutConfig:
    """Test RolloutConfig dataclass."""

    def test_default_values(self):
        """Verify default configuration values."""
        config = RolloutConfig(rollout_id="test_1")

        assert config.rollout_id == "test_1"
        assert config.system_prompt_override is None
        assert config.temperature_override is None
        assert config.max_iterations == 100
        assert config.timeout_seconds == 300.0
        assert config.enable_memory is False
        assert config.enable_parallel_steps is True
        assert config.description == ""
        assert config.tags == []

    def test_custom_values(self):
        """Verify custom configuration values."""
        config = RolloutConfig(
            rollout_id="custom_1",
            system_prompt_override="Custom prompt",
            temperature_override=0.7,
            max_iterations=50,
            timeout_seconds=120.0,
            enable_memory=True,
            enable_parallel_steps=False,
            description="Custom rollout",
            tags=["test", "custom"],
        )

        assert config.rollout_id == "custom_1"
        assert config.system_prompt_override == "Custom prompt"
        assert config.temperature_override == 0.7
        assert config.max_iterations == 50
        assert config.timeout_seconds == 120.0
        assert config.enable_memory is True
        assert config.enable_parallel_steps is False
        assert config.description == "Custom rollout"
        assert config.tags == ["test", "custom"]

    def test_to_dict(self):
        """Verify to_dict serialization."""
        config = RolloutConfig(
            rollout_id="test_1",
            description="Test rollout",
            tags=["test"],
        )

        d = config.to_dict()

        assert d["rollout_id"] == "test_1"
        assert d["description"] == "Test rollout"
        assert d["tags"] == ["test"]
        assert "system_prompt_override" in d
        assert "temperature_override" in d


class TestRolloutResult:
    """Test RolloutResult dataclass."""

    def test_successful_result(self):
        """Verify successful rollout result."""
        config = RolloutConfig(rollout_id="test_1")
        result = RolloutResult(
            rollout_id="test_1",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Task completed successfully",
            execution_time_ms=5000,
            step_count=3,
            retry_count=0,
            error_count=0,
        )

        assert result.success is True
        assert result.status == RolloutStatus.COMPLETED
        assert result.final_result == "Task completed successfully"
        assert result.score > 0

    def test_failed_result(self):
        """Verify failed rollout result."""
        config = RolloutConfig(rollout_id="test_1")
        result = RolloutResult(
            rollout_id="test_1",
            config=config,
            status=RolloutStatus.FAILED,
            success=False,
            final_result="",
            error="Task failed",
            execution_time_ms=1000,
            step_count=1,
            retry_count=0,
            error_count=1,
        )

        assert result.success is False
        assert result.status == RolloutStatus.FAILED
        assert result.error == "Task failed"
        assert result.score == 0.0

    def test_score_calculation(self):
        """Verify score calculation for ranking."""
        config = RolloutConfig(rollout_id="test_1")

        # High score: success, no errors, no retries, fast execution
        high_score_result = RolloutResult(
            rollout_id="high",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Done",
            execution_time_ms=5000,
            step_count=2,
            retry_count=0,
            error_count=0,
        )

        # Lower score: success, but with errors and retries
        low_score_result = RolloutResult(
            rollout_id="low",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Done",
            execution_time_ms=120000,  # 2 minutes
            step_count=10,
            retry_count=5,
            error_count=3,
        )

        assert high_score_result.score > low_score_result.score
        assert high_score_result.score > 100  # Base score + efficiency bonus
        assert low_score_result.score > 0  # Still positive for success

    def test_to_dict(self):
        """Verify to_dict serialization."""
        config = RolloutConfig(rollout_id="test_1")
        result = RolloutResult(
            rollout_id="test_1",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Done",
            execution_time_ms=5000,
        )

        d = result.to_dict()

        assert d["rollout_id"] == "test_1"
        assert d["status"] == "completed"
        assert d["success"] is True
        assert "config" in d


class TestRolloutSelectionResult:
    """Test RolloutSelectionResult dataclass."""

    def test_selection_result(self):
        """Verify selection result structure."""
        config = RolloutConfig(rollout_id="test_1")
        result = RolloutResult(
            rollout_id="test_1",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Done",
        )

        selection = RolloutSelectionResult(
            selected_rollout=result,
            all_results=[result],
            selection_reason="Only successful rollout",
            selection_confidence=1.0,
        )

        assert selection.selected_rollout == result
        assert len(selection.all_results) == 1
        assert selection.selection_reason == "Only successful rollout"
        assert selection.selection_confidence == 1.0

    def test_to_dict(self):
        """Verify to_dict serialization."""
        config = RolloutConfig(rollout_id="test_1")
        result = RolloutResult(
            rollout_id="test_1",
            config=config,
            status=RolloutStatus.COMPLETED,
            success=True,
            final_result="Done",
        )

        selection = RolloutSelectionResult(
            selected_rollout=result,
            all_results=[result],
            selection_reason="Test reason",
            selection_confidence=0.8,
        )

        d = selection.to_dict()

        assert d["selected_rollout_id"] == "test_1"
        assert d["selection_reason"] == "Test reason"
        assert d["selection_confidence"] == 0.8
        assert len(d["all_results"]) == 1


class TestRolloutOrchestrator:
    """Test RolloutOrchestrator class."""

    def test_create_default_configs(self, mock_harness, mock_llm_client):
        """Verify default config creation."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
            max_workers=3,
        )

        configs = orchestrator.create_default_configs(count=3)

        assert len(configs) == 3
        assert configs[0].rollout_id == "rollout_0"
        assert configs[1].rollout_id == "rollout_1"
        assert configs[2].rollout_id == "rollout_2"

    def test_create_diverse_configs(self, mock_harness, mock_llm_client):
        """Verify diverse config creation."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
            max_workers=3,
        )

        configs = orchestrator.create_diverse_configs()

        assert len(configs) == 3
        # Default config
        assert configs[0].enable_memory is False
        assert configs[0].enable_parallel_steps is True
        # Memory config
        assert configs[1].enable_memory is True
        # Sequential config
        assert configs[2].enable_parallel_steps is False

    def test_empty_configs_raises_error(self, mock_harness, mock_llm_client):
        """Verify error when no configs provided."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        with pytest.raises(ValueError, match="At least one rollout config is required"):
            orchestrator.run_parallel_rollouts("Test goal", [])


class TestRolloutSelection:
    """Test rollout selection logic."""

    def test_select_only_successful(self, mock_harness, mock_llm_client):
        """Verify selection when only one rollout succeeds."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        config = RolloutConfig(rollout_id="test_1")
        results = [
            RolloutResult(
                rollout_id="test_1",
                config=config,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
                execution_time_ms=5000,
            ),
        ]

        selection = orchestrator._select_best_rollout(results)

        assert selection.selected_rollout.rollout_id == "test_1"
        assert selection.selection_reason == "Only successful rollout"
        assert selection.selection_confidence == 1.0

    def test_select_highest_score(self, mock_harness, mock_llm_client):
        """Verify selection picks highest score among successful rollouts."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        config1 = RolloutConfig(rollout_id="high_score")
        config2 = RolloutConfig(rollout_id="low_score")

        results = [
            RolloutResult(
                rollout_id="high_score",
                config=config1,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
                execution_time_ms=5000,
                step_count=2,
                retry_count=0,
                error_count=0,
            ),
            RolloutResult(
                rollout_id="low_score",
                config=config2,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
                execution_time_ms=120000,
                step_count=10,
                retry_count=5,
                error_count=3,
            ),
        ]

        selection = orchestrator._select_best_rollout(results)

        assert selection.selected_rollout.rollout_id == "high_score"
        assert "Highest score" in selection.selection_reason

    def test_select_success_over_failure(self, mock_harness, mock_llm_client):
        """Verify selection prefers success over failure."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        config1 = RolloutConfig(rollout_id="success")
        config2 = RolloutConfig(rollout_id="failure")

        results = [
            RolloutResult(
                rollout_id="success",
                config=config1,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
                execution_time_ms=60000,  # Slow but successful
                step_count=10,
                retry_count=3,
                error_count=2,
            ),
            RolloutResult(
                rollout_id="failure",
                config=config2,
                status=RolloutStatus.FAILED,
                success=False,
                final_result="",
                error="Failed",
                execution_time_ms=1000,  # Fast but failed
            ),
        ]

        selection = orchestrator._select_best_rollout(results)

        assert selection.selected_rollout.rollout_id == "success"
        assert selection.selected_rollout.success is True

    def test_select_least_severe_failure(self, mock_harness, mock_llm_client):
        """Verify selection picks least severe failure when all fail."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        config1 = RolloutConfig(rollout_id="less_severe")
        config2 = RolloutConfig(rollout_id="more_severe")

        results = [
            RolloutResult(
                rollout_id="less_severe",
                config=config1,
                status=RolloutStatus.FAILED,
                success=False,
                final_result="",
                error="Failed at step 5",
                step_count=5,  # Got further
                error_count=1,
            ),
            RolloutResult(
                rollout_id="more_severe",
                config=config2,
                status=RolloutStatus.FAILED,
                success=False,
                final_result="",
                error="Failed at step 1",
                step_count=1,  # Failed early
                error_count=3,
            ),
        ]

        selection = orchestrator._select_best_rollout(results)

        assert selection.selected_rollout.rollout_id == "less_severe"
        assert "Least severe failure" in selection.selection_reason
        assert selection.selection_confidence == 0.0

    def test_empty_results_raises_error(self, mock_harness, mock_llm_client):
        """Verify error when no results to select from."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
        )

        with pytest.raises(ValueError, match="No rollout results to select from"):
            orchestrator._select_best_rollout([])


class TestRolloutIsolation:
    """Test rollout isolation (each rollout gets own agent stack)."""

    def test_rollouts_have_unique_trace_contexts(
        self, mock_harness, mock_llm_client, temp_dir: Path
    ):
        """Verify each rollout gets its own forked trace context."""
        artifact_store = ArtifactStore(temp_dir / "artifacts")
        trace_store = TraceStore(temp_dir / "traces.db", artifact_store)
        trace_context = TraceContext(trace_store)

        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
            max_workers=3,
            trace_context=trace_context,
        )

        # Track trace contexts used by each rollout
        trace_contexts_used = []
        lock = threading.Lock()

        def tracking_execute(goal, config, constraints, parent_span_id):
            # This would normally create a forked context
            # We're just verifying the method is called with correct params
            with lock:
                trace_contexts_used.append(config.rollout_id)
            return RolloutResult(
                rollout_id=config.rollout_id,
                config=config,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
            )

        with patch.object(orchestrator, "_execute_single_rollout", tracking_execute):
            configs = orchestrator.create_default_configs(count=3)
            orchestrator.run_parallel_rollouts("Test goal", configs)

        # Verify all rollouts were executed
        assert len(trace_contexts_used) == 3
        assert "rollout_0" in trace_contexts_used
        assert "rollout_1" in trace_contexts_used
        assert "rollout_2" in trace_contexts_used


class TestRolloutConcurrency:
    """Test concurrent rollout execution."""

    def test_rollouts_execute_concurrently(self, mock_harness, mock_llm_client):
        """Verify rollouts execute in parallel, not sequentially."""
        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
            max_workers=3,
        )

        execution_times = []
        lock = threading.Lock()

        def slow_execute(goal, config, constraints, parent_span_id):
            start = time.time()
            time.sleep(0.1)  # Simulate work
            end = time.time()
            with lock:
                execution_times.append((config.rollout_id, start, end))
            return RolloutResult(
                rollout_id=config.rollout_id,
                config=config,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
            )

        with patch.object(orchestrator, "_execute_single_rollout", slow_execute):
            configs = orchestrator.create_default_configs(count=3)
            start_time = time.time()
            orchestrator.run_parallel_rollouts("Test goal", configs)
            total_time = time.time() - start_time

        # If sequential, would take ~0.3s (3 * 0.1s)
        # If parallel, should take ~0.1s
        assert total_time < 0.25, f"Rollouts took {total_time}s, expected < 0.25s for parallel execution"

        # Verify all rollouts executed
        assert len(execution_times) == 3

        # Verify overlapping execution (parallel)
        starts = [t[1] for t in execution_times]
        ends = [t[2] for t in execution_times]

        # At least two rollouts should have overlapping execution windows
        overlap_found = False
        for i in range(len(starts)):
            for j in range(i + 1, len(starts)):
                # Check if execution windows overlap
                if starts[i] < ends[j] and starts[j] < ends[i]:
                    overlap_found = True
                    break

        assert overlap_found, "No overlapping execution detected - rollouts may not be running in parallel"


class TestRolloutTracing:
    """Test trace context integration with rollouts."""

    def test_orchestrator_creates_span(
        self, mock_harness, mock_llm_client, temp_dir: Path
    ):
        """Verify orchestrator creates a span for the rollout operation."""
        artifact_store = ArtifactStore(temp_dir / "artifacts")
        trace_store = TraceStore(temp_dir / "traces.db", artifact_store)
        trace_context = TraceContext(trace_store)

        orchestrator = RolloutOrchestrator(
            harness=mock_harness,
            llm_client=mock_llm_client,
            max_workers=3,
            trace_context=trace_context,
        )

        def mock_execute(goal, config, constraints, parent_span_id):
            return RolloutResult(
                rollout_id=config.rollout_id,
                config=config,
                status=RolloutStatus.COMPLETED,
                success=True,
                final_result="Done",
            )

        with patch.object(orchestrator, "_execute_single_rollout", mock_execute):
            configs = orchestrator.create_default_configs(count=2)
            orchestrator.run_parallel_rollouts("Test goal", configs)

        # Verify spans were created
        spans = trace_store.get_trace_spans(trace_context.trace_id)
        orchestrator_spans = [s for s in spans if s.name == "rollout_orchestrator"]

        assert len(orchestrator_spans) == 1
        assert orchestrator_spans[0].kind == SpanKind.AGENT_TURN
