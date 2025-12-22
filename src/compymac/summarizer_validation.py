"""
ToolOutputSummarizer Validation - A/B Testing Framework

This module provides tools for validating whether tool output summarization
loses critical information that causes agent failures.

Gap 2 from docs/real-gaps-implementation-plans.md

Hypotheses:
- H0: Summarization has no significant impact on task success rate
- H1: Summarization reduces success rate by >10%
- H2: Summarization improves token efficiency
- H3: Summarization increases error recovery time
- H4: Certain tool types are more sensitive to summarization
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExperimentCondition(Enum):
    """Experiment condition for A/B testing."""

    CONTROL = "control"  # Full tool outputs (no summarization)
    TREATMENT = "treatment"  # ToolOutputSummarizer enabled


class OmissionImpact(Enum):
    """Impact level of an omission."""

    CRITICAL = "critical"  # Would cause agent to fail task
    IMPORTANT = "important"  # Would slow down agent
    MINOR = "minor"  # Unlikely to affect agent behavior


class OmissionCategory(Enum):
    """Category of omitted information."""

    ERROR_MESSAGE = "error_message"
    FILE_PATH = "file_path"
    LINE_NUMBER = "line_number"
    CODE_SNIPPET = "code_snippet"
    STACK_TRACE = "stack_trace"
    VARIABLE_VALUE = "variable_value"
    OTHER = "other"


@dataclass
class TaskMetrics:
    """Metrics for a single task execution."""

    task_id: str
    condition: ExperimentCondition

    # Primary outcome
    success: bool  # Did task complete correctly?

    # Secondary outcomes
    iterations: int = 0  # How many agent turns?
    tool_calls: int = 0  # Total tool calls
    tokens_used: int = 0  # Total token consumption
    time_to_completion_sec: float = 0.0

    # Diagnostic metrics
    error_recoveries: int = 0  # How many times agent corrected errors
    false_starts: int = 0  # How many times agent went down wrong path
    critical_info_missed: bool = False  # Manual review flag

    # Per-tool breakdowns
    bash_calls: int = 0
    bash_summarized: int = 0
    file_reads: int = 0
    file_reads_summarized: int = 0
    grep_calls: int = 0
    grep_summarized: int = 0

    # Timestamps
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "condition": self.condition.value,
            "success": self.success,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
            "time_to_completion_sec": self.time_to_completion_sec,
            "error_recoveries": self.error_recoveries,
            "false_starts": self.false_starts,
            "critical_info_missed": self.critical_info_missed,
            "bash_calls": self.bash_calls,
            "bash_summarized": self.bash_summarized,
            "file_reads": self.file_reads,
            "file_reads_summarized": self.file_reads_summarized,
            "grep_calls": self.grep_calls,
            "grep_summarized": self.grep_summarized,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskMetrics:
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            condition=ExperimentCondition(data["condition"]),
            success=data["success"],
            iterations=data.get("iterations", 0),
            tool_calls=data.get("tool_calls", 0),
            tokens_used=data.get("tokens_used", 0),
            time_to_completion_sec=data.get("time_to_completion_sec", 0.0),
            error_recoveries=data.get("error_recoveries", 0),
            false_starts=data.get("false_starts", 0),
            critical_info_missed=data.get("critical_info_missed", False),
            bash_calls=data.get("bash_calls", 0),
            bash_summarized=data.get("bash_summarized", 0),
            file_reads=data.get("file_reads", 0),
            file_reads_summarized=data.get("file_reads_summarized", 0),
            grep_calls=data.get("grep_calls", 0),
            grep_summarized=data.get("grep_summarized", 0),
            started_at=data.get("started_at", 0.0),
            completed_at=data.get("completed_at"),
        )


@dataclass
class Omission:
    """A piece of information that was lost to summarization."""

    category: OmissionCategory
    content: str
    impact: OmissionImpact
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "content": self.content,
            "impact": self.impact.value,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Omission:
        """Create from dictionary."""
        return cls(
            category=OmissionCategory(data["category"]),
            content=data["content"],
            impact=OmissionImpact(data["impact"]),
            reasoning=data["reasoning"],
        )


@dataclass
class OmissionAnalysis:
    """Analysis of what information was lost in a single tool call."""

    tool_name: str
    original_length: int
    summarized_length: int
    omissions: list[Omission] = field(default_factory=list)

    @property
    def critical_omissions(self) -> list[Omission]:
        """Get critical omissions."""
        return [o for o in self.omissions if o.impact == OmissionImpact.CRITICAL]

    @property
    def important_omissions(self) -> list[Omission]:
        """Get important omissions."""
        return [o for o in self.omissions if o.impact == OmissionImpact.IMPORTANT]

    @property
    def minor_omissions(self) -> list[Omission]:
        """Get minor omissions."""
        return [o for o in self.omissions if o.impact == OmissionImpact.MINOR]

    @property
    def compression_ratio(self) -> float:
        """Get compression ratio (0-1, lower = more compression)."""
        if self.original_length == 0:
            return 1.0
        return self.summarized_length / self.original_length

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "original_length": self.original_length,
            "summarized_length": self.summarized_length,
            "omissions": [o.to_dict() for o in self.omissions],
            "compression_ratio": self.compression_ratio,
        }


@dataclass
class ABResults:
    """Results of A/B test analysis."""

    control_success_rate: float
    treatment_success_rate: float
    effect_size: float  # treatment - control
    p_value: float
    significant: bool  # p_value < 0.05

    # Secondary metrics
    control_avg_tokens: float
    treatment_avg_tokens: float
    token_savings_pct: float

    control_avg_iterations: float
    treatment_avg_iterations: float

    # Sample sizes
    control_n: int
    treatment_n: int

    # Recommendation
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "control_success_rate": self.control_success_rate,
            "treatment_success_rate": self.treatment_success_rate,
            "effect_size": self.effect_size,
            "p_value": self.p_value,
            "significant": self.significant,
            "control_avg_tokens": self.control_avg_tokens,
            "treatment_avg_tokens": self.treatment_avg_tokens,
            "token_savings_pct": self.token_savings_pct,
            "control_avg_iterations": self.control_avg_iterations,
            "treatment_avg_iterations": self.treatment_avg_iterations,
            "control_n": self.control_n,
            "treatment_n": self.treatment_n,
            "recommendation": self.recommendation,
        }


@dataclass
class OmissionReport:
    """Report on omission analysis across multiple tasks."""

    total_omissions: int
    critical_omissions: int
    important_omissions: int
    minor_omissions: int
    critical_omission_rate: float
    omission_examples: list[Omission]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_omissions": self.total_omissions,
            "critical_omissions": self.critical_omissions,
            "important_omissions": self.important_omissions,
            "minor_omissions": self.minor_omissions,
            "critical_omission_rate": self.critical_omission_rate,
            "omission_examples": [o.to_dict() for o in self.omission_examples],
            "recommendations": self.recommendations,
        }


@dataclass
class SummarizerConfig:
    """Configuration for ToolOutputSummarizer thresholds."""

    max_file_content: int | None = 8000  # ~2000 tokens
    max_grep_results: int | None = 4000  # ~1000 tokens
    max_shell_output: int | None = 4000  # ~1000 tokens

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_file_content": self.max_file_content,
            "max_grep_results": self.max_grep_results,
            "max_shell_output": self.max_shell_output,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SummarizerConfig:
        """Create from dictionary."""
        return cls(
            max_file_content=data.get("max_file_content"),
            max_grep_results=data.get("max_grep_results"),
            max_shell_output=data.get("max_shell_output"),
        )

    @classmethod
    def no_summarization(cls) -> SummarizerConfig:
        """Create config with no summarization (control condition)."""
        return cls(
            max_file_content=None,
            max_grep_results=None,
            max_shell_output=None,
        )

    @classmethod
    def default(cls) -> SummarizerConfig:
        """Create config with default thresholds (treatment condition)."""
        return cls()


class ABTestRunner:
    """
    Runner for A/B testing of ToolOutputSummarizer.

    Manages task assignment to conditions and metrics collection.
    """

    def __init__(
        self,
        tasks: list[str],
        control_ratio: float = 0.5,
        seed: int | None = None,
    ):
        """
        Initialize A/B test runner.

        Args:
            tasks: List of task IDs to run.
            control_ratio: Ratio of tasks to assign to control (default 0.5).
            seed: Random seed for reproducibility.
        """
        self.tasks = tasks
        self.control_ratio = control_ratio
        self.seed = seed

        # Random assignment
        if seed is not None:
            random.seed(seed)

        shuffled = list(tasks)
        random.shuffle(shuffled)

        split_idx = int(len(shuffled) * control_ratio)
        self.control_tasks = set(shuffled[:split_idx])
        self.treatment_tasks = set(shuffled[split_idx:])

        # Results storage
        self.results: list[TaskMetrics] = []

    def get_condition(self, task_id: str) -> ExperimentCondition:
        """Get the condition for a task."""
        if task_id in self.control_tasks:
            return ExperimentCondition.CONTROL
        return ExperimentCondition.TREATMENT

    def get_config(self, task_id: str) -> SummarizerConfig:
        """Get summarizer config for a task based on its condition."""
        condition = self.get_condition(task_id)
        if condition == ExperimentCondition.CONTROL:
            return SummarizerConfig.no_summarization()
        return SummarizerConfig.default()

    def record_result(self, metrics: TaskMetrics) -> None:
        """Record task result."""
        self.results.append(metrics)

    def get_control_results(self) -> list[TaskMetrics]:
        """Get results for control condition."""
        return [r for r in self.results if r.condition == ExperimentCondition.CONTROL]

    def get_treatment_results(self) -> list[TaskMetrics]:
        """Get results for treatment condition."""
        return [r for r in self.results if r.condition == ExperimentCondition.TREATMENT]

    def analyze(self) -> ABResults:
        """Analyze A/B test results."""
        control = self.get_control_results()
        treatment = self.get_treatment_results()

        if not control or not treatment:
            return ABResults(
                control_success_rate=0.0,
                treatment_success_rate=0.0,
                effect_size=0.0,
                p_value=1.0,
                significant=False,
                control_avg_tokens=0.0,
                treatment_avg_tokens=0.0,
                token_savings_pct=0.0,
                control_avg_iterations=0.0,
                treatment_avg_iterations=0.0,
                control_n=len(control),
                treatment_n=len(treatment),
                recommendation="Insufficient data for analysis.",
            )

        # Primary metric: Success rate
        control_success = sum(t.success for t in control) / len(control)
        treatment_success = sum(t.success for t in treatment) / len(treatment)
        effect_size = treatment_success - control_success

        # Statistical test (chi-square for binary outcome)
        p_value = self._chi_square_test(control, treatment)

        # Secondary metrics
        control_tokens = sum(t.tokens_used for t in control) / len(control)
        treatment_tokens = sum(t.tokens_used for t in treatment) / len(treatment)
        token_savings = (
            (control_tokens - treatment_tokens) / control_tokens
            if control_tokens > 0
            else 0.0
        )

        control_iterations = sum(t.iterations for t in control) / len(control)
        treatment_iterations = sum(t.iterations for t in treatment) / len(treatment)

        # Generate recommendation
        recommendation = self._make_recommendation(
            effect_size, token_savings, p_value
        )

        return ABResults(
            control_success_rate=control_success,
            treatment_success_rate=treatment_success,
            effect_size=effect_size,
            p_value=p_value,
            significant=p_value < 0.05,
            control_avg_tokens=control_tokens,
            treatment_avg_tokens=treatment_tokens,
            token_savings_pct=token_savings * 100,
            control_avg_iterations=control_iterations,
            treatment_avg_iterations=treatment_iterations,
            control_n=len(control),
            treatment_n=len(treatment),
            recommendation=recommendation,
        )

    def _chi_square_test(
        self, control: list[TaskMetrics], treatment: list[TaskMetrics]
    ) -> float:
        """Perform chi-square test on success rates."""
        # Build contingency table
        control_success = sum(t.success for t in control)
        control_fail = len(control) - control_success
        treatment_success = sum(t.success for t in treatment)
        treatment_fail = len(treatment) - treatment_success

        # Simple chi-square calculation (without scipy dependency)
        # Using Yates' correction for small samples
        n = len(control) + len(treatment)
        if n == 0:
            return 1.0

        # Expected values
        total_success = control_success + treatment_success
        total_fail = control_fail + treatment_fail

        if total_success == 0 or total_fail == 0:
            return 1.0  # No variation

        expected_control_success = len(control) * total_success / n
        expected_control_fail = len(control) * total_fail / n
        expected_treatment_success = len(treatment) * total_success / n
        expected_treatment_fail = len(treatment) * total_fail / n

        # Chi-square statistic
        chi2 = 0.0
        for observed, expected in [
            (control_success, expected_control_success),
            (control_fail, expected_control_fail),
            (treatment_success, expected_treatment_success),
            (treatment_fail, expected_treatment_fail),
        ]:
            if expected > 0:
                chi2 += (abs(observed - expected) - 0.5) ** 2 / expected

        # Approximate p-value (1 degree of freedom)
        # Using simple approximation for chi-square distribution
        import math

        if chi2 <= 0:
            return 1.0
        if chi2 > 10:
            return 0.001  # Very significant

        # Approximation using normal distribution
        z = math.sqrt(chi2)
        p_value = 2 * (1 - self._normal_cdf(z))
        return max(0.0, min(1.0, p_value))

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF."""
        import math

        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _make_recommendation(
        self, effect_size: float, token_savings: float, p_value: float
    ) -> str:
        """Make recommendation based on results."""
        if p_value >= 0.05:
            return (
                "No significant difference. "
                "Recommend enabling summarization for token savings."
            )

        if effect_size < -0.10:  # >10% drop in success rate
            return (
                "CRITICAL: Summarization significantly hurts success rate. "
                "Disable immediately."
            )

        if effect_size < -0.05:  # 5-10% drop
            return (
                "WARNING: Summarization reduces success rate. "
                "Investigate and tune thresholds."
            )

        if effect_size < 0.05:  # <5% drop
            if token_savings > 0.20:  # >20% token savings
                return "Acceptable trade-off. Enable summarization with monitoring."
            return "Marginal benefit. Consider disabling."

        # effect_size >= 0.05 (summarization improves success!)
        return "Surprising: Summarization improves success. Enable and investigate why."

    def save_results(self, path: str | Path) -> None:
        """Save results to JSON file."""
        path = Path(path)
        data = {
            "tasks": self.tasks,
            "control_ratio": self.control_ratio,
            "seed": self.seed,
            "control_tasks": list(self.control_tasks),
            "treatment_tasks": list(self.treatment_tasks),
            "results": [r.to_dict() for r in self.results],
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_results(cls, path: str | Path) -> ABTestRunner:
        """Load results from JSON file."""
        path = Path(path)
        data = json.loads(path.read_text())

        runner = cls(
            tasks=data["tasks"],
            control_ratio=data["control_ratio"],
            seed=data["seed"],
        )
        runner.control_tasks = set(data["control_tasks"])
        runner.treatment_tasks = set(data["treatment_tasks"])
        runner.results = [TaskMetrics.from_dict(r) for r in data["results"]]

        return runner


class OmissionAnalyzer:
    """
    Analyzer for detecting information lost to summarization.

    Uses heuristics and optionally LLM to identify critical omissions.
    """

    # Patterns that indicate critical information
    CRITICAL_PATTERNS = [
        r"error:",
        r"Error:",
        r"ERROR:",
        r"exception:",
        r"Exception:",
        r"EXCEPTION:",
        r"failed:",
        r"Failed:",
        r"FAILED:",
        r"traceback",
        r"Traceback",
        r"line \d+",
        r"Line \d+",
        r"at line",
        r"syntax error",
        r"SyntaxError",
        r"TypeError",
        r"ValueError",
        r"KeyError",
        r"AttributeError",
        r"ImportError",
        r"ModuleNotFoundError",
        r"FileNotFoundError",
        r"PermissionError",
        r"AssertionError",
    ]

    # Patterns that indicate file paths
    PATH_PATTERNS = [
        r"/[a-zA-Z0-9_\-./]+\.[a-zA-Z]+",  # Unix paths
        r"[a-zA-Z]:\\[a-zA-Z0-9_\-\\]+\.[a-zA-Z]+",  # Windows paths
    ]

    def __init__(self):
        """Initialize omission analyzer."""
        import re

        self.critical_re = [re.compile(p) for p in self.CRITICAL_PATTERNS]
        self.path_re = [re.compile(p) for p in self.PATH_PATTERNS]

    def analyze(
        self,
        tool_name: str,
        original: str,
        summarized: str,
    ) -> OmissionAnalysis:
        """
        Analyze what information was lost in summarization.

        Args:
            tool_name: Name of the tool.
            original: Original tool output.
            summarized: Summarized tool output.

        Returns:
            OmissionAnalysis with detected omissions.
        """
        omissions: list[Omission] = []

        # Find critical patterns in original but not in summarized
        for pattern in self.critical_re:
            original_matches = set(pattern.findall(original))
            summarized_matches = set(pattern.findall(summarized))
            lost_matches = original_matches - summarized_matches

            for match in lost_matches:
                omissions.append(
                    Omission(
                        category=self._categorize_match(match),
                        content=match,
                        impact=OmissionImpact.CRITICAL,
                        reasoning=f"Error/exception pattern '{match}' was lost",
                    )
                )

        # Find file paths in original but not in summarized
        for pattern in self.path_re:
            original_paths = set(pattern.findall(original))
            summarized_paths = set(pattern.findall(summarized))
            lost_paths = original_paths - summarized_paths

            for path in lost_paths:
                omissions.append(
                    Omission(
                        category=OmissionCategory.FILE_PATH,
                        content=path,
                        impact=OmissionImpact.IMPORTANT,
                        reasoning=f"File path '{path}' was lost",
                    )
                )

        # Check for line numbers
        import re

        line_pattern = re.compile(r"line (\d+)", re.IGNORECASE)
        original_lines = set(line_pattern.findall(original))
        summarized_lines = set(line_pattern.findall(summarized))
        lost_lines = original_lines - summarized_lines

        for line in lost_lines:
            omissions.append(
                Omission(
                    category=OmissionCategory.LINE_NUMBER,
                    content=f"line {line}",
                    impact=OmissionImpact.IMPORTANT,
                    reasoning=f"Line number {line} was lost",
                )
            )

        return OmissionAnalysis(
            tool_name=tool_name,
            original_length=len(original),
            summarized_length=len(summarized),
            omissions=omissions,
        )

    def _categorize_match(self, match: str) -> OmissionCategory:
        """Categorize a matched pattern."""
        match_lower = match.lower()
        if "error" in match_lower or "exception" in match_lower:
            return OmissionCategory.ERROR_MESSAGE
        if "traceback" in match_lower:
            return OmissionCategory.STACK_TRACE
        if "line" in match_lower:
            return OmissionCategory.LINE_NUMBER
        return OmissionCategory.OTHER

    def generate_report(
        self, analyses: list[OmissionAnalysis]
    ) -> OmissionReport:
        """Generate report from multiple analyses."""
        all_omissions: list[Omission] = []
        for analysis in analyses:
            all_omissions.extend(analysis.omissions)

        critical = [o for o in all_omissions if o.impact == OmissionImpact.CRITICAL]
        important = [o for o in all_omissions if o.impact == OmissionImpact.IMPORTANT]
        minor = [o for o in all_omissions if o.impact == OmissionImpact.MINOR]

        critical_rate = len(critical) / len(all_omissions) if all_omissions else 0.0

        recommendations = self._generate_recommendations(
            critical, important, len(analyses)
        )

        return OmissionReport(
            total_omissions=len(all_omissions),
            critical_omissions=len(critical),
            important_omissions=len(important),
            minor_omissions=len(minor),
            critical_omission_rate=critical_rate,
            omission_examples=critical[:10],  # Show worst cases
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        critical: list[Omission],
        important: list[Omission],
        total_analyses: int,
    ) -> list[str]:
        """Generate recommendations based on omission analysis."""
        recommendations = []

        if not critical and not important:
            recommendations.append(
                "No significant omissions detected. Current thresholds appear safe."
            )
            return recommendations

        critical_rate = len(critical) / total_analyses if total_analyses > 0 else 0

        if critical_rate > 0.1:  # >10% of analyses have critical omissions
            recommendations.append(
                "CRITICAL: High rate of critical omissions. "
                "Increase summarization thresholds or disable summarization."
            )

        # Check for specific patterns
        error_omissions = [
            o for o in critical if o.category == OmissionCategory.ERROR_MESSAGE
        ]
        if error_omissions:
            recommendations.append(
                f"Error messages are being lost ({len(error_omissions)} instances). "
                "Consider preserving error patterns in summarization."
            )

        path_omissions = [
            o for o in important if o.category == OmissionCategory.FILE_PATH
        ]
        if path_omissions:
            recommendations.append(
                f"File paths are being lost ({len(path_omissions)} instances). "
                "Consider preserving path references in summarization."
            )

        line_omissions = [
            o for o in important if o.category == OmissionCategory.LINE_NUMBER
        ]
        if line_omissions:
            recommendations.append(
                f"Line numbers are being lost ({len(line_omissions)} instances). "
                "Consider preserving line number references in summarization."
            )

        return recommendations


@dataclass
class ThresholdTuningResult:
    """Result of threshold tuning."""

    thresholds: SummarizerConfig
    success_rate: float
    avg_tokens: float
    critical_omission_rate: float
    is_pareto_optimal: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "thresholds": self.thresholds.to_dict(),
            "success_rate": self.success_rate,
            "avg_tokens": self.avg_tokens,
            "critical_omission_rate": self.critical_omission_rate,
            "is_pareto_optimal": self.is_pareto_optimal,
        }


