"""Tests for Gap 6 Phase 3: Dynamic Orchestration Heuristics."""

import tempfile
from pathlib import Path

from compymac.workflows.dynamic_orchestration import (
    AgentCapability,
    AgentCapabilityProfile,
    AgentRole,
    CapabilityRouter,
    DynamicOrchestrator,
    HeuristicRouter,
    RoutingDecision,
    RoutingFeedbackStore,
    RoutingHeuristic,
    RoutingOutcome,
    TaskAnalysis,
    TaskAnalyzer,
    TaskComplexity,
    TaskType,
)


class TestAgentCapability:
    """Tests for AgentCapability enum."""

    def test_all_capabilities_exist(self):
        assert AgentCapability.PLANNING.value == "planning"
        assert AgentCapability.CODING.value == "coding"
        assert AgentCapability.TESTING.value == "testing"
        assert AgentCapability.DEBUGGING.value == "debugging"
        assert AgentCapability.REVIEWING.value == "reviewing"
        assert AgentCapability.REFACTORING.value == "refactoring"
        assert AgentCapability.DOCUMENTATION.value == "documentation"


class TestTaskType:
    """Tests for TaskType enum."""

    def test_all_types_exist(self):
        assert TaskType.BUG_FIX.value == "bug_fix"
        assert TaskType.FEATURE.value == "feature"
        assert TaskType.REFACTOR.value == "refactor"
        assert TaskType.TEST.value == "test"
        assert TaskType.DOCUMENTATION.value == "documentation"
        assert TaskType.DEBUGGING.value == "debugging"
        assert TaskType.UNKNOWN.value == "unknown"


class TestTaskComplexity:
    """Tests for TaskComplexity enum."""

    def test_all_complexities_exist(self):
        assert TaskComplexity.TRIVIAL.value == "trivial"
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MODERATE.value == "moderate"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.VERY_COMPLEX.value == "very_complex"


class TestAgentCapabilityProfile:
    """Tests for AgentCapabilityProfile dataclass."""

    def test_get_proficiency(self):
        profile = AgentCapabilityProfile(
            agent_role=AgentRole.EXECUTOR,
            capabilities={
                AgentCapability.CODING: 0.9,
                AgentCapability.TESTING: 0.7,
            },
        )
        assert profile.get_proficiency(AgentCapability.CODING) == 0.9
        assert profile.get_proficiency(AgentCapability.TESTING) == 0.7
        assert profile.get_proficiency(AgentCapability.PLANNING) == 0.0

    def test_can_handle_complexity(self):
        profile = AgentCapabilityProfile(
            agent_role=AgentRole.EXECUTOR,
            max_complexity=TaskComplexity.COMPLEX,
        )
        assert profile.can_handle_complexity(TaskComplexity.TRIVIAL) is True
        assert profile.can_handle_complexity(TaskComplexity.SIMPLE) is True
        assert profile.can_handle_complexity(TaskComplexity.MODERATE) is True
        assert profile.can_handle_complexity(TaskComplexity.COMPLEX) is True
        assert profile.can_handle_complexity(TaskComplexity.VERY_COMPLEX) is False

    def test_to_dict(self):
        profile = AgentCapabilityProfile(
            agent_role=AgentRole.PLANNER,
            capabilities={AgentCapability.PLANNING: 1.0},
            preferred_task_types=[TaskType.FEATURE],
            max_complexity=TaskComplexity.VERY_COMPLEX,
        )
        result = profile.to_dict()
        assert result["agent_role"] == "planner"
        assert result["capabilities"]["planning"] == 1.0
        assert "feature" in result["preferred_task_types"]


class TestTaskAnalysis:
    """Tests for TaskAnalysis dataclass."""

    def test_to_dict(self):
        analysis = TaskAnalysis(
            task_description="Fix the bug in login",
            detected_type=TaskType.BUG_FIX,
            estimated_complexity=TaskComplexity.SIMPLE,
            required_capabilities=[AgentCapability.DEBUGGING, AgentCapability.CODING],
            file_count_estimate=2,
            keywords=["fix", "bug"],
            confidence=0.8,
        )
        result = analysis.to_dict()
        assert result["detected_type"] == "bug_fix"
        assert result["estimated_complexity"] == "simple"
        assert "debugging" in result["required_capabilities"]
        assert result["confidence"] == 0.8


