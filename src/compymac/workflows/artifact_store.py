"""
ArtifactStore - Artifact storage for workflow debugging and review.

This module implements artifact storage based on Confucius Code Agent (arXiv:2512.10398):
- Store all tool outputs in structured format
- Link artifacts to workflow stages
- Make artifacts reviewable

Key insight: Persistent artifacts enable debugging and cross-session learning.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactType(Enum):
    """Types of artifacts that can be stored."""
    # Code artifacts
    CODE_DIFF = "code_diff"
    CODE_SNAPSHOT = "code_snapshot"
    SEARCH_REPLACE = "search_replace"

    # Output artifacts
    TEST_OUTPUT = "test_output"
    LINT_OUTPUT = "lint_output"
    BUILD_OUTPUT = "build_output"
    CI_LOG = "ci_log"

    # Analysis artifacts
    ERROR_ANALYSIS = "error_analysis"
    DEBUG_TRACE = "debug_trace"
    PLAN = "plan"
    UNDERSTANDING = "understanding"

    # Git artifacts
    COMMIT = "commit"
    PR = "pr"
    BRANCH = "branch"

    # Other
    NOTE = "note"
    SCREENSHOT = "screenshot"
    GENERIC = "generic"


@dataclass
class Artifact:
    """An artifact from workflow execution."""
    artifact_type: ArtifactType
    content: str | dict[str, Any]
    stage: str
    description: str = ""
    file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    artifact_id: str = ""

    def __post_init__(self):
        """Generate artifact ID if not provided."""
        if not self.artifact_id:
            content_str = json.dumps(self.content) if isinstance(self.content, dict) else str(self.content)
            hash_input = f"{self.artifact_type.value}:{self.stage}:{content_str}:{self.created_at.isoformat()}"
            self.artifact_id = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type.value,
            "content": self.content,
            "stage": self.stage,
            "description": self.description,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        """Deserialize from dictionary."""
        artifact = cls(
            artifact_type=ArtifactType(data["artifact_type"]),
            content=data["content"],
            stage=data["stage"],
            description=data.get("description", ""),
            file_path=data.get("file_path"),
            metadata=data.get("metadata", {}),
            artifact_id=data.get("artifact_id", ""),
        )
        if data.get("created_at"):
            artifact.created_at = datetime.fromisoformat(data["created_at"])
        return artifact


class ArtifactStore:
    """
    Store and retrieve workflow artifacts.

    Based on Confucius patterns:
    - Hierarchical working memory
    - Persistent note-taking
    - Cross-session continual learning
    """

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize artifact store.

        Args:
            storage_path: Path to store artifacts (in-memory if None)
        """
        self.storage_path = storage_path
        self.artifacts: dict[str, Artifact] = {}
        self.by_stage: dict[str, list[str]] = {}
        self.by_type: dict[ArtifactType, list[str]] = {}

        if storage_path:
            storage_path.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def store(self, artifact: Artifact) -> str:
        """
        Store artifact and return ID.

        Args:
            artifact: Artifact to store

        Returns:
            Artifact ID
        """
        self.artifacts[artifact.artifact_id] = artifact

        # Index by stage
        if artifact.stage not in self.by_stage:
            self.by_stage[artifact.stage] = []
        self.by_stage[artifact.stage].append(artifact.artifact_id)

        # Index by type
        if artifact.artifact_type not in self.by_type:
            self.by_type[artifact.artifact_type] = []
        self.by_type[artifact.artifact_type].append(artifact.artifact_id)

        # Persist to disk if storage path is set
        if self.storage_path:
            self._save_artifact(artifact)

        return artifact.artifact_id

    def get(self, artifact_id: str) -> Artifact | None:
        """Get artifact by ID."""
        return self.artifacts.get(artifact_id)

    def get_by_stage(self, stage: str) -> list[Artifact]:
        """Get all artifacts from a stage."""
        artifact_ids = self.by_stage.get(stage, [])
        return [self.artifacts[aid] for aid in artifact_ids if aid in self.artifacts]

    def get_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        """Get all artifacts of a type."""
        artifact_ids = self.by_type.get(artifact_type, [])
        return [self.artifacts[aid] for aid in artifact_ids if aid in self.artifacts]

    def get_history(self) -> list[Artifact]:
        """Get full artifact history for debugging."""
        return sorted(self.artifacts.values(), key=lambda a: a.created_at)

    def get_recent(self, limit: int = 10) -> list[Artifact]:
        """Get most recent artifacts."""
        history = self.get_history()
        return history[-limit:]

    def search(self, query: str) -> list[Artifact]:
        """
        Search artifacts by content.

        Args:
            query: Search query

        Returns:
            List of matching artifacts
        """
        results = []
        query_lower = query.lower()

        for artifact in self.artifacts.values():
            content_str = json.dumps(artifact.content) if isinstance(artifact.content, dict) else str(artifact.content)
            if query_lower in content_str.lower() or query_lower in artifact.description.lower():
                results.append(artifact)

        return results

    def create_code_diff(
        self,
        stage: str,
        file_path: str,
        old_content: str,
        new_content: str,
        description: str = "",
    ) -> Artifact:
        """
        Create and store a code diff artifact.

        Args:
            stage: Workflow stage
            file_path: Path to the file
            old_content: Original content
            new_content: New content
            description: Description of the change

        Returns:
            Created artifact
        """
        artifact = Artifact(
            artifact_type=ArtifactType.CODE_DIFF,
            content={
                "old": old_content,
                "new": new_content,
            },
            stage=stage,
            description=description,
            file_path=file_path,
        )
        self.store(artifact)
        return artifact

    def create_search_replace(
        self,
        stage: str,
        file_path: str,
        search: str,
        replace: str,
        description: str = "",
    ) -> Artifact:
        """
        Create and store a search-replace artifact.

        Uses the search-replace format recommended by Meta research.

        Args:
            stage: Workflow stage
            file_path: Path to the file
            search: Content to search for
            replace: Content to replace with
            description: Description of the change

        Returns:
            Created artifact
        """
        content = f"""<<<<<<< SEARCH
{search}
=======
{replace}
>>>>>>> REPLACE"""

        artifact = Artifact(
            artifact_type=ArtifactType.SEARCH_REPLACE,
            content=content,
            stage=stage,
            description=description,
            file_path=file_path,
        )
        self.store(artifact)
        return artifact

    def create_test_output(
        self,
        stage: str,
        output: str,
        passed: bool,
        test_count: int = 0,
        failed_count: int = 0,
    ) -> Artifact:
        """
        Create and store a test output artifact.

        Args:
            stage: Workflow stage
            output: Test output
            passed: Whether tests passed
            test_count: Total number of tests
            failed_count: Number of failed tests

        Returns:
            Created artifact
        """
        artifact = Artifact(
            artifact_type=ArtifactType.TEST_OUTPUT,
            content=output,
            stage=stage,
            description=f"Tests {'passed' if passed else 'failed'}: {test_count - failed_count}/{test_count}",
            metadata={
                "passed": passed,
                "test_count": test_count,
                "failed_count": failed_count,
            },
        )
        self.store(artifact)
        return artifact

    def create_error_analysis(
        self,
        stage: str,
        errors: list[str],
        analysis: str,
        suggested_fixes: list[str] | None = None,
    ) -> Artifact:
        """
        Create and store an error analysis artifact.

        Args:
            stage: Workflow stage
            errors: List of error messages
            analysis: Analysis of the errors
            suggested_fixes: Suggested fixes

        Returns:
            Created artifact
        """
        artifact = Artifact(
            artifact_type=ArtifactType.ERROR_ANALYSIS,
            content={
                "errors": errors,
                "analysis": analysis,
                "suggested_fixes": suggested_fixes or [],
            },
            stage=stage,
            description=f"Analysis of {len(errors)} errors",
        )
        self.store(artifact)
        return artifact

    def create_note(self, stage: str, note: str, tags: list[str] | None = None) -> Artifact:
        """
        Create and store a note artifact.

        Args:
            stage: Workflow stage
            note: Note content
            tags: Optional tags for categorization

        Returns:
            Created artifact
        """
        artifact = Artifact(
            artifact_type=ArtifactType.NOTE,
            content=note,
            stage=stage,
            description="Note",
            metadata={"tags": tags or []},
        )
        self.store(artifact)
        return artifact

    def get_summary(self) -> dict[str, Any]:
        """Get summary of stored artifacts."""
        by_type_counts = {
            t.value: len(ids) for t, ids in self.by_type.items()
        }
        by_stage_counts = {
            s: len(ids) for s, ids in self.by_stage.items()
        }

        return {
            "total_artifacts": len(self.artifacts),
            "by_type": by_type_counts,
            "by_stage": by_stage_counts,
            "storage_path": str(self.storage_path) if self.storage_path else None,
        }

    def export_to_json(self) -> str:
        """Export all artifacts to JSON."""
        return json.dumps(
            [a.to_dict() for a in self.get_history()],
            indent=2,
        )

    def _save_artifact(self, artifact: Artifact) -> None:
        """Save artifact to disk."""
        if not self.storage_path:
            return

        artifact_file = self.storage_path / f"{artifact.artifact_id}.json"
        with open(artifact_file, "w") as f:
            json.dump(artifact.to_dict(), f, indent=2)

    def _load_from_disk(self) -> None:
        """Load artifacts from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return

        for artifact_file in self.storage_path.glob("*.json"):
            try:
                with open(artifact_file) as f:
                    data = json.load(f)
                artifact = Artifact.from_dict(data)
                self.artifacts[artifact.artifact_id] = artifact

                # Rebuild indexes
                if artifact.stage not in self.by_stage:
                    self.by_stage[artifact.stage] = []
                self.by_stage[artifact.stage].append(artifact.artifact_id)

                if artifact.artifact_type not in self.by_type:
                    self.by_type[artifact.artifact_type] = []
                self.by_type[artifact.artifact_type].append(artifact.artifact_id)
            except Exception:
                pass  # Skip invalid files

    def clear(self) -> None:
        """Clear all artifacts."""
        self.artifacts.clear()
        self.by_stage.clear()
        self.by_type.clear()

        if self.storage_path:
            for artifact_file in self.storage_path.glob("*.json"):
                artifact_file.unlink()
