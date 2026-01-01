"""
Gap 6 Phase 2: Parallel Workstreams with Merge/Review.

This module extends the parallel execution infrastructure with:
1. Structured result comparison using Phase 1 artifact handoffs
2. HypothesisArbiter integration with Reviewer agent
3. Git-based workspace merge strategies
4. Conflict detection and resolution

Based on research from:
- MetaGPT (arXiv:2308.00352): SOP-style structured outputs
- AgentOrchestra (arXiv:2506.12508): Hierarchical orchestration
- ChatDev (arXiv:2307.07924): Communicative dehallucination
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from compymac.workflows.agent_handoffs import (
    AgentArtifactType,
    HandoffManager,
    ReviewFeedback,
    StructuredHandoff,
)

if TYPE_CHECKING:
    from compymac.llm_client import LLMClient
    from compymac.parallel import HypothesisResult


class MergeStrategy(Enum):
    """Git merge strategies for combining parallel workstreams."""

    FAST_FORWARD = "fast_forward"  # Only if no divergence
    THREE_WAY = "three_way"  # Standard merge with merge commit
    CHERRY_PICK = "cherry_pick"  # Pick specific commits
    REBASE = "rebase"  # Rebase onto target
    SQUASH = "squash"  # Squash all commits into one


class ConflictType(Enum):
    """Types of conflicts that can occur during merge."""

    NONE = "none"
    FILE_MODIFIED = "file_modified"  # Same file modified differently
    FILE_DELETED = "file_deleted"  # File deleted in one branch, modified in another
    DIRECTORY_FILE = "directory_file"  # Directory vs file conflict
    RENAME_CONFLICT = "rename_conflict"  # Same file renamed differently


class ResolutionStrategy(Enum):
    """Strategies for resolving merge conflicts."""

    OURS = "ours"  # Keep our changes
    THEIRS = "theirs"  # Keep their changes
    MANUAL = "manual"  # Require manual resolution
    LLM_MERGE = "llm_merge"  # Use LLM to merge conflicting changes
    BEST_HYPOTHESIS = "best_hypothesis"  # Use the winning hypothesis's version


@dataclass
class FileConflict:
    """Represents a conflict in a specific file."""

    file_path: str
    conflict_type: ConflictType
    our_content: str | None = None
    their_content: str | None = None
    base_content: str | None = None
    conflict_markers: str | None = None  # Git conflict markers if present

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "conflict_type": self.conflict_type.value,
            "has_our_content": self.our_content is not None,
            "has_their_content": self.their_content is not None,
            "has_base_content": self.base_content is not None,
        }


@dataclass
class ConflictReport:
    """Report of all conflicts detected during merge attempt."""

    hypothesis_a_id: str
    hypothesis_b_id: str
    conflicts: list[FileConflict] = field(default_factory=list)
    can_auto_resolve: bool = False
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.MANUAL
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_a_id": self.hypothesis_a_id,
            "hypothesis_b_id": self.hypothesis_b_id,
            "conflict_count": self.conflict_count,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "can_auto_resolve": self.can_auto_resolve,
            "resolution_strategy": self.resolution_strategy.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class StructuredHypothesisResult:
    """
    Extended hypothesis result with structured artifact comparison.

    Extends the basic HypothesisResult with:
    - Structured handoff artifacts from Phase 1
    - Detailed diff statistics
    - Test results and coverage
    - Review feedback from Reviewer agent
    """

    hypothesis_id: str
    approach_description: str
    success: bool
    result_summary: str
    confidence_score: float
    execution_time_ms: int

    # Structured artifacts from Phase 1
    handoffs: list[StructuredHandoff] = field(default_factory=list)

    # Detailed metrics
    files_modified: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    test_results: dict[str, Any] = field(default_factory=dict)
    lint_results: dict[str, Any] = field(default_factory=dict)

    # Review feedback
    review_feedback: ReviewFeedback | None = None
    reviewer_score: float = 0.0

    # Errors
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_hypothesis_result(
        cls,
        result: HypothesisResult,
        handoffs: list[StructuredHandoff] | None = None,
    ) -> StructuredHypothesisResult:
        """Create from a basic HypothesisResult."""
        return cls(
            hypothesis_id=result.hypothesis_id,
            approach_description=result.approach_description,
            success=result.success,
            result_summary=result.result_summary,
            confidence_score=result.confidence_score,
            execution_time_ms=result.execution_time_ms,
            handoffs=handoffs or [],
            errors=result.errors,
            lines_added=result.diff_stats.get("lines_added", 0),
            lines_removed=result.diff_stats.get("lines_removed", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "approach_description": self.approach_description,
            "success": self.success,
            "result_summary": self.result_summary,
            "confidence_score": self.confidence_score,
            "execution_time_ms": self.execution_time_ms,
            "files_modified": self.files_modified,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "test_results": self.test_results,
            "lint_results": self.lint_results,
            "reviewer_score": self.reviewer_score,
            "handoff_count": len(self.handoffs),
            "errors": self.errors,
        }


class ConflictDetector:
    """
    Detects conflicts between parallel workstreams before merge.

    Uses git to identify potential merge conflicts without actually
    performing the merge.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def detect_conflicts(
        self,
        branch_a: str,
        branch_b: str,
    ) -> ConflictReport:
        """
        Detect conflicts between two branches without merging.

        Args:
            branch_a: First branch name
            branch_b: Second branch name

        Returns:
            ConflictReport with detected conflicts
        """
        conflicts: list[FileConflict] = []

        try:
            # Get list of files modified in each branch relative to their merge base
            merge_base = self._get_merge_base(branch_a, branch_b)
            if not merge_base:
                return ConflictReport(
                    hypothesis_a_id=branch_a,
                    hypothesis_b_id=branch_b,
                    conflicts=[],
                    can_auto_resolve=True,
                )

            files_a = self._get_modified_files(merge_base, branch_a)
            files_b = self._get_modified_files(merge_base, branch_b)

            # Find overlapping files
            overlapping = set(files_a) & set(files_b)

            for file_path in overlapping:
                conflict = self._check_file_conflict(
                    file_path, merge_base, branch_a, branch_b
                )
                if conflict:
                    conflicts.append(conflict)

            # Check for delete/modify conflicts
            deleted_a = self._get_deleted_files(merge_base, branch_a)
            deleted_b = self._get_deleted_files(merge_base, branch_b)

            for file_path in deleted_a & set(files_b):
                conflicts.append(
                    FileConflict(
                        file_path=file_path,
                        conflict_type=ConflictType.FILE_DELETED,
                    )
                )

            for file_path in deleted_b & set(files_a):
                conflicts.append(
                    FileConflict(
                        file_path=file_path,
                        conflict_type=ConflictType.FILE_DELETED,
                    )
                )

        except subprocess.CalledProcessError:
            pass

        can_auto_resolve = len(conflicts) == 0 or all(
            c.conflict_type == ConflictType.NONE for c in conflicts
        )

        return ConflictReport(
            hypothesis_a_id=branch_a,
            hypothesis_b_id=branch_b,
            conflicts=conflicts,
            can_auto_resolve=can_auto_resolve,
            resolution_strategy=(
                ResolutionStrategy.OURS if can_auto_resolve else ResolutionStrategy.MANUAL
            ),
        )

    def _get_merge_base(self, branch_a: str, branch_b: str) -> str | None:
        """Get the merge base commit between two branches."""
        try:
            result = subprocess.run(
                ["git", "merge-base", branch_a, branch_b],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return result.stdout.decode().strip()
        except subprocess.CalledProcessError:
            return None

    def _get_modified_files(self, base: str, branch: str) -> list[str]:
        """Get list of files modified between base and branch."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base, branch],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return result.stdout.decode().strip().split("\n")
        except subprocess.CalledProcessError:
            return []

    def _get_deleted_files(self, base: str, branch: str) -> set[str]:
        """Get set of files deleted between base and branch."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=D", base, branch],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            files = result.stdout.decode().strip()
            return set(files.split("\n")) if files else set()
        except subprocess.CalledProcessError:
            return set()

    def _check_file_conflict(
        self,
        file_path: str,
        merge_base: str,
        branch_a: str,
        branch_b: str,
    ) -> FileConflict | None:
        """Check if a specific file has conflicts between branches."""
        try:
            # Get the content from each version
            base_content = self._get_file_content(merge_base, file_path)
            content_a = self._get_file_content(branch_a, file_path)
            content_b = self._get_file_content(branch_b, file_path)

            # If both branches made the same change, no conflict
            if content_a == content_b:
                return None

            # If one branch didn't change from base, no conflict
            if content_a == base_content or content_b == base_content:
                return None

            # Real conflict - both branches modified differently
            return FileConflict(
                file_path=file_path,
                conflict_type=ConflictType.FILE_MODIFIED,
                our_content=content_a,
                their_content=content_b,
                base_content=base_content,
            )

        except subprocess.CalledProcessError:
            return None

    def _get_file_content(self, ref: str, file_path: str) -> str | None:
        """Get file content at a specific git ref."""
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{file_path}"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return result.stdout.decode()
        except subprocess.CalledProcessError:
            return None


