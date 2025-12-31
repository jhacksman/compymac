"""
RunStore - Persistent storage for agent runs and sessions.

This module implements Gap 1: Session Persistence + Resume by providing
a storage layer for saving and restoring agent sessions.

Key features:
- Save/load sessions to disk (JSON files)
- Track run metadata (status, timestamps, step count)
- Support for resuming interrupted runs
- List and query past runs
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from compymac.session import Session


class RunStatus(Enum):
    """Status of an agent run."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class RunMetadata:
    """Metadata about an agent run."""
    run_id: str
    created_at: datetime
    updated_at: datetime
    status: RunStatus
    task_description: str
    step_count: int = 0
    tool_calls_count: int = 0
    error_message: str = ""
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "task_description": self.task_description,
            "step_count": self.step_count,
            "tool_calls_count": self.tool_calls_count,
            "error_message": self.error_message,
            "tags": self.tags,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunMetadata":
        return cls(
            run_id=data["run_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            status=RunStatus(data["status"]),
            task_description=data.get("task_description", ""),
            step_count=data.get("step_count", 0),
            tool_calls_count=data.get("tool_calls_count", 0),
            error_message=data.get("error_message", ""),
            tags=data.get("tags", []),
            extra=data.get("extra", {}),
        )


@dataclass
class SavedRun:
    """A complete saved run with session and metadata."""
    metadata: RunMetadata
    session: Session
    harness_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "session": self.session.to_dict(),
            "harness_state": self.harness_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SavedRun":
        return cls(
            metadata=RunMetadata.from_dict(data["metadata"]),
            session=Session.from_dict(data["session"]),
            harness_state=data.get("harness_state", {}),
        )


class RunStore:
    """
    Persistent storage for agent runs.
    
    This class provides the storage layer for Gap 1: Session Persistence + Resume.
    It saves runs as JSON files in a configurable directory.
    
    Usage:
        store = RunStore("/path/to/runs")
        
        # Save a run
        store.save_run(run_id, session, metadata)
        
        # Load a run
        saved_run = store.load_run(run_id)
        
        # Resume from a run
        session = saved_run.session
        
        # List all runs
        runs = store.list_runs()
    """

    def __init__(self, storage_dir: str | Path = "~/.compymac/runs"):
        """
        Initialize the run store.
        
        Args:
            storage_dir: Directory to store run files. Defaults to ~/.compymac/runs
        """
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        """Get the file path for a run."""
        return self.storage_dir / f"{run_id}.json"

    def save_run(
        self,
        run_id: str,
        session: Session,
        task_description: str = "",
        status: RunStatus = RunStatus.RUNNING,
        step_count: int = 0,
        tool_calls_count: int = 0,
        harness_state: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> SavedRun:
        """
        Save a run to persistent storage.
        
        Args:
            run_id: Unique identifier for the run
            session: The session to save
            task_description: Description of the task
            status: Current status of the run
            step_count: Number of steps completed
            tool_calls_count: Number of tool calls made
            harness_state: Optional harness state to save
            tags: Optional tags for the run
            extra: Optional extra metadata
            
        Returns:
            The saved run object
        """
        now = datetime.utcnow()

        # Check if run already exists (for updates)
        existing = self.load_run(run_id)
        created_at = existing.metadata.created_at if existing else now

        metadata = RunMetadata(
            run_id=run_id,
            created_at=created_at,
            updated_at=now,
            status=status,
            task_description=task_description,
            step_count=step_count,
            tool_calls_count=tool_calls_count,
            tags=tags or [],
            extra=extra or {},
        )

        saved_run = SavedRun(
            metadata=metadata,
            session=session,
            harness_state=harness_state or {},
        )

        # Write to file
        run_path = self._run_path(run_id)
        with open(run_path, "w") as f:
            json.dump(saved_run.to_dict(), f, indent=2)

        return saved_run

    def load_run(self, run_id: str) -> SavedRun | None:
        """
        Load a run from persistent storage.
        
        Args:
            run_id: The run ID to load
            
        Returns:
            The saved run, or None if not found
        """
        run_path = self._run_path(run_id)
        if not run_path.exists():
            return None

        try:
            with open(run_path) as f:
                data = json.load(f)
            return SavedRun.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            # Corrupted file - log and return None
            import logging
            logging.getLogger(__name__).warning(f"Failed to load run {run_id}: {e}")
            return None

    def update_status(self, run_id: str, status: RunStatus, error_message: str = "") -> bool:
        """
        Update the status of a run.
        
        Args:
            run_id: The run ID to update
            status: New status
            error_message: Optional error message (for failed runs)
            
        Returns:
            True if updated, False if run not found
        """
        saved_run = self.load_run(run_id)
        if not saved_run:
            return False

        saved_run.metadata.status = status
        saved_run.metadata.updated_at = datetime.utcnow()
        if error_message:
            saved_run.metadata.error_message = error_message

        run_path = self._run_path(run_id)
        with open(run_path, "w") as f:
            json.dump(saved_run.to_dict(), f, indent=2)

        return True

    def increment_step(self, run_id: str) -> int:
        """
        Increment the step count for a run.
        
        Args:
            run_id: The run ID to update
            
        Returns:
            The new step count, or -1 if run not found
        """
        saved_run = self.load_run(run_id)
        if not saved_run:
            return -1

        saved_run.metadata.step_count += 1
        saved_run.metadata.updated_at = datetime.utcnow()

        run_path = self._run_path(run_id)
        with open(run_path, "w") as f:
            json.dump(saved_run.to_dict(), f, indent=2)

        return saved_run.metadata.step_count

    def list_runs(
        self,
        status: RunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunMetadata]:
        """
        List all runs, optionally filtered by status.
        
        Args:
            status: Optional status filter
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            
        Returns:
            List of run metadata, sorted by updated_at descending
        """
        runs: list[RunMetadata] = []

        for run_file in self.storage_dir.glob("*.json"):
            try:
                with open(run_file) as f:
                    data = json.load(f)
                metadata = RunMetadata.from_dict(data["metadata"])

                if status is None or metadata.status == status:
                    runs.append(metadata)
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by updated_at descending
        runs.sort(key=lambda r: r.updated_at, reverse=True)

        return runs[offset:offset + limit]

    def get_resumable_runs(self) -> list[RunMetadata]:
        """
        Get all runs that can be resumed.
        
        Returns:
            List of runs with status PAUSED or INTERRUPTED
        """
        resumable = []
        for status in [RunStatus.PAUSED, RunStatus.INTERRUPTED]:
            resumable.extend(self.list_runs(status=status))
        return resumable

    def delete_run(self, run_id: str) -> bool:
        """
        Delete a run from storage.
        
        Args:
            run_id: The run ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        run_path = self._run_path(run_id)
        if run_path.exists():
            run_path.unlink()
            return True
        return False

    def cleanup_old_runs(self, max_age_days: int = 30) -> int:
        """
        Delete runs older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of runs deleted
        """
        cutoff = datetime.utcnow().timestamp() - (max_age_days * 24 * 60 * 60)
        deleted = 0

        for run_file in self.storage_dir.glob("*.json"):
            if run_file.stat().st_mtime < cutoff:
                run_file.unlink()
                deleted += 1

        return deleted
