"""
CIIntegration - CI status polling and log parsing.

This module implements CI integration based on Meta's Engineering Agent (arXiv:2507.18755):
- Poll CI status for PRs
- Parse CI logs for actionable errors
- Generate auto-fixes for common CI errors (lint, type)

Key insight: CI feedback is critical for the iterate loop.
"""

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CIStatus(Enum):
    """Status of CI checks."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class CIErrorType(Enum):
    """Types of CI errors."""
    LINT = "lint"
    TYPE_CHECK = "type_check"
    TEST = "test"
    BUILD = "build"
    SECURITY = "security"
    COVERAGE = "coverage"
    UNKNOWN = "unknown"


@dataclass
class CIError:
    """A CI error with location and fix suggestion."""
    error_type: CIErrorType
    message: str
    file_path: str | None = None
    line_number: int | None = None
    column: int | None = None
    rule: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "rule": self.rule,
            "suggestion": self.suggestion,
        }


@dataclass
class CICheckResult:
    """Result of a CI check."""
    name: str
    status: CIStatus
    url: str | None = None
    duration_seconds: int | None = None
    errors: list[CIError] = field(default_factory=list)
    raw_log: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "url": self.url,
            "duration_seconds": self.duration_seconds,
            "errors": [e.to_dict() for e in self.errors],
            "raw_log_length": len(self.raw_log),
        }


@dataclass
class Fix:
    """A suggested fix for a CI error."""
    file_path: str
    original: str
    replacement: str
    error: CIError
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "original": self.original,
            "replacement": self.replacement,
            "error": self.error.to_dict(),
            "confidence": self.confidence,
        }

    def to_search_replace(self) -> str:
        """Convert to search-replace format."""
        return f"""<<<<<<< SEARCH
{self.original}
=======
{self.replacement}
>>>>>>> REPLACE"""


class CIIntegration:
    """
    CI integration for polling status and parsing logs.

    Based on Meta's Engineering Agent patterns:
    - Rule-based test failure triage
    - Static analysis feedback
    - Auto-fix generation for common errors
    """

    def __init__(self, repo_path: Path | None = None):
        """Initialize CI integration."""
        self.repo_path = repo_path
        self.check_history: list[CICheckResult] = []

    def poll_status(self, pr_url: str, fetch_logs: bool = True) -> tuple[CIStatus, list[CICheckResult]]:
        """
        Poll CI status for PR.

        Args:
            pr_url: URL of the pull request
            fetch_logs: If True, fetch logs for failed checks (slower but enables error parsing)

        Returns:
            Tuple of (overall_status, list of check results)
        """
        import json

        match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if not match:
            return CIStatus.UNKNOWN, []

        owner, repo, pr_number = match.groups()

        try:
            result = subprocess.run(
                ["gh", "pr", "checks", pr_number, "--repo", f"{owner}/{repo}", "--json", "name,state,conclusion,detailsUrl"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return CIStatus.UNKNOWN, []

            checks_data = json.loads(result.stdout)

            checks = []
            overall_status = CIStatus.PASSED

            for check in checks_data:
                name = check.get("name", "unknown")
                state = check.get("state", "").lower()
                conclusion = check.get("conclusion", "").lower()
                details_url = check.get("detailsUrl", "")

                if state == "pending" or state == "queued":
                    status = CIStatus.PENDING
                    if overall_status != CIStatus.FAILED:
                        overall_status = CIStatus.PENDING
                elif state == "in_progress":
                    status = CIStatus.RUNNING
                    if overall_status != CIStatus.FAILED:
                        overall_status = CIStatus.RUNNING
                elif conclusion == "success":
                    status = CIStatus.PASSED
                elif conclusion == "failure":
                    status = CIStatus.FAILED
                    overall_status = CIStatus.FAILED
                elif conclusion == "cancelled":
                    status = CIStatus.CANCELLED
                else:
                    status = CIStatus.UNKNOWN

                raw_log = ""
                if fetch_logs and status == CIStatus.FAILED and details_url:
                    raw_log = self._fetch_job_logs(owner, repo, details_url)

                checks.append(CICheckResult(name=name, status=status, url=details_url, raw_log=raw_log))

            self.check_history.extend(checks)
            return overall_status, checks

        except Exception:
            return CIStatus.UNKNOWN, []

    def _fetch_job_logs(self, owner: str, repo: str, details_url: str) -> str:
        """
        Fetch logs for a failed CI job.

        Args:
            owner: Repository owner
            repo: Repository name
            details_url: URL to the job details (contains run ID)

        Returns:
            Raw log content or empty string on failure
        """
        run_id_match = re.search(r"/runs/(\d+)", details_url)
        if not run_id_match:
            return ""

        run_id = run_id_match.group(1)

        try:
            result = subprocess.run(
                ["gh", "run", "view", run_id, "--repo", f"{owner}/{repo}", "--log"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return result.stdout[:50000]

            result = subprocess.run(
                ["gh", "run", "view", run_id, "--repo", f"{owner}/{repo}", "--log-failed"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return result.stdout[:50000]

        except Exception:
            pass

        return ""

    def parse_logs(self, log_content: str) -> list[CIError]:
        """
        Parse CI logs for actionable errors.

        Args:
            log_content: Raw CI log content

        Returns:
            List of parsed CI errors
        """
        errors = []

        # Parse ruff/lint errors
        # Format: path/to/file.py:10:5: E501 Line too long
        lint_pattern = r"([^\s:]+\.py):(\d+):(\d+): ([A-Z]\d+) (.+)"
        for match in re.finditer(lint_pattern, log_content):
            file_path, line, col, rule, message = match.groups()
            errors.append(CIError(
                error_type=CIErrorType.LINT,
                message=message,
                file_path=file_path,
                line_number=int(line),
                column=int(col),
                rule=rule,
            ))

        # Parse mypy/type errors
        # Format: path/to/file.py:10: error: Incompatible types
        type_pattern = r"([^\s:]+\.py):(\d+): error: (.+)"
        for match in re.finditer(type_pattern, log_content):
            file_path, line, message = match.groups()
            errors.append(CIError(
                error_type=CIErrorType.TYPE_CHECK,
                message=message,
                file_path=file_path,
                line_number=int(line),
            ))

        # Parse pytest failures
        # Format: FAILED tests/test_foo.py::test_bar - AssertionError
        test_pattern = r"FAILED ([^\s]+)::([^\s]+) - (.+)"
        for match in re.finditer(test_pattern, log_content):
            file_path, test_name, message = match.groups()
            errors.append(CIError(
                error_type=CIErrorType.TEST,
                message=f"{test_name}: {message}",
                file_path=file_path,
            ))

        # Parse build errors
        build_patterns = [
            r"error: (.+)",
            r"Error: (.+)",
            r"BUILD FAILED: (.+)",
        ]
        for pattern in build_patterns:
            for match in re.finditer(pattern, log_content):
                message = match.group(1)
                # Avoid duplicates from other patterns
                if not any(e.message == message for e in errors):
                    errors.append(CIError(
                        error_type=CIErrorType.BUILD,
                        message=message,
                    ))

        return errors

    def auto_fix(self, errors: list[CIError]) -> list[Fix]:
        """
        Generate fixes for common CI errors.

        Args:
            errors: List of CI errors

        Returns:
            List of suggested fixes
        """
        fixes = []

        for error in errors:
            if error.error_type == CIErrorType.LINT:
                fix = self._generate_lint_fix(error)
                if fix:
                    fixes.append(fix)
            elif error.error_type == CIErrorType.TYPE_CHECK:
                fix = self._generate_type_fix(error)
                if fix:
                    fixes.append(fix)

        return fixes

    def _generate_lint_fix(self, error: CIError) -> Fix | None:
        """Generate fix for lint error."""
        if not error.file_path or not error.rule:
            return None

        # Common lint fixes
        lint_fixes = {
            "E501": ("Line too long", "Break line or use shorter variable names"),
            "F401": ("Unused import", "Remove the unused import"),
            "F841": ("Unused variable", "Remove or use the variable"),
            "E302": ("Expected 2 blank lines", "Add blank line"),
            "E303": ("Too many blank lines", "Remove extra blank lines"),
            "W291": ("Trailing whitespace", "Remove trailing whitespace"),
            "W292": ("No newline at end of file", "Add newline at end of file"),
            "W293": ("Blank line contains whitespace", "Remove whitespace from blank line"),
        }

        if error.rule in lint_fixes:
            _, suggestion = lint_fixes[error.rule]
            error.suggestion = suggestion

        # For now, return None - actual fix generation requires reading the file
        # This would be implemented with file reading and AST manipulation
        return None

    def _generate_type_fix(self, error: CIError) -> Fix | None:
        """Generate fix for type error."""
        # Type fixes are complex and context-dependent
        # For now, just add suggestions
        if "Incompatible return type" in error.message:
            error.suggestion = "Check return type annotation matches actual return value"
        elif "Incompatible types in assignment" in error.message:
            error.suggestion = "Check variable type annotation matches assigned value"
        elif "has no attribute" in error.message:
            error.suggestion = "Check object type and available attributes"
        elif "Missing return statement" in error.message:
            error.suggestion = "Add return statement or change return type to None"

        return None

    def get_actionable_errors(self, errors: list[CIError]) -> list[CIError]:
        """
        Filter errors to only actionable ones.

        Args:
            errors: List of all CI errors

        Returns:
            List of errors that can be automatically fixed or easily addressed
        """
        actionable_types = {CIErrorType.LINT, CIErrorType.TYPE_CHECK}
        return [e for e in errors if e.error_type in actionable_types]

    def summarize_errors(self, errors: list[CIError]) -> str:
        """
        Create a summary of CI errors for the agent.

        Args:
            errors: List of CI errors

        Returns:
            Human-readable summary
        """
        if not errors:
            return "No CI errors found."

        by_type: dict[CIErrorType, list[CIError]] = {}
        for error in errors:
            if error.error_type not in by_type:
                by_type[error.error_type] = []
            by_type[error.error_type].append(error)

        lines = ["CI Error Summary:"]
        for error_type, type_errors in by_type.items():
            lines.append(f"\n{error_type.value.upper()} ({len(type_errors)} errors):")
            for error in type_errors[:5]:  # Limit to 5 per type
                location = ""
                if error.file_path:
                    location = f"{error.file_path}"
                    if error.line_number:
                        location += f":{error.line_number}"
                lines.append(f"  - {location}: {error.message}")
            if len(type_errors) > 5:
                lines.append(f"  ... and {len(type_errors) - 5} more")

        return "\n".join(lines)

    def wait_for_ci(
        self,
        pr_url: str,
        timeout_seconds: int = 600,
        poll_interval: int = 30,
    ) -> tuple[CIStatus, list[CICheckResult]]:
        """
        Wait for CI to complete.

        Args:
            pr_url: URL of the pull request
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between polls

        Returns:
            Tuple of (final_status, check_results)
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            status, checks = self.poll_status(pr_url)

            if status in [CIStatus.PASSED, CIStatus.FAILED, CIStatus.CANCELLED]:
                return status, checks

            time.sleep(poll_interval)

        return CIStatus.UNKNOWN, []

    def get_stats(self) -> dict[str, Any]:
        """Get CI integration statistics."""
        passed = sum(1 for c in self.check_history if c.status == CIStatus.PASSED)
        failed = sum(1 for c in self.check_history if c.status == CIStatus.FAILED)
        total = len(self.check_history)

        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "recent_checks": [c.to_dict() for c in self.check_history[-10:]],
        }
