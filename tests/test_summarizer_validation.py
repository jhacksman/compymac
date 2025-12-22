"""
Tests for ToolOutputSummarizer Validation (Gap 2).

Tests cover:
- TaskMetrics dataclass and serialization
- Omission and OmissionAnalysis dataclasses
- ABTestRunner for A/B testing
- OmissionAnalyzer for detecting lost information
- ThresholdTuner for finding optimal thresholds
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from compymac.summarizer_validation import (
    ABResults,
    ABTestRunner,
    ExperimentCondition,
    Omission,
    OmissionAnalysis,
    OmissionAnalyzer,
    OmissionCategory,
    OmissionImpact,
    OmissionReport,
    SummarizerConfig,
    TaskMetrics,
    ThresholdTuner,
)


class TestTaskMetrics:
    """Tests for TaskMetrics dataclass."""

    def test_creation(self) -> None:
        """Test metrics creation."""
        metrics = TaskMetrics(
            task_id="task-1",
            condition=ExperimentCondition.CONTROL,
            success=True,
            iterations=5,
            tool_calls=10,
            tokens_used=5000,
        )
        assert metrics.task_id == "task-1"
        assert metrics.condition == ExperimentCondition.CONTROL
        assert metrics.success is True
        assert metrics.iterations == 5
        assert metrics.tool_calls == 10
        assert metrics.tokens_used == 5000

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        metrics = TaskMetrics(
            task_id="task-1",
            condition=ExperimentCondition.TREATMENT,
            success=False,
            iterations=3,
            tool_calls=7,
        )
        data = metrics.to_dict()
        assert data["task_id"] == "task-1"
        assert data["condition"] == "treatment"
        assert data["success"] is False
        assert data["iterations"] == 3

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "task_id": "task-2",
            "condition": "control",
            "success": True,
            "iterations": 10,
            "tool_calls": 20,
            "tokens_used": 10000,
            "time_to_completion_sec": 120.5,
            "error_recoveries": 2,
            "false_starts": 1,
            "critical_info_missed": False,
            "bash_calls": 5,
            "bash_summarized": 2,
            "file_reads": 8,
            "file_reads_summarized": 3,
            "grep_calls": 4,
            "grep_summarized": 1,
            "started_at": 1000.0,
            "completed_at": 1120.5,
        }
        metrics = TaskMetrics.from_dict(data)
        assert metrics.task_id == "task-2"
        assert metrics.condition == ExperimentCondition.CONTROL
        assert metrics.success is True
        assert metrics.iterations == 10
        assert metrics.error_recoveries == 2

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        original = TaskMetrics(
            task_id="task-3",
            condition=ExperimentCondition.TREATMENT,
            success=True,
            iterations=7,
            tool_calls=15,
            tokens_used=8000,
            time_to_completion_sec=90.0,
            error_recoveries=1,
            bash_calls=3,
            bash_summarized=1,
        )
        data = original.to_dict()
        restored = TaskMetrics.from_dict(data)
        assert restored.task_id == original.task_id
        assert restored.condition == original.condition
        assert restored.success == original.success
        assert restored.iterations == original.iterations
        assert restored.bash_summarized == original.bash_summarized


class TestOmission:
    """Tests for Omission dataclass."""

    def test_creation(self) -> None:
        """Test omission creation."""
        omission = Omission(
            category=OmissionCategory.ERROR_MESSAGE,
            content="TypeError: cannot read property",
            impact=OmissionImpact.CRITICAL,
            reasoning="Error message needed for debugging",
        )
        assert omission.category == OmissionCategory.ERROR_MESSAGE
        assert "TypeError" in omission.content
        assert omission.impact == OmissionImpact.CRITICAL

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        omission = Omission(
            category=OmissionCategory.FILE_PATH,
            content="/src/main.py",
            impact=OmissionImpact.IMPORTANT,
            reasoning="File path needed for navigation",
        )
        data = omission.to_dict()
        assert data["category"] == "file_path"
        assert data["content"] == "/src/main.py"
        assert data["impact"] == "important"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "category": "line_number",
            "content": "line 42",
            "impact": "important",
            "reasoning": "Line number needed for locating issue",
        }
        omission = Omission.from_dict(data)
        assert omission.category == OmissionCategory.LINE_NUMBER
        assert omission.content == "line 42"
        assert omission.impact == OmissionImpact.IMPORTANT


class TestOmissionAnalysis:
    """Tests for OmissionAnalysis dataclass."""

    def test_creation(self) -> None:
        """Test analysis creation."""
        analysis = OmissionAnalysis(
            tool_name="bash",
            original_length=10000,
            summarized_length=4000,
            omissions=[
                Omission(
                    category=OmissionCategory.ERROR_MESSAGE,
                    content="Error: file not found",
                    impact=OmissionImpact.CRITICAL,
                    reasoning="Error message lost",
                ),
                Omission(
                    category=OmissionCategory.FILE_PATH,
                    content="/path/to/file",
                    impact=OmissionImpact.IMPORTANT,
                    reasoning="Path lost",
                ),
            ],
        )
        assert analysis.tool_name == "bash"
        assert analysis.original_length == 10000
        assert analysis.summarized_length == 4000
        assert len(analysis.omissions) == 2

    def test_critical_omissions(self) -> None:
        """Test filtering critical omissions."""
        analysis = OmissionAnalysis(
            tool_name="grep",
            original_length=5000,
            summarized_length=2000,
            omissions=[
                Omission(
                    category=OmissionCategory.ERROR_MESSAGE,
                    content="Error",
                    impact=OmissionImpact.CRITICAL,
                    reasoning="Critical",
                ),
                Omission(
                    category=OmissionCategory.FILE_PATH,
                    content="/path",
                    impact=OmissionImpact.IMPORTANT,
                    reasoning="Important",
                ),
                Omission(
                    category=OmissionCategory.OTHER,
                    content="misc",
                    impact=OmissionImpact.MINOR,
                    reasoning="Minor",
                ),
            ],
        )
        assert len(analysis.critical_omissions) == 1
        assert len(analysis.important_omissions) == 1
        assert len(analysis.minor_omissions) == 1

    def test_compression_ratio(self) -> None:
        """Test compression ratio calculation."""
        analysis = OmissionAnalysis(
            tool_name="read",
            original_length=10000,
            summarized_length=4000,
        )
        assert analysis.compression_ratio == 0.4

    def test_compression_ratio_zero_original(self) -> None:
        """Test compression ratio with zero original length."""
        analysis = OmissionAnalysis(
            tool_name="read",
            original_length=0,
            summarized_length=0,
        )
        assert analysis.compression_ratio == 1.0


class TestSummarizerConfig:
    """Tests for SummarizerConfig dataclass."""

    def test_default(self) -> None:
        """Test default configuration."""
        config = SummarizerConfig.default()
        assert config.max_file_content == 8000
        assert config.max_grep_results == 4000
        assert config.max_shell_output == 4000

    def test_no_summarization(self) -> None:
        """Test no summarization configuration."""
        config = SummarizerConfig.no_summarization()
        assert config.max_file_content is None
        assert config.max_grep_results is None
        assert config.max_shell_output is None

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        config = SummarizerConfig(12000, 6000, 6000)
        data = config.to_dict()
        assert data["max_file_content"] == 12000
        assert data["max_grep_results"] == 6000
        assert data["max_shell_output"] == 6000

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "max_file_content": 16000,
            "max_grep_results": 8000,
            "max_shell_output": 8000,
        }
        config = SummarizerConfig.from_dict(data)
        assert config.max_file_content == 16000
        assert config.max_grep_results == 8000


class TestABTestRunner:
    """Tests for ABTestRunner."""

    def test_initialization(self) -> None:
        """Test runner initialization."""
        tasks = [f"task-{i}" for i in range(10)]
        runner = ABTestRunner(tasks, control_ratio=0.5, seed=42)

        assert len(runner.control_tasks) == 5
        assert len(runner.treatment_tasks) == 5
        assert runner.control_tasks.isdisjoint(runner.treatment_tasks)

    def test_get_condition(self) -> None:
        """Test getting condition for a task."""
        tasks = ["task-1", "task-2", "task-3", "task-4"]
        runner = ABTestRunner(tasks, control_ratio=0.5, seed=42)

        # All tasks should have a condition
        for task in tasks:
            condition = runner.get_condition(task)
            assert condition in [ExperimentCondition.CONTROL, ExperimentCondition.TREATMENT]

    def test_get_config(self) -> None:
        """Test getting config for a task."""
        tasks = ["task-1", "task-2"]
        runner = ABTestRunner(tasks, control_ratio=0.5, seed=42)

        for task in tasks:
            config = runner.get_config(task)
            condition = runner.get_condition(task)

            if condition == ExperimentCondition.CONTROL:
                assert config.max_file_content is None
            else:
                assert config.max_file_content == 8000

    def test_record_result(self) -> None:
        """Test recording results."""
        tasks = ["task-1", "task-2"]
        runner = ABTestRunner(tasks, seed=42)

        metrics = TaskMetrics(
            task_id="task-1",
            condition=runner.get_condition("task-1"),
            success=True,
        )
        runner.record_result(metrics)

        assert len(runner.results) == 1
        assert runner.results[0].task_id == "task-1"

    def test_analyze_empty(self) -> None:
        """Test analysis with no results."""
        runner = ABTestRunner(["task-1"], seed=42)
        results = runner.analyze()

        assert results.control_n == 0
        assert results.treatment_n == 0
        assert "Insufficient data" in results.recommendation

    def test_analyze_with_results(self) -> None:
        """Test analysis with results."""
        tasks = [f"task-{i}" for i in range(20)]
        runner = ABTestRunner(tasks, control_ratio=0.5, seed=42)

        # Record results for all tasks
        for task in tasks:
            condition = runner.get_condition(task)
            # Control has 80% success, treatment has 70% success
            success = (
                (hash(task) % 10 < 8)
                if condition == ExperimentCondition.CONTROL
                else (hash(task) % 10 < 7)
            )
            metrics = TaskMetrics(
                task_id=task,
                condition=condition,
                success=success,
                tokens_used=5000 if condition == ExperimentCondition.CONTROL else 3000,
                iterations=10 if condition == ExperimentCondition.CONTROL else 8,
            )
            runner.record_result(metrics)

        results = runner.analyze()

        assert results.control_n == 10
        assert results.treatment_n == 10
        assert 0 <= results.control_success_rate <= 1
        assert 0 <= results.treatment_success_rate <= 1
        assert results.recommendation != ""

    def test_save_and_load_results(self) -> None:
        """Test saving and loading results."""
        tasks = ["task-1", "task-2", "task-3", "task-4"]
        runner = ABTestRunner(tasks, control_ratio=0.5, seed=42)

        # Record some results
        for task in tasks:
            metrics = TaskMetrics(
                task_id=task,
                condition=runner.get_condition(task),
                success=True,
            )
            runner.record_result(metrics)

        # Save and load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            runner.save_results(path)
            loaded = ABTestRunner.load_results(path)

            assert loaded.tasks == runner.tasks
            assert loaded.control_ratio == runner.control_ratio
            assert loaded.seed == runner.seed
            assert len(loaded.results) == len(runner.results)
        finally:
            path.unlink()


class TestOmissionAnalyzer:
    """Tests for OmissionAnalyzer."""

    def test_detect_error_omission(self) -> None:
        """Test detecting error message omission."""
        analyzer = OmissionAnalyzer()

        original = """
        Running tests...
        Error: TypeError: cannot read property 'foo' of undefined
        at line 42 in /src/main.js
        Test failed.
        """
        summarized = """
        Running tests...
        Test failed.
        """

        analysis = analyzer.analyze("bash", original, summarized)

        assert len(analysis.omissions) > 0
        # Should detect the error message
        error_omissions = [
            o for o in analysis.omissions
            if o.category == OmissionCategory.ERROR_MESSAGE
        ]
        assert len(error_omissions) > 0

    def test_detect_path_omission(self) -> None:
        """Test detecting file path omission."""
        analyzer = OmissionAnalyzer()

        original = """
        Found files:
        /src/main.py
        /src/utils.py
        /tests/test_main.py
        """
        summarized = """
        Found files:
        /src/main.py
        """

        analysis = analyzer.analyze("grep", original, summarized)

        # Should detect lost paths
        path_omissions = [
            o for o in analysis.omissions
            if o.category == OmissionCategory.FILE_PATH
        ]
        assert len(path_omissions) >= 2

    def test_detect_line_number_omission(self) -> None:
        """Test detecting line number omission."""
        analyzer = OmissionAnalyzer()

        original = """
        Error at line 42
        Warning at line 100
        Info at line 200
        """
        summarized = """
        Error at line 42
        """

        analysis = analyzer.analyze("bash", original, summarized)

        # Should detect lost line numbers
        line_omissions = [
            o for o in analysis.omissions
            if o.category == OmissionCategory.LINE_NUMBER
        ]
        assert len(line_omissions) >= 2

    def test_no_omissions(self) -> None:
        """Test when there are no omissions."""
        analyzer = OmissionAnalyzer()

        original = "Hello world"
        summarized = "Hello world"

        analysis = analyzer.analyze("bash", original, summarized)

        assert len(analysis.omissions) == 0

    def test_generate_report(self) -> None:
        """Test generating omission report."""
        analyzer = OmissionAnalyzer()

        analyses = [
            OmissionAnalysis(
                tool_name="bash",
                original_length=1000,
                summarized_length=500,
                omissions=[
                    Omission(
                        category=OmissionCategory.ERROR_MESSAGE,
                        content="Error",
                        impact=OmissionImpact.CRITICAL,
                        reasoning="Critical",
                    ),
                ],
            ),
            OmissionAnalysis(
                tool_name="grep",
                original_length=2000,
                summarized_length=1000,
                omissions=[
                    Omission(
                        category=OmissionCategory.FILE_PATH,
                        content="/path",
                        impact=OmissionImpact.IMPORTANT,
                        reasoning="Important",
                    ),
                ],
            ),
        ]

        report = analyzer.generate_report(analyses)

        assert report.total_omissions == 2
        assert report.critical_omissions == 1
        assert report.important_omissions == 1
        assert report.minor_omissions == 0
        assert len(report.recommendations) > 0


class TestThresholdTuner:
    """Tests for ThresholdTuner."""

    def test_initialization(self) -> None:
        """Test tuner initialization."""
        tuner = ThresholdTuner()
        assert len(tuner.thresholds) == 5  # Default thresholds

    def test_record_result(self) -> None:
        """Test recording results."""
        tuner = ThresholdTuner()

        config = SummarizerConfig(8000, 4000, 4000)
        tuner.record_result(
            config=config,
            success_rate=0.85,
            avg_tokens=5000,
            critical_omission_rate=0.05,
        )

        assert len(tuner.results) == 1
        assert tuner.results[0].success_rate == 0.85

    def test_find_pareto_optimal(self) -> None:
        """Test finding Pareto-optimal configurations."""
        tuner = ThresholdTuner()

        # Add results with different trade-offs
        tuner.record_result(
            config=SummarizerConfig(4000, 2000, 2000),
            success_rate=0.70,  # Low success
            avg_tokens=3000,  # Low tokens
            critical_omission_rate=0.15,  # High omissions
        )
        tuner.record_result(
            config=SummarizerConfig(8000, 4000, 4000),
            success_rate=0.85,  # Medium success
            avg_tokens=5000,  # Medium tokens
            critical_omission_rate=0.05,  # Low omissions
        )
        tuner.record_result(
            config=SummarizerConfig.no_summarization(),
            success_rate=0.90,  # High success
            avg_tokens=10000,  # High tokens
            critical_omission_rate=0.0,  # No omissions
        )

        pareto = tuner.find_pareto_optimal()

        # Should have at least one Pareto-optimal result
        assert len(pareto) >= 1

    def test_get_recommendation(self) -> None:
        """Test getting recommendation."""
        tuner = ThresholdTuner()

        tuner.record_result(
            config=SummarizerConfig(8000, 4000, 4000),
            success_rate=0.85,
            avg_tokens=5000,
            critical_omission_rate=0.05,
        )

        recommendation = tuner.get_recommendation()

        assert recommendation is not None
        assert recommendation.success_rate == 0.85

    def test_save_results(self) -> None:
        """Test saving results."""
        tuner = ThresholdTuner()

        tuner.record_result(
            config=SummarizerConfig(8000, 4000, 4000),
            success_rate=0.85,
            avg_tokens=5000,
            critical_omission_rate=0.05,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            tuner.save_results(path)

            # Verify file contents
            data = json.loads(path.read_text())
            assert "thresholds_tested" in data
            assert "results" in data
            assert "pareto_optimal" in data
        finally:
            path.unlink()


class TestABResults:
    """Tests for ABResults dataclass."""

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        results = ABResults(
            control_success_rate=0.80,
            treatment_success_rate=0.75,
            effect_size=-0.05,
            p_value=0.15,
            significant=False,
            control_avg_tokens=10000,
            treatment_avg_tokens=6000,
            token_savings_pct=40.0,
            control_avg_iterations=12,
            treatment_avg_iterations=10,
            control_n=50,
            treatment_n=50,
            recommendation="No significant difference.",
        )

        data = results.to_dict()

        assert data["control_success_rate"] == 0.80
        assert data["treatment_success_rate"] == 0.75
        assert data["effect_size"] == -0.05
        assert data["significant"] is False
        assert data["token_savings_pct"] == 40.0


class TestOmissionReport:
    """Tests for OmissionReport dataclass."""

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        report = OmissionReport(
            total_omissions=10,
            critical_omissions=2,
            important_omissions=5,
            minor_omissions=3,
            critical_omission_rate=0.2,
            omission_examples=[
                Omission(
                    category=OmissionCategory.ERROR_MESSAGE,
                    content="Error",
                    impact=OmissionImpact.CRITICAL,
                    reasoning="Critical error lost",
                ),
            ],
            recommendations=["Increase thresholds"],
        )

        data = report.to_dict()

        assert data["total_omissions"] == 10
        assert data["critical_omissions"] == 2
        assert data["critical_omission_rate"] == 0.2
        assert len(data["omission_examples"]) == 1
        assert len(data["recommendations"]) == 1