class ThresholdTuner:
    """
    Tuner for finding optimal summarization thresholds.

    Uses grid search to find Pareto-optimal thresholds that balance
    success rate and token efficiency.
    """

    # Default thresholds to test
    DEFAULT_THRESHOLDS = [
        SummarizerConfig(4000, 2000, 2000),  # Aggressive
        SummarizerConfig(8000, 4000, 4000),  # Current default
        SummarizerConfig(12000, 6000, 6000),  # Conservative
        SummarizerConfig(16000, 8000, 8000),  # Minimal
        SummarizerConfig.no_summarization(),  # Control
    ]

    def __init__(
        self,
        thresholds: list[SummarizerConfig] | None = None,
    ):
        """
        Initialize threshold tuner.

        Args:
            thresholds: List of threshold configs to test.
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.results: list[ThresholdTuningResult] = []

    def record_result(
        self,
        config: SummarizerConfig,
        success_rate: float,
        avg_tokens: float,
        critical_omission_rate: float,
    ) -> None:
        """Record result for a threshold configuration."""
        self.results.append(
            ThresholdTuningResult(
                thresholds=config,
                success_rate=success_rate,
                avg_tokens=avg_tokens,
                critical_omission_rate=critical_omission_rate,
                is_pareto_optimal=False,  # Will be computed later
            )
        )

    def find_pareto_optimal(self) -> list[ThresholdTuningResult]:
        """Find Pareto-optimal threshold configurations."""
        if not self.results:
            return []

        # A result is Pareto-optimal if no other result dominates it
        # (better in all objectives: higher success, lower tokens, lower omissions)
        pareto_optimal = []

        for result in self.results:
            is_dominated = False
            for other in self.results:
                if other is result:
                    continue

                # Check if other dominates result
                if (
                    other.success_rate >= result.success_rate
                    and other.avg_tokens <= result.avg_tokens
                    and other.critical_omission_rate <= result.critical_omission_rate
                    and (
                        other.success_rate > result.success_rate
                        or other.avg_tokens < result.avg_tokens
                        or other.critical_omission_rate < result.critical_omission_rate
                    )
                ):
                    is_dominated = True
                    break

            if not is_dominated:
                result.is_pareto_optimal = True
                pareto_optimal.append(result)

        return pareto_optimal

    def get_recommendation(self) -> ThresholdTuningResult | None:
        """Get recommended threshold configuration."""
        pareto = self.find_pareto_optimal()
        if not pareto:
            return None

        # Prefer configuration with highest success rate among Pareto-optimal
        return max(pareto, key=lambda r: r.success_rate)

    def save_results(self, path: str | Path) -> None:
        """Save results to JSON file."""
        path = Path(path)
        data = {
            "thresholds_tested": [t.to_dict() for t in self.thresholds],
            "results": [r.to_dict() for r in self.results],
            "pareto_optimal": [
                r.to_dict() for r in self.find_pareto_optimal()
            ],
        }
        path.write_text(json.dumps(data, indent=2))