class EnhancedWorkspaceMerger:
    """
    Enhanced workspace merger with multiple strategies and conflict resolution.

    Extends WorkspaceIsolation.merge_changes() with:
    - Multiple merge strategies
    - Conflict detection before merge
    - Automatic conflict resolution for simple cases
    - LLM-assisted conflict resolution
    """

    def __init__(
        self,
        repo_path: str,
        llm_client: LLMClient | None = None,
    ):
        self.repo_path = repo_path
        self.llm_client = llm_client
        self.conflict_detector = ConflictDetector(repo_path)
        self._lock = threading.Lock()

    def merge_with_strategy(
        self,
        source_branch: str,
        target_branch: str = "HEAD",
        strategy: MergeStrategy = MergeStrategy.THREE_WAY,
        auto_resolve: bool = False,
    ) -> tuple[bool, str, ConflictReport | None]:
        """
        Merge source branch into target with specified strategy.

        Args:
            source_branch: Branch to merge from
            target_branch: Branch to merge into
            strategy: Merge strategy to use
            auto_resolve: Whether to attempt automatic conflict resolution

        Returns:
            Tuple of (success, message, conflict_report)
        """
        with self._lock:
            # First detect conflicts
            conflict_report = self.conflict_detector.detect_conflicts(
                target_branch, source_branch
            )

            if conflict_report.has_conflicts and not auto_resolve:
                return (
                    False,
                    f"Conflicts detected: {conflict_report.conflict_count} files",
                    conflict_report,
                )

            # Attempt merge based on strategy
            if strategy == MergeStrategy.FAST_FORWARD:
                return self._merge_fast_forward(source_branch, target_branch)
            elif strategy == MergeStrategy.THREE_WAY:
                return self._merge_three_way(
                    source_branch, target_branch, auto_resolve, conflict_report
                )
            elif strategy == MergeStrategy.CHERRY_PICK:
                return self._merge_cherry_pick(source_branch, target_branch)
            elif strategy == MergeStrategy.SQUASH:
                return self._merge_squash(source_branch, target_branch)
            else:
                return self._merge_three_way(
                    source_branch, target_branch, auto_resolve, conflict_report
                )

    def _merge_fast_forward(
        self,
        source_branch: str,
        target_branch: str,
    ) -> tuple[bool, str, ConflictReport | None]:
        """Attempt fast-forward merge."""
        try:
            result = subprocess.run(
                ["git", "merge", "--ff-only", source_branch],
                cwd=self.repo_path,
                capture_output=True,
            )
            if result.returncode == 0:
                return True, "Fast-forward merge successful", None
            else:
                return (
                    False,
                    f"Fast-forward not possible: {result.stderr.decode()}",
                    None,
                )
        except subprocess.CalledProcessError as e:
            return False, f"Merge failed: {e}", None

    def _merge_three_way(
        self,
        source_branch: str,
        target_branch: str,
        auto_resolve: bool,
        conflict_report: ConflictReport | None,
    ) -> tuple[bool, str, ConflictReport | None]:
        """Perform three-way merge with optional auto-resolution."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "merge",
                    "--no-ff",
                    source_branch,
                    "-m",
                    f"Merge {source_branch} into {target_branch}",
                ],
                cwd=self.repo_path,
                capture_output=True,
            )

            if result.returncode == 0:
                return True, "Three-way merge successful", None

            # Merge failed - check if we should auto-resolve
            if auto_resolve and conflict_report:
                resolved = self._auto_resolve_conflicts(conflict_report)
                if resolved:
                    # Complete the merge
                    subprocess.run(
                        ["git", "add", "."],
                        cwd=self.repo_path,
                        check=True,
                    )
                    subprocess.run(
                        [
                            "git",
                            "commit",
                            "-m",
                            f"Merge {source_branch} (auto-resolved conflicts)",
                        ],
                        cwd=self.repo_path,
                        check=True,
                    )
                    return True, "Merge successful with auto-resolved conflicts", conflict_report

            # Abort the failed merge
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=self.repo_path,
                check=False,
            )
            return (
                False,
                f"Merge conflicts: {result.stderr.decode()}",
                conflict_report,
            )

        except subprocess.CalledProcessError as e:
            subprocess.run(
                ["git", "merge", "--abort"],
                cwd=self.repo_path,
                check=False,
            )
            return False, f"Merge failed: {e}", conflict_report

    def _merge_cherry_pick(
        self,
        source_branch: str,
        target_branch: str,
    ) -> tuple[bool, str, ConflictReport | None]:
        """Cherry-pick commits from source branch."""
        try:
            # Get commits unique to source branch
            result = subprocess.run(
                ["git", "log", "--oneline", f"{target_branch}..{source_branch}"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            commits = result.stdout.decode().strip().split("\n")
            if not commits or commits == [""]:
                return True, "No commits to cherry-pick", None

            # Cherry-pick each commit (in reverse order)
            for commit_line in reversed(commits):
                commit_hash = commit_line.split()[0]
                subprocess.run(
                    ["git", "cherry-pick", commit_hash],
                    cwd=self.repo_path,
                    check=True,
                )

            return True, f"Cherry-picked {len(commits)} commits", None

        except subprocess.CalledProcessError as e:
            subprocess.run(
                ["git", "cherry-pick", "--abort"],
                cwd=self.repo_path,
                check=False,
            )
            return False, f"Cherry-pick failed: {e}", None

    def _merge_squash(
        self,
        source_branch: str,
        target_branch: str,
    ) -> tuple[bool, str, ConflictReport | None]:
        """Squash merge all commits into one."""
        try:
            result = subprocess.run(
                ["git", "merge", "--squash", source_branch],
                cwd=self.repo_path,
                capture_output=True,
            )

            if result.returncode == 0:
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"Squash merge {source_branch}",
                    ],
                    cwd=self.repo_path,
                    check=True,
                )
                return True, "Squash merge successful", None
            else:
                subprocess.run(
                    ["git", "reset", "--hard", "HEAD"],
                    cwd=self.repo_path,
                    check=False,
                )
                return False, f"Squash merge failed: {result.stderr.decode()}", None

        except subprocess.CalledProcessError as e:
            return False, f"Squash merge failed: {e}", None

    def _auto_resolve_conflicts(self, conflict_report: ConflictReport) -> bool:
        """Attempt to automatically resolve conflicts."""
        if not conflict_report.has_conflicts:
            return True

        for conflict in conflict_report.conflicts:
            if conflict.conflict_type == ConflictType.FILE_MODIFIED:
                # For now, just take "ours" version for auto-resolve
                try:
                    subprocess.run(
                        ["git", "checkout", "--ours", conflict.file_path],
                        cwd=self.repo_path,
                        check=True,
                    )
                except subprocess.CalledProcessError:
                    return False
            elif conflict.conflict_type == ConflictType.FILE_DELETED:
                # Keep the file if it was modified
                try:
                    subprocess.run(
                        ["git", "checkout", "--ours", conflict.file_path],
                        cwd=self.repo_path,
                        check=False,
                    )
                except subprocess.CalledProcessError:
                    pass

        return True


class ReviewerArbiter:
    """
    Enhanced arbiter that uses a Reviewer agent to evaluate hypotheses.

    Integrates with Phase 1's structured handoffs to:
    - Create REVIEW_FEEDBACK artifacts for each hypothesis
    - Use objective signals (tests, lint) to gate selection
    - Provide structured reasoning for selection decisions
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        handoff_manager: HandoffManager | None = None,
    ):
        self.llm_client = llm_client
        self.handoff_manager = handoff_manager or HandoffManager()

    def select_best_with_review(
        self,
        results: list[StructuredHypothesisResult],
        require_tests_pass: bool = True,
        require_lint_pass: bool = True,
    ) -> tuple[StructuredHypothesisResult | None, str, StructuredHandoff | None]:
        """
        Select the best hypothesis with structured review.

        Args:
            results: List of structured hypothesis results
            require_tests_pass: Only consider hypotheses where tests pass
            require_lint_pass: Only consider hypotheses where lint passes

        Returns:
            Tuple of (best_result, reasoning, review_handoff)
        """
        if not results:
            return None, "No results to compare", None

        # Filter by objective signals
        candidates = results
        if require_tests_pass:
            candidates = [
                r
                for r in candidates
                if r.test_results.get("passed", True)
            ]
            if not candidates:
                return (
                    results[0],
                    "No hypotheses passed tests, returning first result",
                    None,
                )

        if require_lint_pass:
            candidates = [
                r
                for r in candidates
                if r.lint_results.get("passed", True)
            ]
            if not candidates:
                return (
                    results[0],
                    "No hypotheses passed lint, returning first result",
                    None,
                )

        # Filter by success
        successful = [r for r in candidates if r.success]
        if not successful:
            return candidates[0], "All candidates failed, returning first", None

        # Use LLM to review and select
        if self.llm_client and len(successful) > 1:
            best, reasoning = self._llm_review_and_select(successful)
        else:
            # Fallback to highest confidence
            best = max(successful, key=lambda r: r.confidence_score)
            reasoning = f"Selected highest confidence ({best.confidence_score:.2f})"

        # Create review handoff
        review_handoff = self._create_review_handoff(best, results, reasoning)

        return best, reasoning, review_handoff

    def _llm_review_and_select(
        self,
        results: list[StructuredHypothesisResult],
    ) -> tuple[StructuredHypothesisResult, str]:
        """Use LLM to review and select the best hypothesis."""
        prompt = self._build_review_prompt(results)

        try:
            response = self.llm_client.chat([{"role": "user", "content": prompt}])
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Parse selection from response
            for i, r in enumerate(results):
                if str(i + 1) in response_text[:100]:
                    return r, f"Reviewer selected approach {i+1}: {response_text[:300]}"

            # Fallback
            return results[0], f"Reviewer response unclear: {response_text[:200]}"

        except Exception as e:
            best = max(results, key=lambda r: r.confidence_score)
            return best, f"Review failed ({e}), using highest confidence"

    def _build_review_prompt(
        self,
        results: list[StructuredHypothesisResult],
    ) -> str:
        """Build a structured review prompt."""
        prompt = """You are a code reviewer evaluating multiple solution approaches.

Compare these approaches and select the BEST one based on:
1. Code quality and maintainability
2. Test coverage and results
3. Minimal changes (prefer smaller, focused changes)
4. Correctness of the solution

"""
        for i, r in enumerate(results):
            prompt += f"""
## Approach {i+1}: {r.hypothesis_id}
- Description: {r.approach_description}
- Result: {r.result_summary[:200]}
- Files modified: {len(r.files_modified)}
- Lines added: {r.lines_added}, removed: {r.lines_removed}
- Confidence: {r.confidence_score:.2f}
- Tests: {r.test_results}
- Errors: {r.errors[:3] if r.errors else 'None'}
"""

        prompt += """
Which approach is BEST? Respond with:
1. The approach number (1, 2, etc.)
2. Brief reasoning (2-3 sentences)

Format: "Approach X is best because..."
"""
        return prompt

    def _create_review_handoff(
        self,
        selected: StructuredHypothesisResult,
        all_results: list[StructuredHypothesisResult],
        reasoning: str,
    ) -> StructuredHandoff:
        """Create a structured handoff for the review decision."""
        return self.handoff_manager.create_handoff(
            from_agent="reviewer",
            to_agent="manager",
            artifact_type=AgentArtifactType.REVIEW_FEEDBACK,
            content={
                "selected_hypothesis": selected.hypothesis_id,
                "total_candidates": len(all_results),
                "successful_candidates": sum(1 for r in all_results if r.success),
                "reasoning": reasoning,
                "selected_confidence": selected.confidence_score,
                "selected_files_modified": len(selected.files_modified),
                "selected_lines_changed": selected.lines_added + selected.lines_removed,
            },
        )


