"""Tests for Gap 6 Phase 2: Parallel Workstreams with Merge/Review."""

from compymac.workflows.parallel_workstreams import (
    ConflictDetector,
    ConflictReport,
    ConflictType,
    EnhancedWorkspaceMerger,
    FileConflict,
    MergeStrategy,
    ParallelWorkstreamOrchestrator,
    ResolutionStrategy,
    ReviewerArbiter,
    StructuredHypothesisResult,
)


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_all_strategies_exist(self):
        assert MergeStrategy.FAST_FORWARD.value == "fast_forward"
        assert MergeStrategy.THREE_WAY.value == "three_way"
        assert MergeStrategy.CHERRY_PICK.value == "cherry_pick"
        assert MergeStrategy.REBASE.value == "rebase"
        assert MergeStrategy.SQUASH.value == "squash"


class TestConflictType:
    """Tests for ConflictType enum."""

    def test_all_types_exist(self):
        assert ConflictType.NONE.value == "none"
        assert ConflictType.FILE_MODIFIED.value == "file_modified"
        assert ConflictType.FILE_DELETED.value == "file_deleted"
        assert ConflictType.DIRECTORY_FILE.value == "directory_file"
        assert ConflictType.RENAME_CONFLICT.value == "rename_conflict"


class TestResolutionStrategy:
    """Tests for ResolutionStrategy enum."""

    def test_all_strategies_exist(self):
        assert ResolutionStrategy.OURS.value == "ours"
        assert ResolutionStrategy.THEIRS.value == "theirs"
        assert ResolutionStrategy.MANUAL.value == "manual"
        assert ResolutionStrategy.LLM_MERGE.value == "llm_merge"
        assert ResolutionStrategy.BEST_HYPOTHESIS.value == "best_hypothesis"


class TestFileConflict:
    """Tests for FileConflict dataclass."""

    def test_to_dict(self):
        conflict = FileConflict(
            file_path="src/main.py",
            conflict_type=ConflictType.FILE_MODIFIED,
            our_content="def foo(): pass",
            their_content="def foo(): return 1",
            base_content="def foo(): return None",
        )
        result = conflict.to_dict()
        assert result["file_path"] == "src/main.py"
        assert result["conflict_type"] == "file_modified"
        assert result["has_our_content"] is True
        assert result["has_their_content"] is True
        assert result["has_base_content"] is True

    def test_to_dict_without_content(self):
        conflict = FileConflict(
            file_path="deleted.py",
            conflict_type=ConflictType.FILE_DELETED,
        )
        result = conflict.to_dict()
        assert result["has_our_content"] is False
        assert result["has_their_content"] is False
        assert result["has_base_content"] is False


class TestConflictReport:
    """Tests for ConflictReport dataclass."""

    def test_has_conflicts(self):
        report = ConflictReport(
            hypothesis_a_id="hyp1",
            hypothesis_b_id="hyp2",
            conflicts=[
                FileConflict(
                    file_path="test.py",
                    conflict_type=ConflictType.FILE_MODIFIED,
                )
            ],
        )
        assert report.has_conflicts is True
        assert report.conflict_count == 1

    def test_no_conflicts(self):
        report = ConflictReport(
            hypothesis_a_id="hyp1",
            hypothesis_b_id="hyp2",
            conflicts=[],
        )
        assert report.has_conflicts is False
        assert report.conflict_count == 0

    def test_to_dict(self):
        report = ConflictReport(
            hypothesis_a_id="hyp1",
            hypothesis_b_id="hyp2",
            conflicts=[],
            can_auto_resolve=True,
            resolution_strategy=ResolutionStrategy.OURS,
        )
        result = report.to_dict()
        assert result["hypothesis_a_id"] == "hyp1"
        assert result["hypothesis_b_id"] == "hyp2"
        assert result["conflict_count"] == 0
        assert result["can_auto_resolve"] is True
        assert result["resolution_strategy"] == "ours"


class TestStructuredHypothesisResult:
    """Tests for StructuredHypothesisResult dataclass."""

    def test_create_basic(self):
        result = StructuredHypothesisResult(
            hypothesis_id="test_hyp",
            approach_description="Test approach",
            success=True,
            result_summary="Test passed",
            confidence_score=0.9,
            execution_time_ms=1000,
        )
        assert result.hypothesis_id == "test_hyp"
        assert result.success is True
        assert result.confidence_score == 0.9

    def test_to_dict(self):
        result = StructuredHypothesisResult(
            hypothesis_id="test_hyp",
            approach_description="Test approach",
            success=True,
            result_summary="Test passed",
            confidence_score=0.9,
            execution_time_ms=1000,
            files_modified=["a.py", "b.py"],
            lines_added=10,
            lines_removed=5,
        )
        data = result.to_dict()
        assert data["hypothesis_id"] == "test_hyp"
        assert data["files_modified"] == ["a.py", "b.py"]
        assert data["lines_added"] == 10
        assert data["lines_removed"] == 5

    def test_with_test_results(self):
        result = StructuredHypothesisResult(
            hypothesis_id="test_hyp",
            approach_description="Test approach",
            success=True,
            result_summary="Test passed",
            confidence_score=0.9,
            execution_time_ms=1000,
            test_results={"passed": True, "count": 10},
            lint_results={"passed": True, "errors": 0},
        )
        assert result.test_results["passed"] is True
        assert result.lint_results["errors"] == 0