class TestTaskAnalyzer:
    """Tests for TaskAnalyzer."""

    def test_detect_bug_fix(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Fix the bug in the login page")
        assert analysis.detected_type == TaskType.BUG_FIX

    def test_detect_feature(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Add a new feature for user profiles")
        assert analysis.detected_type == TaskType.FEATURE

    def test_detect_refactor(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Refactor the authentication module")
        assert analysis.detected_type == TaskType.REFACTOR

    def test_detect_test(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Run the pytest tests and check coverage")
        assert analysis.detected_type == TaskType.TEST

    def test_detect_documentation(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Update the README documentation")
        assert analysis.detected_type == TaskType.DOCUMENTATION

    def test_detect_unknown(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("xyz abc 123")
        assert analysis.detected_type == TaskType.UNKNOWN

    def test_complexity_trivial(self):
        analyzer = TaskAnalyzer()
        analysis = analyzer.analyze("Fix a simple typo in the config")
        assert analysis.estimated_complexity == TaskComplexity.TRIVIAL

    def test_complexity_with_context(self):
        analyzer = TaskAnalyzer()
        context = {"files": ["a.py", "b.py", "c.py"]}
        analysis = analyzer.analyze("Update these files", context)
        assert analysis.file_count_estimate == 3


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_to_dict(self):
        analysis = TaskAnalysis(
            task_description="Test task",
            detected_type=TaskType.BUG_FIX,
            estimated_complexity=TaskComplexity.SIMPLE,
            required_capabilities=[],
            confidence=0.8,
        )
        decision = RoutingDecision(
            task_analysis=analysis,
            selected_agent=AgentRole.EXECUTOR,
            alternative_agents=[AgentRole.REFLECTOR],
            reasoning="Best match for bug fix",
            confidence=0.9,
        )
        result = decision.to_dict()
        assert result["selected_agent"] == "executor"
        assert "reflector" in result["alternative_agents"]
        assert result["confidence"] == 0.9


class TestCapabilityRouter:
    """Tests for CapabilityRouter."""

    def test_route_bug_fix(self):
        router = CapabilityRouter()
        analysis = TaskAnalysis(
            task_description="Fix the bug",
            detected_type=TaskType.BUG_FIX,
            estimated_complexity=TaskComplexity.SIMPLE,
            required_capabilities=[AgentCapability.DEBUGGING, AgentCapability.CODING],
            confidence=0.8,
        )
        decision = router.route(analysis)
        assert decision.selected_agent in [AgentRole.EXECUTOR, AgentRole.REFLECTOR]
        assert decision.confidence > 0

    def test_route_planning(self):
        router = CapabilityRouter()
        analysis = TaskAnalysis(
            task_description="Plan the feature",
            detected_type=TaskType.FEATURE,
            estimated_complexity=TaskComplexity.COMPLEX,
            required_capabilities=[AgentCapability.PLANNING],
            confidence=0.8,
        )
        decision = router.route(analysis)
        assert decision.selected_agent == AgentRole.PLANNER

    def test_route_code_review(self):
        router = CapabilityRouter()
        analysis = TaskAnalysis(
            task_description="Review the code",
            detected_type=TaskType.CODE_REVIEW,
            estimated_complexity=TaskComplexity.MODERATE,
            required_capabilities=[AgentCapability.REVIEWING],
            confidence=0.8,
        )
        decision = router.route(analysis)
        assert decision.selected_agent in [AgentRole.REFLECTOR, AgentRole.REVIEWER]


class TestRoutingHeuristic:
    """Tests for RoutingHeuristic."""

    def test_matches(self):
        heuristic = RoutingHeuristic(
            name="test_failures",
            condition=r"test.*fail",
            preferred_agent=AgentRole.EXECUTOR,
        )
        assert heuristic.matches("The test is failing") is True
        assert heuristic.matches("Add a new feature") is False

    def test_to_dict(self):
        heuristic = RoutingHeuristic(
            name="lint_errors",
            condition=r"lint|ruff",
            preferred_agent=AgentRole.EXECUTOR,
            priority=10,
        )
        result = heuristic.to_dict()
        assert result["name"] == "lint_errors"
        assert result["preferred_agent"] == "executor"
        assert result["priority"] == 10


class TestHeuristicRouter:
    """Tests for HeuristicRouter."""

    def test_route_test_failure(self):
        router = HeuristicRouter()
        agent, name = router.route("The pytest test is failing")
        assert agent == AgentRole.EXECUTOR
        assert name == "test_failures"

    def test_route_lint_error(self):
        router = HeuristicRouter()
        agent, name = router.route("Fix the ruff lint errors")
        assert agent == AgentRole.EXECUTOR
        assert name == "lint_errors"

    def test_route_code_review(self):
        router = HeuristicRouter()
        agent, name = router.route("Review the pull request")
        assert agent == AgentRole.REVIEWER
        assert name == "code_review"

    def test_route_no_match(self):
        router = HeuristicRouter()
        agent, name = router.route("xyz abc 123")
        assert agent is None
        assert name is None

    def test_add_heuristic(self):
        router = HeuristicRouter()
        initial_count = len(router.heuristics)
        router.add_heuristic(
            RoutingHeuristic(
                name="custom",
                condition=r"custom.*pattern",
                preferred_agent=AgentRole.PLANNER,
                priority=100,
            )
        )
        assert len(router.heuristics) == initial_count + 1
        # Should be first due to high priority
        assert router.heuristics[0].name == "custom"


class TestRoutingFeedbackStore:
    """Tests for RoutingFeedbackStore."""

    def test_init_with_temp_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            store = RoutingFeedbackStore(storage_path=path)
            assert store.storage_path == path

    def test_record_outcome(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            store = RoutingFeedbackStore(storage_path=path)

            analysis = TaskAnalysis(
                task_description="Test",
                detected_type=TaskType.BUG_FIX,
                estimated_complexity=TaskComplexity.SIMPLE,
                required_capabilities=[],
                confidence=0.8,
            )
            decision = RoutingDecision(
                task_analysis=analysis,
                selected_agent=AgentRole.EXECUTOR,
                alternative_agents=[],
                reasoning="Test",
                confidence=0.9,
            )
            outcome = RoutingOutcome(
                decision=decision,
                success=True,
                execution_time_ms=1000,
                iterations_used=3,
            )

            store.record_outcome(outcome)
            assert len(store.outcomes) == 1

    def test_get_success_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            store = RoutingFeedbackStore(storage_path=path)

            # No data - should return 0.5
            rate = store.get_success_rate(AgentRole.EXECUTOR)
            assert rate == 0.5

    def test_get_statistics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            store = RoutingFeedbackStore(storage_path=path)
            stats = store.get_statistics()
            assert "total_outcomes" in stats
            assert "session_success_rate" in stats


class TestDynamicOrchestrator:
    """Tests for DynamicOrchestrator."""

    def test_init(self):
        orchestrator = DynamicOrchestrator()
        assert orchestrator.task_analyzer is not None
        assert orchestrator.capability_router is not None
        assert orchestrator.heuristic_router is not None

    def test_route_task_with_heuristic(self):
        orchestrator = DynamicOrchestrator()
        decision = orchestrator.route_task("Fix the failing pytest test")
        assert decision.selected_agent == AgentRole.EXECUTOR
        assert "heuristic" in decision.reasoning.lower()

    def test_route_task_without_heuristic(self):
        orchestrator = DynamicOrchestrator()
        decision = orchestrator.route_task(
            "Implement a new authentication system",
            use_heuristics=False,
        )
        assert decision.selected_agent is not None
        assert decision.confidence > 0

    def test_route_task_with_context(self):
        orchestrator = DynamicOrchestrator()
        context = {"files": ["auth.py", "login.py"]}
        decision = orchestrator.route_task(
            "Update the authentication",
            context=context,
            use_heuristics=False,
        )
        assert decision.task_analysis.file_count_estimate == 2

    def test_get_orchestration_stats(self):
        orchestrator = DynamicOrchestrator()
        stats = orchestrator.get_orchestration_stats()
        assert "feedback_stats" in stats
        assert "heuristic_count" in stats
        assert stats["heuristic_count"] > 0