class ParallelWorkstreamOrchestrator:
    """
    Orchestrates parallel workstreams with structured handoffs and merge.

    This is the main entry point for Phase 2, combining:
    - ParallelHypothesisExecutor for parallel execution
    - ReviewerArbiter for structured selection
    - EnhancedWorkspaceMerger for git-based merging
    - HandoffManager for artifact tracking
    """

    def __init__(
        self,
        repo_path: str,
        llm_client: LLMClient | None = None,
        handoff_manager: HandoffManager | None = None,
        max_parallel: int = 3,
    ):
        self.repo_path = repo_path
        self.llm_client = llm_client
        self.handoff_manager = handoff_manager or HandoffManager()
        self.max_parallel = max_parallel

        self.merger = EnhancedWorkspaceMerger(repo_path, llm_client)
        self.reviewer = ReviewerArbiter(llm_client, self.handoff_manager)
        self.conflict_detector = ConflictDetector(repo_path)

    def execute_and_merge(
        self,
        results: list[StructuredHypothesisResult],
        merge_strategy: MergeStrategy = MergeStrategy.THREE_WAY,
        require_tests_pass: bool = True,
    ) -> tuple[StructuredHypothesisResult | None, bool, str]:
        """
        Select best hypothesis and merge its changes.

        Args:
            results: List of hypothesis results with branch info
            merge_strategy: Strategy for merging the winning hypothesis
            require_tests_pass: Only consider hypotheses where tests pass

        Returns:
            Tuple of (selected_result, merge_success, message)
        """
        # Select best hypothesis
        best, reasoning, review_handoff = self.reviewer.select_best_with_review(
            results,
            require_tests_pass=require_tests_pass,
        )

        if not best:
            return None, False, "No suitable hypothesis found"

        # Create selection handoff
        self.handoff_manager.create_handoff(
            from_agent="orchestrator",
            to_agent="merger",
            artifact_type=AgentArtifactType.EXECUTION_PLAN,
            content={
                "action": "merge_hypothesis",
                "hypothesis_id": best.hypothesis_id,
                "merge_strategy": merge_strategy.value,
                "reasoning": reasoning,
            },
        )

        # Attempt merge
        branch_name = f"parallel-worker-{best.hypothesis_id}"
        success, message, conflict_report = self.merger.merge_with_strategy(
            source_branch=branch_name,
            strategy=merge_strategy,
            auto_resolve=True,
        )

        # Record merge result
        self.handoff_manager.create_handoff(
            from_agent="merger",
            to_agent="manager",
            artifact_type=(
                AgentArtifactType.TEST_RESULT
                if success
                else AgentArtifactType.FAILURE_ANALYSIS
            ),
            content={
                "merge_success": success,
                "message": message,
                "hypothesis_id": best.hypothesis_id,
                "conflicts": conflict_report.to_dict() if conflict_report else None,
            },
        )

        return best, success, message

    def get_orchestration_stats(self) -> dict[str, Any]:
        """Get statistics about the orchestration process."""
        handoff_stats = self.handoff_manager.get_validation_stats()
        return {
            "handoff_stats": handoff_stats,
            "max_parallel": self.max_parallel,
            "repo_path": self.repo_path,
        }


# Export all public classes
__all__ = [
    "MergeStrategy",
    "ConflictType",
    "ResolutionStrategy",
    "FileConflict",
    "ConflictReport",
    "StructuredHypothesisResult",
    "ConflictDetector",
    "EnhancedWorkspaceMerger",
    "ReviewerArbiter",
    "ParallelWorkstreamOrchestrator",
]