class TestReviewerArbiter:
    """Tests for ReviewerArbiter."""

    def test_select_best_empty_results(self):
        arbiter = ReviewerArbiter()
        best, reasoning, handoff = arbiter.select_best_with_review([])
        assert best is None
        assert "No results" in reasoning

    def test_select_best_single_result(self):
        arbiter = ReviewerArbiter()
        results = [
            StructuredHypothesisResult(
                hypothesis_id="hyp1",
                approach_description="Approach 1",
                success=True,
                result_summary="Success",
                confidence_score=0.8,
                execution_time_ms=1000,
            )
        ]
        best, reasoning, handoff = arbiter.select_best_with_review(results)
        assert best is not None
        assert best.hypothesis_id == "hyp1"

    def test_select_best_multiple_results(self):
        arbiter = ReviewerArbiter()
        results = [
            StructuredHypothesisResult(
                hypothesis_id="hyp1",
                approach_description="Approach 1",
                success=True,
                result_summary="Success",
                confidence_score=0.7,
                execution_time_ms=1000,
            ),
            StructuredHypothesisResult(
                hypothesis_id="hyp2",
                approach_description="Approach 2",
                success=True,
                result_summary="Success",
                confidence_score=0.9,
                execution_time_ms=1000,
            ),
        ]
        best, reasoning, handoff = arbiter.select_best_with_review(results)
        assert best is not None
        assert best.hypothesis_id == "hyp2"  # Higher confidence
        assert "0.9" in reasoning or "highest" in reasoning.lower()

    def test_select_best_filters_failed_tests(self):
        arbiter = ReviewerArbiter()
        results = [
            StructuredHypothesisResult(
                hypothesis_id="hyp1",
                approach_description="Approach 1",
                success=True,
                result_summary="Success",
                confidence_score=0.9,
                execution_time_ms=1000,
                test_results={"passed": False},
            ),
            StructuredHypothesisResult(
                hypothesis_id="hyp2",
                approach_description="Approach 2",
                success=True,
                result_summary="Success",
                confidence_score=0.7,
                execution_time_ms=1000,
                test_results={"passed": True},
            ),
        ]
        best, reasoning, handoff = arbiter.select_best_with_review(
            results, require_tests_pass=True
        )
        assert best is not None
        assert best.hypothesis_id == "hyp2"  # Only one with passing tests

    def test_select_best_all_failed(self):
        arbiter = ReviewerArbiter()
        results = [
            StructuredHypothesisResult(
                hypothesis_id="hyp1",
                approach_description="Approach 1",
                success=False,
                result_summary="Failed",
                confidence_score=0.5,
                execution_time_ms=1000,
            ),
        ]
        best, reasoning, handoff = arbiter.select_best_with_review(results)
        assert best is not None
        assert "failed" in reasoning.lower()


class TestConflictDetector:
    """Tests for ConflictDetector (basic tests without git repo)."""

    def test_init(self):
        detector = ConflictDetector("/tmp/test-repo")
        assert detector.repo_path == "/tmp/test-repo"


class TestEnhancedWorkspaceMerger:
    """Tests for EnhancedWorkspaceMerger (basic tests without git repo)."""

    def test_init(self):
        merger = EnhancedWorkspaceMerger("/tmp/test-repo")
        assert merger.repo_path == "/tmp/test-repo"
        assert merger.llm_client is None


class TestParallelWorkstreamOrchestrator:
    """Tests for ParallelWorkstreamOrchestrator."""

    def test_init(self):
        orchestrator = ParallelWorkstreamOrchestrator("/tmp/test-repo")
        assert orchestrator.repo_path == "/tmp/test-repo"
        assert orchestrator.max_parallel == 3

    def test_get_orchestration_stats(self):
        orchestrator = ParallelWorkstreamOrchestrator("/tmp/test-repo", max_parallel=5)
        stats = orchestrator.get_orchestration_stats()
        assert stats["max_parallel"] == 5
        assert stats["repo_path"] == "/tmp/test-repo"
        assert "handoff_stats" in stats
