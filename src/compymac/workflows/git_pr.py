"""
GitPRWorkflow - Automated Git PR workflow with approval gates.

This module implements Gap 4: Git PR Loop Automation by providing:
- Automated branch creation and management
- Commit staging with approval gates
- PR creation workflow
- CI status monitoring
- Approval gates before destructive operations

Design decision: This workflow wraps the existing git tools in tool_menu.py
and adds approval gates and state management on top.
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowState(Enum):
    """State of the PR workflow."""
    IDLE = "idle"
    BRANCH_CREATED = "branch_created"
    CHANGES_STAGED = "changes_staged"
    COMMITTED = "committed"
    PUSHED = "pushed"
    PR_CREATED = "pr_created"
    CI_PENDING = "ci_pending"
    CI_PASSED = "ci_passed"
    CI_FAILED = "ci_failed"
    APPROVED = "approved"
    MERGED = "merged"
    FAILED = "failed"


@dataclass
class ApprovalGate:
    """
    An approval gate that must be passed before proceeding.
    
    Approval gates can be:
    - Automatic (passes if condition is met)
    - Manual (requires explicit user approval)
    """
    name: str
    description: str
    is_automatic: bool = True
    condition: Callable[[], bool] | None = None
    approved: bool = False
    approved_at: datetime | None = None
    approved_by: str | None = None

    def check(self) -> tuple[bool, str]:
        """
        Check if the gate passes.
        
        Returns:
            Tuple of (passed, reason)
        """
        if self.approved:
            return True, f"Previously approved by {self.approved_by}"

        if self.is_automatic and self.condition:
            try:
                if self.condition():
                    self.approved = True
                    self.approved_at = datetime.utcnow()
                    self.approved_by = "automatic"
                    return True, "Automatic condition passed"
                else:
                    return False, f"Automatic condition failed: {self.description}"
            except Exception as e:
                return False, f"Condition check error: {e}"

        if not self.is_automatic:
            return False, f"Manual approval required: {self.description}"

        return False, "No condition defined"

    def approve(self, approver: str = "user") -> None:
        """Manually approve this gate."""
        self.approved = True
        self.approved_at = datetime.utcnow()
        self.approved_by = approver

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "is_automatic": self.is_automatic,
            "approved": self.approved,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
        }


@dataclass
class GitPRWorkflow:
    """
    Automated Git PR workflow with approval gates.
    
    This class manages the lifecycle of a PR from branch creation to merge,
    with approval gates at critical points.
    """
    repo_path: Path
    branch_name: str | None = None
    base_branch: str = "main"
    state: WorkflowState = WorkflowState.IDLE
    pr_url: str | None = None
    pr_number: int | None = None
    commits: list[str] = field(default_factory=list)
    gates: dict[str, ApprovalGate] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Initialize default approval gates."""
        if not self.gates:
            self._setup_default_gates()

    def _setup_default_gates(self) -> None:
        """Set up default approval gates for the workflow."""
        self.gates = {
            "pre_commit": ApprovalGate(
                name="pre_commit",
                description="Verify changes are ready to commit",
                is_automatic=True,
                condition=self._check_staged_changes,
            ),
            "pre_push": ApprovalGate(
                name="pre_push",
                description="Verify commits are ready to push",
                is_automatic=True,
                condition=self._check_commits_exist,
            ),
            "pre_pr": ApprovalGate(
                name="pre_pr",
                description="Verify branch is ready for PR",
                is_automatic=True,
                condition=self._check_branch_pushed,
            ),
            "ci_pass": ApprovalGate(
                name="ci_pass",
                description="CI checks must pass before merge",
                is_automatic=True,
                condition=lambda: self.state == WorkflowState.CI_PASSED,
            ),
            "merge_approval": ApprovalGate(
                name="merge_approval",
                description="Manual approval required before merge",
                is_automatic=False,
            ),
        }

    def _run_git(self, *args: str) -> tuple[bool, str]:
        """Run a git command and return (success, output)."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except Exception as e:
            return False, str(e)

    def _check_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        success, output = self._run_git("diff", "--cached", "--name-only")
        return success and bool(output.strip())

    def _check_commits_exist(self) -> bool:
        """Check if there are commits to push."""
        return len(self.commits) > 0

    def _check_branch_pushed(self) -> bool:
        """Check if branch has been pushed."""
        return self.state in [WorkflowState.PUSHED, WorkflowState.PR_CREATED]

    def create_branch(self, branch_name: str | None = None) -> tuple[bool, str]:
        """
        Create a new branch for the PR.
        
        Args:
            branch_name: Optional branch name (auto-generated if not provided)
            
        Returns:
            Tuple of (success, message)
        """
        if self.state != WorkflowState.IDLE:
            return False, f"Cannot create branch in state: {self.state.value}"

        if branch_name:
            self.branch_name = branch_name
        else:
            timestamp = int(datetime.utcnow().timestamp())
            self.branch_name = f"devin/{timestamp}-auto-branch"

        # Fetch latest from remote
        self._run_git("fetch", "origin", self.base_branch)

        # Create and checkout new branch
        success, output = self._run_git("checkout", "-b", self.branch_name)
        if not success:
            self.errors.append(f"Failed to create branch: {output}")
            return False, output

        self.state = WorkflowState.BRANCH_CREATED
        self.updated_at = datetime.utcnow()
        return True, f"Created branch: {self.branch_name}"

    def stage_files(self, files: list[str] | None = None) -> tuple[bool, str]:
        """
        Stage files for commit.
        
        Args:
            files: List of file paths to stage (stages all if None)
            
        Returns:
            Tuple of (success, message)
        """
        if self.state not in [WorkflowState.BRANCH_CREATED, WorkflowState.COMMITTED]:
            return False, f"Cannot stage files in state: {self.state.value}"

        if files:
            for f in files:
                success, output = self._run_git("add", f)
                if not success:
                    self.errors.append(f"Failed to stage {f}: {output}")
                    return False, output
        else:
            success, output = self._run_git("add", "-A")
            if not success:
                self.errors.append(f"Failed to stage files: {output}")
                return False, output

        self.state = WorkflowState.CHANGES_STAGED
        self.updated_at = datetime.utcnow()
        return True, "Files staged successfully"

    def commit(self, message: str) -> tuple[bool, str]:
        """
        Commit staged changes with approval gate.
        
        Args:
            message: Commit message
            
        Returns:
            Tuple of (success, message)
        """
        if self.state != WorkflowState.CHANGES_STAGED:
            return False, f"Cannot commit in state: {self.state.value}"

        # Check pre-commit gate
        gate = self.gates.get("pre_commit")
        if gate:
            passed, reason = gate.check()
            if not passed:
                return False, f"Pre-commit gate failed: {reason}"

        success, output = self._run_git("commit", "-m", message)
        if not success:
            self.errors.append(f"Failed to commit: {output}")
            return False, output

        # Extract commit hash
        hash_success, hash_output = self._run_git("rev-parse", "HEAD")
        if hash_success:
            self.commits.append(hash_output.strip()[:8])

        self.state = WorkflowState.COMMITTED
        self.updated_at = datetime.utcnow()
        return True, f"Committed: {message}"

    def push(self, force: bool = False) -> tuple[bool, str]:
        """
        Push commits to remote with approval gate.
        
        Args:
            force: Whether to force push (requires manual approval)
            
        Returns:
            Tuple of (success, message)
        """
        if self.state != WorkflowState.COMMITTED:
            return False, f"Cannot push in state: {self.state.value}"

        # Check pre-push gate
        gate = self.gates.get("pre_push")
        if gate:
            passed, reason = gate.check()
            if not passed:
                return False, f"Pre-push gate failed: {reason}"

        # Force push requires manual approval
        if force:
            force_gate = self.gates.get("force_push")
            if not force_gate:
                force_gate = ApprovalGate(
                    name="force_push",
                    description="Force push requires manual approval",
                    is_automatic=False,
                )
                self.gates["force_push"] = force_gate

            passed, reason = force_gate.check()
            if not passed:
                return False, f"Force push blocked: {reason}"

        args = ["push", "-u", "origin", self.branch_name]
        if force:
            args.insert(1, "--force")

        success, output = self._run_git(*args)
        if not success:
            self.errors.append(f"Failed to push: {output}")
            return False, output

        self.state = WorkflowState.PUSHED
        self.updated_at = datetime.utcnow()
        return True, f"Pushed to origin/{self.branch_name}"

    def check_gate(self, gate_name: str) -> tuple[bool, str]:
        """
        Check if a specific gate passes.
        
        Args:
            gate_name: Name of the gate to check
            
        Returns:
            Tuple of (passed, reason)
        """
        gate = self.gates.get(gate_name)
        if not gate:
            return False, f"Gate not found: {gate_name}"
        return gate.check()

    def approve_gate(self, gate_name: str, approver: str = "user") -> tuple[bool, str]:
        """
        Manually approve a gate.
        
        Args:
            gate_name: Name of the gate to approve
            approver: Who is approving
            
        Returns:
            Tuple of (success, message)
        """
        gate = self.gates.get(gate_name)
        if not gate:
            return False, f"Gate not found: {gate_name}"

        gate.approve(approver)
        self.updated_at = datetime.utcnow()
        return True, f"Gate '{gate_name}' approved by {approver}"

    def get_status(self) -> dict[str, Any]:
        """Get current workflow status."""
        return {
            "state": self.state.value,
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "commits": self.commits,
            "gates": {name: gate.to_dict() for name, gate in self.gates.items()},
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def get_pending_gates(self) -> list[ApprovalGate]:
        """Get list of gates that haven't been approved."""
        return [gate for gate in self.gates.values() if not gate.approved]

    def get_blocking_gates(self) -> list[tuple[str, str]]:
        """Get list of gates that are blocking progress."""
        blocking = []
        for name, gate in self.gates.items():
            passed, reason = gate.check()
            if not passed:
                blocking.append((name, reason))
        return blocking

    def can_proceed(self) -> tuple[bool, str]:
        """
        Check if workflow can proceed to next step.
        
        Returns:
            Tuple of (can_proceed, reason)
        """
        blocking = self.get_blocking_gates()
        if blocking:
            reasons = [f"{name}: {reason}" for name, reason in blocking]
            return False, f"Blocked by gates: {'; '.join(reasons)}"
        return True, "All gates passed"

    def set_ci_status(self, passed: bool) -> None:
        """Update CI status."""
        if passed:
            self.state = WorkflowState.CI_PASSED
            self.gates["ci_pass"].approve("ci_system")
        else:
            self.state = WorkflowState.CI_FAILED
        self.updated_at = datetime.utcnow()

    def set_pr_info(self, pr_url: str, pr_number: int) -> None:
        """Set PR information after creation."""
        self.pr_url = pr_url
        self.pr_number = pr_number
        self.state = WorkflowState.PR_CREATED
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Serialize workflow to dictionary."""
        return {
            "repo_path": str(self.repo_path),
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
            "state": self.state.value,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "commits": self.commits,
            "gates": {name: gate.to_dict() for name, gate in self.gates.items()},
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitPRWorkflow":
        """Deserialize workflow from dictionary."""
        workflow = cls(
            repo_path=Path(data["repo_path"]),
            branch_name=data.get("branch_name"),
            base_branch=data.get("base_branch", "main"),
            state=WorkflowState(data.get("state", "idle")),
            pr_url=data.get("pr_url"),
            pr_number=data.get("pr_number"),
            commits=data.get("commits", []),
            errors=data.get("errors", []),
        )

        # Parse timestamps
        if data.get("created_at"):
            workflow.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            workflow.updated_at = datetime.fromisoformat(data["updated_at"])

        # Restore gates (without conditions - they need to be re-setup)
        workflow._setup_default_gates()
        for name, gate_data in data.get("gates", {}).items():
            if name in workflow.gates:
                workflow.gates[name].approved = gate_data.get("approved", False)
                if gate_data.get("approved_at"):
                    workflow.gates[name].approved_at = datetime.fromisoformat(gate_data["approved_at"])
                workflow.gates[name].approved_by = gate_data.get("approved_by")

        return workflow
